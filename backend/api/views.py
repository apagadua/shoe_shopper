import base64
import copy
import io
import json
import logging
import math

from PIL import Image

import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.serializers import RecommendationSerializer, ShoeSerializer
from backend.models import Measurement, Profile, Shoe, ShoeColorwaySize
from backend.services.ar_measurement import compute_dimensions as ar_compute_dimensions
from backend.services.fit_algorithm import ALGORITHM_VERSION, LENGTH_BIAS_CORRECTION, estimate_us_size, score_shoe, status_label

logger = logging.getLogger(__name__)
User = get_user_model()


PAPER_WIDTH_LETTER = 8.5        # US Letter short side, inches
PAPER_LONG_LETTER  = 11.0       # US Letter long side, inches
PAPER_WIDTH_A4     = 210 / 25.4 # A4 short side, inches (~8.268)
PAPER_LONG_A4      = 297 / 25.4 # A4 long side, inches (~11.693)

PAPER_LABELS = {
    'letter': 'US Letter',
    'a4': 'A4',
}


def _pts(pred):
    """Extract (x, y) tuples from a Roboflow prediction's polygon points."""
    return [(pt.get("x", 0), pt.get("y", 0)) for pt in pred.get("points", [])]


def _counter_rotate_preds(all_preds, H_sensor):
    """
    Counter-rotate Roboflow polygon points from 90°-CW-rotated image space
    back to sensor (landscape) space.

    When we send a 90° CW-rotated image to Roboflow:
        rotated image size: W_rot = H_sensor, H_rot = W_sensor
    Roboflow returns (x_rf, y_rf) in that rotated space.

    Inverse of 90° CW rotation:
        x_sensor = y_rf
        y_sensor = H_sensor - 1 - x_rf

    Returns a deep copy of all_preds with point coords replaced.
    """
    preds = copy.deepcopy(all_preds)
    for pred in preds:
        for pt in pred.get("points", []):
            x_rf = pt["x"]
            y_rf = pt["y"]
            pt["x"] = y_rf
            pt["y"] = H_sensor - 1 - x_rf
    return preds


def _ppi_from_paper_bbox(paper, short_in, long_in):
    """
    Estimate pixels-per-inch from a paper prediction's bounding box.
    Detects portrait vs landscape orientation and averages PPI derived
    from both the known short and long real-world dimensions.
    """
    w = paper.get("width", 0)
    h = paper.get("height", 0)
    if not w or not h:
        return None
    if w <= h:  # portrait
        return (w / short_in + h / long_in) / 2
    else:       # landscape
        return (w / long_in + h / short_in) / 2


def _foot_dimensions_px(points):
    """
    Return (length_px, width_px) for a foot polygon.
    Length = distance between the two farthest polygon vertices (heel to toe).
    Width  = 95th-percentile perpendicular span, which filters out outlier
             polygon points that sit slightly outside the true foot boundary.
    """
    max_dist, p1, p2 = 0, points[0], points[1]
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = math.hypot(points[j][0] - points[i][0], points[j][1] - points[i][1])
            if d > max_dist:
                max_dist, p1, p2 = d, points[i], points[j]

    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    hyp = math.hypot(dx, dy)
    px, py = -dy / hyp, dx / hyp  # unit perpendicular
    projs = sorted(pt[0] * px + pt[1] * py for pt in points)
    n = len(projs)
    lo = projs[max(0, int(n * 0.025))]
    hi = projs[min(n - 1, int(n * 0.975))]
    width_px = hi - lo
    return max_dist, width_px


class _RoboflowError(Exception):
    """Raised by _run_roboflow when the upstream call fails.

    Carries an HTTP status code and a user-facing detail string so the
    caller can build the appropriate Response without knowing why it failed.
    """
    def __init__(self, detail, http_status):
        super().__init__(detail)
        self.detail = detail
        self.http_status = http_status


