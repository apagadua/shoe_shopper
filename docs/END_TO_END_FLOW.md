# Shoe Shopper — End-to-End System Flow

> **Audience:** engineers working on the Shoe Shopper backend or frontend.
> **Scope:** the complete path from a user opening the app to receiving shoe
> recommendations, including authentication, foot measurement (paper + AR),
> the fit-scoring algorithm, the catalog/sync pipeline, and the
> (partially built) feedback-learning subsystem.
>
> This document was written by reading the source directly. Where behavior
> differs from older notes in `CLAUDE.md`, the **code** is treated as the
> source of truth and the discrepancy is called out explicitly.

---

## 1. System shape

Two independent applications communicate over a plain JSON REST API. There are
no websockets or server push; everything is request/response, and the frontend
relies on local caching to feel responsive.

```
┌──────────────────────────┐         HTTPS / JSON          ┌──────────────────────────┐
│  React Native (Expo)     │  ───────────────────────────► │  Django + DRF backend    │
│  frontend/               │  ◄─────────────────────────── │  backend/ + shoeshopper/ │
│                          │   Authorization: Token <key>  │                          │
│  - SecureStore: token    │                               │  - Roboflow (CV)         │
│  - AsyncStorage: caches  │                               │  - PostgreSQL / SQLite   │
└──────────────────────────┘                               └──────────────────────────┘
```

**Auth header format:** `Authorization: Token <key>` (DRF token auth) — **not**
`Bearer`. This is a common source of bugs.

**API mounting:** `shoeshopper/urls.py` mounts `path("api/", include("backend.api.urls"))`,
so every route below is prefixed with `/api/`.

### 1.1 The core value chain

Everything in the product serves one pipeline:

```
Photo of foot
   → CV / AR inference produces dimensions in inches
   → a Measurement row is persisted (status = complete)
   → the fit algorithm scores every active shoe against that measurement
   → a ranked, colorway-enriched recommendation list is returned
   → the frontend renders cards and caches the result
```

---

## 2. API surface

Source: `backend/api/urls.py` and `backend/api/views.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health/` | None | `{status, shoe_count}` — the frontend uses `shoe_count` as a coarse cache-bust signal. It only counts `Shoe` rows, so active-state flips, price changes, and availability changes leave it unchanged (cache can go stale) |
| GET | `/api/shoes/` | None | Full shoe list with sizes |
| POST | `/api/auth/google/` | None | Exchange a Google ID token for a DRF token key |
| DELETE | `/api/auth/delete/` | Token | Hard-delete the authenticated user (cascades) |
| GET / PATCH | `/api/profile/` | Token | Read / update display name |
| POST | `/api/foot/measure/` | **Token (required)** | Upload a foot photo → measurement in inches |
| POST | `/api/measurements/upload/` | None (AllowAny) | Simple image store, no inference (guest path) |
| GET | `/api/measurements/latest/` | Token | Latest complete measurement for the user |
| GET | `/api/recommendations/` | Token | Live-scored shoes for the user's latest measurement |
| POST | `/api/dev/mock-measurement/` | Token | Dev-only mock measurement (gated by setting) |
| GET | `/api/proxy-image/` | None | Host-restricted CDN image proxy |

> **Precision note:** `FootMeasureView` has `permission_classes = [IsAuthenticated]`.
> The "Optional" auth shown for `/api/foot/measure/` in `CLAUDE.md` is **inaccurate** —
> a token is required. `/api/measurements/upload/` is the `AllowAny` guest path.

---

## 3. Authentication flow

Google Sign-In is the only login path.

**Frontend** (`frontend/services/auth.js`):

1. `googleSignIn()` — calls `GoogleSignin.hasPlayServices()` then
   `GoogleSignin.signIn()`, returning a Google **`idToken`**. Returns `null` if
   the user cancels.
2. `signInWithGoogle(idToken)` — `POST /api/auth/google/` with body
   `{ id_token }`, returns `data.key`.
3. The caller stores `key` in `expo-secure-store` under the key `authToken`.

