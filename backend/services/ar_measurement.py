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

Wall-anchored path (compute_dimensions_with_wall):
  When Roboflow also detects a "Wall Base" bounding box, the top edge of
  that bbox is the wall-floor seam.  Sampling that edge, counter-rotating
  to sensor space, and ray-casting to the floor gives a stable 3D seam
  line that anchors the heel reference — eliminating heel-polygon jitter
  and heel-pad compression bias from the length measurement.
"""

import numpy as np

METERS_TO_INCHES = 39.3701
_SEAM_NORMAL_MAX_DOT = 0.15   # |dot(seam_dir, floor_normal)| threshold (~9°)
_SEAM_SAMPLE_COUNT   = 20     # points sampled along the wall base top edge
_SEAM_MIN_INLIERS    = 5      # minimum ray-cast seam points for a valid fit

# Maximum plausible heel gap for the wall-seam anchor path.
#
# When the heel is pressed flush against the wall, Roboflow typically misses
# 0–10 mm of the heel tip (foot polygon stops short of the wall).  A gap up
# to ~25 mm (≈1 in) is treated as a plausible worst-case under-detection.
#
# Gaps larger than this almost always mean the seam centroid has drifted
# backward — caused by a noisy/angled seam fit or the foot not being flush
# against the wall.  In either case the seam-to-toe path would inflate the
# measured length by the spurious gap, so we fall back to polygon span.
_HEEL_GAP_SEAM_ANCHOR_MAX_M = 0.025   # 25 mm ≈ 1.0 in


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
    # Unproject pixel into the camera image frame.
    # camera.imageIntrinsics is for the CPU image in SENSOR space:
    #   +X right (column direction), +Y down (row direction), +Z into scene.
    # K_inv @ [px, py, 1] therefore gives the ray in that OpenCV convention.
    ray_cam = K_inv @ np.array([pixel_x, pixel_y, 1.0])

    # camera.pose (ARCore/OpenGL convention):
    #   +X right, +Y up, -Z into scene.
    # We must convert the OpenCV ray to the OpenGL camera frame before
    # applying the world-from-camera rotation R:
    #   • Y: image rows increase downward (+Y down) → OpenGL camera +Y is up → negate
    #   • Z: OpenCV +Z toward scene → OpenGL -Z toward scene → negate
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


def _counter_rotate_point(x_rf, y_rf, H_sensor):
    """
    Inverse of the 90° CW rotation applied before sending to Roboflow.
    Maps a single point from rotated (Roboflow) space back to sensor space.
    """
    return float(y_rf), float(H_sensor - 1 - x_rf)


def _fit_seam_line(points_3d):
    """
    Fit a 3D line through a set of world points via PCA (first principal component).

    Returns (centroid, direction) where direction is a unit vector along the line.
    Raises ValueError if fewer than 2 distinct points are provided.
    """
    pts = np.array(points_3d, dtype=float)
    if len(pts) < 2:
        raise ValueError("Need at least 2 points to fit a seam line")
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    direction = Vt[0]
    direction = direction / np.linalg.norm(direction)
    return centroid, direction


def extract_wall_seam(wall_pred, H_sensor, K_inv, ray_origin, R, n, p0):
    """
    Derive a 3D wall-floor seam line from a "Wall Base" prediction.

    Handles two cases:

    Polygon path (new model):
        wall_pred has polygon points already counter-rotated to sensor space by
        _counter_rotate_preds in the caller.  The Wall Base polygon outlines the
        entire wall-base region; the seam (floor-wall junction) is its topmost
        edge at each lateral position in the original portrait/Roboflow space.
        We split the polygon's lateral extent (x_rf direction) into bins and
        take the minimum y_rf (= minimum x_sensor) per bin.  This per-column
        minimum approach correctly handles diagonal seam appearances caused by
        camera perspective or tilt — a single global y_rf threshold would mix
        floor pixels and elevated baseboard pixels, corrupting the seam direction.

    Bbox path (legacy / bbox-only Wall Base):
        Synthesises a horizontal scanline at the top edge of the bbox, counter-
        rotates it to sensor space, and ray-casts to the floor plane.  Used as a
        fallback when the model does not output polygon points.

    Args:
        wall_pred:  Roboflow prediction dict.  If it has a "points" list the
                    polygon path is used; otherwise the bbox path is used.
                    In the polygon path, points must already be in sensor space
                    (counter-rotated by the caller).  In the bbox path, x/y/w/h
                    are in Roboflow (rotated) space and counter-rotation is done
                    internally.
        H_sensor:   Height of the sensor (landscape) image in pixels.
        K_inv:      Inverse camera intrinsics matrix (3×3 ndarray).
        ray_origin: Camera position in world space (3,) ndarray.
        R:          Camera rotation matrix (3×3 ndarray).
        n:          Normalised floor-plane normal (3,) ndarray.
        p0:         Any point on the floor plane (3,) ndarray.

    Returns:
        (seam_centroid, seam_dir) — 3D point on the seam and unit direction vector.

    Raises:
        ValueError: if the seam can't be fitted or fails the floor-coplanarity check.
    """
    pts = wall_pred.get("points", [])

    if pts and len(pts) >= 3:
        # ── Polygon path ──────────────────────────────────────────────────────
        # Points are already in sensor space (counter-rotated by the caller).
        # Coordinate mapping: x_sensor = y_rf, y_sensor = H_sensor-1-x_rf.
        #
        # The seam (floor-wall junction) is the minimum x_sensor (= minimum
        # y_rf = topmost in the rotated image) within the Wall Base polygon.
        #
        # IMPORTANT: when the camera is not horizontally centred above the seam,
        # the seam appears at DIFFERENT y_rf values at different lateral (x_rf)
        # positions due to perspective.  A single global "x_sensor ≤ threshold"
        # band then either clips the seam on one side or mixes in elevated
        # baseboard pixels on the other, corrupting the fitted seam direction.
        #
        # Fix: per-column minimum.  Divide the polygon's lateral extent into
        # N_SEAM_BINS bins along x_rf (= H_sensor-1 - y_sensor), then for each
        # bin take the point(s) with the smallest x_sensor (= y_rf).  This
        # always selects the true seam edge at each lateral position regardless
        # of how the seam appears across the image.
        all_xs  = np.array([pt["x"] for pt in pts], dtype=float)   # x_sensor = y_rf
        all_ys  = np.array([pt["y"] for pt in pts], dtype=float)   # y_sensor
        all_xrf = H_sensor - 1 - all_ys                            # x_rf_original (lateral)

        xrf_span = float(all_xrf.max() - all_xrf.min())
        n_bins   = max(5, min(30, len(pts) // 4))

        if xrf_span > 1.0:
            bin_w  = xrf_span / n_bins
            xrf_lo = float(all_xrf.min())

            # ── Pass 1: per-column minimums ──────────────────────────────────
            # For each lateral bin collect the minimum x_sensor (= y_rf).
            # Larger x_sensor/y_rf = lower in the Roboflow portrait image
            # = closer to the true floor-wall seam.
            # Smaller x_sensor/y_rf = higher in image = leg/pants artifact.
            per_col_min: list[float] = []   # one entry per non-empty bin
            per_col_pts: list        = []   # (col_xs, col_ys) per bin

            for b in range(n_bins):
                blo  = xrf_lo + b * bin_w
                bhi  = xrf_lo + (b + 1) * bin_w
                # The last bin includes its right edge.
                mask = (
                    (all_xrf >= blo) &
                    (all_xrf <= bhi if b == n_bins - 1 else all_xrf < bhi)
                )
                if mask.sum() == 0:
                    continue
                col_xs = all_xs[mask]
                col_ys = all_ys[mask]
                per_col_min.append(float(col_xs.min()))
                per_col_pts.append((col_xs, col_ys))

            # ── Pass 2: leg-artifact rejection ──────────────────────────────
            # The Wall Base polygon can overlap the leg/pants silhouette in
            # the central columns.  There the per-column minimum x_sensor is
            # well BELOW (smaller y_rf = higher in the rotated image) the true
            # seam level.  Keep only bins whose minimum is ≥ the median of all
            # per-column minimums; bins below the median are leg artifacts.
            seam_px_list: list[float] = []
            seam_py_list: list[float] = []
            n_clean = 0

            if per_col_min:
                col_min_arr    = np.array(per_col_min)
                seam_threshold = float(np.percentile(col_min_arr, 50))

                for col_min, (col_xs, col_ys) in zip(per_col_min, per_col_pts):
                    if col_min < seam_threshold:
                        continue      # leg artifact — skip
                    seam_mask = col_xs <= col_min + 2.0
                    seam_px_list.extend(col_xs[seam_mask].tolist())
                    seam_py_list.extend(col_ys[seam_mask].tolist())
                    n_clean += 1

            seam_px = np.array(seam_px_list)
            seam_py = np.array(seam_py_list)
            n_total = len(per_col_min)
            path_label = (
                f"polygon per-col-robust ({len(seam_px)} seam pts / "
                f"{n_clean}/{n_total} clean bins / {len(pts)} wall pts)"
            )
        else:
            # Degenerate polygon with negligible lateral extent — global fallback.
            x_min    = float(all_xs.min())
            x_span   = float(all_xs.max()) - x_min
            seam_tol = max(8.0, x_span * 0.20)
            mask     = all_xs <= x_min + seam_tol
            seam_px  = all_xs[mask]
            seam_py  = all_ys[mask]
            n_clean  = int(mask.sum())
            n_total  = len(pts)
            path_label = (
                f"polygon global-min ({len(seam_px)}/{len(pts)} pts, "
                f"x_min={x_min:.1f}+{seam_tol:.1f}px)"
            )

        seam_3d = []
        for px, py in zip(seam_px, seam_py):
            try:
                seam_3d.append(unproject_to_plane(px, py, K_inv, ray_origin, R, n, p0))
            except ValueError:
                continue

    else:
        # ── Bbox path (legacy) ────────────────────────────────────────────────
        # Top edge of the Wall Base bbox = wall-floor seam in rotated Roboflow
        # space.  Clamp x to [0, H_sensor-1] so counter-rotated coords stay in
        # bounds.
        x_c = wall_pred["x"]
        y_c = wall_pred["y"]
        w   = wall_pred["width"]
        h   = wall_pred["height"]

        y_seam_rf  = y_c - h / 2.0
        x_left_rf  = max(0.0, x_c - w / 2.0)
        x_right_rf = min(float(H_sensor - 1), x_c + w / 2.0)

        if x_right_rf <= x_left_rf:
            raise ValueError("Wall Base bbox is entirely outside the image bounds")

        xs_rf = np.linspace(x_left_rf, x_right_rf, _SEAM_SAMPLE_COUNT)

        seam_3d = []
        for x_rf in xs_rf:
            px, py = _counter_rotate_point(x_rf, y_seam_rf, H_sensor)
            try:
                seam_3d.append(unproject_to_plane(px, py, K_inv, ray_origin, R, n, p0))
            except ValueError:
                continue

        path_label = "bbox-fallback"
        n_clean = _SEAM_SAMPLE_COUNT
        n_total = _SEAM_SAMPLE_COUNT

    if len(seam_3d) < _SEAM_MIN_INLIERS:
        raise ValueError(
            f"Wall seam underdetermined ({path_label}): "
            f"only {len(seam_3d)} valid ray-cast points"
        )

    centroid, direction = _fit_seam_line(seam_3d)

    # The seam lies in the floor plane — it must be (near-)perpendicular to the
    # floor normal.  A large dot product means the fitted line is tilting into
    # the wall rather than running along the floor.
    if abs(float(np.dot(direction, n))) > _SEAM_NORMAL_MAX_DOT:
        raise ValueError(
            f"Wall seam ({path_label}) is not coplanar with the floor — "
            "geometry is unreliable"
        )

    seam_meta = {
        "path_label":    path_label,
        "seam_3d_pts":   len(seam_3d),
        "clean_bins":    n_clean,
        "total_bins":    n_total,
    }
    return centroid, direction, seam_meta


def compute_dimensions_with_wall(foot_points_px, wall_pred, ar_snapshot,
                                 toebox_points_px=None):
    """
    Compute foot dimensions using the wall-floor seam as the heel reference.

    The heel is anchored to the seam line rather than derived from the foot
    polygon, eliminating heel-vertex jitter and heel-pad compression bias.

    Args:
        foot_points_px:    list of (x, y) pixel coords from the Roboflow foot polygon
                           (already counter-rotated to sensor space by the caller)
        wall_pred:         Roboflow "Wall Base" prediction dict (rotated/Roboflow space)
        ar_snapshot:       AR snapshot dict (same schema as compute_dimensions)
        toebox_points_px:  optional list of (x, y) pixel coords from a "Toe Box"
                           Roboflow prediction (counter-rotated to sensor space).
                           When provided, the toe reference is extended to include
                           the farthest toebox vertex, recovering the last ~1" that
                           the foot polygon often misses at the toe tip.

    Returns:
        dict with:
          length_in    — foot length in inches, using an adaptive strategy:
                           heel_gap ≥ 0 → seam-to-toe (seam used as wall anchor;
                             recovers the heel area the polygon misses near wall)
                           heel_gap < 0 → polygon span (max−min; used when the
                             seam drifted inside the foot and is unreliable)
          width_in     — 95th-percentile span parallel to wall (inches)
          area_sq_in   — shoelace area of foot polygon on floor plane (sq in)
          heel_gap_in  — distance from rearmost foot vertex to detected seam
                         (inches); negative = seam inside foot polygon
          heel_point   — 3D world coords of the rearmost foot polygon point
          toe_point    — 3D world coords of the farthest foot polygon point
          measurement_path — "wall_seam"

    Raises:
        ValueError: if fewer than 3 foot points, geometry is degenerate,
                    or wall seam fitting fails
    """
    if len(foot_points_px) < 3:
        raise ValueError("At least 3 foot polygon points are required")

    K_inv      = np.linalg.inv(np.array(ar_snapshot["camera_intrinsics"], dtype=float))
    pose       = np.array(ar_snapshot["camera_pose"], dtype=float)
    ray_origin = pose[:3, 3]
    R          = pose[:3, :3]
    n          = np.array(ar_snapshot["plane_normal"], dtype=float)
    n          = n / np.linalg.norm(n)
    p0         = np.array(ar_snapshot["plane_center"], dtype=float)
    H_sensor   = int(ar_snapshot["image_dimensions"][1])

    seam_centroid, seam_dir, seam_meta = extract_wall_seam(
        wall_pred, H_sensor, K_inv, ray_origin, R, n, p0
    )

    # u_axis points from wall toward toes (perpendicular to seam, in floor plane)
    u_axis = np.cross(seam_dir, n)
    if np.linalg.norm(u_axis) < 1e-8:
        raise ValueError("Seam direction is parallel to floor normal — degenerate geometry")
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = seam_dir   # parallel to wall

    # Ray-cast foot polygon vertices onto the floor plane
    foot_3d = np.array([
        unproject_to_plane(px, py, K_inv, ray_origin, R, n, p0)
        for px, py in foot_points_px
    ])

    # Project foot points into the wall-aligned frame
    rel    = foot_3d - seam_centroid
    u_proj = np.array([float(np.dot(r, u_axis)) for r in rel])   # + = toward toes
    v_proj = np.array([float(np.dot(r, v_axis)) for r in rel])   # parallel to wall

    # Ensure u_axis actually points toward the foot (not away from it)
    if np.median(u_proj) < 0:
        u_axis  = -u_axis
        u_proj  = -u_proj

    # --- Length: adaptive wall-anchor vs polygon-span ---
    #
    # Two failure modes exist for the wall seam:
    #
    # (A) heel_gap < 0 — seam centroid drifted INTO the foot polygon.
    #     Wall Base detection captured floor area past the real wall-floor
    #     contact, so the seam origin is unreliable.  Fix: ignore seam
    #     position and use the full polygon span (max − min) instead.
    #
    # (B) heel_gap ≥ 0 — seam is at or behind the physical wall.
    #     The polygon heel vertex doesn't reach the wall (Roboflow stops
    #     short of the heel pressed against the wall).  Fix: use the seam
    #     as the wall anchor and measure seam→toe (max(u_proj)), which
    #     recovers the missing heel distance.
    #
    # Neither mode corrects for toe underdetection (Roboflow often misses
    # the last ~1" of the toe tip).  That requires model improvement.
    toe_idx  = int(np.argmax(u_proj))
    heel_idx = int(np.argmin(u_proj))
    toe_3d   = foot_3d[toe_idx]
    heel_3d  = foot_3d[heel_idx]
    heel_gap_m = float(np.min(u_proj))

    # Extend the toe reference with the Toe Box polygon when provided.
    # The Foot polygon often undershoots the true toe tip slightly; the Toe Box
    # prediction is trained on the toe region and may capture a bit more.
    #
    # Strategy: take max(foot_polygon_toe, toebox_polygon_toe) in the u_axis
    # direction.  No polynomial extrapolation — fitting the outer tapering
    # edges of the toe box is unreliable when the coordinate frame has a high
    # seam_Z_tilt or the polygon edge points are not clean: the nearly-zero
    # slope gives a tip prediction far into the future which hits any cap and
    # inflates the length measurement.
    max_u_foot   = float(np.max(u_proj))
    toe_ext_m    = 0.0   # how far the toebox extended beyond the foot polygon
    if toebox_points_px and len(toebox_points_px) >= 3:
        try:
            toebox_3d = np.array([
                unproject_to_plane(px, py, K_inv, ray_origin, R, n, p0)
                for px, py in toebox_points_px
            ])
            tb_rel       = toebox_3d - seam_centroid
            tb_u         = np.array([float(np.dot(r, u_axis)) for r in tb_rel])
            max_u_toebox = float(np.max(tb_u))

            # Use the toebox toe if it projects further than the foot polygon.
            if max_u_toebox > max_u_foot:
                toe_ext_idx = int(np.argmax(tb_u))
                toe_3d      = toebox_3d[toe_ext_idx]
                toe_ext_m   = max_u_toebox - max_u_foot

            max_u_toe = max(max_u_foot, max_u_toebox)
        except ValueError:
            max_u_toe = max_u_foot
    else:
        max_u_toe = max_u_foot

    if 0 <= heel_gap_m <= _HEEL_GAP_SEAM_ANCHOR_MAX_M:
        # Seam is at/behind the foot AND close enough to be a credible wall
        # anchor.  The polygon heel vertex stopped short of the wall by
        # heel_gap_m; using seam-to-toe recovers that missing distance.
        # Toe extension is applied (max_u_toe includes it).
        length_m   = max_u_toe
        length_path = "wall_seam"

        # Width uses the seam-derived coordinate frame (u_proj, v_proj).
        u_proj_w  = u_proj
        v_proj_w  = v_proj
        u_min_w   = float(np.min(u_proj))
        u_max_w   = max_u_toe
        used_toe_ext = toe_ext_m

    else:
        # Either the seam drifted INSIDE the foot (heel_gap < 0, seam
        # detection overshot) or the gap is implausibly large (> 25 mm):
        # seam mis-fit, steep seam angle, or foot not flush against wall.
        #
        # In both cases the seam coordinate frame is unreliable:
        #   • length  → raw foot-polygon span (heel extreme → toe extreme),
        #               no toe extension (the toe extension was designed for
        #               the seam-anchor path; applying it here double-stacks
        #               the heel-pad overshoot + toe extension errors).
        #   • width   → re-derived from the foot polygon's own heel→toe axis
        #               so we don't inherit the wrong v_axis from the seam.
        length_path = (
            "wall_seam_gap_fallback"
            if heel_gap_m > _HEEL_GAP_SEAM_ANCHOR_MAX_M
            else "wall_seam_inside_fallback"
        )

        # Raw foot-polygon heel and toe (no toebox extension).
        raw_heel_3d = foot_3d[heel_idx]
        raw_toe_3d  = foot_3d[toe_idx]
        foot_vec    = raw_toe_3d - raw_heel_3d
        foot_dist   = float(np.linalg.norm(foot_vec))

        if foot_dist > 1e-6:
            fa = foot_vec / foot_dist               # heel→toe unit vector
            wa = np.cross(fa, n)                    # lateral width axis (floor plane)
            wa_norm = float(np.linalg.norm(wa))
            if wa_norm > 1e-6:
                wa = wa / wa_norm
            else:
                wa = v_axis                         # degenerate — keep seam lateral axis
        else:
            fa       = u_axis                       # degenerate — keep seam axes
            wa       = v_axis
            foot_dist = float(max_u_toe - np.min(u_proj))

        # Project foot polygon relative to the raw heel (not seam centroid).
        rel_fb    = foot_3d - raw_heel_3d
        u_proj_w  = np.array([float(np.dot(r, fa)) for r in rel_fb])
        v_proj_w  = np.array([float(np.dot(r, wa)) for r in rel_fb])
        u_min_w   = float(np.min(u_proj_w))         # ≈ 0 (heel is the reference)
        u_max_w   = float(np.max(u_proj_w))         # ≈ foot_dist

        length_m     = u_max_w - u_min_w            # foot-axis projection span
        used_toe_ext = 0.0                           # not applied in fallback

    # ── Width: mid-foot band (10%–85% of the length span) ────────────────────
    # Excludes the wide ankle/leg region at the heel end and the narrow
    # toe tip — the ball/arch area sits in this band and defines true width.
    u_foot_span = float(u_max_w - u_min_w)
    u_band_lo   = u_min_w + 0.10 * u_foot_span
    u_band_hi   = u_min_w + 0.85 * u_foot_span
    band_mask   = (u_proj_w >= u_band_lo) & (u_proj_w <= u_band_hi)
    mid_v_proj  = v_proj_w[band_mask] if band_mask.sum() >= 4 else v_proj_w

    n_pts      = len(mid_v_proj)
    v_sorted   = np.sort(mid_v_proj)
    lo         = v_sorted[max(0, int(n_pts * 0.025))]
    hi         = v_sorted[min(n_pts - 1, int(n_pts * 0.975))]
    width_m    = float(hi - lo)

    # Shoelace area in the seam-aligned 2D frame (informational; uses original
    # u_proj / v_proj so it remains consistent regardless of fallback path).
    all_n   = len(v_proj)
    pts_2d  = list(zip(u_proj, v_proj))
    area_m2 = abs(sum(
        pts_2d[i][0] * pts_2d[(i + 1) % all_n][1]
        - pts_2d[(i + 1) % all_n][0] * pts_2d[i][1]
        for i in range(all_n)
    )) / 2.0

    return {
        "length_in":        round(length_m   * METERS_TO_INCHES,      3),
        "width_in":         round(width_m    * METERS_TO_INCHES,      3),
        "area_sq_in":       round(area_m2    * METERS_TO_INCHES ** 2, 3),
        "heel_gap_in":      round(heel_gap_m * METERS_TO_INCHES,      3),
        "heel_point":       heel_3d.tolist(),           # 3D heel polygon extreme (debug)
        "toe_point":        toe_3d.tolist(),            # 3D toe polygon extreme (debug)
        "seam_centroid":    seam_centroid.tolist(),     # 3D wall-seam origin (debug)
        "seam_dir":         seam_dir.tolist(),          # fitted seam direction unit vector (debug)
        "u_axis":           u_axis.tolist(),            # foot-length direction (debug)
        "width_band_pts":   int(band_mask.sum()),       # polygon pts used for width (debug)
        "width_lo_in":      round(lo * METERS_TO_INCHES, 3),
        "width_hi_in":      round(hi * METERS_TO_INCHES, 3),
        "toe_ext_in":       round(used_toe_ext * METERS_TO_INCHES, 3),
        "seam_clean_bins":  seam_meta.get("clean_bins", -1),
        "seam_total_bins":  seam_meta.get("total_bins", -1),
        "measurement_path": length_path,
    }


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
