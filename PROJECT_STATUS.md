# Project Status — Shoe Shopper

Last updated: March 2026

---

## Overview

Shoe Shopper is a mobile app that measures a user's foot from a photo and recommends shoes that fit. The core measurement and recommendation flows are **fully working end-to-end**. Two screens (Saved Shoes, Owned Shoes) remain unimplemented stubs. The rest of the app is production-ready.

---

## Backend

### API Endpoints — All Implemented

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/` | Status check + shoe count |
| GET | `/api/shoes/` | List all shoes with sizes |
| POST | `/api/auth/google/` | Exchange Google ID token → auth key |
| DELETE | `/api/auth/delete/` | Delete authenticated user account |
| POST | `/api/foot/measure/` | Upload foot photo → measurements in inches |
| GET | `/api/measurements/latest/` | Return user's most recent measurement |
| GET | `/api/recommendations/` | Score all shoes against latest measurement |

### Models — All Implemented

| Model | Notes |
|---|---|
| `Profile` | 1-to-1 with Django User; display name, avatar URL |
| `GuestSession` | Anonymous session with expiry |
| `Measurement` | Foot dimensions (length, width, area), paper type, status |
| `Shoe` | Full shoe data: insole dimensions, gender, tags, toe shape, cap type |
| `ShoeSize` | Per-shoe size availability with width variants |
| `UserCollection` | Wishlist and owned shoe tracking (model only — not wired in frontend) |
| `Recommendation` | Persisted recommendation runs with score and algorithm version |
| `TrainingImage` | ML training image management |

### Fit Algorithm (`backend/services/fit_algorithm.py`) — Fully Implemented

Version 1.5. Scores shoes 0–100 using clearance-based zone scoring across up to four dimensions (length, width, toebox length, toebox width). Key behaviors:

- **14 tolerance profiles** mapped from shoe function tags via hierarchical tag routes (e.g. `Athletic` + `Running` + `Road` → `ROAD_RUNNING`)
- **Hard-reject logic**: three conditions (toebox compression, length out of range, width out of range) can reject a shoe outright
- **Three point budget variants** depending on available data:
  - Full toebox data: 20 + 30 + 20 + 30 = 100 pts (default)
  - No toebox, with area: 35 + 40 + 25 = 100 pts
  - Length + width only: 50 + 50 = 100 pts
- **CV bias corrections** applied before scoring: `+0.508"` to foot length (model underestimates), `−0.371"` from foot width (model overestimates)
- **Status labels**: PERFECT (≥90), GOOD (≥75), ACCEPTABLE (≥60), MARGINAL (≥40), POOR (<40), REJECTED, UNSCORED
- **Brannock formula** for US size estimation (women: `3×length − 20.5`, men: `3×length − 22.0`)
- Sub-type modifiers for specialized activities (marathon, clay court, olympic lifting, etc.)

---

## Frontend

### Screens

| Screen | Status | Notes |
|---|---|---|
| WelcomeScreen | **Full** | Hero section + 3-step feature carousel |
| LoginScreen | **Full** | Google Sign-In, loading states, token persistence via SecureStore |
| ClosetScreen | **Full** | Shows latest foot measurements and estimated shoe size; links to Saved/Owned/Capture |
| FootCaptureScreen | **Full** | Instruction screen with mockup diagram and tips before camera |
| CameraScreen | **Full** | Live camera feed, accelerometer tilt detection (≤10°), Android light sensor, A4/Letter paper size toggle, preview phase, FormData upload to `/api/foot/measure/` |
| MeasurementsScreen | **Full** | Displays length/width/area in inches and cm; calculates Brannock size range |
| RecommendationsScreen | **Full** | Live API data, fit score badges, filter drawer (function/silhouette/attributes), save-to-wishlist with toast |
| ProfileScreen | **Partial** | Sign out and delete account work; backend smoke test button works; avatar/photo change is a UI stub (no image picker wired) |
| SavedShoesScreen | **Stub** | Empty state placeholder only — no logic to add, view, or remove saved shoes |
| OwnedShoesScreen | **Stub** | Empty state placeholder only — no logic to add, view, or remove owned shoes |

### Other Frontend Modules

| File | Status | Notes |
|---|---|---|
| `services/auth.js` | **Full** | `googleSignIn()` triggers native picker; `signInWithGoogle(idToken)` exchanges token with backend |
| `config/api.js` | **Full** | Platform-aware `API_BASE_URL`; respects `EXPO_PUBLIC_API_URL` env override |
| `utils/shoeSize.js` | **Full** | Brannock formula for frontend size display: `getBestSize()`, `getSizeRange()` |
| `components/` | **Empty** | Directory exists; no shared UI components extracted yet |

### Navigation (`App.js`) — Fully Implemented

```
Stack Navigator
├── Welcome
├── Login
└── MainTabs (Bottom Tab Navigator)
    ├── Closet Stack
    │   ├── ClosetHome
    │   ├── SavedShoes      ← stub
    │   ├── OwnedShoes      ← stub
    │   ├── FootCapture
    │   ├── Camera
    │   └── Measurements
    ├── Recommendations
    └── Profile
```

Tab bar is hidden on FootCapture, Camera, and Measurements screens.

---

## What's Not Implemented

### SavedShoesScreen & OwnedShoesScreen
The `UserCollection` model exists in the database with fields for type (wishlist/owned), size, color, and notes. However, the frontend screens are empty state placeholders — there are no API endpoints or UI to add, view, or delete items from these lists.

### Shoe Detail View
RecommendationsScreen renders shoe cards with a "View details" button. Due to unresolved merge conflicts, the HEAD version has a no-op handler (`() => {}`), while the OrsBranch version opens `product_url` via `Linking.openURL()`. After resolving conflicts to the OrsBranch version, the button will open the shoe's product page in the browser (when `product_url` is available). No in-app shoe detail screen exists.

### Shoe Photos
The `shoe_image_url` field exists on the `Shoe` model and is returned by the API. RecommendationsScreen renders a placeholder box where the image should appear. No actual shoe images are loaded or displayed.

### Profile Avatar Change
ProfileScreen has a camera icon on the avatar that triggers `handleChangePhoto`. The function body is empty — no image picker is integrated and the avatar is hardcoded to `null`.

### Shared Component Library
`frontend/components/` is empty. UI elements are inline in each screen with no extraction into reusable components.

---

## Known Issues / Pending Investigations

- `POST /api/foot/measure/` occasionally returns 400 when Roboflow does not detect the `paper` class. The raw Roboflow response is not currently logged, making it difficult to debug. Adding temporary logging after the `rf_resp.json()` call in `FootMeasureView` would help diagnose this.
- Paper size is a manual toggle (Letter/A4) in CameraScreen — no auto-detection is implemented.
