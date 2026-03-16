import base64
import math

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
from backend.models import Measurement, Profile, Shoe
from backend.services.fit_algorithm import ALGORITHM_VERSION, estimate_us_size, score_shoe, status_label

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

        image_bytes = image_file.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        workspace = settings.ROBOFLOW_WORKSPACE
        project = settings.ROBOFLOW_PROJECT
        api_key = settings.ROBOFLOW_API_KEY

        if not all([workspace, project, api_key]):
            return Response(
                {"detail": "Roboflow not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Resolve paper size: explicit param or default to Letter
        paper_size_param = request.data.get("paper_size", "").lower()
        if paper_size_param == "a4":
            paper_short_in, paper_long_in = PAPER_WIDTH_A4, PAPER_LONG_A4
            paper_size_used = "a4"
        else:
            paper_short_in, paper_long_in = PAPER_WIDTH_LETTER, PAPER_LONG_LETTER
            paper_size_used = "letter"

        rf_url = f"https://detect.roboflow.com/{workspace}/workflows/{project}"
        try:
            rf_resp = http_requests.post(
                rf_url,
                json={
                    "api_key": api_key,
                    "inputs": {
                        "image": {"type": "base64", "value": b64_image}
                    },
                },
                timeout=30,
            )
            rf_resp.raise_for_status()
        except http_requests.RequestException:
            return Response(
                {"detail": "Measurement service unavailable. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_json = rf_resp.json()

        all_preds = []
        for output in response_json.get("outputs", []):
            for val in output.values():
                if not isinstance(val, dict):
                    continue
                preds = val.get("predictions", [])
                # Workflows API sometimes wraps: {"predictions": [...], "image": {...}}
                if isinstance(preds, dict):
                    preds = preds.get("predictions", [])
                if isinstance(preds, list):
                    all_preds.extend(preds)

        paper = next((p for p in all_preds if p.get("class", "").lower() == "paper"), None)
        if paper is None:
            label = PAPER_LABELS[paper_size_used]
            return Response(
                {"detail": f"No paper detected in image. Place foot on a sheet of {label} paper."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Compute PPI from paper bounding box with orientation detection
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

        # Compute foot dimensions from polygon if available, fall back to bbox
        foot_pts = _pts(foot)
        if len(foot_pts) >= 3:
            length_px, width_px = _foot_dimensions_px(foot_pts)
            length_in = length_px / ppi
            width_in  = width_px  / ppi

            # Area via shoelace formula on the polygon
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

        # Extract toebox dimensions from "Toe Box" prediction if present
        toebox_length_in = None
        toebox_width_in  = None
        toebox_pred = next(
            (p for p in all_preds if p.get("class", "").lower() == "toe box"),
            None,
        )
        if toebox_pred:
            tb_pts = _pts(toebox_pred)
            if len(tb_pts) >= 3:
                tb_length_px, tb_width_px = _foot_dimensions_px(tb_pts)
                toebox_length_in = round(tb_length_px / ppi, 3)
                toebox_width_in  = round(tb_width_px  / ppi, 3)

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
        })


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

        shoes = Shoe.objects.prefetch_related("sizes").all()

        results = []
        for shoe in shoes:
            # Normalize attributes_json: some rows store a list, algorithm needs a dict
            raw_attrs = shoe.attributes_json or {}
            if isinstance(raw_attrs, list):
                attrs = {k: True for k in raw_attrs}
            else:
                attrs = raw_attrs

            can_score = bool(shoe.insole_length_in and shoe.insole_width_in)

            if can_score:
                shoe_data = {
                    "id":                       shoe.id,
                    "gender":                   shoe.gender,
                    "function_tags":            shoe.function_tags or [],
                    "style_tags":               shoe.style_tags or [],
                    "insole_length_in":         float(shoe.insole_length_in),
                    "insole_width_in":          float(shoe.insole_width_in),
                    "insole_area_sq_in":        float(shoe.insole_area_sq_in) if shoe.insole_area_sq_in else None,
                    "insole_toebox_length_in":  float(shoe.insole_toebox_length_in) if shoe.insole_toebox_length_in else None,
                    "insole_toebox_width_in":   float(shoe.insole_toebox_width_in)  if shoe.insole_toebox_width_in  else None,
                    "toe_shape":                shoe.toe_shape,
                    "cap_type":                 shoe.cap_type,
                    "attributes_json":          attrs,
                }
                fit = score_shoe(foot, shoe_data, sub_type=sub_type)

                # Find the closest available size to the estimated US size
                est_size = fit.get("estimated_us_size")
                available_sizes = [s for s in shoe.sizes.all() if s.is_available]
                if est_size is not None and available_sizes:
                    best = min(available_sizes, key=lambda s: abs(float(s.us_size) - est_size))
                    recommended_size = float(best.us_size)
                else:
                    recommended_size = None
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
                    "estimated_us_size": estimate_us_size(float(measurement.length_in), shoe.gender),
                    "dimensions": {},
                    "flags": [],
                }
                # Still compute recommended size for unscored shoes
                est_size = fit["estimated_us_size"]
                available_sizes = [s for s in shoe.sizes.all() if s.is_available]
                if est_size is not None and available_sizes:
                    best = min(available_sizes, key=lambda s: abs(float(s.us_size) - est_size))
                    recommended_size = float(best.us_size)
                else:
                    recommended_size = None

            results.append({
                "shoe":             shoe,
                "fit":              fit,
                "attributes":       attrs,
                "recommended_size": recommended_size,
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
