# ARCore Foot Measurement — Implementation Plan

> **Status (June 2026):** AR measurement is **implemented on `main`**. `FootCaptureScreen` offers AR as the primary path and paper as secondary; `ARCameraScreen` uploads to `/api/foot/measure/` with `measurement_method: arcore`. This document remains the design reference for the AR snapshot approach.

Experimental branch to test ARCore-based foot measurement as an alternative to the paper-based method. Goal: compare usability, speed, and accuracy side-by-side to decide if AR replaces paper, supplements it, or gets cut.

---

## Why This Branch Exists

The current paper method works and is accurate (~1% error), but requires the user to find a sheet of printer paper every time. ARCore could eliminate that friction — at the cost of device compatibility (~75% of Android), accuracy uncertainty (~2-5% error depending on conditions), and significant dev effort. This branch exists to **measure the tradeoff**, not to ship AR as the default.

---

## How It Works (The "AR Snapshot" Approach)

The core challenge: Roboflow runs server-side and returns foot endpoint coordinates seconds after capture. But ARCore's 3D plane/depth data is ephemeral — it lives only in the live AR session. We solve this by caching the AR context at capture time.

### Flow

```
1. User opens AR Camera screen
2. ARCore initializes → detects floor plane (2-4 seconds)
3. User positions foot on detected floor (no paper needed)
4. Phone guides: "Floor detected. Hold steady."
5. User taps capture →
   a. Save photo (same as today)
   b. Save AR snapshot: camera intrinsics matrix, camera extrinsics (pose),
      floor plane equation (ax + by + cz + d = 0)
6. Photo uploads to Roboflow (same /api/foot/measure/ endpoint)
7. Roboflow returns 2D pixel coordinates of foot endpoints
8. Backend unprojects 2D points → 3D world coordinates using cached AR data
9. Backend computes real-world distance between 3D points → measurements in inches
```

### What "AR Snapshot" Contains

Captured once at the moment the shutter fires — all from the same ARCore frame:

| Field | Type | Purpose |
|---|---|---|
| `camera_intrinsics` | 3x3 float matrix | Focal length + principal point — maps pixels ↔ camera rays |
| `camera_pose` | 4x4 float matrix | Camera position + orientation in world space |
| `plane_center` | `[x, y, z]` | Center point of the detected floor plane |
| `plane_normal` | `[x, y, z]` | Normal vector of the floor plane |
| `plane_extent_x` | float | How far the plane extends (confidence indicator) |
| `plane_extent_z` | float | Same, other axis |
| `tracking_state` | string | `TRACKING` / `PAUSED` / `STOPPED` — gate capture on `TRACKING` |
| `image_dimensions` | `[width, height]` | Resolution of the captured frame |

### The Math (Backend Unprojection)

```
Given:
  - 2D pixel point (px, py) from Roboflow
  - Camera intrinsics K (3x3)
  - Camera pose M (4x4, world-from-camera)
  - Floor plane (normal n, point p0)

Step 1: Pixel → camera ray
  ray_cam = K_inv * [px, py, 1]

Step 2: Camera ray → world ray
  ray_origin = M * [0, 0, 0, 1]  (camera position in world)
  ray_dir = M_rot * ray_cam       (ray direction in world)

Step 3: Ray-plane intersection
  t = dot(p0 - ray_origin, n) / dot(ray_dir, n)
  world_point = ray_origin + t * ray_dir

Step 4: Distance between two world points
  distance = ||world_point_heel - world_point_toe||
```

