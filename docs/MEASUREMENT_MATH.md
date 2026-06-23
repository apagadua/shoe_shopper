# Shoe Shopper — Measurement Math

> **Audience:** engineers working on the foot-measurement pipeline.
> **Scope:** the geometry that turns Roboflow pixel detections into real-world
> foot dimensions (inches) — the **paper** (pixels-per-inch) method and the
> **AR** (ray-cast-to-floor) method. Request plumbing is in
> [`END_TO_END_FLOW.md`](./END_TO_END_FLOW.md) §5–6; this doc is the math only.
>
> Written by reading the source. Symbols below match the code so you can map
> each formula back to its function.

---

## 1. Overview

Both methods produce the same outputs — `length_in`, `width_in`, `area_sq_in`
(plus optional toebox dims) — but bridge "pixels → inches" differently:

| Method | Scale reference | Core idea | Code |
|---|---|---|---|
| **Paper** | A sheet of Letter/A4 paper of known size | Detect the paper's pixel size → **pixels-per-inch**; divide foot pixels by it | `backend/api/views.py` |
| **AR** | The ARCore floor plane + camera pose/intrinsics | Cast a ray through each foot pixel, intersect the floor → real 3D coordinates | `backend/services/ar_measurement.py` |

A third path, **manual entry** (`ManualMeasurementScreen`), has the user type
length/width/toebox directly — no CV. Its only computation is the area, derived
with the same heuristic as the paper bbox fallback (§3.4):
`area = length × width × 0.70`. Note: this screen only navigates to
`Measurements` with route params — it does **not** persist a backend
`Measurement`, so `GET /api/recommendations/` (which reads the latest *complete*
`Measurement`) will not use a manually entered value.

> Downstream, the fit algorithm applies **CV bias corrections**
> (`+0.508"` length, `−0.371"` width) and a Brannock size estimate. Those are
> *scoring/sizing* math, not measurement, and live in `fit_algorithm.py`
> (see `END_TO_END_FLOW.md` §7.2). The raw measurement is stored uncorrected.

---

## 2. Coordinate conventions

Two pixel frames and two 3D frames are in play; mixing them up is the most
common source of AR bugs.

- **Sensor / OpenCV image frame** — `+X` right, `+Y` down, `+Z` into the scene.
  Roboflow detections and the camera intrinsics `K` live here.
- **OpenGL / ARCore camera frame** — `+X` right, `+Y` up, `−Z` into the scene.
  The ARCore `camera_pose` (world-from-camera) lives here.

**Image rotation (AR only):** the phone delivers sensor bytes that are
landscape when held portrait, so the backend rotates the image **90° CW**
(`ROTATE_270`) before Roboflow. Predictions then come back in that rotated
space and are **counter-rotated** back to sensor space before any 3D math:

```
x_sensor = y_rf
y_sensor = H_sensor − 1 − x_rf        (H_sensor = sensor image height)
```

The paper method sends the image unrotated and never needs this.

---

## 3. Paper method (`backend/api/views.py`)

### 3.1 Pixels-per-inch — `_ppi_from_paper_bbox`

Given the paper detection's bounding box `(w, h)` in pixels and the real paper
dimensions `short_in`, `long_in` (Letter `8.5 × 11.0"`; A4 `8.268 × 11.693"`),
orientation is inferred from the box aspect and PPI is the **average** of the
two derived scales:

```
portrait  (w ≤ h):  ppi = (w / short_in + h / long_in) / 2
landscape (w > h):  ppi = (w / long_in  + h / short_in) / 2
```

Averaging both edges reduces error from a slightly skewed or imperfectly
detected box. Returns `None` (→ 400) if either dimension is zero.

### 3.2 Foot length & width — `_foot_dimensions_px`

Given the foot polygon vertices `points`:

**Length** = the largest distance between any two vertices (heel-to-toe),
found by brute-force pairwise scan:

```
length_px = max over i<j of  hypot(xj − xi, yj − yi)
```

**Width** = the spread perpendicular to the length axis. Let `(dx, dy)` be the
heel→toe vector and its unit perpendicular `p = (−dy, dx) / |(dx,dy)|`. Project
every vertex onto `p`, sort, and take the **central-95% span** (2.5th to 97.5th
percentile by nearest-rank index):

```
projs = sorted( xk·px + yk·py  for each vertex k )
lo = projs[ int(n · 0.025) ]
hi = projs[ int(n · 0.975) ]
width_px = hi − lo
```

The percentile clipping discards a few stray polygon points that sit just
outside the true foot edge. (The code comment calls this "95th-percentile"; it
is the central 95% inter-percentile range.)

