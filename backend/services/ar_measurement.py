"""
AR-based foot measurement service.

Takes 2D pixel coordinates from Roboflow + an AR snapshot captured at
shutter-press time, and returns real-world foot dimensions in inches.

The AR snapshot contains:
  - camera_intrinsics: 3x3 matrix (focal length + principal point)
  - camera_pose: 4x4 world-from-camera transform
  - plane_center: [x, y, z] point on the detected floor plane
  - plane_normal: [x, y, z] normal vector of the floor plane
  - image_dimensions: [width, height] of the captured frame

Math: for each 2D pixel point, cast a ray from the camera origin through
the pixel and find where it intersects the floor plane. The resulting 3D
world coordinates are then used to compute length, width, and area.
"""

import numpy as np

METERS_TO_INCHES = 39.3701


def unproject_to_plane(pixel_x, pixel_y, K_inv, ray_origin, R, n, p0):
    """
    Unproject a single 2D pixel coordinate onto a 3D floor plane.

    Accepts pre-computed matrices so callers processing many points avoid
    recomputing K_inv / pose decomposition on every call.

    Args:
        pixel_x, pixel_y: 2D image coordinates (from Roboflow)
        K_inv:       Inverse of the 3x3 camera intrinsics matrix (ndarray)
        ray_origin:  Camera position in world space, shape (3,) (ndarray)
        R:           3x3 rotation sub-matrix of camera pose (ndarray)
        n:           Normalised floor-plane normal, shape (3,) (ndarray)
        p0:          Any point on the floor plane, shape (3,) (ndarray)

    Returns:
        np.ndarray of shape (3,) — world coordinate where the ray hits the plane

    Raises:
        ValueError: if the ray is parallel to the plane or intersects behind
                    the camera (degenerate geometry)
    """
    # Unproject pixel into OpenCV camera frame: X right, Y down, +Z into scene.
    ray_cam = K_inv @ np.array([pixel_x, pixel_y, 1.0])

    # ARCore's camera.pose rotation R maps from the ARCore/OpenGL camera frame
    # (X right, Y up, -Z toward the scene) to world. Convert OpenCV → OpenGL by
    # flipping both Y and Z before applying R.
    ray_cam[1] = -ray_cam[1]
    ray_cam[2] = -ray_cam[2]

    ray_dir = R @ ray_cam
    ray_dir = ray_dir / np.linalg.norm(ray_dir)

    denom = np.dot(ray_dir, n)
    if abs(denom) < 1e-8:
        raise ValueError("Ray is parallel to the floor plane — cannot intersect")

    t = np.dot(p0 - ray_origin, n) / denom
    if t < 0:
        raise ValueError("Plane intersection is behind the camera")

    return ray_origin + t * ray_dir


def _refine_heel_with_wall_base(foot_points_px, wall_base, K_inv, ray_origin, R, n, p0):
    """
    Use the Wall Base bounding box to compute a more accurate heel world point.

    The Wall Base marks the floor-wall junction in image space. The true heel
    position is where the foot contacts that junction. We find the foot polygon's
    heel cluster x-centroid, then project (heel_x, wall_base_y) onto the floor
    plane — placing the heel exactly on the wall-floor line rather than relying
    on the foot polygon edge which may fall slightly short.

    Args:
        foot_points_px: list of (x, y) pixel tuples from the foot polygon
        wall_base:      Roboflow prediction dict for the "Wall Base" class,
                        containing x (center), y (center), width, height
        K_inv, ray_origin, R, n, p0: pre-computed camera geometry

    Returns:
        np.ndarray of shape (3,) — refined heel world point, or None if the
        projection fails or the wall base is too far from the foot polygon.
    """
    # The Wall Base bbox encloses a chunk of wall above the floor; the actual
    # floor-wall junction is the bottom edge of the bbox (largest y in image coords).
    wb_x = wall_base["x"]
    wb_w = wall_base["width"]
    wb_h = wall_base["height"]
    wb_y = wall_base["y"] + wb_h / 2.0

    foot_ys = [py for _, py in foot_points_px]
    foot_min_y, foot_max_y = min(foot_ys), max(foot_ys)

    # Determine which end of the foot is the heel: whichever extreme is
    # closest to the wall base centre in image y.
    if abs(foot_max_y - wb_y) <= abs(foot_min_y - wb_y):
        heel_threshold = foot_max_y - (foot_max_y - foot_min_y) * 0.15
        heel_pts = [(px, py) for px, py in foot_points_px if py >= heel_threshold]
    else:
        heel_threshold = foot_min_y + (foot_max_y - foot_min_y) * 0.15
        heel_pts = [(px, py) for px, py in foot_points_px if py <= heel_threshold]

    if not heel_pts:
        return None

    heel_x = sum(px for px, _ in heel_pts) / len(heel_pts)

    # Clamp to the wall base's horizontal span so we don't project outside it.
    half_w = wb_w / 2.0
    heel_x = max(wb_x - half_w, min(wb_x + half_w, heel_x))

    try:
        return unproject_to_plane(heel_x, wb_y, K_inv, ray_origin, R, n, p0)
    except ValueError:
        return None