def _validate_ar_snapshot(snapshot):
    """
    Validate that ar_snapshot has the expected structure before passing to numpy.
    Returns an error string, or None if valid.
    """
    required = {
        "camera_intrinsics": (list, 3),
        "camera_pose":       (list, 4),
        "plane_center":      (list, 3),
        "plane_normal":      (list, 3),
        "image_dimensions":  (list, 2),
    }
    for key, (typ, length) in required.items():
        val = snapshot.get(key)
        if not isinstance(val, typ) or len(val) != length:
            return f"ar_snapshot.{key} must be a list of length {length}"
    for row in snapshot["camera_intrinsics"]:
        if not isinstance(row, list) or len(row) != 3:
            return "camera_intrinsics must be a 3x3 matrix"
    for row in snapshot["camera_pose"]:
        if not isinstance(row, list) or len(row) != 4:
            return "camera_pose must be a 4x4 matrix"
    try:
        for row in snapshot["camera_intrinsics"]:
            [float(v) for v in row]
        for row in snapshot["camera_pose"]:
            [float(v) for v in row]
        [float(v) for v in snapshot["plane_center"]]
        [float(v) for v in snapshot["plane_normal"]]
        [float(v) for v in snapshot["image_dimensions"]]
    except (TypeError, ValueError):
        return "All ar_snapshot matrix/vector values must be numeric"

    # Gate on tracking state: only TRACKING guarantees a valid floor plane.
    tracking_state = snapshot.get("tracking_state")
    if tracking_state is None:
        return "ar_snapshot.tracking_state is required"
    if tracking_state != "TRACKING":
        return (
            f"AR tracking state is '{tracking_state}' — capture is only valid "
            "when tracking_state is 'TRACKING'. Hold the phone steady and retry."
        )

    return None


class FootMeasureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"detail": "image field required"}, status=status.HTTP_400_BAD_REQUEST)

        MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
        ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

        if image_file.size > MAX_UPLOAD_BYTES:
            return Response({"detail": "Image too large (max 10 MB)"}, status=status.HTTP_400_BAD_REQUEST)
        if image_file.content_type not in ALLOWED_MIME_TYPES:
            return Response({"detail": "Unsupported image type"}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        measurement_method = request.data.get("measurement_method", "paper").lower()

        if measurement_method == "arcore":
            ar_snapshot_raw = request.data.get("ar_snapshot")
            if not ar_snapshot_raw:
                return Response(
                    {"detail": "ar_snapshot required for ARCore method"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # 64 KB is far more than a 4x4 matrix + 3-vectors ever needs.
            # Guard before json.loads() to prevent memory exhaustion from a
            # deliberately oversized payload.
            if len(ar_snapshot_raw) > 64 * 1024:
                return Response(
                    {"detail": "ar_snapshot payload too large"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                ar_snapshot = json.loads(ar_snapshot_raw)
            except (json.JSONDecodeError, TypeError):
                return Response(
                    {"detail": "ar_snapshot must be valid JSON"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            error = _validate_ar_snapshot(ar_snapshot)
            if error:
                return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
            return self._measure_with_ar(request, image_file, ar_snapshot)
        else:
            return self._measure_with_paper(request, image_file)

    def _measure_with_paper(self, request, image_file):
        image_bytes = image_file.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Resolve paper size: explicit param or default to Letter
        paper_size_param = request.data.get("paper_size", "").lower()
        if paper_size_param == "a4":
            paper_short_in, paper_long_in = PAPER_WIDTH_A4, PAPER_LONG_A4
            paper_size_used = "a4"
        else:
            paper_short_in, paper_long_in = PAPER_WIDTH_LETTER, PAPER_LONG_LETTER
            paper_size_used = "letter"

        try:
            all_preds = self._run_roboflow(request, b64_image)
        except _RoboflowError as e:
            return Response({"detail": e.detail}, status=e.http_status)

        paper = next((p for p in all_preds if p.get("class", "").lower() == "paper"), None)
        if paper is None:
            label = PAPER_LABELS[paper_size_used]
            return Response(
                {"detail": f"No paper detected in image. Place foot on a sheet of {label} paper."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ppi = _ppi_from_paper_bbox(paper, paper_short_in, paper_long_in)
        if not ppi:
            return Response(
                {"detail": "Could not determine paper dimensions from image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        foot = None
        for cls in ("foot", "insole"):
            candidates = [p for p in all_preds if p.get("class", "").lower() == cls]
            if candidates:
                foot = max(candidates, key=lambda p: p.get("confidence", 0))
                break

        if foot is None:
            return Response(
                {"detail": "No foot or insole detected in image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        foot_pts = _pts(foot)
        if len(foot_pts) >= 3:
            length_px, width_px = _foot_dimensions_px(foot_pts)
            length_in = length_px / ppi
            width_in  = width_px  / ppi

            n = len(foot_pts)
            area_px = abs(sum(
                foot_pts[i][0] * foot_pts[(i + 1) % n][1]
                - foot_pts[(i + 1) % n][0] * foot_pts[i][1]
                for i in range(n)
            )) / 2
            area_sq_in = area_px / (ppi * ppi)
        else:
            foot_height = foot.get("height")
            foot_width  = foot.get("width")
            if not foot_height or not foot_width:
                return Response(
                    {"detail": "Could not determine foot dimensions from image."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            length_in  = foot_height / ppi
            width_in   = foot_width  / ppi
            area_sq_in = length_in * width_in * 0.70

        toebox_length_in, toebox_width_in = self._extract_toebox(all_preds, ppi=ppi)

        measurement = Measurement.objects.create(
            user=request.user,
            status=Measurement.Status.COMPLETE,
            image_url="",
            length_in=round(length_in, 3),
            width_in=round(width_in, 3),
            toebox_length_in=toebox_length_in,
            toebox_width_in=toebox_width_in,
            area_sq_in=round(area_sq_in, 3),
            paper_type=paper_size_used,
            measurement_method=Measurement.MeasurementMethod.PAPER,
        )

        return Response({
            "id": measurement.id,
            "length_in": round(length_in, 3),
            "width_in": round(width_in, 3),
            "toebox_length_in": toebox_length_in,
            "toebox_width_in": toebox_width_in,
            "area_sq_in": round(area_sq_in, 3),
            "ppi": round(ppi, 3),
            "paper_size": paper_size_used,
            "measurement_method": "paper",
        })

    def _measure_with_ar(self, request, image_file, ar_snapshot):
        image_bytes = image_file.read()

        # Rotate 90° CW before Roboflow so the foot appears portrait-upright.
        # acquireCameraImage() gives sensor-orientation bytes (landscape when the
        # phone is held portrait). Roboflow expects portrait orientation.
        img = Image.open(io.BytesIO(image_bytes))
        img_rotated = img.transpose(Image.Transpose.ROTATE_270)  # 270° CCW = 90° CW
        buf = io.BytesIO()
        img_rotated.save(buf, format="JPEG", quality=90)
        b64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

        try:
            all_preds = self._run_roboflow(request, b64_image)
        except _RoboflowError as e:
            return Response({"detail": e.detail}, status=e.http_status)

        # Counter-rotate all polygon points back to sensor space so the
        # camera-intrinsics-based ray casting uses consistent coordinates.
        H_sensor = ar_snapshot.get("image_dimensions", [640, 480])[1]
        all_preds = _counter_rotate_preds(all_preds, H_sensor)

        foot = None
        for cls in ("foot", "insole"):
            candidates = [p for p in all_preds if p.get("class", "").lower() == cls]
            if candidates:
                foot = max(candidates, key=lambda p: p.get("confidence", 0))
                break

        if foot is None:
            return Response(
                {"detail": "No foot or insole detected in image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        foot_pts = _pts(foot)
        if len(foot_pts) < 3:
            return Response(
                {"detail": "Foot polygon has too few points for AR measurement."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            dims = ar_compute_dimensions(foot_pts, ar_snapshot)
        except ValueError as exc:
            logger.warning("AR unprojection failed for user %s: %s", request.user.id, exc)
            return Response(
                {"detail": f"AR measurement failed: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        length_in  = dims["length_in"]
        width_in   = dims["width_in"]
        area_sq_in = dims["area_sq_in"]

        # Sanity-check before writing to DB. A human foot is always 3–16 inches.
        # Values outside this window indicate corrupt AR plane data (e.g., a
        # stale plane from a different session, or a near-zero normal vector).
        FOOT_MIN_IN, FOOT_MAX_IN = 3.0, 16.0
        if not (FOOT_MIN_IN <= length_in <= FOOT_MAX_IN):
            logger.warning(
                "AR measurement out of range for user %s: length_in=%s",
                request.user.id, length_in,
            )
            return Response(
                {
                    "detail": (
                        "AR measurement result is outside the expected range "
                        f"({length_in:.2f} in). Ensure the floor is flat and "
                        "well-lit, then try again."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        toebox_length_in, toebox_width_in = self._extract_toebox(all_preds, ar_snapshot=ar_snapshot)

        # paper_type intentionally omitted (left NULL) — AR measurements have
        # no paper reference, so the field doesn't apply.
        measurement = Measurement.objects.create(
            user=request.user,
            status=Measurement.Status.COMPLETE,
            image_url="",
            length_in=length_in,
            width_in=width_in,
            toebox_length_in=toebox_length_in,
            toebox_width_in=toebox_width_in,
            area_sq_in=area_sq_in,
            measurement_method=Measurement.MeasurementMethod.ARCORE,
        )

        return Response({
            "id": measurement.id,
            "length_in": length_in,
            "width_in": width_in,
            "toebox_length_in": toebox_length_in,
            "toebox_width_in": toebox_width_in,
            "area_sq_in": area_sq_in,
            "measurement_method": "arcore",
        })

    def _run_roboflow(self, request, b64_image):
        """
        Call Roboflow and return the flat list of predictions.

        Raises:
            _RoboflowError: if the upstream call fails or Roboflow is not
                            configured.  The caller should catch this and
                            return Response({"detail": e.detail}, status=e.http_status).
        """
        workspace = settings.ROBOFLOW_WORKSPACE
        project   = settings.ROBOFLOW_PROJECT
        api_key   = settings.ROBOFLOW_API_KEY

        if not all([workspace, project, api_key]):
            raise _RoboflowError(
                "Roboflow not configured",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        rf_url = f"https://detect.roboflow.com/{workspace}/workflows/{project}"
        try:
            rf_resp = http_requests.post(
                rf_url,
                json={
                    "api_key": api_key,
                    "inputs": {"image": {"type": "base64", "value": b64_image}},
                },
                timeout=30,
            )
            rf_resp.raise_for_status()
        except http_requests.RequestException as exc:
            logger.warning("Roboflow request failed for user %s: %s", request.user.id, exc)
            raise _RoboflowError(
                "Measurement service unavailable. Please try again.",
                status.HTTP_502_BAD_GATEWAY,
            ) from exc

        response_json = rf_resp.json()
        all_preds = []
        for output in response_json.get("outputs", []):
            for val in output.values():
                if not isinstance(val, dict):
                    continue
                preds = val.get("predictions", [])
                if isinstance(preds, dict):
                    preds = preds.get("predictions", [])
                if isinstance(preds, list):
                    all_preds.extend(preds)
        return all_preds

    def _extract_toebox(self, all_preds, ppi=None, ar_snapshot=None):
        """
        Extract toebox dimensions from a 'Toe Box' Roboflow prediction.
        Uses ppi (paper method) or ar_snapshot (AR method) to convert to inches.
        Returns (toebox_length_in, toebox_width_in) — both None if not found.
        """
        toebox_pred = next(
            (p for p in all_preds if p.get("class", "").lower() == "toe box"),
            None,
        )
        if not toebox_pred:
            return None, None

        tb_pts = _pts(toebox_pred)
        if len(tb_pts) < 3:
            return None, None

        if ppi is not None:
            tb_length_px, tb_width_px = _foot_dimensions_px(tb_pts)
            return round(tb_length_px / ppi, 3), round(tb_width_px / ppi, 3)

        if ar_snapshot is not None:
            try:
                dims = ar_compute_dimensions(tb_pts, ar_snapshot)
                return dims["length_in"], dims["width_in"]
            except ValueError as exc:
                logger.debug("AR toebox unprojection failed (non-fatal): %s", exc)
                return None, None

        return None, None


class LatestMeasurementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        measurement = (
            Measurement.objects
            .filter(user=request.user, status=Measurement.Status.COMPLETE)
            .order_by("-created_at")
            .first()
        )
        if measurement is None:
            return Response({"detail": "No measurements found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": measurement.id,
            "length_in": float(measurement.length_in),
            "width_in": float(measurement.width_in),
            "area_sq_in": float(measurement.area_sq_in),
            "paper_size": measurement.paper_type,
            "created_at": measurement.created_at.isoformat(),
        })


class RecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        measurement = (
            Measurement.objects
            .filter(user=request.user, status=Measurement.Status.COMPLETE)
            .order_by("-created_at")
            .first()
        )
        if measurement is None:
            return Response(
                {"detail": "No measurements found. Scan your foot first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # v1.6: foot length and width carry Roboflow CV measurement uncertainty
        # (±0.55" length, ±0.35" width). These are passed through as-is; the
        # algorithm's FOOT_*_LO/HI constants widen the reject window to absorb
        # that uncertainty. Toebox dimensions are also CV-derived and passed
        # through directly; the scoring algorithm handles their uncertainty
        # via profile tolerance bands.
        raw_area = float(measurement.area_sq_in) if measurement.area_sq_in is not None else None

        foot = {
            "length_in":        float(measurement.length_in),
            "width_in":         float(measurement.width_in),
            "area_sq_in":       raw_area,
            "toebox_length_in": float(measurement.toebox_length_in) if measurement.toebox_length_in is not None else None,
            "toebox_width_in":  float(measurement.toebox_width_in)  if measurement.toebox_width_in  is not None else None,
        }

        sub_type = request.query_params.get("sub_type") or None

        shoes = Shoe.objects.prefetch_related("sizes").filter(is_active=True)

        results = []
        for shoe in shoes:
            # Normalize attributes_json: some rows store a list, algorithm needs a dict
            raw_attrs = shoe.attributes_json or {}
            if isinstance(raw_attrs, list):
                attrs = {k: True for k in raw_attrs}
            else:
                attrs = raw_attrs

            all_sizes = list(shoe.sizes.all())

            # Estimate the user's size for this shoe (bias-corrected, consistent with algorithm)
            est_size = estimate_us_size(
                float(measurement.length_in) + LENGTH_BIAS_CORRECTION,
                shoe.gender,
            )

            # Find the size whose insole data we'll use for scoring
            scoring_size = (
                min(all_sizes, key=lambda s: abs(float(s.us_size) - est_size))
                if all_sizes else None
            )

            can_score = bool(
                scoring_size
                and scoring_size.insole_length_in
                and scoring_size.insole_width_in
            )

            if can_score:
                shoe_data = {
                    "id":                       shoe.id,
                    "gender":                   shoe.gender,
                    "function_tags":            shoe.function_tags or [],
                    "style_tags":               shoe.style_tags or [],
                    "insole_length_in":         float(scoring_size.insole_length_in),
                    "insole_width_in":          float(scoring_size.insole_width_in),
                    "insole_area_sq_in":        float(scoring_size.insole_area_sq_in) if scoring_size.insole_area_sq_in else None,
                    "insole_toebox_length_in":  float(scoring_size.insole_toebox_length_in) if scoring_size.insole_toebox_length_in else None,
                    "insole_toebox_width_in":   float(scoring_size.insole_toebox_width_in)  if scoring_size.insole_toebox_width_in  else None,
                    "toe_shape":                shoe.toe_shape,
                    "cap_type":                 shoe.cap_type,
                    "attributes_json":          attrs,
                }
                fit = score_shoe(foot, shoe_data, sub_type=sub_type)
            else:
                fit = {
                    "status": "UNSCORED",
                    "total_score": None,
                    "reject_reason": None,
                    "profile_used": None,
                    "sub_type": sub_type,
                    "adjustments_applied": [],
                    "has_toebox_data": False,
                    "has_area_data": False,
                    "estimated_us_size": est_size,
                    "dimensions": {},
                    "flags": [],
                }

            # Sizes available in at least one live colorway
            available_us_sizes = set(
                float(v)
                for v in ShoeColorwaySize.objects.filter(
                    colorway__shoe=shoe,
                    is_available=True,
                ).values_list("us_size", flat=True)
            )

            if available_us_sizes:
                # Pick the insole-measured size closest to user's estimated size
                # that also has a live colorway available
                candidates = [s for s in all_sizes if float(s.us_size) in available_us_sizes]
                if candidates:
                    best = min(candidates, key=lambda s: abs(float(s.us_size) - est_size))
                    recommended_size = float(best.us_size)
                else:
                    recommended_size = None
            else:
                # Fall back to insole-measured sizes (pre-colorway-sync behaviour)
                insole_sizes = [s for s in all_sizes if s.insole_length_in is not None]
                if insole_sizes:
                    best = min(insole_sizes, key=lambda s: abs(float(s.us_size) - est_size))
                    recommended_size = float(best.us_size)
                else:
                    recommended_size = None

            # Build colorway options for the recommended size (cheapest first)
            colorway_options = []
            if recommended_size is not None:
                colorway_options = list(
                    ShoeColorwaySize.objects.filter(
                        colorway__shoe=shoe,
                        us_size=recommended_size,
                        is_available=True,
                    )
                    .select_related("colorway")
                    .order_by("price_usd")
                    .values(
                        "colorway__name",
                        "colorway__image_url",
                        "colorway__product_url",
                        "price_usd",
                    )
                )
                # Rename keys for the serializer / frontend
                colorway_options = [
                    {
                        "name":        row["colorway__name"],
                        "image_url":   row["colorway__image_url"],
                        "product_url": row["colorway__product_url"],
                        "price_usd":   str(row["price_usd"]) if row["price_usd"] is not None else None,
                    }
                    for row in colorway_options
                ]

            results.append({
                "shoe":             shoe,
                "fit":              fit,
                "attributes":       attrs,
                "recommended_size": recommended_size,
                "colorway_options": colorway_options,
            })

        # Sort: scored non-rejected first (by score desc), then unscored, then rejected
        def _sort_key(r):
            s = r["fit"]["status"]
            if s == "REJECTED":    return (2, 0)
            if s == "UNSCORED":    return (1, 0)
            return (0, -(r["fit"]["total_score"] or 0))

        results.sort(key=_sort_key)

        serializer = RecommendationSerializer(results, many=True)
        return Response({
            "measurement_id": measurement.id,
            "algorithm_version": ALGORITHM_VERSION,
            "has_toebox_data": foot["toebox_length_in"] is not None,
            "results": serializer.data,
        })


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "shoe_count": Shoe.objects.count()})


class ShoeListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        shoes = Shoe.objects.prefetch_related("sizes").order_by("brand", "model")
        serializer = ShoeSerializer(shoes, many=True)
        return Response(serializer.data)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('id_token', '')
        if isinstance(token, str):
            token = token.strip()
        if not token:
            return Response(
                {'detail': 'id_token required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {'detail': 'Invalid ID token'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = idinfo.get('email')
        if not email:
            return Response(
                {'detail': 'No email in token'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': idinfo.get('given_name', ''),
                    'last_name': idinfo.get('family_name', ''),
                },
            )
            if created:
                Profile.objects.create(
                    user=user,
                    display_name=idinfo.get('name', ''),
                    avatar_url=idinfo.get('picture', ''),
                )

        user_token, _ = Token.objects.get_or_create(user=user)
        return Response({'key': user_token.key})
