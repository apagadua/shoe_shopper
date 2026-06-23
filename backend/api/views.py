import base64
import copy
import io
import json
import logging
import math
import os
import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from PIL import Image

import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.serializers import (
    MeasurementSerializer,
    MeasurementUploadSerializer,
    RecommendationSerializer,
    ShoeSerializer,
)
from backend.models import GuestSession, Measurement, Profile, Shoe
from backend.services.ar_measurement import compute_dimensions as ar_compute_dimensions
from backend.services.ar_measurement import compute_dimensions_with_wall as ar_compute_dimensions_with_wall
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


_AR_DEBUG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ar_debug",
)

def _save_ar_debug_image(rotated_img, predictions, label=""):
    """
    Draw Roboflow polygon predictions on the (already-rotated) image and
    save it to ar_debug/ at the repo root for offline inspection.

    Coordinate system: predictions here are still in Roboflow/rotated-image
    space, so they map directly onto rotated_img without any counter-rotation.

    Each class gets a distinct colour; polygons are outlined and labelled
    with class name + confidence.  Saves as JPEG named:
        ar_debug_<label>_<timestamp>.jpg
    """
    try:
        from PIL import ImageDraw, ImageFont
        import datetime

        os.makedirs(_AR_DEBUG_DIR, exist_ok=True)

        vis = rotated_img.copy().convert("RGB")
        draw = ImageDraw.Draw(vis)

        CLASS_COLORS = {
            "foot":       (0,   220,  0),    # green
            "insole":     (0,   180, 255),   # cyan-blue
            "toe box":    (255, 140,  0),    # orange
            "wall base":  (220,   0,  0),    # red
        }
        DEFAULT_COLOR = (180, 0, 220)        # purple for anything else

        for pred in predictions:
            cls   = (pred.get("class") or "").lower()
            conf  = pred.get("confidence", 0)
            color = CLASS_COLORS.get(cls, DEFAULT_COLOR)
            pts   = pred.get("points", [])

            if pts:
                poly = [(pt["x"], pt["y"]) for pt in pts]
                # Outline the polygon
                for i in range(len(poly)):
                    draw.line([poly[i], poly[(i + 1) % len(poly)]], fill=color, width=3)
                # Label near first point
                if poly:
                    lx, ly = poly[0]
                    draw.rectangle([lx - 2, ly - 14, lx + len(cls) * 7 + 4, ly + 2], fill=(0, 0, 0))
                    draw.text((lx, ly - 13), f"{cls} {conf:.2f}", fill=color)
            else:
                # Bounding-box-only prediction (Wall Base has no polygon)
                x  = pred.get("x", 0)
                y  = pred.get("y", 0)
                w  = pred.get("width", 0)
                h  = pred.get("height", 0)
                x0, y0 = x - w / 2, y - h / 2
                x1, y1 = x + w / 2, y + h / 2
                draw.rectangle([x0, y0, x1, y1], outline=color, width=3)
                draw.text((x0 + 2, y0 + 2), f"{cls} {conf:.2f}", fill=color)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = f"ar_debug{'_' + label if label else ''}_{ts}.jpg"
        fpath = os.path.join(_AR_DEBUG_DIR, fname)
        vis.save(fpath, format="JPEG", quality=90)
        logger.info("AR debug image saved: %s", fpath)
    except Exception as exc:
        logger.warning("AR debug image save failed (non-fatal): %s", exc)


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

        # Save debug image BEFORE counter-rotation so polygon coords match
        # the rotated image that was actually sent to Roboflow.
        _save_ar_debug_image(img_rotated, all_preds, label=str(request.user.id))

        # Counter-rotate all polygon points back to sensor space so the
        # camera-intrinsics-based ray casting uses consistent coordinates.
        H_sensor = ar_snapshot.get("image_dimensions", [640, 480])[1]
        all_preds = _counter_rotate_preds(all_preds, H_sensor)

        # ── Diagnostic: resolution + intrinsics ──────────────────────────────
        snap_w, snap_h = ar_snapshot.get("image_dimensions", [0, 0])
        pil_w, pil_h   = img.size   # original (pre-rotation) PIL dimensions
        K = ar_snapshot.get("camera_intrinsics", [])
        fx = K[0][0] if K else None
        fy = K[1][1] if K else None
        cx = K[0][2] if K else None
        cy = K[1][2] if K else None
        logger.info(
            "AR dims: snapshot=%dx%d  PIL_sensor=%dx%d  match=%s",
            snap_w, snap_h, pil_w, pil_h,
            "YES" if (pil_w == snap_w and pil_h == snap_h) else "NO — MISMATCH",
        )
        logger.info(
            "AR intrinsics: fx=%.1f  fy=%.1f  cx=%.1f  cy=%.1f",
            fx or 0, fy or 0, cx or 0, cy or 0,
        )
        import numpy as _np
        _cam_h_in = None   # used below for camera-height gate
        try:
            _pose = _np.array(ar_snapshot["camera_pose"], dtype=float)
            _n    = _np.array(ar_snapshot["plane_normal"], dtype=float)
            _p0   = _np.array(ar_snapshot["plane_center"], dtype=float)
            _n    = _n / _np.linalg.norm(_n)
            _cam  = _pose[:3, 3]
            _cam_h_m  = float(_np.dot(_cam - _p0, _n))
            _cam_h_in = _cam_h_m * 39.3701
            logger.info(
                "AR camera height above floor: %.4f m  (%.3f in)  cam_pos=%s",
                _cam_h_m, _cam_h_in,
                [round(float(v), 4) for v in _cam],
            )
        except Exception as _e:
            logger.info("AR height calc failed: %s", _e)

        # Camera-height gate: floor projections become unreliable when the phone
        # is held too high (>35") because any sub-pixel detection error in the
        # Roboflow polygon maps to a proportionally larger floor distance, causing
        # uniform over-measurement across both length and width.  Below ~12" the
        # camera is too close for the floor plane to stabilise.
        _CAM_H_MIN_IN, _CAM_H_MAX_IN = 12.0, 35.0
        if _cam_h_in is not None and not (_CAM_H_MIN_IN <= _cam_h_in <= _CAM_H_MAX_IN):
            logger.warning(
                "AR camera height out of range for user %s: %.1f in (allowed %g–%g in)",
                request.user.id, _cam_h_in, _CAM_H_MIN_IN, _CAM_H_MAX_IN,
            )
            if _cam_h_in > _CAM_H_MAX_IN:
                msg = (
                    f"Camera is too far from your foot ({_cam_h_in:.0f}\"). "
                    "Hold your phone 20–30\" above your foot and try again."
                )
            else:
                msg = (
                    f"Camera is too close to your foot ({_cam_h_in:.0f}\"). "
                    "Hold your phone 20–30\" above your foot and try again."
                )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        # ────────────────────────────────────────────────────────────────────

        logger.info(
            "AR Roboflow classes for user %s: %s",
            request.user.id,
            [(p.get("class"), round(p.get("confidence", 0), 2)) for p in all_preds],
        )

        # Collect foot/insole candidates (prefer "foot", fall back to "insole")
        foot_candidates = []
        for cls in ("foot", "insole"):
            candidates = [p for p in all_preds if p.get("class", "").lower() == cls]
            if candidates:
                foot_candidates = candidates
                break

        if not foot_candidates:
            return Response(
                {"detail": "No foot or insole detected in image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Wall Base — model v24+ returns a polygon; earlier models returned only a
        # bbox.  _counter_rotate_preds already converted polygon points to sensor
        # space, so extract_wall_seam's polygon path receives pre-rotated coords.
        # The bbox fallback path inside extract_wall_seam does its own rotation.
        wall_pred = next(
            (p for p in all_preds if p.get("class", "").lower() == "wall base"),
            None,
        )

        # Toe Box polygon — already counter-rotated to sensor space.
        # Passed to the wall measurement so the toe reference can be extended
        # past where the Foot polygon stops (often ~1" short of the true tip).
        toebox_pred = next(
            (p for p in all_preds if p.get("class", "").lower() == "toe box"),
            None,
        )
        toebox_pts = _pts(toebox_pred) if toebox_pred else []
        if toebox_pts:
            logger.info("AR toe box polygon: %d points (will extend toe reference)", len(toebox_pts))

        if wall_pred is not None:
            wall_pts = wall_pred.get("points", [])
            if wall_pts:
                logger.info("AR wall base: polygon (%d pts) — will use actual seam edge", len(wall_pts))
            else:
                logger.info("AR wall base: bbox-only — falling back to horizontal scanline")

        # When multiple feet are visible and a wall is detected, pick the foot
        # whose heel is closest to the wall seam — that is the foot being measured.
        # Pre-computes dims so we don't re-do the wall math below.
        pre_dims = None
        if wall_pred is not None and len(foot_candidates) > 1:
            logger.info(
                "AR multi-foot: %d foot candidates detected, using wall seam to select",
                len(foot_candidates),
            )
            foot, pre_dims = self._select_foot_for_wall(
                foot_candidates, wall_pred, ar_snapshot, request.user.id,
                toebox_pts=toebox_pts,
            )
        else:
            foot = max(foot_candidates, key=lambda p: p.get("confidence", 0))

        foot_pts = _pts(foot)
        if len(foot_pts) < 3:
            return Response(
                {"detail": "Foot polygon has too few points for AR measurement."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        measurement_path = "pairwise"
        heel_gap_in = None

        if pre_dims is not None:
            # Already computed by _select_foot_for_wall — reuse to avoid a duplicate API call.
            # Re-run with toebox_pts since _select_foot_for_wall didn't have them.
            if wall_pred is not None and toebox_pts:
                try:
                    pre_dims = ar_compute_dimensions_with_wall(
                        _pts(foot), wall_pred, ar_snapshot,
                        toebox_points_px=toebox_pts,
                    )
                except ValueError:
                    pass   # keep pre_dims as-is if toebox extension fails
            dims = pre_dims
            measurement_path = dims["measurement_path"]
            heel_gap_in = dims.get("heel_gap_in")
        else:
            try:
                if wall_pred is not None:
                    dims = ar_compute_dimensions_with_wall(
                        foot_pts, wall_pred, ar_snapshot,
                        toebox_points_px=toebox_pts,
                    )
                    measurement_path = dims["measurement_path"]
                    heel_gap_in = dims.get("heel_gap_in")
                else:
                    dims = ar_compute_dimensions(foot_pts, ar_snapshot)
            except ValueError as exc:
                if wall_pred is not None:
                    logger.info(
                        "Wall seam fitting failed for user %s (%s) — falling back to pairwise",
                        request.user.id, exc,
                    )
                    try:
                        dims = ar_compute_dimensions(foot_pts, ar_snapshot)
                    except ValueError as exc2:
                        logger.warning("AR unprojection failed for user %s: %s", request.user.id, exc2)
                        return Response(
                            {"detail": f"AR measurement failed: {exc2}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    logger.warning("AR unprojection failed for user %s: %s", request.user.id, exc)
                    return Response(
                        {"detail": f"AR measurement failed: {exc}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        length_in  = dims["length_in"]
        width_in   = dims["width_in"]
        area_sq_in = dims["area_sq_in"]

        # Sanity-check before writing to DB.  Human feet range from toddler (~3")
        # to the largest men's sizes (~13.0").  Values outside this window indicate
        # bad AR plane data or a camera that was held at the wrong height/angle.
        # The camera-height gate above already catches the most common over-shoot
        # scenario; this is a last-resort catch for corner cases.
        FOOT_MIN_IN, FOOT_MAX_IN = 3.0, 13.0
        if not (FOOT_MIN_IN <= length_in <= FOOT_MAX_IN):
            logger.warning(
                "AR measurement out of range for user %s: length_in=%s path=%s",
                request.user.id, length_in, measurement_path,
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

        logger.info(
            "AR measurement complete for user %s: path=%s length_in=%.3f width_in=%.3f heel_gap_in=%s",
            request.user.id, measurement_path, length_in, width_in,
            f"{heel_gap_in:.3f}" if heel_gap_in is not None else "n/a",
        )
        if heel_gap_in is not None and heel_gap_in > 1.0:
            logger.warning(
                "AR large heel_gap for user %s: %.3f in — seam may have drifted; "
                "falling back to polygon span (path=%s)",
                request.user.id, heel_gap_in, measurement_path,
            )
        if dims.get("heel_point") and dims.get("toe_point"):
            hp = dims["heel_point"]
            tp = dims["toe_point"]
            sc = dims.get("seam_centroid")
            logger.info(
                "AR 3D points: heel=[%.4f, %.4f, %.4f]  toe=[%.4f, %.4f, %.4f]  "
                "direct_dist_m=%.4f (%.3f in)",
                hp[0], hp[1], hp[2], tp[0], tp[1], tp[2],
                sum((a - b) ** 2 for a, b in zip(hp, tp)) ** 0.5,
                sum((a - b) ** 2 for a, b in zip(hp, tp)) ** 0.5 * 39.3701,
            )
            if sc:
                logger.info(
                    "AR seam centroid: [%.4f, %.4f, %.4f]",
                    sc[0], sc[1], sc[2],
                )
            sd = dims.get("seam_dir")
            ua = dims.get("u_axis")
            if sd and ua:
                import math as _math
                seam_tilt_deg = _math.degrees(_math.asin(abs(float(sd[2]))))
                logger.info(
                    "AR seam_dir: [%.4f, %.4f, %.4f]  u_axis: [%.4f, %.4f, %.4f]  "
                    "seam_Z_tilt=%.1f°",
                    sd[0], sd[1], sd[2], ua[0], ua[1], ua[2], seam_tilt_deg,
                )
            if dims.get("width_band_pts") is not None:
                width_frame = (
                    "foot-axis" if "fallback" in measurement_path else "seam-axis"
                )
                logger.info(
                    "AR width: %.3f in  band_pts=%d  lo=%.3f in  hi=%.3f in  frame=%s",
                    dims["width_in"],
                    dims["width_band_pts"],
                    dims.get("width_lo_in", 0),
                    dims.get("width_hi_in", 0),
                    width_frame,
                )
            clean = dims.get("seam_clean_bins", -1)
            total = dims.get("seam_total_bins", -1)
            if clean >= 0:
                logger.info(
                    "AR seam bins: %d/%d clean  toe_ext=%.3f in",
                    clean, total, dims.get("toe_ext_in", 0.0),
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

        response_data = {
            "id": measurement.id,
            "length_in": length_in,
            "width_in": width_in,
            "toebox_length_in": toebox_length_in,
            "toebox_width_in": toebox_width_in,
            "area_sq_in": area_sq_in,
            "measurement_method": "arcore",
            "measurement_path": measurement_path,
        }
        # Warn the client when it appears the heel wasn't flush against the wall.
        # Covers both pairwise path (large gap) and wall_seam_gap_fallback (seam
        # centroid drifted > 25 mm from heel, so polygon span was used instead).
        if heel_gap_in is not None and heel_gap_in > 0.4 and measurement_path != "wall_seam":
            response_data["warning"] = "heel_not_touching_wall"
        return Response(response_data)

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

        model_id = settings.ROBOFLOW_MODEL_ID
        rf_url = f"https://serverless.roboflow.com/{model_id}"
        logger.info("Roboflow request URL: %s", rf_url)
        try:
            rf_resp = http_requests.post(
                rf_url,
                params={"api_key": api_key, "confidence": 0.25},
                data=b64_image,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
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
        return response_json.get("predictions", [])

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

    def _select_foot_for_wall(self, foot_candidates, wall_pred, ar_snapshot, user_id,
                              toebox_pts=None):
        """
        When multiple foot polygons are detected and a wall seam is present,
        pick the foot whose heel is closest to the wall on the positive (toe) side.

        Strategy: run ar_compute_dimensions_with_wall for every candidate and
        compare heel_gap_in.  The foot pressed against the wall has the smallest
        non-negative gap.  If all candidates return negative gaps (anomalous
        geometry), fall back to the least-negative one.

        Returns (foot_pred, dims) — dims is already computed so the caller can
        reuse it without a second call.  Returns (highest-confidence candidate, None)
        if every candidate raises ValueError.
        """
        scored = []
        for candidate in foot_candidates:
            pts = _pts(candidate)
            if len(pts) < 3:
                continue
            try:
                dims = ar_compute_dimensions_with_wall(
                    pts, wall_pred, ar_snapshot,
                    toebox_points_px=toebox_pts or [],
                )
                gap = dims.get("heel_gap_in", float("inf"))
                scored.append((gap, candidate, dims))
            except ValueError:
                continue

        if not scored:
            # All candidates failed — return highest-confidence foot, no pre-computed dims
            logger.warning(
                "AR multi-foot: all %d candidates failed wall fitting for user %s",
                len(foot_candidates), user_id,
            )
            return max(foot_candidates, key=lambda p: p.get("confidence", 0)), None

        # Prefer the foot with a non-negative heel_gap closest to zero
        positive = [(g, c, d) for g, c, d in scored if g >= 0]
        if positive:
            positive.sort(key=lambda x: x[0])
            gap, foot, dims = positive[0]
            logger.info(
                "AR multi-foot: selected foot with heel_gap=%.3f in (wall-side, %d candidates)",
                gap, len(foot_candidates),
            )
        else:
            # All negative — pick least-negative (closest to wall seam)
            scored.sort(key=lambda x: x[0], reverse=True)
            gap, foot, dims = scored[0]
            logger.warning(
                "AR multi-foot: all candidates have negative heel_gap; "
                "chose %.3f in for user %s",
                gap, user_id,
            )

        return foot, dims


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

        shoes = Shoe.objects.prefetch_related("sizes", "colorways__sizes").filter(is_active=True)

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

            # Sizes available in at least one live colorway (uses prefetched data — no extra query)
            available_us_sizes = set(
                float(s.us_size)
                for cw in shoe.colorways.all()
                for s in cw.sizes.all()
                if s.is_available
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

            # Build colorway options using prefetched data (no extra DB queries).
            # Each entry includes goat_id/sku so the frontend can key the carousel,
            # plus sizes scoped to the recommended size so price/availability are correct.
            colorway_options = []
            for cw in shoe.colorways.all():
                if recommended_size is not None:
                    cw_sizes = [
                        s for s in cw.sizes.all()
                        if float(s.us_size) == recommended_size
                    ]
                else:
                    cw_sizes = [s for s in cw.sizes.all() if s.is_available]
                colorway_options.append({
                    "goat_id":            cw.goat_id,
                    "sku":                cw.sku,
                    "name":               cw.name,
                    "image_url":          cw.image_url,
                    "product_url":        cw.product_url,
                    "dominant_color_hex": cw.dominant_color_hex,
                    "color_palette_hex":  cw.color_palette_hex or [],
                    "sizes": [
                        {
                            "us_size":      float(s.us_size),
                            "price_usd":    str(s.price_usd) if s.price_usd is not None else None,
                            "is_available": s.is_available,
                        }
                        for s in sorted(cw_sizes, key=lambda s: s.price_usd or 999999)
                    ],
                })
            # Colorways with images first, then alphabetically by name
            colorway_options.sort(key=lambda c: (0 if c["image_url"] else 1, c["name"] or ""))

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


class DevMockMeasurementView(APIView):
    """
    Insert a COMPLETE Measurement for the current user (dev / emulator testing only).
    Disabled unless DEBUG or ENABLE_DEV_MOCK_MEASUREMENT is set.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        allowed = settings.DEBUG or settings.ENABLE_DEV_MOCK_MEASUREMENT
        if not allowed:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if Measurement.objects.filter(user=request.user, status=Measurement.Status.COMPLETE).exists():
            return Response(
                {"skipped": True, "detail": "A completed measurement already exists"},
                status=status.HTTP_200_OK,
            )

        m = Measurement.objects.create(
            user=request.user,
            status=Measurement.Status.COMPLETE,
            image_url="dev://mock-foot-scan",
            paper_type=Measurement.PaperType.LETTER,
            length_in=Decimal("10.200"),
            width_in=Decimal("3.950"),
            area_sq_in=Decimal("40.250"),
            toebox_length_in=Decimal("4.350"),
            toebox_width_in=Decimal("3.200"),
            algorithm_version="dev-mock",
        )
        return Response(
            {
                "id": m.id,
                "length_in": float(m.length_in),
                "width_in": float(m.width_in),
                "detail": "Mock measurement created for emulator/dev testing",
            },
            status=status.HTTP_201_CREATED,
        )


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

        audience_list = []
        for x in (settings.GOOGLE_CLIENT_ID, settings.GOOGLE_ANDROID_CLIENT_ID):
            if x and x not in audience_list:
                audience_list.append(x)
        if not audience_list:
            return Response(
                {'detail': 'Server missing GOOGLE_CLIENT_ID'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        audience = audience_list[0] if len(audience_list) == 1 else audience_list
        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience,
                clock_skew_in_seconds=120,
            )
        except (ValueError, google_auth_exceptions.GoogleAuthError) as exc:
            body = {'detail': 'Invalid ID token'}
            if settings.DEBUG:
                body['debug'] = str(exc)
            return Response(body, status=status.HTTP_400_BAD_REQUEST)

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


class ProfileView(APIView):
    """Read and update the authenticated user's profile (display name, etc.)."""

    permission_classes = [IsAuthenticated]

    MAX_DISPLAY_NAME_LEN = 200

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(
            user=request.user,
            defaults={"display_name": None, "avatar_url": None},
        )
        return Response(
            {
                "display_name": (profile.display_name or "").strip(),
            }
        )

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(
            user=request.user,
            defaults={"display_name": None, "avatar_url": None},
        )
        name = request.data.get("display_name")
        if name is None:
            return Response(
                {"detail": "display_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(name, str):
            return Response(
                {"detail": "display_name must be a string"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile.display_name = name.strip()[: self.MAX_DISPLAY_NAME_LEN] or None
        profile.save()
        return Response(
            {
                "display_name": (profile.display_name or "").strip(),
            }
        )


class MeasurementUploadView(APIView):
    """
    Store a foot image for later processing (simple upload, no Roboflow inference).
    Use FootMeasureView for full measurement + inference in one step.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = MeasurementUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        extension = os.path.splitext(image_file.name)[1] or ".jpg"
        storage_path = f"measurements/{uuid.uuid4()}{extension}"
        saved_path = default_storage.save(storage_path, image_file)

        image_url = default_storage.url(saved_path)
        if request is not None:
            image_url = request.build_absolute_uri(image_url)

        guest_session = GuestSession.objects.create(
            expires_at=timezone.now() + timedelta(days=30)
        )

        measurement = Measurement.objects.create(
            guest_session=guest_session,
            status=Measurement.Status.UPLOADED,
            image_url=image_url,
            image_width_px=serializer.validated_data.get("image_width_px"),
            image_height_px=serializer.validated_data.get("image_height_px"),
        )

        output = MeasurementSerializer(measurement).data
        return Response(output, status=status.HTTP_201_CREATED)


class ProxyImageView(APIView):
    """
    Server-side proxy for CDN images that require browser-like headers
    (e.g. Converse / Demandware) which block plain app requests.

    GET /api/proxy-image/?url=<percent-encoded URL>

    Only whitelisted CDN hostnames are permitted.
    """
    permission_classes = [AllowAny]
    # Suffix-matched against the request URL's hostname (not a substring of the
    # whole URL) so crafted URLs like http://169.254.169.254/?x=converse.com
    # or http://converse.com.attacker.com/ cannot pass the check (SSRF guard).
    # Converse's Demandware images are served from www.converse.com (the
    # "demandware.static" token lives in the URL path, not the host), so the
    # converse.com rule already covers them.
    ALLOWED_HOSTS = ('converse.com',)

    def _host_allowed(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = parsed.hostname or ''
        return any(
            host == allowed or host.endswith('.' + allowed)
            for allowed in self.ALLOWED_HOSTS
        )

    def get(self, request):
        url = request.GET.get('url', '')
        if not url or not self._host_allowed(url):
            return HttpResponse(status=400)
        try:
            resp = http_requests.get(
                url,
                headers={
                    'Referer':          'https://www.converse.com/',
                    'Origin':           'https://www.converse.com',
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/124.0.0.0 Safari/537.36'
                    ),
                    'Accept':           'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Language':  'en-US,en;q=0.9',
                    'Accept-Encoding':  'gzip, deflate, br',
                    'sec-fetch-dest':   'image',
                    'sec-fetch-mode':   'no-cors',
                    'sec-fetch-site':   'same-origin',
                },
                timeout=10,
            )
            # Surface upstream errors clearly rather than silently passing them through.
            if resp.status_code >= 400:
                logger.warning(
                    'ProxyImageView upstream %s for %s', resp.status_code, url
                )
            proxied = HttpResponse(
                resp.content,
                content_type=resp.headers.get('Content-Type', 'image/jpeg'),
                status=resp.status_code,
            )
            if resp.status_code == 200:
                # CDN images are immutable per URL — let the device image
                # cache hold them so repeat views skip this proxy entirely.
                proxied['Cache-Control'] = 'public, max-age=86400'
            return proxied
        except Exception as exc:
            logger.warning('ProxyImageView error fetching %s: %s', url, exc)
            return HttpResponse(status=502)