**Backend** (`GoogleLoginView`, `views.py`):

1. Reads `id_token`, strips whitespace, 400s if missing.
2. Builds the accepted audience list from `GOOGLE_CLIENT_ID` and
   `GOOGLE_ANDROID_CLIENT_ID` (500s if neither is configured).
3. Verifies the token with `google_id_token.verify_oauth2_token(...)`,
   `clock_skew_in_seconds=120`. On failure → 400 `Invalid ID token`
   (includes a `debug` field only when `DEBUG`).
4. Requires an `email` claim. In a single `transaction.atomic()`:
   `User.objects.get_or_create(email=...)` and, **only on first creation**, a
   `Profile` is created (display name + avatar from Google claims).
5. `Token.objects.get_or_create(user=user)` → returns `{ "key": <token> }`.

**App launch** (`frontend/App.js`): reads `authToken` from SecureStore;
routes to `MainTabs` if a token exists, otherwise `Welcome`.

> Each authenticated `fetch` attaches the `Authorization: Token <key>` header
> inline. There is no shared HTTP client / interceptor.

---

## 4. Data model — what is tracked

Source: `backend/models/__init__.py` (all models live in this single file by
project convention).

### 4.1 `Measurement` (the central record)

| Field | Notes |
|---|---|
| `user` / `guest_session` | Exactly one must be set — enforced by `CheckConstraint chk_measurement_owner` |
| `status` | `uploaded` / `processing` / `complete` / `error` |
| `length_in`, `width_in`, `area_sq_in` | Primary dimensions (DecimalField). Check constraints require `> 0` when not null |
| `toebox_length_in`, `toebox_width_in` | Finer geometry; enables higher-fidelity scoring when present |
| `measurement_method` | `paper` / `arcore` (default `paper`) |
| `paper_type` | `letter` / `a4` (null for AR) |
| `algorithm_version` | Free text (e.g. `"dev-mock"` for mocks) |

Recommendations and the "latest" endpoint always select the **most recent
`status = complete`** measurement: `order_by("-created_at").first()`.

### 4.2 Catalog models

- **`Shoe`** — `brand`, `model`, `gender`, `function_tags[]`, `style_tags[]`,
  `attributes_json`, `toe_shape`, `cap_type`, `is_active`, plus image/product
  URLs. The base catalog entity.
- **`ShoeSize`** — per-size insole geometry: `insole_length_in`,
  `insole_width_in`, `insole_area_sq_in`, `insole_toebox_length_in`,
  `insole_toebox_width_in`. **These insole dimensions are the shoe-side inputs
  to the fit algorithm.** Unique on `(shoe, us_size, width)`.
- **`ShoeColorway`** — a color variant of a base shoe (`goat_id`, name,
  `image_url`, `product_url`, `dominant_color_hex`, `color_palette_hex[]`).
- **`ShoeColorwaySize`** — live price + availability per colorway per size.

### 4.3 Other models

- **`Profile`**, **`GuestSession`**, **`UserCollection`** (wishlist/owned —
  note the frontend keeps its own copy in AsyncStorage; see §8),
  **`Recommendation`** (a table for persisted recommendation runs —
  **currently not written by the live endpoint**; see §7.3),
  **`TrainingImage`**, **`UserFeedback`**, **`ToleranceHistory`** (see §9).

---

## 5. Foot measurement — the two flows

Both flows converge on `POST /api/foot/measure/` → `FootMeasureView.post`, which
branches on the `measurement_method` form field (`"paper"` default, or
`"arcore"`). Both call **Roboflow** and persist a `complete` `Measurement`.

### 5.0 Shared frontend path

The capture screens **do not upload directly**. They navigate to the shared
`PhotoPreviewScreen` with the captured image URI and method-specific params.
`PhotoPreviewScreen.handleUsePhoto()` builds the `FormData` and performs the
upload, then navigates to `MeasurementsScreen` passing the response **via
navigation route params**.