### 3.3 Area — shoelace

Polygon area in pixels via the shoelace formula, then scaled by `ppi²`:

```
area_px    = ½ · | Σ (xi·y_{i+1} − x_{i+1}·yi) |      (indices mod n)
area_sq_in = area_px / ppi²
```

### 3.4 Pixels → inches & the small-polygon fallback

`length_in = length_px / ppi`, `width_in = width_px / ppi`. Toebox dims use the
same `_foot_dimensions_px` on the `Toe Box` polygon.

If the foot polygon has **< 3 points**, the code falls back to the detection's
bbox `height`/`width` and an area heuristic:

```
length_in = bbox_height / ppi
width_in  = bbox_width  / ppi
area_sq_in = length_in · width_in · 0.70      (0.70 ≈ foot-fill of its bbox)
```

---

## 4. AR method (`backend/services/ar_measurement.py`)

### 4.1 Ray–plane unprojection — `unproject_to_plane` (the core)

This maps one pixel to a 3D point on the floor. Inputs are precomputed once per
frame: `K_inv` (inverse intrinsics), the camera world position `ray_origin` and
rotation `R` (from `camera_pose`), the unit floor normal `n`, and a floor point
`p0`.

```
1.  ray_cam = K_inv · [px, py, 1]          # pixel → camera-frame ray (OpenCV)
2.  ray_cam.y = −ray_cam.y                  # OpenCV → OpenGL: flip Y
    ray_cam.z = −ray_cam.z                  #               : flip Z
3.  ray_dir = normalize( R · ray_cam )      # rotate into world space
4.  denom = ray_dir · n
    if |denom| < 1e-8: raise               # ray parallel to floor
    t = (p0 − ray_origin) · n / denom
    if t < 0: raise                         # intersection behind camera
5.  hit = ray_origin + t · ray_dir          # 3D world point on the floor
```

Step 2 is the convention bridge from §2; getting it wrong tilts every result.

### 4.2 Camera-height gate (`views.py`, pre-check)

Before measuring, the camera's height above the floor is computed and used as a
quality gate:

```
cam_height_m  = (camera_position − p0) · n
cam_height_in = cam_height_m · 39.3701
reject (400) unless 12" ≤ cam_height_in ≤ 35"
```

Too high amplifies any sub-pixel detection error into a large floor distance;
too low destabilizes the plane fit.

### 4.3 Pairwise method — `compute_dimensions` (no wall)

Unproject every foot vertex to 3D (`world_points`), then mirror the paper logic
in 3D:

- **Length** = max pairwise 3D distance; the two extreme points define the
  length axis `a = normalize(p2 − p1)`.
- **Width** = central-95% span (2.5th–97.5th percentile) along the in-plane
  perpendicular `perp = normalize(a × n)`.
- **Area** = shoelace over the points projected into the 2D `(a, perp)` frame.

Multiply lengths by `39.3701` (`METERS_TO_INCHES`) for inches. Requires ≥ 3
points.

### 4.4 Wall-anchored method — `compute_dimensions_with_wall`

When a `Wall Base` is detected, the wall–floor **seam** is used as the heel
reference, which removes heel-polygon jitter and heel-pad compression.

**(a) Seam line — `extract_wall_seam`.** Build a set of seam pixels, ray-cast
them to the floor, and fit a 3D line by **PCA** (`_fit_seam_line`: the first
singular vector of the mean-centered points is the seam direction). Two ways to
get the seam pixels:

- *Polygon path* (newer model): split the Wall Base polygon's lateral extent
  into bins; per bin take the **topmost** edge point (the floor-wall junction),
  then drop bins whose minimum is below the median (leg/pants artifacts).
  Per-column minima handle a seam that appears diagonal under perspective/tilt —
  a single global threshold would mix floor and baseboard pixels.
- *Bbox path* (legacy): sample a horizontal scanline along the bbox top edge.

Validity: ≥ `_SEAM_MIN_INLIERS` (5) ray-cast points, and the seam must be
**coplanar with the floor** — rejected if `|seam_dir · n| > 0.15` (≈ 9°).

**(b) Wall-aligned frame.** With seam centroid `c` and direction `seam_dir`:

```
u_axis = normalize(seam_dir × n)    # points toward the toes (flipped if needed)
v_axis = seam_dir                   # runs parallel to the wall
```

Project each foot point relative to `c`: `u = (point − c)·u_axis` (distance from
wall), `v = (point − c)·v_axis` (lateral).

**(c) Adaptive length.** Let `heel_gap = min(u)` (signed distance from the seam
to the rearmost foot vertex). With `0.025 m ≈ 1"` as the threshold:

