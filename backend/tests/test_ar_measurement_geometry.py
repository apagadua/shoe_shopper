"""Geometry tests for backend/services/ar_measurement.py.

Uses the synthetic straight-down camera from conftest.make_ar_snapshot:
at the default 0.7 m height with f=700, one sensor pixel maps to exactly
1 mm on the floor plane (world_x = (px-320)/1000, world_z = -(py-240)/1000).
"""

import numpy as np
import pytest

from backend.services.ar_measurement import (
    METERS_TO_INCHES,
    _counter_rotate_point,
    _fit_seam_line,
    compute_dimensions,
    compute_dimensions_with_wall,
    extract_wall_seam,
    unproject_to_plane,
)
from backend.tests.conftest import bbox_pred, make_ar_snapshot


def snapshot_matrices(snapshot):
    K_inv = np.linalg.inv(np.array(snapshot["camera_intrinsics"], dtype=float))
    pose = np.array(snapshot["camera_pose"], dtype=float)
    n = np.array(snapshot["plane_normal"], dtype=float)
    n = n / np.linalg.norm(n)
    p0 = np.array(snapshot["plane_center"], dtype=float)
    return K_inv, pose[:3, 3], pose[:3, :3], n, p0


def sensor_rect(x0, x1, y0, y1, n_edge=5):
    """Sensor-space rectangle outline as (px, py) tuples."""
    pts = []
    for i in range(n_edge + 1):
        pts.append((x0 + (x1 - x0) * i / n_edge, y0))
    for i in range(n_edge + 1):
        pts.append((x1, y0 + (y1 - y0) * i / n_edge))
    for i in range(n_edge + 1):
        pts.append((x1 - (x1 - x0) * i / n_edge, y1))
    for i in range(n_edge + 1):
        pts.append((x0, y1 - (y1 - y0) * i / n_edge))
    return pts


def wall_bbox(seam_x_sensor):
    """Rotated-space Wall Base bbox whose top edge lands on x_sensor == seam."""
    return bbox_pred("Wall Base", x=229, y=seam_x_sensor + 100, width=160, height=200)


# ---------------------------------------------------------------------------
# unproject_to_plane
# ---------------------------------------------------------------------------

