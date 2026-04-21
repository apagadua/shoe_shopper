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
    # Unproject pixel into the camera image frame (OpenCV convention:
    # X right, Y down, Z toward the scene).
    ray_cam = K_inv @ np.array([pixel_x, pixel_y, 1.0])

    # ARCore's camera.pose rotation R maps FROM the ARCore/OpenGL camera frame
    # (X right, Y up, Z toward the viewer — i.e., *away* from the scene) TO world
    # space.  The K_inv formula puts Z toward the scene (+Z forward, OpenCV), which
    # is the opposite convention.  Negate Z to convert before applying R so the ray
    # points toward the floor rather than toward the ceiling.
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


def compute_dimensions(foot_points_px, ar_snapshot):
    """
    Compute foot dimensions in inches from 2D Roboflow points + AR snapshot.

    Uses the same heel-to-toe (max span) and perpendicular-width (95th-percentile)
    logic as the paper method, but in 3D world space.

    Args:
        foot_points_px: list of (x, y) pixel coordinates from the Roboflow polygon
        ar_snapshot:    dict with keys:
                          camera_intrinsics, camera_pose,
                          plane_center, plane_normal

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
