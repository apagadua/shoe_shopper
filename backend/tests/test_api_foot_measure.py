"""Tests for POST /api/foot/measure/ — paper and ARCore paths.

Roboflow is always mocked (patch backend.api.views.http_requests.post).
AR geometry uses the synthetic straight-down camera from conftest:
1 sensor pixel == 1 mm on the floor at the default 0.7 m camera height.
"""

import io
import json
from unittest.mock import patch

import pytest
import requests as real_requests
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from backend.models import Measurement
from backend.tests.conftest import (
    FakeRoboflowResponse,
    bbox_pred,
    make_ar_snapshot,
    make_jpeg_bytes,
    polygon_pred,
)

pytestmark = pytest.mark.django_db

URL_NAME = "foot-measure"


def upload_image(name="foot.jpg", content=None, content_type="image/jpeg"):
    return SimpleUploadedFile(name, content or make_jpeg_bytes(), content_type=content_type)


def post_paper(client, preds, paper_size=None, **extra):
    data = {"image": upload_image(), **extra}
    if paper_size:
        data["paper_size"] = paper_size
    with patch(
        "backend.api.views.http_requests.post",
        return_value=FakeRoboflowResponse(preds),
    ):
        return client.post(reverse(URL_NAME), data, format="multipart")


def post_ar(client, preds, snapshot, raw_snapshot=None):
    data = {
        "image": upload_image(),
        "measurement_method": "arcore",
        "ar_snapshot": raw_snapshot if raw_snapshot is not None else json.dumps(snapshot),
    }
    with patch(
        "backend.api.views.http_requests.post",
        return_value=FakeRoboflowResponse(preds),
    ), patch("backend.api.views._save_ar_debug_image"):
        return client.post(reverse(URL_NAME), data, format="multipart")


# A paper bbox giving exactly 100 PPI for US Letter (portrait: 850x1100 px).
PAPER_LETTER_100PPI = bbox_pred("Paper", x=500, y=600, width=850, height=1100)

# Thin vertical rectangle: ~10" long, ~0.5" wide at 100 PPI.
FOOT_RECT = polygon_pred("Foot", [(100, 100), (150, 100), (150, 1100), (100, 1100)])


# ---------------------------------------------------------------------------
# Input validation (shared)
# ---------------------------------------------------------------------------

class TestUploadValidation:
    def test_missing_image_400(self, auth_client):
        response = auth_client.post(reverse(URL_NAME), {}, format="multipart")
        assert response.status_code == 400

    def test_oversized_image_400(self, auth_client):
        big = upload_image(content=b"x" * (10 * 1024 * 1024 + 1))
        response = auth_client.post(reverse(URL_NAME), {"image": big}, format="multipart")
        assert response.status_code == 400
        assert "too large" in response.data["detail"]

    def test_unsupported_image_format_415(self, auth_client):
        # A real GIF: Pillow verifies it as an image, but the format is
        # outside the pipeline's allowlist.
        buf = io.BytesIO()
        PILImage.new("RGB", (10, 10)).save(buf, format="GIF")
        gif = upload_image(name="foot.gif", content=buf.getvalue(), content_type="image/gif")
        response = auth_client.post(reverse(URL_NAME), {"image": gif}, format="multipart")
        assert response.status_code == 415

    def test_spoofed_content_type_rejected_400(self, auth_client):
        # Content-type header claims JPEG but the bytes aren't an image —
        # validation keys on the bytes (Pillow), not the client header.
        fake = upload_image(content=b"<script>alert(1)</script>")
        response = auth_client.post(reverse(URL_NAME), {"image": fake}, format="multipart")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Roboflow plumbing
# ---------------------------------------------------------------------------