| `heel_gap` | Path | Length |
|---|---|---|
| `0 ≤ gap ≤ 0.025 m` | `wall_seam` | seam→toe = `max(u)`; a `Toe Box` polygon may **extend** the toe to its farthest vertex |
| `gap < 0` (seam inside foot) | `wall_seam_inside_fallback` | raw foot-polygon span (heel vertex → toe vertex) |
| `gap > 0.025 m` (implausible) | `wall_seam_gap_fallback` | raw foot-polygon span (heel vertex → toe vertex) |

Both fallback paths share the same code branch: length is the raw foot-polygon
span (no toebox extension), and **width is re-derived from the foot's own
heel→toe axis** rather than the seam frame, so a mis-fit seam doesn't corrupt the
lateral axis. The seam-anchor path (top row) recovers heel length the polygon
misses when the heel is pressed against the wall; the fallbacks avoid inflating
length when the seam fit is unreliable.

**(d) Width** = central-95% span of `v`, but only over a **mid-foot band**
(`u` between 10% and 85% of the length span) to exclude the wide ankle and the
narrow toe tip.

**(e) Area** = shoelace in the seam-aligned `(u, v)` frame.

After computing, a **sanity gate** in `views.py` rejects (400) any
`length_in` outside `3.0"–13.0"`.

---

## 5. Validation gates (numeric summary)

| Gate | Method | Rule |
|---|---|---|
| Tracking state | AR | must be `"TRACKING"` |
| `ar_snapshot` size | AR | ≤ 64 KB before `json.loads` |
| Camera height | AR | `12" ≤ h ≤ 35"` |
| Seam inliers | AR (wall) | ≥ 5 valid ray-cast points |
| Seam coplanarity | AR (wall) | `|seam_dir · n| ≤ 0.15` |
| Heel-gap anchor window | AR (wall) | `0 ≤ gap ≤ 0.025 m` selects seam→toe |
| Foot length sanity | AR | `3.0" ≤ length ≤ 13.0"` |
| Paper present | Paper | a `paper` detection is required |
| Polygon size | both | < 3 points → bbox fallback (paper) / `ValueError` (AR) |
| Upload | both | ≤ 10 MB, MIME ∈ {jpeg, png, webp} |

---

## 6. Constants

| Symbol | Value | Meaning |
|---|---|---|
| `METERS_TO_INCHES` | `39.3701` | metre → inch |
| Letter | `8.5 × 11.0"` | paper short × long |
| A4 | `210/25.4 × 297/25.4` ≈ `8.268 × 11.693"` | paper short × long |
| width percentile | `0.025 / 0.975` | central-95% span (both methods) |
| width mid-band | `10% – 85%` of length span | wall-method width region |
| `_SEAM_MIN_INLIERS` | `5` | min seam ray-cast points |
| `_SEAM_NORMAL_MAX_DOT` | `0.15` | seam–floor coplanarity limit |
| `_HEEL_GAP_SEAM_ANCHOR_MAX_M` | `0.025` (≈ 1") | heel-gap anchor window |
| bbox area fill | `0.70` | foot fraction of its bbox (paper fallback) |
| camera-height window | `12" – 35"` | AR capture gate |
| foot-length sanity | `3.0" – 13.0"` | AR result gate |

---

## Appendix A — Key files

| Area | File / function |
|---|---|
| Paper PPI | `backend/api/views.py` · `_ppi_from_paper_bbox` |
| Paper foot dims | `backend/api/views.py` · `_foot_dimensions_px`, `_pts`, `_extract_toebox` |
| AR counter-rotation | `backend/api/views.py` · `_counter_rotate_preds` |
| AR unprojection | `backend/services/ar_measurement.py` · `unproject_to_plane` |
| AR pairwise dims | `…/ar_measurement.py` · `compute_dimensions` |
| AR wall method | `…/ar_measurement.py` · `compute_dimensions_with_wall`, `extract_wall_seam`, `_fit_seam_line` |

## Appendix B — Notes & caveats

1. **Width is an inter-percentile span, not a true ball width.** Both methods
   take the central-95% lateral spread of the polygon; the code comment's
   "95th-percentile" wording refers to this central-95% range.
2. **Length tends to under-detect the toe.** Roboflow often stops ~1" short of
   the toe tip; the wall method's optional Toe Box extension partially
   compensates, but neither method fully corrects it — that needs model work.
3. **Stored measurements are raw.** CV bias correction and Brannock sizing are
   applied later in scoring, not at measurement time.
4. **Area is informational.** It is computed and stored but contributes to fit
   scoring only when toebox data is absent (see `END_TO_END_FLOW.md` §7.2).