```
CameraScreen   ─┐
                ├─►  PhotoPreviewScreen  ──►  POST /api/foot/measure/  ──►  MeasurementsScreen
ARCameraScreen ─┘     (builds FormData,            (Roboflow + math)        (route params)
                       does the upload)
```

> **Precision note — measurement persistence on the client:**
> `MeasurementsScreen` reads the result from `route.params.measurements` only.
> It does **not** write the measurement to AsyncStorage. A search of the
> frontend shows AsyncStorage writes exist only for saved shoes, owned shoes,
> and the recommendations cache. The claim in `CLAUDE.md` / memory that
> "Measurements stored in AsyncStorage as JSON after capture" is **outdated**.
> The durable copy of a measurement is the backend `Measurement` row, re-read
> on demand via `/api/measurements/latest/`.

### 5.1 Roboflow inference (shared)

`FootMeasureView._run_roboflow`:

- Requires `ROBOFLOW_WORKSPACE`, `ROBOFLOW_PROJECT`, `ROBOFLOW_API_KEY`
  (503 if any are missing).
- POSTs the base64 image to `https://serverless.roboflow.com/{ROBOFLOW_MODEL_ID}`
  with query params `api_key` and `confidence=0.25`, and a 30 s request timeout.
  `ROBOFLOW_MODEL_ID` defaults to `"{workspace}/{project}"`.
- Network/HTTP failures raise `_RoboflowError` → the view returns 502
  "Measurement service unavailable."
- Returns the flat `predictions` list. Each prediction has a `class`
  (`paper`, `foot`, `insole`, `toe box`, `wall base`), a `confidence`, a
  bounding box (`x`, `y`, `width`, `height`), and often a polygon `points` list.

### 5.2 Paper flow (`_measure_with_paper`)

**Frontend** (`CameraScreen.js`):

- Live camera with an **accelerometer tilt gate**: tilt is computed from the
  accelerometer's z-axis; capture is enabled only when tilt ≤ `10°`
  (`TILT_OK_DEGREES`). Lighting (Android `LightSensor`, threshold 50 lux) is
  **guidance only** — `canCapture = isAligned` gates on tilt alone.
- Paper-size toggle: `letter` (default) or `a4`.
- On capture → `PhotoPreviewScreen` with `method: 'paper'`, `paperSize`.

**Backend** (`_measure_with_paper`):

1. Validates upload: ≤ 10 MB, MIME in `{image/jpeg, image/png, image/webp}`
   (otherwise 400 / 415). *(These checks run in `post()` before branching.)*
2. Resolves real paper dimensions: A4 (`8.268 × 11.693"`) or Letter
   (`8.5 × 11.0"`, the default for any non-`a4` value).
3. Runs Roboflow. Finds the `paper` prediction (400 if absent).
4. **Pixels-per-inch (PPI)** from the paper bounding box
   (`_ppi_from_paper_bbox`), auto-detecting portrait vs landscape and
   averaging the two derived scales.
5. Picks the highest-confidence `foot` polygon, falling back to `insole`
   (400 if neither exists).
6. `_foot_dimensions_px` on the polygon:
   - **length** = maximum pairwise distance between polygon vertices
     (heel-to-toe).
   - **width** = perpendicular span between the 2.5th and 97.5th percentile
     projections onto the axis perpendicular to the length axis (rejects
     outlier points).
   - **area** = shoelace formula over the polygon.
   - If the polygon has < 3 points, falls back to the bbox `height`/`width`
     and an area heuristic (`length × width × 0.70`).
7. Converts px → inches by dividing by PPI. Extracts toebox dims the same way
   (`_extract_toebox`, using PPI).
8. Persists a `Measurement` (`status=complete`, `measurement_method=paper`,
   `paper_type=<used>`) and returns:
   `{id, length_in, width_in, toebox_length_in, toebox_width_in, area_sq_in,
   ppi, paper_size, measurement_method: "paper"}`.

### 5.3 AR flow (`_measure_with_ar`)

The AR path uses ARCore geometry instead of a paper scale reference. The phone
captures an `ar_snapshot` at shutter time and sends it alongside the image.