class TestRoboflowErrors:
    @override_settings(ROBOFLOW_WORKSPACE="")
    def test_unconfigured_503(self, auth_client):
        response = auth_client.post(
            reverse(URL_NAME), {"image": upload_image()}, format="multipart"
        )
        assert response.status_code == 503

    def test_upstream_failure_502(self, auth_client):
        with patch(
            "backend.api.views.http_requests.post",
            side_effect=real_requests.ConnectionError("down"),
        ):
            response = auth_client.post(
                reverse(URL_NAME), {"image": upload_image()}, format="multipart"
            )
        assert response.status_code == 502


# ---------------------------------------------------------------------------
# Paper path
# ---------------------------------------------------------------------------

class TestPaperMeasurement:
    def test_polygon_foot_success_letter(self, auth_client, user):
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, FOOT_RECT])
        assert response.status_code == 200
        data = response.data
        assert data["paper_size"] == "letter"
        assert data["measurement_method"] == "paper"
        assert data["ppi"] == pytest.approx(100.0)
        # rectangle diagonal: sqrt(1000^2 + 50^2) / 100 ppi
        assert data["length_in"] == pytest.approx(10.01, abs=0.01)
        # width is the span perpendicular to the diagonal length axis,
        # which for a thin rectangle is ~2x its short side
        assert data["width_in"] == pytest.approx(1.0, abs=0.05)
        assert data["area_sq_in"] == pytest.approx(5.0, abs=0.1)

        m = Measurement.objects.get(user=user)
        assert m.status == Measurement.Status.COMPLETE
        assert m.measurement_method == Measurement.MeasurementMethod.PAPER
        assert float(m.length_in) == data["length_in"]

    def test_a4_paper_size(self, auth_client):
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, FOOT_RECT], paper_size="a4")
        assert response.status_code == 200
        assert response.data["paper_size"] == "a4"
        # same bbox interpreted as A4 (8.27 x 11.69 in): (850/8.27 + 1100/11.69)/2
        assert response.data["ppi"] == pytest.approx(98.4, abs=0.1)

    def test_landscape_paper_orientation(self, auth_client):
        landscape_paper = bbox_pred("Paper", x=600, y=500, width=1100, height=850)
        response = post_paper(auth_client, [landscape_paper, FOOT_RECT])
        assert response.status_code == 200
        assert response.data["ppi"] == pytest.approx(100.0)

    def test_insole_class_fallback(self, auth_client):
        insole = polygon_pred("Insole", [(100, 100), (150, 100), (150, 1100), (100, 1100)])
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, insole])
        assert response.status_code == 200

    def test_highest_confidence_foot_wins(self, auth_client):
        small = polygon_pred("Foot", [(0, 0), (10, 0), (10, 100), (0, 100)], confidence=0.95)
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, FOOT_RECT, small])
        assert response.status_code == 200
        assert response.data["length_in"] == pytest.approx(1.0, abs=0.01)

    def test_bbox_only_foot_fallback(self, auth_client):
        foot_bbox = bbox_pred("Foot", x=300, y=600, width=400, height=1000)
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, foot_bbox])
        assert response.status_code == 200
        assert response.data["length_in"] == pytest.approx(10.0)
        assert response.data["width_in"] == pytest.approx(4.0)
        assert response.data["area_sq_in"] == pytest.approx(28.0)  # l * w * 0.70

    def test_toebox_extracted_when_present(self, auth_client):
        toebox = polygon_pred("Toe Box", [(100, 100), (150, 100), (150, 400), (100, 400)])
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, FOOT_RECT, toebox])
        assert response.status_code == 200
        assert response.data["toebox_length_in"] == pytest.approx(3.0, abs=0.05)
        assert response.data["toebox_width_in"] is not None

    def test_degenerate_toebox_ignored(self, auth_client):
        toebox = polygon_pred("Toe Box", [(100, 100), (150, 100)])
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, FOOT_RECT, toebox])
        assert response.status_code == 200
        assert response.data["toebox_length_in"] is None

    def test_no_paper_400(self, auth_client):
        response = post_paper(auth_client, [FOOT_RECT])
        assert response.status_code == 400
        assert "No paper detected" in response.data["detail"]

    def test_paper_without_dimensions_400(self, auth_client):
        bad_paper = bbox_pred("Paper", x=500, y=600, width=0, height=0)
        response = post_paper(auth_client, [bad_paper, FOOT_RECT])
        assert response.status_code == 400
        assert "paper dimensions" in response.data["detail"]

    def test_no_foot_400(self, auth_client):
        response = post_paper(auth_client, [PAPER_LETTER_100PPI])
        assert response.status_code == 400
        assert "No foot or insole" in response.data["detail"]

    def test_bbox_foot_without_size_400(self, auth_client):
        broken_foot = {"class": "Foot", "confidence": 0.9, "points": []}
        response = post_paper(auth_client, [PAPER_LETTER_100PPI, broken_foot])
        assert response.status_code == 400
        assert "foot dimensions" in response.data["detail"]