class TestUnprojectToPlane:
    def test_center_pixel_lands_below_camera(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        point = unproject_to_plane(320, 240, K_inv, origin, R, n, p0)
        np.testing.assert_allclose(point, [0.0, 0.0, 0.0], atol=1e-9)

    def test_pixel_offset_maps_to_mm(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        point = unproject_to_plane(420, 140, K_inv, origin, R, n, p0)
        np.testing.assert_allclose(point, [0.1, 0.0, 0.1], atol=1e-9)

    def test_ray_parallel_to_plane_raises(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, _, _ = snapshot_matrices(snapshot)
        # vertical wall plane: the straight-down center ray never crosses it
        with pytest.raises(ValueError, match="parallel"):
            unproject_to_plane(320, 240, K_inv, origin, R,
                               np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]))

    def test_intersection_behind_camera_raises(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, _ = snapshot_matrices(snapshot)
        # plane above the camera while looking down
        with pytest.raises(ValueError, match="behind"):
            unproject_to_plane(320, 240, K_inv, origin, R, n, np.array([0.0, 2.0, 0.0]))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_counter_rotate_point_inverts_90cw():
    assert _counter_rotate_point(10, 25, 480) == (25.0, 469.0)


class TestFitSeamLine:
    def test_fits_axis_aligned_line(self):
        pts = [[0.0, 0.0, float(z)] for z in range(5)]
        centroid, direction = _fit_seam_line(pts)
        np.testing.assert_allclose(centroid, [0.0, 0.0, 2.0])
        assert abs(direction[2]) == pytest.approx(1.0)

    def test_fewer_than_two_points_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            _fit_seam_line([[0.0, 0.0, 0.0]])


# ---------------------------------------------------------------------------
# compute_dimensions (pairwise path)
# ---------------------------------------------------------------------------

class TestComputeDimensions:
    def test_square_dimensions(self):
        snapshot = make_ar_snapshot()
        # 100mm x 100mm square on the floor
        result = compute_dimensions(sensor_rect(320, 420, 240, 340), snapshot)
        diag_in = 0.1 * np.sqrt(2) * METERS_TO_INCHES
        assert result["length_in"] == pytest.approx(diag_in, abs=0.01)
        assert result["width_in"] == pytest.approx(diag_in, abs=0.01)
        assert result["area_sq_in"] == pytest.approx(0.01 * METERS_TO_INCHES**2, abs=0.1)

    def test_requires_three_points(self):
        with pytest.raises(ValueError, match="At least 3"):
            compute_dimensions([(0, 0), (1, 1)], make_ar_snapshot())


# ---------------------------------------------------------------------------
# extract_wall_seam
# ---------------------------------------------------------------------------

class TestExtractWallSeam:
    def test_bbox_path_fits_seam_on_floor(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        centroid, direction, meta = extract_wall_seam(
            wall_bbox(190), 480, K_inv, origin, R, n, p0
        )
        # seam line: x_sensor = 190 -> world_x = (190-320)/1000 = -0.13
        assert centroid[0] == pytest.approx(-0.13, abs=1e-6)
        assert abs(np.dot(direction, n)) < 0.01
        assert meta["path_label"] == "bbox-fallback"

    def test_bbox_outside_image_raises(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        # x range clamps to empty: left edge beyond H_sensor-1
        with pytest.raises(ValueError, match="outside the image"):
            extract_wall_seam(
                bbox_pred("Wall Base", x=600, y=290, width=100, height=200),
                480, K_inv, origin, R, n, p0,
            )

    def test_underdetermined_seam_raises(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, _, _ = snapshot_matrices(snapshot)
        # vertical plane through the seam pixels' rays -> every cast fails
        n_wall = np.array([1.0, 0.0, 0.0])
        p0_wall = np.array([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="underdetermined"):
            extract_wall_seam(wall_bbox(320), 480, K_inv, origin, R, n_wall, p0_wall)

    def test_polygon_path_uses_per_column_minimums(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        # wall-base region: sensor x in [150, 190], y in [100, 400] — the seam
        # is the min-x edge at 150. Provide a dense grid so binning engages.
        pts = [
            {"x": float(x), "y": float(y)}
            for x in range(150, 191, 10)
            for y in range(100, 401, 20)
        ]
        centroid, direction, meta = extract_wall_seam(
            {"points": pts}, 480, K_inv, origin, R, n, p0
        )
        assert centroid[0] == pytest.approx((150 - 320) / 1000, abs=1e-6)
        assert abs(np.dot(direction, n)) < 0.01
        assert "per-col-robust" in meta["path_label"]

    def test_polygon_path_rejects_leg_artifact_columns(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        # true seam at x=150 plus a leg artifact poking above it (x=100) in a
        # few central columns — those columns fall below the median and are
        # dropped, keeping the fitted seam on the real edge
        pts = [
            {"x": float(x), "y": float(y)}
            for x in range(150, 191, 10)
            for y in range(100, 401, 20)
        ]
        pts += [{"x": 100.0, "y": float(y)} for y in (240.0, 250.0, 260.0)]
        centroid, direction, meta = extract_wall_seam(
            {"points": pts}, 480, K_inv, origin, R, n, p0
        )
        assert centroid[0] == pytest.approx((150 - 320) / 1000, abs=1e-6)
        assert meta["clean_bins"] < meta["total_bins"]

    def test_polygon_degenerate_lateral_span_uses_global_min(self):
        snapshot = make_ar_snapshot()
        K_inv, origin, R, n, p0 = snapshot_matrices(snapshot)
        # all points share one y (zero lateral extent in rotated space);
        # step 2 keeps >= 5 points within the 8px seam tolerance band
        pts = [{"x": float(x), "y": 250.0} for x in range(150, 191, 2)]
        centroid, direction, meta = extract_wall_seam(
            {"points": pts}, 480, K_inv, origin, R, n, p0
        )
        assert "global-min" in meta["path_label"]


# ---------------------------------------------------------------------------
# compute_dimensions_with_wall
# ---------------------------------------------------------------------------

FOOT_RECT = sensor_rect(200, 460, 200, 300)  # 260mm x 100mm, heel at x=200


class TestComputeDimensionsWithWall:
    def test_wall_seam_anchor_path(self):
        result = compute_dimensions_with_wall(FOOT_RECT, wall_bbox(190), make_ar_snapshot())
        assert result["measurement_path"] == "wall_seam"
        # seam-to-toe: (460 - 190) mm
        assert result["length_in"] == pytest.approx(0.270 * METERS_TO_INCHES, abs=0.05)
        assert result["heel_gap_in"] == pytest.approx(0.010 * METERS_TO_INCHES, abs=0.02)

    def test_seam_inside_foot_falls_back_to_polygon_span(self):
        result = compute_dimensions_with_wall(FOOT_RECT, wall_bbox(230), make_ar_snapshot())
        assert result["measurement_path"] == "wall_seam_inside_fallback"
        assert result["heel_gap_in"] < 0
        # span projected on the heel->toe axis
        assert result["length_in"] == pytest.approx(10.72, abs=0.06)

    def test_large_gap_falls_back(self):
        result = compute_dimensions_with_wall(FOOT_RECT, wall_bbox(140), make_ar_snapshot())
        assert result["measurement_path"] == "wall_seam_gap_fallback"
        assert result["toe_ext_in"] == 0.0

    def test_toebox_extends_toe_reference(self):
        toebox = sensor_rect(420, 500, 210, 290)
        result = compute_dimensions_with_wall(
            FOOT_RECT, wall_bbox(190), make_ar_snapshot(), toebox_points_px=toebox
        )
        assert result["measurement_path"] == "wall_seam"
        # toebox reaches x=500: length = (500 - 190) mm; extension = 40 mm
        assert result["length_in"] == pytest.approx(0.310 * METERS_TO_INCHES, abs=0.05)
        assert result["toe_ext_in"] == pytest.approx(0.040 * METERS_TO_INCHES, abs=0.05)

    def test_toebox_behind_toe_is_ignored(self):
        toebox = sensor_rect(380, 440, 210, 290)
        result = compute_dimensions_with_wall(
            FOOT_RECT, wall_bbox(190), make_ar_snapshot(), toebox_points_px=toebox
        )
        assert result["toe_ext_in"] == 0.0
        assert result["length_in"] == pytest.approx(0.270 * METERS_TO_INCHES, abs=0.05)

    def test_requires_three_foot_points(self):
        with pytest.raises(ValueError, match="At least 3"):
            compute_dimensions_with_wall([(0, 0), (1, 1)], wall_bbox(190), make_ar_snapshot())

    def test_toebox_unprojection_failure_is_non_fatal(self):
        # tilt the floor so pixels right of x~670 intersect behind the camera;
        # the foot and seam stay valid, only the toebox extension fails
        snapshot = make_ar_snapshot()
        snapshot["plane_normal"] = [2.0, 1.0, 0.0]
        doomed_toebox = sensor_rect(700, 760, 210, 290)
        result = compute_dimensions_with_wall(
            FOOT_RECT, wall_bbox(190), snapshot, toebox_points_px=doomed_toebox
        )
        assert result["toe_ext_in"] == 0.0

    def test_degenerate_point_foot_in_gap_fallback(self):
        # three identical foot points 110mm from the seam: gap fallback with a
        # zero-length heel->toe vector exercises the degenerate-axis branch
        foot = [(300, 250), (300, 250), (300, 250)]
        result = compute_dimensions_with_wall(foot, wall_bbox(190), make_ar_snapshot())
        assert result["measurement_path"] == "wall_seam_gap_fallback"
        assert result["length_in"] == pytest.approx(0.0, abs=1e-6)