**`ar_snapshot` schema** (validated by `_validate_ar_snapshot`):

| Key | Type |
|---|---|
| `camera_intrinsics` | 3×3 matrix (focal length + principal point) |
| `camera_pose` | 4×4 world-from-camera transform |
| `plane_center` | 3-vector, a point on the detected floor plane |
| `plane_normal` | 3-vector, floor-plane normal |
| `image_dimensions` | `[width, height]` of the captured frame |
| `tracking_state` | must equal `"TRACKING"` |

**Backend pipeline** (`_measure_with_ar`):

1. `post()` first enforces: `ar_snapshot` present, raw payload ≤ 64 KB
   (guard before `json.loads`), valid JSON, and `_validate_ar_snapshot`
   passes — which includes a **hard gate that `tracking_state == "TRACKING"`**
   (only TRACKING guarantees a valid floor plane).
2. The image is rotated **90° CW** (`ROTATE_270`) before Roboflow, because
   `acquireCameraImage()` yields sensor-orientation (landscape) bytes while
   Roboflow expects portrait.
3. A debug overlay image is saved to `ar_debug/` (non-fatal best effort).
4. Predictions are **counter-rotated back to sensor space**
   (`_counter_rotate_preds`) so they align with the camera intrinsics:
   `x_sensor = y_rf`, `y_sensor = H_sensor − 1 − x_rf`.
5. **Camera-height gate:** the camera's height above the floor plane is
   computed; capture is rejected (400) unless it is within
   `12"–35"` (`_CAM_H_MIN_IN`–`_CAM_H_MAX_IN`), with a user-facing message
   tuned to "too close" vs "too far."
6. Picks foot candidates (`foot`, falling back to `insole`); 400 if none.
   Looks for a `wall base` and a `toe box` prediction.
7. Computes 3D dimensions via `backend/services/ar_measurement.py`
   (detailed in §6). Two paths:
   - **With a wall**: `compute_dimensions_with_wall` (heel anchored to the
     wall–floor seam). If multiple feet are present, `_select_foot_for_wall`
     chooses the foot whose heel gap to the seam is smallest non-negative.
   - **Without a wall**: `compute_dimensions` (pairwise max-span method, the
     same idea as paper but in 3D world space).
   - If wall fitting raises `ValueError`, it falls back to the pairwise method.
8. **Sanity gate:** final `length_in` must be within `3.0"–13.0"`
   (`FOOT_MIN_IN`–`FOOT_MAX_IN`) or it returns 400.