This gives real-world distance in meters (ARCore's native unit), which we convert to inches.

---

## What Changes vs Current Flow

### What Stays the Same
- Roboflow still does object detection (foot endpoints, toebox)
- Backend still receives a photo + returns measurements
- `Measurement` model unchanged
- `MeasurementsScreen` unchanged
- Recommendations flow unchanged
- Auth, navigation structure unchanged

### What Changes

| Component | Current (Paper) | New (AR) |
|---|---|---|
| Scale reference | Paper dimensions (known physical size) | ARCore floor plane (device depth estimation) |
| PPI calculation | `paper_bbox_pixels / paper_inches` | Not needed — direct 3D unprojection |
| Camera screen | `expo-camera` + accelerometer overlay | ARCore session + plane visualization overlay |
| Backend input | `image` + `paper_size` | `image` + `ar_snapshot` JSON |
| Backend math | `foot_pixels / ppi = inches` | Ray-plane intersection → 3D distance |
| Device requirement | Any camera | ARCore-supported Android |
| User prep | Place foot on paper | Just stand on floor |

---

## New Files

### Frontend

| File | Purpose |
|---|---|
| `frontend/screens/ARCameraScreen.js` | AR measurement camera screen (parallel to `CameraScreen.js`) |
| `frontend/screens/ARFootCaptureScreen.js` | Instructions screen for AR flow (parallel to `FootCaptureScreen.js`) |
| `frontend/native/ARCoreModule.java` | Native Android module exposing ARCore to JS |
| `frontend/native/ARCoreViewManager.java` | Native ViewManager to render ARCore camera preview in React Native |
| `frontend/native/ARCorePackage.java` | React Native package registration (registers both module + view manager) |
| `frontend/plugins/withARCore.js` | Expo config plugin to wire up native module + ARCore deps |

### Backend

| File | Purpose |
|---|---|
| `backend/services/ar_measurement.py` | Unprojection math: AR snapshot + 2D points → 3D measurements |

### Modified Files

| File | Change |
|---|---|
| `frontend/App.js` | AR screen routes added to Closet stack and root stack (done) |
| `frontend/screens/FootCaptureScreen.js` | AR vs paper method chooser (implemented — AR is the primary path) |
| `frontend/app.json` | Add `withARCore` config plugin |
| `frontend/package.json` | Add ARCore-related dependencies |
| `backend/api/views.py` | `FootMeasureView.post()` — detect `ar_snapshot` in request, branch to AR math |
| `backend/api/urls.py` | No change — same `/api/foot/measure/` endpoint |

---

## Frontend Implementation

### Native Module: `ARCoreModule`

Two native Java components:

**`ARCoreModule.java`** (NativeModule) — headless logic:

1. **Checks availability** — Returns `supported`, `supported_not_installed`, or `unsupported`
2. **Starts an AR session** — Creates an `ArSession` with plane detection enabled
3. **Streams plane state to JS** — Emits events: `onPlaneDetected`, `onTrackingStateChanged`
4. **Captures AR snapshot** — On demand, returns the camera intrinsics, pose, and best floor plane as a JSON object
5. **Captures frame image** — Returns the camera frame as a JPEG
6. **Manages session lifecycle** — Pauses session on `onHostPause`, resumes on `onHostResume`, destroys on `onHostDestroy` (implements `LifecycleEventListener`)

**`ARCoreViewManager.java`** (SimpleViewManager) — renders the AR camera preview:

1. Wraps an Android `GLSurfaceView` that ARCore renders into
2. Exposes it as a `<ARCorePreview />` React Native component
3. Overlays are pure React Native views positioned absolutely on top

#### Option A: ARCore handles both camera + AR (cleaner)
ARCore owns the camera session. We render the AR camera preview in a native view and overlay React Native UI on top. The capture returns both the image and the AR snapshot atomically from the same frame.

#### Option B: expo-camera for image, ARCore for 3D data (safer)
Keep `expo-camera` for the photo (proven, already working). Run ARCore in parallel for plane detection + snapshot. Risk: the two cameras may fight for the hardware camera resource.

**Recommendation: Option A.** ARCore needs exclusive camera access anyway. Fighting over the camera between two systems is a reliability nightmare. ARCore gives us both the image and the 3D data from the exact same frame — no sync issues.

### Config Plugin: `withARCore.js`

Expo config plugin that modifies the Android build to:

1. Add `com.google.ar:core:1.44+` to `build.gradle` dependencies (use latest stable; minimum 1.40)
2. Add `<uses-feature android:name="android.hardware.camera.ar" android:required="false" />` to `AndroidManifest.xml` (required="false" so the app still installs on non-AR devices)
3. Add `<meta-data android:name="com.google.ar.core" android:value="optional" />` to manifest (allows graceful fallback)
4. Register the native module package in `MainApplication.java`

### ARCameraScreen.js

New screen, parallel to the existing `CameraScreen.js`. Key differences:

```
Phases: 'initializing' → 'scanning' → 'ready' → 'preview' → 'processing'

'initializing': Check ARCore availability. If not supported, show message
                + button to fall back to paper method.

'scanning':     ARCore is running, looking for a floor plane.
                Show camera preview with animated scanning indicator.
                "Point your phone at the floor and move slightly"

'ready':        Floor plane detected and tracking state is TRACKING.
                Show camera preview with floor plane highlighted (subtle overlay).
                "Place your foot on the highlighted area"
                Capture button enabled.
                Tilt detection (reuse accelerometer logic from CameraScreen).

'preview':      Same as current CameraScreen preview phase.
                Show captured image, "Use this photo" / "Retake" buttons.

'processing':   Same as current — spinner while Roboflow processes.
```

#### AR Availability Check

```javascript
// Pseudocode — actual API depends on native module design
const arAvailable = await ARCoreModule.checkAvailability();
// Returns: 'supported' | 'supported_not_installed' | 'unsupported'

if (arAvailable === 'supported_not_installed') {
  // Prompt user to install ARCore (Google Play Services for AR)
  await ARCoreModule.requestInstall();
}

if (arAvailable === 'unsupported') {
  // Show fallback UI → navigate to paper CameraScreen
}
```

#### Capture Flow

```javascript
const handleCapture = async () => {
  const snapshot = await ARCoreModule.captureSnapshot();
  // snapshot = {
  //   imageUri: 'file:///...',
  //   cameraIntrinsics: [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
  //   cameraPose: [[...], [...], [...], [...]],  // 4x4
  //   planeCenter: [x, y, z],
  //   planeNormal: [x, y, z],
  //   planeExtentX: 1.2,
  //   planeExtentZ: 0.8,
  //   trackingState: 'TRACKING',
  //   imageDimensions: [1920, 1080],
  // }

  if (snapshot.trackingState !== 'TRACKING') {
    setError('Lost tracking. Hold phone steady and try again.');
    return;
  }

  setCapturedUri(snapshot.imageUri);
  setArSnapshot(snapshot);
  setPhase('preview');
};
```

#### Upload (modified handleUsePhoto)

```javascript
const handleUsePhoto = async () => {
  setPhase('processing');
  const formData = new FormData();
  formData.append('image', { uri: capturedUri, name: 'foot.jpg', type: 'image/jpeg' });
  formData.append('measurement_method', 'arcore');
  formData.append('ar_snapshot', JSON.stringify({
    camera_intrinsics: arSnapshot.cameraIntrinsics,
    camera_pose: arSnapshot.cameraPose,
    plane_center: arSnapshot.planeCenter,
    plane_normal: arSnapshot.planeNormal,
    plane_extent_x: arSnapshot.planeExtentX,
    plane_extent_z: arSnapshot.planeExtentZ,
    image_dimensions: arSnapshot.imageDimensions,
  }));

  const token = await SecureStore.getItemAsync('authToken');
  const response = await fetch(`${API_BASE_URL}/api/foot/measure/`, {
    method: 'POST',
    headers: { Authorization: `Token ${token}` },
    body: formData,
  });
  // ... same error handling and navigation as current
};
```

### ARFootCaptureScreen.js

Instructions screen parallel to `FootCaptureScreen.js`, but with AR-specific guidance:

- "Stand on a flat, well-lit floor"
- "No paper needed"
- "Wear a light, fitted sock"
- "Your phone will scan the floor first — move it slightly until the surface is detected"
- Button: "Open AR Camera"

---

## Backend Implementation

### Modified: `FootMeasureView.post()` in `views.py`

The existing endpoint branches based on whether `ar_snapshot` is present:

```python
def post(self, request):
    image_file = request.FILES.get("image")
    # ... existing validation ...

    measurement_method = request.data.get("measurement_method", "paper")

    if measurement_method == "arcore":
        ar_snapshot_raw = request.data.get("ar_snapshot")
        if not ar_snapshot_raw:
            return Response({"detail": "ar_snapshot required for ARCore method"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            ar_snapshot = json.loads(ar_snapshot_raw)
        except (json.JSONDecodeError, TypeError):
            return Response({"detail": "ar_snapshot must be valid JSON"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate ar_snapshot schema before passing to numpy
        error = _validate_ar_snapshot(ar_snapshot)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return self._measure_with_ar(request, image_file, ar_snapshot)
    else:
        return self._measure_with_paper(request, image_file)


def _validate_ar_snapshot(snapshot):
    """
    Validate that ar_snapshot has the expected structure before passing
    to numpy. Returns an error string, or None if valid.
    """
    required = {
        "camera_intrinsics": (list, 3),   # 3x3
        "camera_pose": (list, 4),         # 4x4
        "plane_center": (list, 3),        # [x, y, z]
        "plane_normal": (list, 3),        # [x, y, z]
        "image_dimensions": (list, 2),    # [w, h]
    }
    for key, (typ, length) in required.items():
        val = snapshot.get(key)
        if not isinstance(val, typ) or len(val) != length:
            return f"ar_snapshot.{key} must be a {typ.__name__} of length {length}"
    # Verify nested dimensions for matrices
    for row in snapshot["camera_intrinsics"]:
        if not isinstance(row, list) or len(row) != 3:
            return "camera_intrinsics must be a 3x3 matrix"
    for row in snapshot["camera_pose"]:
        if not isinstance(row, list) or len(row) != 4:
            return "camera_pose must be a 4x4 matrix"
    # Verify all values are numeric
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
    return None
```

`_measure_with_paper()` = current logic, extracted into a method.

`_measure_with_ar()`:
1. Send image to Roboflow (same as today)
2. Get foot polygon endpoints (same as today)
3. Instead of PPI calculation, call `ar_measurement.compute_dimensions()`
4. Create `Measurement` with `measurement_method='arcore'`

### New: `backend/services/ar_measurement.py`

```python
import numpy as np

def unproject_to_plane(pixel_x, pixel_y, intrinsics, camera_pose, plane_normal, plane_point):
    """
    Unproject a 2D pixel coordinate onto a 3D plane using AR camera data.

    Args:
        pixel_x, pixel_y: 2D image coordinates from Roboflow
        intrinsics: 3x3 camera intrinsics matrix
        camera_pose: 4x4 world-from-camera transform
        plane_normal: [nx, ny, nz] floor plane normal
        plane_point: [px, py, pz] point on the floor plane

    Returns:
        [x, y, z] world coordinate where the ray hits the plane
    """
    K_inv = np.linalg.inv(np.array(intrinsics))
    ray_cam = K_inv @ np.array([pixel_x, pixel_y, 1.0])

    pose = np.array(camera_pose)
    ray_origin = pose[:3, 3]
    ray_dir = pose[:3, :3] @ ray_cam
    ray_dir = ray_dir / np.linalg.norm(ray_dir)

    n = np.array(plane_normal)
    p0 = np.array(plane_point)

    denom = np.dot(ray_dir, n)
    if abs(denom) < 1e-8:
        raise ValueError("Ray is parallel to plane — cannot intersect")

    t = np.dot(p0 - ray_origin, n) / denom
    if t < 0:
        raise ValueError("Intersection is behind the camera")

    return ray_origin + t * ray_dir


def compute_dimensions(foot_points_px, ar_snapshot):
    """
    Compute foot dimensions in inches from 2D Roboflow points + AR snapshot.

    Uses the same heel-to-toe and perpendicular-width logic as the paper method,
    but in 3D world space instead of 2D pixel space.

    Args:
        foot_points_px: list of (x, y) pixel coordinates from Roboflow polygon
        ar_snapshot: dict with camera_intrinsics, camera_pose, plane_center, plane_normal

    Returns:
        dict with length_in, width_in, area_sq_in
    """
    intrinsics = ar_snapshot["camera_intrinsics"]
    camera_pose = ar_snapshot["camera_pose"]
    plane_normal = ar_snapshot["plane_normal"]
    plane_point = ar_snapshot["plane_center"]

    # Unproject all foot polygon points onto the floor plane
    world_points = []
    for px, py in foot_points_px:
        wp = unproject_to_plane(px, py, intrinsics, camera_pose, plane_normal, plane_point)
        world_points.append(wp)

    world_points = np.array(world_points)

    # Length: max distance between any two points (heel to toe)
    max_dist = 0
    p1_idx, p2_idx = 0, 1
    for i in range(len(world_points)):
        for j in range(i + 1, len(world_points)):
            d = np.linalg.norm(world_points[j] - world_points[i])
            if d > max_dist:
                max_dist = d
                p1_idx, p2_idx = i, j

    length_m = max_dist

    # Width: 95th percentile perpendicular span (same logic as _foot_dimensions_px)
    axis = world_points[p2_idx] - world_points[p1_idx]
    axis_norm = axis / np.linalg.norm(axis)

    # Project onto plane's 2D coordinate system for perpendicular calculation
    # Use cross product of axis and plane normal to get perpendicular direction
    perp = np.cross(axis_norm, np.array(plane_normal))
    perp = perp / np.linalg.norm(perp)

    projs = sorted(np.dot(world_points, perp))
    n = len(projs)
    lo = projs[max(0, int(n * 0.025))]
    hi = projs[min(n - 1, int(n * 0.975))]
    width_m = hi - lo

    # Area via shoelace on the 2D plane projection
    # Project world points onto the floor plane's 2D basis
    u_axis = axis_norm
    v_axis = perp
    pts_2d = [(np.dot(wp, u_axis), np.dot(wp, v_axis)) for wp in world_points]
    n_pts = len(pts_2d)
    area_m2 = abs(sum(
        pts_2d[i][0] * pts_2d[(i + 1) % n_pts][1]
        - pts_2d[(i + 1) % n_pts][0] * pts_2d[i][1]
        for i in range(n_pts)
    )) / 2

    METERS_TO_INCHES = 39.3701

    return {
        "length_in": round(length_m * METERS_TO_INCHES, 3),
        "width_in": round(width_m * METERS_TO_INCHES, 3),
        "area_sq_in": round(area_m2 * METERS_TO_INCHES ** 2, 3),
    }
```

### Measurement Model Addition

Add `measurement_method` field to `Measurement`:

```python
class MeasurementMethod(models.TextChoices):
    PAPER = "paper", "Paper"
    ARCORE = "arcore", "ARCore"

measurement_method = models.CharField(
    max_length=10,
    choices=MeasurementMethod.choices,
    default=MeasurementMethod.PAPER,
)
```

This lets us query and compare accuracy by method later.

---

## Navigation: How the User Chooses

Entry is **`Dashboard` → Update Measurements** or **`FootCaptureScreen`** (implemented):

```
FootCaptureScreen
├── "Measure with AR"    → ARFootCaptureScreen → ARCameraScreen
└── "Paper method"       → CameraScreen (or gallery pick)
```

Both flows end at the same `MeasurementsScreen` with the same data shape. The user doesn't need to know the difference after capture.

If ARCore is not available on the device, the "Measure with AR" button either:
- Doesn't appear (check on screen mount via `ARCoreModule.checkAvailability()`)
- Shows but navigates to a "Not supported on this device" screen with a link to the paper method

---

## A/B Comparison Plan

### What We're Measuring

| Metric | How to Measure |
|---|---|
| **Accuracy** | Same person measures with both methods. Compare `length_in` and `width_in` between paper and AR measurements. |
| **Consistency** | Same person, same foot, 5 measurements each method. Compare standard deviation. |
| **Speed** | Time from screen open to measurement result (can log timestamps on frontend). |
| **Success rate** | % of attempts that produce a measurement vs error/abort. |
| **Device coverage** | % of test devices that support ARCore. |
| **User preference** | Which method users choose when given the option. |

### Test Protocol

1. Recruit 5-10 testers with ARCore-compatible Android devices
2. Each tester measures the same foot 3x with paper, 3x with AR
3. Compare mean and std dev of `length_in` and `width_in` across methods
4. Record qualitative feedback: which felt easier? Which would they use again?
5. Bonus: measure a known object (ruler, credit card) with both methods to establish ground truth error

### Success Criteria

AR replaces paper as default if:
- Mean error within 2% of paper method
- Std dev within 1.5x of paper method
- Success rate >= 90% on supported devices
- Users prefer it in qualitative feedback

AR supplements paper (offered as option) if:
- Mean error within 5% of paper method
- Works reliably on tested devices
- At least some users prefer it

AR gets cut if:
- Error > 5% or inconsistency > 3x paper
- Success rate < 80%
- Floor detection fails frequently in normal conditions

---

## Dependencies to Add

### Frontend (`package.json`)

No new JS dependencies. ARCore is accessed via the custom native module. The config plugin handles the Android-side dependency (`com.google.ar:core`).

### Backend (`requirements.txt`)

```
numpy>=1.24.0
```

numpy is likely already installed (scikit-learn depends on it), but pin it explicitly for the matrix math in `ar_measurement.py`.

### Android (`build.gradle` via config plugin)

```gradle
dependencies {
    implementation 'com.google.ar:core:1.44.+'  // latest patch in 1.44 series; bump as needed
}
```

---

## Implementation Order

### Phase 0: Roboflow Feasibility Check (go/no-go gate)

0. Send 5-10 photos of a foot on a bare floor (no paper) through the existing Roboflow `foot-measuring` workflow.
   - If Roboflow detects the foot reliably: proceed to Phase 1.
   - If detection fails or is inconsistent: **stop**. The Roboflow model needs retraining with paperless images before any AR code is worth writing. This is the single largest risk to the feature.

**No code required. Takes < 1 hour. Must pass before investing dev time.**

### Phase 1: Backend AR Math (no device needed)

1. Add `measurement_method` field to `Measurement` model + migration
2. Create `backend/services/ar_measurement.py` with unprojection logic
3. Modify `FootMeasureView` to branch on `measurement_method`, including `ar_snapshot` schema validation
4. Unit test `ar_measurement.py` with synthetic AR snapshots (known camera matrix + known plane + known pixel coords → verify expected distances)

**Testable without a phone.** Use fabricated AR snapshots with known geometry to verify the math produces correct inch values.

### Phase 2: Native Module

5. Create `withARCore.js` Expo config plugin
6. Create `ARCoreModule.java` native module (with `LifecycleEventListener` for session lifecycle)
7. Create `ARCoreViewManager.java` (SimpleViewManager wrapping GLSurfaceView for camera preview)
8. Create `ARCorePackage.java` registration (registers both module + view manager)
9. Build dev client with `eas build --profile development --platform android`
10. Verify: ARCore initializes, plane detection works, snapshot capture returns valid data, session pauses/resumes correctly on app background/foreground

**Requires an ARCore-compatible physical Android device.** Emulators have limited AR support.

### Phase 3: Frontend Screens

10. Create `ARFootCaptureScreen.js` (instructions)
11. Create `ARCameraScreen.js` (AR camera + capture)
12. Add AR routes to `App.js` navigation
13. ~~Add "Measure with AR" entry point on `ClosetScreen`~~ → done via `FootCaptureScreen` / Dashboard

### Phase 4: Integration + Testing

14. End-to-end test: AR capture → Roboflow → AR math → measurement result
15. Run A/B comparison protocol (see above)
16. Iterate based on accuracy/usability findings

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Roboflow can't detect feet without paper in frame | High | **Blocks entire feature** | Phase 0 go/no-go test before writing any code; retrain model if needed |
| ARCore + expo-camera fight for camera hardware | High | Blocks AR screen | Option A: let ARCore own the camera entirely |
| AR session not properly managed on app lifecycle | High | Resource leaks, crashes | ARCoreModule implements LifecycleEventListener; pause/resume/destroy on host events |
| Floor detection fails on glossy/plain surfaces | Medium | Bad UX, user falls back to paper | Clear guidance in instructions screen; detect and warn |
| Unprojection math has systematic bias | Medium | Inaccurate measurements | Unit test with known geometry; calibration offset if needed |
| ARCore not installed on user's device | Medium | User can't use AR | Mark AR as `optional` in manifest; graceful fallback to paper |
| Malformed ar_snapshot crashes backend | Medium | 500 error | Schema validation before passing to numpy (see `_validate_ar_snapshot`) |
| Config plugin breaks existing dev client build | Low | Blocks all development | Test on separate branch first; keep paper flow untouched |
| numpy not available or version conflict on backend | Low | Backend crash | Already a transitive dependency via scikit-learn |

---

## What This Branch Does NOT Do

- Does not remove or modify the paper measurement flow
- Does not change the `Measurement` model shape (same fields, just adds `measurement_method`)
- Does not affect recommendations, shoe data, or any non-measurement feature
- Does not target iOS (no ARKit implementation)
- Does not auto-detect foot endpoints on-device (still uses Roboflow server-side)
- Does not change the Roboflow workflow/model

---

## Open Questions

1. ~~**Does Roboflow need the paper to anchor its foot detection?**~~ Resolved: Phase 0 gates all implementation on testing this. If the existing model fails on paperless images, the feature is blocked until the model is retrained.

2. **Can ARCore and expo-camera coexist in the same app?** They'd never run simultaneously (different screens), but they both register camera-related manifest entries. Need to verify no conflicts in the config plugin.

3. **What's the minimum plane extent for reliable measurement?** If ARCore detects a tiny floor patch (0.1m x 0.1m), the plane equation may be unreliable. We should gate capture on a minimum extent (e.g., 0.5m x 0.5m).

4. **Toebox measurement feasibility.** The current paper flow measures toebox via a separate Roboflow "Toe Box" class detection. This should work identically with AR unprojection — same 2D points, same math — but needs verification.

---

## Branch Strategy

```
main
 └── feature/arcore-measurement    ← this plan
      ├── Phase 1 commits (backend math)
      ├── Phase 2 commits (native module)
      ├── Phase 3 commits (frontend screens)
      └── Phase 4 commits (integration fixes)
```

Do NOT merge into main until A/B testing results justify it. This branch is experimental.