def compute_dimensions(foot_points_px, ar_snapshot, wall_base=None):
    """
    Compute foot dimensions in inches from 2D Roboflow points + AR snapshot.

    Uses the same heel-to-toe (max span) and perpendicular-width (95th-percentile)
    logic as the paper method, but in 3D world space.

    Args:
        foot_points_px: list of (x, y) pixel coordinates from the Roboflow polygon
        ar_snapshot:    dict with keys:
                          camera_intrinsics, camera_pose,
                          plane_center, plane_normal
        wall_base:      optional Roboflow prediction dict for the "Wall Base" class.
                        When provided, the heel endpoint is anchored to the
                        wall-floor junction for improved length accuracy.

    Returns:
        dict with:
          length_in  — heel-to-toe distance in inches
          width_in   — 95th-percentile perpendicular span in inches
          area_sq_in — shoelace area of the polygon projected onto the floor plane

    Raises:
        ValueError: if fewer than 3 points are provided or geometry is degenerate
    """
    if len(foot_points_px) < 3:
        raise ValueError("At least 3 foot polygon points are required")

    # Pre-compute once — these are identical for every polygon point.
    K_inv      = np.linalg.inv(np.array(ar_snapshot["camera_intrinsics"], dtype=float))
    pose       = np.array(ar_snapshot["camera_pose"], dtype=float)
    ray_origin = pose[:3, 3]
    R          = pose[:3, :3]
    n          = np.array(ar_snapshot["plane_normal"], dtype=float)
    n          = n / np.linalg.norm(n)   # normalise once here (see Fix #7)
    p0         = np.array(ar_snapshot["plane_center"], dtype=float)

    # Unproject every Roboflow polygon point onto the floor plane
    world_points = np.array([
        unproject_to_plane(px, py, K_inv, ray_origin, R, n, p0)
        for px, py in foot_points_px
    ])

    # --- Length: max pairwise distance (heel to toe) ---
    max_dist = 0.0
    p1_idx, p2_idx = 0, 1
    for i in range(len(world_points)):
        for j in range(i + 1, len(world_points)):
            d = float(np.linalg.norm(world_points[j] - world_points[i]))
            if d > max_dist:
                max_dist = d
                p1_idx, p2_idx = i, j

    # If a Wall Base was detected, replace the heel endpoint with a point
    # projected from the wall-floor junction — more accurate than the polygon edge.
    if wall_base:
        refined_heel = _refine_heel_with_wall_base(
            foot_points_px, wall_base, K_inv, ray_origin, R, n, p0
        )
        if refined_heel is not None:
            # Identify which of the two span endpoints is the heel (the one
            # closest to the refined heel position), then replace it.
            d0 = float(np.linalg.norm(world_points[p1_idx] - refined_heel))
            d1 = float(np.linalg.norm(world_points[p2_idx] - refined_heel))
            if d0 <= d1:
                toe_world = world_points[p2_idx]
            else:
                toe_world = world_points[p1_idx]
            max_dist = float(np.linalg.norm(toe_world - refined_heel))
            # Rebuild world_points with the refined heel so width/area stay consistent
            if d0 <= d1:
                world_points[p1_idx] = refined_heel
            else:
                world_points[p2_idx] = refined_heel

    length_m = max_dist

    # --- Width: 95th-percentile perpendicular span ---
    axis = world_points[p2_idx] - world_points[p1_idx]
    axis_norm = axis / np.linalg.norm(axis)

    # n is already normalised above; reuse it here
    perp = np.cross(axis_norm, n)
    if np.linalg.norm(perp) < 1e-8:
        # axis is parallel to plane normal — degenerate; fall back to any perpendicular
        perp = np.cross(axis_norm, np.array([0.0, 1.0, 0.0]))
    perp = perp / np.linalg.norm(perp)

    projs = sorted(float(np.dot(wp, perp)) for wp in world_points)
    n_pts = len(projs)
    lo = projs[max(0, int(n_pts * 0.025))]
    hi = projs[min(n_pts - 1, int(n_pts * 0.975))]
    width_m = hi - lo

    # --- Area: shoelace on the 2D floor-plane projection ---
    u_axis = axis_norm
    v_axis = perp
    pts_2d = [(float(np.dot(wp, u_axis)), float(np.dot(wp, v_axis))) for wp in world_points]
    area_m2 = abs(sum(
        pts_2d[i][0] * pts_2d[(i + 1) % n_pts][1]
        - pts_2d[(i + 1) % n_pts][0] * pts_2d[i][1]
        for i in range(n_pts)
    )) / 2.0

    return {
        "length_in":   round(length_m  * METERS_TO_INCHES,       3),
        "width_in":    round(width_m   * METERS_TO_INCHES,       3),
        "area_sq_in":  round(area_m2   * METERS_TO_INCHES ** 2,  3),
    }