# ---------------------------------------------------------------------------
# AR snapshot validation
# ---------------------------------------------------------------------------

class TestArSnapshotValidation:
    def test_missing_snapshot_400(self, auth_client):
        response = auth_client.post(
            reverse(URL_NAME),
            {"image": upload_image(), "measurement_method": "arcore"},
            format="multipart",
        )
        assert response.status_code == 400
        assert "ar_snapshot required" in response.data["detail"]

    def test_oversized_snapshot_400(self, auth_client):
        response = post_ar(auth_client, [], None, raw_snapshot="x" * (64 * 1024 + 1))
        assert response.status_code == 400
        assert "too large" in response.data["detail"]

    def test_invalid_json_400(self, auth_client):
        response = post_ar(auth_client, [], None, raw_snapshot="{not json")
        assert response.status_code == 400
        assert "valid JSON" in response.data["detail"]

    @pytest.mark.parametrize("mutate,fragment", [
        (lambda s: s.pop("camera_intrinsics"), "camera_intrinsics"),
        (lambda s: s.update(plane_center=[0.0]), "plane_center"),
        (lambda s: s["camera_intrinsics"].__setitem__(0, [1.0, 2.0]), "3x3"),
        (lambda s: s["camera_pose"].__setitem__(0, [1.0]), "4x4"),
        (lambda s: s["plane_normal"].__setitem__(0, "abc"), "numeric"),
        (lambda s: s.pop("tracking_state"), "tracking_state"),
        (lambda s: s.update(tracking_state="PAUSED"), "PAUSED"),
    ])
    def test_malformed_snapshot_400(self, auth_client, mutate, fragment):
        snapshot = make_ar_snapshot()
        mutate(snapshot)
        response = post_ar(auth_client, [], snapshot)
        assert response.status_code == 400
        assert fragment in response.data["detail"]


# ---------------------------------------------------------------------------
# AR measurement paths
# ---------------------------------------------------------------------------

def sensor_rect_to_roboflow(x0, x1, y0, y1, h_sensor=480, n_edge=5):
    """Build a rotated-space (Roboflow) polygon whose counter-rotation gives a
    sensor-space rectangle [x0..x1] x [y0..y1]. Inverse mapping:
    y_rf = x_sensor, x_rf = (H-1) - y_sensor. Edge points are interpolated so
    percentile width logic has more than 4 vertices to chew on."""
    pts_sensor = []
    for i in range(n_edge + 1):
        t = i / n_edge
        pts_sensor.append((x0 + t * (x1 - x0), y0))
    for i in range(n_edge + 1):
        t = i / n_edge
        pts_sensor.append((x1, y0 + t * (y1 - y0)))
    for i in range(n_edge + 1):
        t = i / n_edge
        pts_sensor.append((x1 - t * (x1 - x0), y1))
    for i in range(n_edge + 1):
        t = i / n_edge
        pts_sensor.append((x0, y1 - t * (y1 - y0)))
    return [((h_sensor - 1) - ys, xs) for xs, ys in pts_sensor]