9. Persists a `Measurement` (`measurement_method=arcore`, `paper_type` left
   null) and returns dims plus `measurement_method: "arcore"` and
   `measurement_path`. If the heel appears not flush against the wall
   (`heel_gap_in > 0.4` and the path isn't the clean `wall_seam`), a
   `warning: "heel_not_touching_wall"` is added.

---

## 6. AR measurement math (`backend/services/ar_measurement.py`)

### 6.1 Core unprojection

`unproject_to_plane(pixel_x, pixel_y, K_inv, ray_origin, R, n, p0)` casts a ray
from the camera origin through a pixel and intersects the floor plane:

1. `ray_cam = K_inv @ [px, py, 1]` — pixel → camera-frame ray, in the OpenCV
   sensor convention (+X right, +Y down, +Z into scene).
2. Convert OpenCV → OpenGL/ARCore camera convention by negating Y and Z
   (`ray_cam[1] *= -1`, `ray_cam[2] *= -1`).
3. Rotate into world space: `ray_dir = R @ ray_cam`, normalized.
4. Ray–plane intersection: `t = dot(p0 − ray_origin, n) / dot(ray_dir, n)`.
   Raises `ValueError` if the ray is parallel to the plane (`|denom| < 1e-8`)
   or the hit is behind the camera (`t < 0`).

Constants: `METERS_TO_INCHES = 39.3701`.

### 6.2 Pairwise method (`compute_dimensions`)

Unprojects every foot polygon vertex to 3D, then:
- **length** = maximum pairwise 3D distance (heel-to-toe).
- **width** = 2.5th–97.5th percentile span perpendicular to the length axis
  (perpendicular built via cross product with the plane normal).
- **area** = shoelace over the 2D floor-plane projection.

Requires ≥ 3 points (else `ValueError`).

### 6.3 Wall-anchored method (`compute_dimensions_with_wall`)

When a `wall base` prediction exists, the wall–floor **seam** becomes the heel
reference, removing heel-polygon jitter and heel-pad compression bias.

1. `extract_wall_seam` derives a 3D seam line:
   - **Polygon path** (newer model): the seam is the topmost edge of the Wall
     Base polygon, found via a robust **per-column minimum** across lateral
     bins (handles perspective/tilt), then a leg/pants-artifact rejection pass
     (drop columns whose minimum is below the median). Surviving points are
     ray-cast to the floor and fit with PCA (`_fit_seam_line`).
   - **Bbox path** (legacy): synthesizes a horizontal scanline at the top edge
     of the bbox, counter-rotates, ray-casts.
   - Requires ≥ `_SEAM_MIN_INLIERS` (5) valid ray-cast points and rejects a
     seam that isn't coplanar with the floor
     (`|dot(seam_dir, n)| > _SEAM_NORMAL_MAX_DOT = 0.15`).
2. A wall-aligned frame is built: `u_axis` (perpendicular to seam, toward the
   toes) and `v_axis` (`= seam_dir`, parallel to the wall). `u_axis` is flipped
   if it points away from the foot.
3. **Adaptive length** based on `heel_gap_m = min(u_proj)`:
   - `0 ≤ heel_gap ≤ 0.025 m` (≈ 1") → **seam-to-toe** (`length = max_u_toe`):
     the seam is a credible wall anchor and recovers heel distance the polygon
     misses. A `toe box` polygon, if provided, can **extend** the toe reference
     to the farthest toebox vertex (`measurement_path = "wall_seam"`).
   - `heel_gap < 0` (seam drifted inside the foot) → polygon-span fallback
     (`"wall_seam_inside_fallback"`).
   - `heel_gap > 0.025 m` (implausibly large) → polygon-span fallback
     (`"wall_seam_gap_fallback"`); width is re-derived from the foot's own
     heel→toe axis rather than the seam frame.
4. **width** = 2.5th–97.5th percentile span within a mid-foot band
   (10%–85% of the length span), excluding the ankle and the toe tip.
5. **area** = shoelace in the seam-aligned frame.

Returns length/width/area in inches plus a large set of debug fields
(`heel_gap_in`, `heel_point`, `toe_point`, `seam_centroid`, `seam_dir`,
`u_axis`, band point counts, `measurement_path`).

---

## 7. Recommendations

### 7.1 Backend (`RecommendationsView.get`, `GET /api/recommendations/`)

1. Fetch the user's latest `complete` measurement (404 if none:
   "No measurements found. Scan your foot first.").
2. Build the `foot` dict: `length_in`, `width_in`, `area_sq_in`,
   `toebox_length_in`, `toebox_width_in` (passed through as-is; the algorithm
   absorbs CV uncertainty internally).
3. Optional `sub_type` query param is read and forwarded to scoring
   (the current frontend does **not** send it).
4. Load catalog efficiently:
   `Shoe.objects.prefetch_related("sizes", "colorways__sizes").filter(is_active=True)`
   — a single prefetch avoids N+1 queries.
5. For each shoe:
   - Normalize `attributes_json` (a stored list is coerced to
     `{tag: True}`).
   - Estimate the user's US size with **bias-corrected** length:
     `estimate_us_size(length_in + LENGTH_BIAS_CORRECTION, gender)`.
   - Choose the `ShoeSize` whose `us_size` is nearest the estimate; it is
     scorable only if it has both `insole_length_in` and `insole_width_in`.
   - Scorable → call `score_shoe(foot, shoe_data, sub_type)`; otherwise emit a
     synthetic `status: "UNSCORED"` fit object.
   - Compute `recommended_size`: prefer the insole-measured size nearest the
     estimate **that is also live in at least one colorway**
     (`ShoeColorwaySize.is_available`); fall back to nearest insole-measured
     size.
   - Build `colorway_options` from prefetched data (no extra queries): each
     includes `goat_id`, `sku`, `name`, `image_url`, `product_url`,
     `dominant_color_hex`, `color_palette_hex`, and sizes scoped to the
     recommended size (price/availability). Sorted images-first, then by name.
6. Sort results: scored-non-rejected first (by `total_score` desc), then
   `UNSCORED`, then `REJECTED`.
7. Serialize via `RecommendationSerializer` (flattens `{shoe, fit,
   colorway_options}` into one flat card object) and return:
   `{measurement_id, algorithm_version, has_toebox_data, results: [...]}`.

### 7.2 The fit algorithm (`backend/services/fit_algorithm.py`)

`score_shoe(foot, shoe, sub_type=None)`. Current `ALGORITHM_VERSION = "1.5"`.
Every shoe starts at 100 points; deviations subtract.

**Step 0 — CV bias correction.** Applied to the raw foot measurement before any
clearance or reject logic:
`foot_length += LENGTH_BIAS_CORRECTION (0.508")`,
`foot_width −= WIDTH_BIAS_CORRECTION (0.371")`.
*(The same length correction is applied in `RecommendationsView` when picking a
size, so estimation and scoring stay consistent.)*

**Step 1 — Profile selection.** `_get_profile_name` maps `function_tags` to one
of 14 profiles via `_TAG_ROUTES` (most-specific match first), defaulting to
`CASUAL`. Profiles are `_BASE_PROFILE` + per-profile `_DELTAS`, each defining
`{min, opt_low, opt_high, max}` clearance bands for length, width, toebox
length, and toebox width (width values are **per side**).

**Step 2 — Effective shoe dimensions (pre-processing):**
- `DRESS`: fashion allowance subtracts from length by `toe_shape`
  (round 0, almond 0.39", chisel 0.70", pointed 0.99").
- `WORK_OUTDOOR` (always) / `WORK_INDOOR` (only if `attributes_json.safety_toe`):
  safety-cap deduction per side from toebox width (steel 0.079", composite
  0.157").
- `style_tags` containing `combat` raises the length/toebox-length minimums.
- `sub_type` adjustments (e.g. `marathon`/`half_marathon` add length room,
  `thick_socks` adds width, `olympic_lifting`/`hiit` tighten, `clay_court`
  loosens, `comfort_mode` for skate).

**Step 3 — Clearances.** `c_length = eff_shoe_length − foot_length`;
`c_width = (eff_shoe_ball_width − foot_width) / 2` (per side); toebox clearances
computed only when both foot and shoe have toebox data.

**Step 4 — Hard rejects** (return `status: "REJECTED"`, score 0):
- Toebox width compression beyond `−(FOOT_WIDTH_LO / 2)`.
- Length range non-overlap (foot range widened by `FOOT_LENGTH_LO/HI`, shoe by
  `SHOE_LENGTH_LO/HI`).
- Width range non-overlap (intentionally wide window — CV width is noisy).

**Step 5 — Scoring.** `_score_dimension` is piecewise: full points inside
`[opt_low, opt_high]`; a linear ramp below `opt_low`; above `opt_high` it decays
toward a **0.70 floor at `max`** (a shoe at max clearance is still "decent"
given CV imprecision), then decays further beyond `max`. Point budgets
(`_get_points`) depend on available data:
- Full toebox → length/width/tb_len/tb_width (e.g. default 20/30/20/30).
- No toebox but area present → length/width/area.
- Neither → length/width only (default 50/50).
Area, when used, scores the `insole_area / foot_area` ratio against a lenient
band.

**Step 6 — Status thresholds:** `≥90 PERFECT`, `≥75 GOOD`, `≥60 ACCEPTABLE`,
`≥40 MARGINAL`, else `POOR`. (`REJECTED` and `UNSCORED` are separate.)

The return dict includes `total_score`, `status`, `profile_used`, `sub_type`,
`adjustments_applied`, `has_toebox_data`, `has_area_data`,
`estimated_us_size`, a per-dimension `dimensions` breakdown, and `flags`.

`estimate_us_size` uses a Brannock-style formula:
men/unisex `3 × length − 22`; women `3 × length − 20.5`; rounded to the nearest
half size.

### 7.3 Persistence caveat

Although a `Recommendation` model exists, `RecommendationsView` **computes
scores live on every request and does not write `Recommendation` rows**. The
endpoint is effectively stateless scoring.

### 7.4 Frontend (`frontend/screens/RecommendationsScreen.js`)

Caching strategy via `frontend/services/recommendationsCache.js`
(AsyncStorage key `rec_cache_v4`):

1. On focus, **render cached results immediately** if the cache holds a
   non-empty result set (`cache?.results?.length`); an empty cached set is
   treated as no usable cache and shows the loading state.
2. In parallel, fetch `/api/health/` (for `shoe_count`) and
   `/api/measurements/latest/` (for the latest `id`).
3. `isCacheStale(cache, latestMeasurementId, currentShoeCount)` returns true if
   no cache, the measurement id changed (user re-measured), **or** the total
   `Shoe` row count changed. Both signals are checked because a remeasure
   changes the id but not the count, and vice versa. (As noted in §2, the count
   is only a coarse signal — active-flips, price, and availability changes don't
   move it.)
4. If stale, fetch `/api/recommendations/`, render, and re-cache.
5. A `404` sets a "no measurement yet" state.

UI behavior:
- Client-side filtering by function/silhouette category + subcategory and
  boolean attribute filters (`attributes_json`). `REJECTED` shoes are always
  hidden, as are shoes already in the wishlist or closet.
- A horizontal **colorway carousel** per card with pie-slice color swatches
  built from `color_palette_hex` / `dominant_color_hex`.
- Converse / Demandware image URLs are rewritten to go through
  `/api/proxy-image/` (see §10).

---

## 8. Client-side state & caching

| Data | Where | Key |
|---|---|---|
| Auth token | `expo-secure-store` | `authToken` |
| Recommendations | AsyncStorage | `rec_cache_v4` |
| Saved (wishlist) shoes | AsyncStorage via `SavedShoesContext` | context's `STORAGE_KEY` |
| Owned (closet) shoes | AsyncStorage via `OwnedShoesContext` | context's `STORAGE_KEY` |
| Latest measurement | **Not cached on device** | re-read from `/api/measurements/latest/` |

> The wishlist/closet are maintained **client-side only** in AsyncStorage. The
> backend `UserCollection` model exists but is not the source of truth for the
> current UI lists.

Navigation (`frontend/App.js`): a root native-stack with `Welcome` / `Login` /
`MainTabs`. `MainTabs` is a bottom-tab navigator (Closet / Recommendations /
Profile); the Closet tab contains its own stack (Dashboard, Wishlist, Closet,
capture/measure screens, etc.). The tab bar is hidden on capture-flow screens.

---

## 9. Catalog & sync pipeline

The catalog is populated by an assisted browser-scrape pipeline (the
`/sync-shoes` skill), not a live third-party API call at request time.

```
/sync-shoes skill  →  scrapes GOAT / retailers  →  payload JSON
   →  python manage.py apply_shoe_sync --input payload.json
   →  upserts ShoeColorway + ShoeColorwaySize, sets Shoe.is_active
```

`apply_shoe_sync` status handling:
- `found_goat` / `found_retailer` → mark `Shoe.is_active = True`.
- `discontinued` → mark inactive.
- `error` → skip (leave `is_active` unchanged).

Recommendation **quality depends directly** on `ShoeSize` insole dimensions
(the shoe-side scoring inputs) and on live `ShoeColorwaySize` availability
(which drives `recommended_size` and shown prices).

---

## 10. Image proxy (`ProxyImageView`)

`GET /api/proxy-image/?url=<encoded>` exists because React Native's image loader
(Fresco on Android) does not reliably forward custom request headers, while some
CDNs (Converse / Demandware) require a browser-like `Referer`. The view:
- Accepts a URL only if it contains one of `('converse.com',
  'demandware.static')` (400 otherwise).
- Fetches it server-side with browser-like headers and streams the bytes back.

It is **intentionally host-restricted** — do not generalize it into an open
proxy.

---

## 11. Feedback & tolerance learning — built but **not yet wired**

This subsystem is designed but **not connected end-to-end**:

- Models exist: `UserFeedback` (type, severity, fit score, measurements,
  per-profile tolerances) and `ToleranceHistory`.
- `backend/services/tolerance_learning.py` computes width/length **signals**
  from severity-weighted feedback and shifts tolerance bands
  (`new_opt = opt + alpha · K · signal`, `K = 0.05`).
- `backend/services/feedback_service.py` reads feedback rows **directly from
  Supabase** (`supabase.table("user_feedback")`), bypassing the Django ORM.

However:
- There is **no feedback endpoint** in `backend/api/urls.py`.
- The frontend `frontend/screens/feedback.js` submit handler only sets a local
  `submitted` flag — it does **not** POST anywhere.
- The live fit algorithm uses the **static** profiles in `fit_algorithm.py`;
  learned tolerances are not yet fed back into scoring.

Treat this as in-progress infrastructure, not an active feedback loop.

---

## 12. End-to-end sequence (paper happy path)

```
launch (token → MainTabs)
  → Closet → FootCapture → CameraScreen (tilt ≤ 10°, pick Letter/A4)
  → PhotoPreviewScreen → POST /api/foot/measure/ {image, paper_size}
  → FootMeasureView._measure_with_paper: Roboflow → PPI → polygon → dims
       → persist Measurement(complete) → dims JSON
  → MeasurementsScreen (dims + size, from route params)
  → Recommendations tab → cache check (/health/ + /measurements/latest/)
       → if stale: GET /api/recommendations/ → score active shoes → ranked JSON
  → render cards + re-cache (rec_cache_v4)
```

**AR method** differs only in capture/measure: `ARFootCapture → ARCameraScreen`
sends `measurement_method=arcore` + `ar_snapshot`, and the backend runs the AR
unprojection math (§6) instead of the paper/PPI path. Everything from
MeasurementsScreen onward is identical.

---

## Appendix A — Key source files

| Area | File |
|---|---|
| API routing | `backend/api/urls.py`, `shoeshopper/urls.py` |
| API views | `backend/api/views.py` |
| Serializers | `backend/api/serializers.py` |
| Models | `backend/models/__init__.py` |
| Fit algorithm | `backend/services/fit_algorithm.py` |
| AR math | `backend/services/ar_measurement.py` |
| Tolerance learning | `backend/services/tolerance_learning.py`, `feedback_service.py` |
| Shoe sync | `backend/management/commands/apply_shoe_sync.py` |
| App / navigation | `frontend/App.js` |
| Auth | `frontend/services/auth.js` |
| API base URL | `frontend/config/api.js` |
| Capture screens | `frontend/screens/CameraScreen.js`, `ARCameraScreen.js`, `PhotoPreviewScreen.js` |
| Results | `frontend/screens/MeasurementsScreen.js` |
| Recommendations | `frontend/screens/RecommendationsScreen.js`, `services/recommendationsCache.js` |

## Appendix B — Discrepancies with older notes

These were found while reading the code and are corrected above:

1. **`/api/foot/measure/` auth is required, not optional.** `FootMeasureView`
   uses `IsAuthenticated`.
2. **Measurements are not persisted to AsyncStorage.** They flow via navigation
   params and are re-read from the backend; only saved shoes, owned shoes, and
   the recommendations cache use AsyncStorage.
3. **The live recommendations endpoint does not write `Recommendation` rows** —
   scoring is computed per request.
4. **The feedback/tolerance learning loop is not wired** to any endpoint or to
   live scoring.