def ar_foot_pred(x0=200, x1=460, y0=200, y1=300, confidence=0.9):
    """Foot rectangle in sensor space; at 0.7 m height this is
    (x1-x0) mm long and (y1-y0) mm wide on the floor."""
    return polygon_pred("Foot", sensor_rect_to_roboflow(x0, x1, y0, y1), confidence=confidence)


def ar_wall_pred(seam_x_sensor=190):
    """Wall Base bbox in rotated space whose top edge counter-rotates to the
    sensor line x_sensor == seam_x_sensor, spanning the foot's y range."""
    # top edge: y_rf = y_c - h/2 == seam_x_sensor; lateral span x_rf 149..309
    return bbox_pred("Wall Base", x=229, y=seam_x_sensor + 100, width=160, height=200)


class TestArMeasurement:
    def test_pairwise_path_success(self, auth_client, user):
        response = post_ar(auth_client, [ar_foot_pred()], make_ar_snapshot())
        assert response.status_code == 200
        data = response.data
        assert data["measurement_method"] == "arcore"
        assert data["measurement_path"] == "pairwise"
        # 260mm x 100mm rectangle -> diagonal 278.6mm = 10.97 in
        assert data["length_in"] == pytest.approx(10.97, abs=0.05)
        # width: span perpendicular to the diagonal = 2*l*w/diag = 186.6mm
        assert data["width_in"] == pytest.approx(7.35, abs=0.1)

        m = Measurement.objects.get(user=user)
        assert m.measurement_method == Measurement.MeasurementMethod.ARCORE
        assert m.paper_type is None

    def test_wall_seam_path(self, auth_client):
        # heel at x=200, seam at x=190 -> 10mm gap (within 25mm anchor window)
        preds = [ar_foot_pred(), ar_wall_pred(seam_x_sensor=190)]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        data = response.data
        assert data["measurement_path"] == "wall_seam"
        # seam-to-toe: 460 - 190 = 270mm = 10.63 in
        assert data["length_in"] == pytest.approx(10.63, abs=0.05)
        assert "warning" not in data

    def test_wall_seam_gap_fallback_warns(self, auth_client):
        # seam 60mm behind heel -> gap exceeds the 25mm anchor max
        preds = [ar_foot_pred(), ar_wall_pred(seam_x_sensor=140)]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        data = response.data
        assert data["measurement_path"] == "wall_seam_gap_fallback"
        # falls back to the polygon span projected on the heel->toe axis
        assert data["length_in"] == pytest.approx(10.72, abs=0.06)
        assert data["warning"] == "heel_not_touching_wall"

    def test_multi_foot_selects_wall_side_foot(self, auth_client):
        near = ar_foot_pred(x0=200, x1=460, confidence=0.5)
        far = ar_foot_pred(x0=250, x1=510, y0=320, y1=420, confidence=0.99)
        preds = [near, far, ar_wall_pred(seam_x_sensor=190)]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        # near foot (10mm gap) chosen over far foot (60mm gap) despite confidence
        assert response.data["length_in"] == pytest.approx(10.63, abs=0.05)

    def test_toebox_present_in_ar_response(self, auth_client):
        toebox = polygon_pred("Toe Box", sensor_rect_to_roboflow(380, 460, 210, 290))
        response = post_ar(auth_client, [ar_foot_pred(), toebox], make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["toebox_length_in"] is not None

    def test_camera_too_high_400(self, auth_client):
        response = post_ar(auth_client, [], make_ar_snapshot(camera_height_m=1.2))
        assert response.status_code == 400
        assert "too far" in response.data["detail"]

    def test_camera_too_low_400(self, auth_client):
        response = post_ar(auth_client, [], make_ar_snapshot(camera_height_m=0.2))
        assert response.status_code == 400
        assert "too close" in response.data["detail"]

    def test_no_foot_detected_400(self, auth_client):
        response = post_ar(auth_client, [], make_ar_snapshot())
        assert response.status_code == 400
        assert "No foot or insole" in response.data["detail"]

    def test_too_few_polygon_points_400(self, auth_client):
        tiny = polygon_pred("Foot", [(100, 100), (200, 200)])
        response = post_ar(auth_client, [tiny], make_ar_snapshot())
        assert response.status_code == 400
        assert "too few points" in response.data["detail"]

    def test_out_of_range_length_400(self, auth_client):
        # 400mm -> 15.7 in, beyond the 13 in human-foot ceiling
        huge = ar_foot_pred(x0=100, x1=500)
        response = post_ar(auth_client, [huge], make_ar_snapshot())
        assert response.status_code == 400
        assert "outside the expected range" in response.data["detail"]

    def test_roboflow_failure_in_ar_path_502(self, auth_client):
        data = {
            "image": upload_image(),
            "measurement_method": "arcore",
            "ar_snapshot": json.dumps(make_ar_snapshot()),
        }
        with patch(
            "backend.api.views.http_requests.post",
            side_effect=real_requests.ConnectionError("down"),
        ), patch("backend.api.views._save_ar_debug_image"):
            response = auth_client.post(reverse(URL_NAME), data, format="multipart")
        assert response.status_code == 502

    def test_broken_wall_falls_back_to_pairwise(self, auth_client):
        # Wall Base bbox entirely outside the image -> seam fitting raises,
        # the view falls back to the pairwise path.
        bad_wall = bbox_pred("Wall Base", x=600, y=290, width=100, height=200)
        response = post_ar(auth_client, [ar_foot_pred(), bad_wall], make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "pairwise"

    def test_multi_foot_all_candidates_fail_wall_fitting(self, auth_client):
        # Both feet present but the wall seam can't be fitted: selection falls
        # back to the highest-confidence foot and the pairwise path.
        near = ar_foot_pred(confidence=0.4)
        far = ar_foot_pred(x0=250, x1=510, y0=320, y1=420, confidence=0.95)
        bad_wall = bbox_pred("Wall Base", x=600, y=290, width=100, height=200)
        response = post_ar(auth_client, [near, far, bad_wall], make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "pairwise"

    def test_multi_foot_all_negative_gaps_picks_least_negative(self, auth_client):
        # Seam sits inside both feet; the least-negative gap wins.
        foot_a = ar_foot_pred(x0=200, x1=460, confidence=0.9)               # gap -100mm
        foot_b = ar_foot_pred(x0=250, x1=510, y0=320, y1=420, confidence=0.5)  # gap -50mm
        preds = [foot_a, foot_b, ar_wall_pred(seam_x_sensor=300)]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "wall_seam_inside_fallback"

    def test_multi_foot_with_toebox_reruns_wall_math(self, auth_client):
        near = ar_foot_pred(confidence=0.5)
        far = ar_foot_pred(x0=250, x1=510, y0=320, y1=420, confidence=0.99)
        toebox = polygon_pred("Toe Box", sensor_rect_to_roboflow(420, 500, 210, 290))
        preds = [near, far, ar_wall_pred(seam_x_sensor=190), toebox]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "wall_seam"
        # toebox extends the near foot's toe from 460 to 500: (500-190)mm = 12.2 in
        assert response.data["length_in"] == pytest.approx(12.2, abs=0.06)


def tilted_snapshot():
    """Floor plane tilted toward the camera: pixels right of x~670 cast rays
    that intersect the plane behind the camera, making unprojection fail while
    the camera-height gate still passes (height = 0.7 * 0.447 = 12.3 in)."""
    snapshot = make_ar_snapshot()
    snapshot["plane_normal"] = [2.0, 1.0, 0.0]
    return snapshot


class TestArUnprojectionFailures:
    def test_pairwise_failure_400(self, auth_client):
        doomed = polygon_pred("Foot", sensor_rect_to_roboflow(700, 760, 200, 300))
        response = post_ar(auth_client, [doomed], tilted_snapshot())
        assert response.status_code == 400
        assert "AR measurement failed" in response.data["detail"]

    def test_wall_then_pairwise_failure_400(self, auth_client):
        doomed = polygon_pred("Foot", sensor_rect_to_roboflow(700, 760, 200, 300))
        # wall seam pixels also land in the failing region
        wall = ar_wall_pred(seam_x_sensor=700)
        response = post_ar(auth_client, [doomed, wall], tilted_snapshot())
        assert response.status_code == 400
        assert "AR measurement failed" in response.data["detail"]

    def test_multi_foot_skips_degenerate_candidate(self, auth_client):
        stub = polygon_pred("Foot", [(100, 100), (200, 200)], confidence=0.99)
        preds = [ar_foot_pred(confidence=0.5), stub, ar_wall_pred(seam_x_sensor=190)]
        response = post_ar(auth_client, preds, make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "wall_seam"
        assert response.data["length_in"] == pytest.approx(10.63, abs=0.05)

    def test_extract_toebox_ar_failure_returns_none(self):
        from backend.api.views import FootMeasureView

        toebox = polygon_pred("Toe Box", [(700, 200), (760, 200), (760, 300)])
        result = FootMeasureView()._extract_toebox([toebox], ar_snapshot=tilted_snapshot())
        assert result == (None, None)

    def test_extract_toebox_without_scale_source_returns_none(self):
        from backend.api.views import FootMeasureView

        toebox = polygon_pred("Toe Box", [(10, 10), (60, 10), (60, 80)])
        assert FootMeasureView()._extract_toebox([toebox]) == (None, None)

    def test_polygon_wall_base_in_view(self, auth_client):
        # model v24+ returns the Wall Base as a polygon; build one (in rotated
        # space) whose sensor-space seam edge sits 10mm behind the heel
        sensor_pts = [
            (x, y)
            for x in range(190, 231, 10)
            for y in range(100, 401, 20)
        ]
        rotated = [((480 - 1) - ys, xs) for xs, ys in sensor_pts]
        wall_poly = polygon_pred("Wall Base", rotated)
        response = post_ar(auth_client, [ar_foot_pred(), wall_poly], make_ar_snapshot())
        assert response.status_code == 200
        assert response.data["measurement_path"] == "wall_seam"
        assert response.data["length_in"] == pytest.approx(10.63, abs=0.05)


# ---------------------------------------------------------------------------
# AR debug image rendering
# ---------------------------------------------------------------------------

class TestSaveArDebugImage:
    @override_settings(AR_DEBUG_IMAGES=True)
    def test_writes_annotated_jpeg(self, tmp_path):
        from PIL import Image

        from backend.api import views

        img = Image.new("RGB", (200, 200), (40, 40, 40))
        preds = [
            polygon_pred("foot", [(10, 10), (100, 10), (100, 150)]),
            bbox_pred("wall base", x=50, y=50, width=40, height=20),
        ]
        with patch.object(views, "_AR_DEBUG_DIR", str(tmp_path)):
            views._save_ar_debug_image(img, preds, label="42")
        files = list(tmp_path.glob("ar_debug_42_*.jpg"))
        assert len(files) == 1

    def test_noop_when_debug_flags_off(self, tmp_path):
        # User foot photos must never be persisted unless explicitly
        # debugging — the guard lives inside the function so every caller
        # inherits it.
        from PIL import Image

        from backend.api import views

        img = Image.new("RGB", (200, 200), (40, 40, 40))
        with patch.object(views, "_AR_DEBUG_DIR", str(tmp_path)):
            views._save_ar_debug_image(img, [], label="42")
        assert list(tmp_path.iterdir()) == []

    @override_settings(AR_DEBUG_IMAGES=True)
    def test_failure_is_non_fatal(self, tmp_path):
        from backend.api import views

        with patch.object(views, "_AR_DEBUG_DIR", str(tmp_path)):
            # not an image — .copy() exists on str? no -> exception swallowed
            views._save_ar_debug_image("not-an-image", [], label="x")
