# CLAUDE.md — Shoe Shopper Dev

Living reference for Claude Code working in this repo. Update as the project evolves.

---

## Project Overview

**Shoe Shopper** is a mobile app that uses computer vision to measure a user's foot from a photo and recommend shoes that fit. The user places their foot on a standard sheet of paper, takes a photo in-app, and the backend runs AI inference to extract measurements in inches. Those measurements drive shoe recommendations.

---

## Repository Layout

```
shoe_shopper_dev/
├── backend/              # Django REST API
│   ├── api/
│   │   ├── views.py      # All API view logic
│   │   ├── urls.py       # API URL routing
│   │   └── serializers.py
│   ├── models/
│   │   └── __init__.py   # All DB models defined here (do not split)
│   ├── migrations/
│   ├── services/         # Business logic (fit, AR, tolerance, feedback)
│   ├── utils/
│   ├── roboflow/         # Roboflow AI integration helpers
│   ├── management/commands/ # Shoe sync, seed, audit, data commands
│   ├── tests/            # Focused Python tests
│   ├── requirements.txt
│   └── README.md
├── frontend/             # React Native (Expo) app
│   ├── App.js            # Root navigation, providers, font loading
│   ├── app.config.js     # Loads repo root .env then frontend/.env
│   ├── app.json          # Expo config (plugins, android package)
│   ├── package.json
│   ├── screens/          # One file per screen
│   ├── services/         # Frontend service modules and caches
│   │   └── auth.js       # Google Sign-In + token exchange
│   ├── config/
│   │   └── api.js        # API_BASE_URL (platform-aware)
│   ├── components/       # Shared UI components
│   ├── SavedShoesContext.js  # AsyncStorage-backed saved shoe state
│   ├── OwnedShoesContext.js  # AsyncStorage-backed owned shoe state
│   ├── plugins/withARCore.js # Expo config plugin for Android ARCore
│   ├── styles/
│   ├── utils/
│   └── assets/
├── shoeshopper/          # Django project config
│   ├── settings.py
│   └── urls.py           # Mounts /api/ → backend/api/urls.py
├── docs/                 # Architecture, setup, CV, ARCore, integration plans
├── ar_debug/             # Generated AR debug images — do not treat as source
├── media/                # Local uploaded media
├── .claude/tasks/        # Task specs written by Claude for Codex to implement
├── manage.py
├── db.sqlite3            # Local SQLite (dev fallback)
└── .env                  # Secrets — never commit
```

---

## Tech Stack

### Backend
| Layer | Choice |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16.1 |
| Auth | Token auth (`rest_framework.authtoken`) + Google OAuth2 |
| AI / CV | Roboflow (custom `foot-measuring` workflow) |
| DB (prod) | PostgreSQL via Supabase |
| DB (dev) | SQLite (`db.sqlite3`) |
| ML libs | scikit-learn, joblib, nltk |

### Frontend
| Layer | Choice |
|---|---|
| Framework | React Native + Expo SDK 54 |
| Navigation | React Navigation (Stack + Bottom Tabs) |
| Auth | `@react-native-google-signin/google-signin` |
| Storage | `expo-secure-store` (tokens), `AsyncStorage` (measurements) |
| Camera | `expo-camera` |
| Sensors | `expo-sensors` (accelerometer + light) |
| Font | Outfit (Google Fonts via `expo-font`) |

---

## Environment Variables

Backend env is read by `shoeshopper/settings.py`. Frontend public env must use `EXPO_PUBLIC_` prefix. `frontend/app.config.js` loads repo root `.env` first, then `frontend/.env` (frontend values win on conflict). Never commit `.env` files.

| Variable | Used By | Purpose |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Backend | Verify Google ID tokens |
| `GOOGLE_ANDROID_CLIENT_ID` | Backend | Android-specific Google OAuth |
| `DJANGO_SECRET_KEY` | Backend | Django secret |
| `DJANGO_DEBUG` | Backend | Debug mode — be careful changing in prod |
| `DJANGO_ALLOWED_HOSTS` | Backend | Comma-separated allowed hosts |
| `DATABASE_URL` | Backend | PostgreSQL connection string (blank = SQLite) |
| `DB_SSLMODE` | Backend | `require` for Supabase |
| `ROBOFLOW_API_KEY` | Backend | Roboflow inference API |
| `ROBOFLOW_WORKSPACE` | Backend | `armaanai` |
| `ROBOFLOW_PROJECT` | Backend | `foot-measuring` |
| `ENABLE_DEV_MOCK_MEASUREMENT` | Backend | Enables `/api/dev/mock-measurement/` route (dev only) |
| `EXPO_PUBLIC_API_URL` | Frontend | Override default backend URL |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Frontend | Google OAuth client ID |
| `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT` | Frontend | Skip real camera; use mock measurement on emulator |
| `EXPO_PUBLIC_SUPABASE_URL` | Frontend | Supabase URL if using client-side Supabase features |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Frontend | Supabase anon key |

**Gotcha:** `DATABASE_URL` set in the shell overrides `.env`. Clear it when switching back to SQLite.

---

## Database Models (`backend/models/__init__.py`)

All models live in a single file — do not split into separate files unless the project explicitly changes that convention. Always commit migrations alongside model changes.

| Model | Key Fields | Notes |
|---|---|---|
| `Profile` | `user`, `display_name`, `avatar_url` | 1-to-1 with Django User |
| `GuestSession` | `session_uuid`, `expires_at` | Anonymous usage |
| `Measurement` | `length_in`, `width_in`, `area_sq_in`, `status` | Status: uploaded/processing/complete/error |
| `Shoe` | `brand`, `model`, `gender`, `price_usd`, `insole_*` dimensions | Arrays: `function_tags`, `style_tags` |
| `ShoeSize` | `shoe`, `us_size`, `width`, `is_available` | Unique on (shoe, us_size, width) |
| `ShoeColorway` | `shoe`, `color_name`, `image_url` | Color variants of a base shoe |
| `ShoeColorwaySize` | `colorway`, `us_size`, `width`, `is_available` | Availability per colorway + size |
| `UserCollection` | `type` (wishlist/owned), `size`, `color`, `notes` | |
| `Recommendation` | `run_id`, `rank`, `score`, `algorithm_version` | Links user ↔ shoe ↔ measurement |
| `TrainingImage` | `image_url`, `label_json`, `in_dataset` | ML training data |

Preserve `ShoeColorway` and `ShoeColorwaySize` relationships when editing recommendation logic or sync commands — they drive colorway options in the recommendations response.

---

## API Endpoints (`/api/`)

Authenticated requests use `Authorization: Token <key>` (DRF format — not Bearer).

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health/` | None | Status + shoe count |
| GET | `/api/shoes/` | None | List all shoes with sizes |
| POST | `/api/auth/google/` | None | Exchange Google ID token → DRF auth key |
| DELETE | `/api/auth/delete/` | Token | Delete authenticated user's account |
| GET/PATCH | `/api/profile/` | Token | Read or update display name |
| POST | `/api/foot/measure/` | Optional | Upload foot photo (paper or ARCore) → measurements in inches |
| POST | `/api/measurements/upload/` | Optional | Simple upload / guest session path |
| GET | `/api/measurements/latest/` | Token | Latest complete measurement for user |
| GET | `/api/recommendations/` | Token | Scored shoes for user's latest measurement (includes colorways) |
| POST | `/api/dev/mock-measurement/` | Token | Dev-only mock measurement (requires `ENABLE_DEV_MOCK_MEASUREMENT`) |
| GET | `/api/proxy-image/` | None | Limited CDN image proxy — intentionally restricted to specific hosts |

---

## Frontend Screens

### Navigation Tree
```
Stack Navigator
├── Welcome          (WelcomeScreen.js)   — hero + carousel
├── Login            (LoginScreen.js)     — Google Sign-In
└── MainTabs (Bottom Tab Navigator)
    ├── Closet tab
    │   ├── ClosetHome  (Dashboard.js)
    │   ├── SavedShoes  (Wishlist.js)
    │   ├── OwnedShoes  (Closet.js)
    │   ├── FootCapture (FootCaptureScreen.js) — instructions
    │   ├── Camera      (CameraScreen.js)      — live capture
    │   └── Measurements (MeasurementsScreen.js)
    ├── Recommendations tab (RecommendationsScreen.js)
    └── Profile tab         (ProfileScreen.js)
```

### Screen Responsibilities
- **CameraScreen** — Most complex screen. Accelerometer tilt detection (≤10° optimal), Android light sensor, paper-size toggle (A4/Letter/Auto), FormData upload to `/api/foot/measure/`, preview phase before submit.
- **ARCameraScreen / ARFootCaptureScreen** — ARCore measurement flow; sends `measurement_method=arcore` + `ar_snapshot` to backend.
- **MeasurementsScreen** — Displays results in inches + cm; persists to AsyncStorage as JSON.
- **RecommendationsScreen** — Fully wired to `GET /api/recommendations/`. Filtering UI: function (Athletic/Casual/Work/Formal), silhouette (Boot/Sneaker/Slip-on/Dress), attributes (waterproof, vegan, etc.). Includes colorway options from `ShoeColorwaySize`.
- **Dashboard.js** — Closet home tab.
- **Wishlist.js / Closet.js** — Saved/owned shoe lists with cards; state via `SavedShoesContext.js` / `OwnedShoesContext.js`.
- **ProfileScreen** — Delete account, sign out, backend smoke test (health + shoes endpoints). Avatar change UI present but not implemented.

### State Management
- Auth token: `expo-secure-store` under key `authToken`
- Saved/owned shoes: `SavedShoesContext.js` and `OwnedShoesContext.js` (AsyncStorage-backed)
- Measurements: AsyncStorage as JSON after capture
- Use `useFocusEffect` for data that should refresh when the user returns to a screen

---

## Key Flows

### Foot Measurement Flow (Paper)
1. User navigates: Closet → FootCapture (instructions) → Camera
2. Camera screen shows live feed with overlay guides
3. Accelerometer warns if phone is tilted > 10°
4. User taps capture → preview shown → user confirms
5. `FormData` POST to `/api/foot/measure/` with `image` + optional `paper_size`
6. Backend sends image to Roboflow; detects paper bounding box (scale reference) + foot/insole polygon
7. Backend returns `{ length_in, width_in, area_sq_in, pixels_per_inch }`
8. Frontend stores in AsyncStorage; navigates to MeasurementsScreen

### Foot Measurement Flow (ARCore)
1. User navigates to ARFootCaptureScreen → ARCameraScreen
2. ARCore tracking state validated before capture
3. POST to `/api/foot/measure/` with `measurement_method=arcore` + `ar_snapshot`
4. Backend uses `backend/services/ar_measurement.py` (AR unprojection math) for dimensions
5. Same response shape and AsyncStorage persistence as paper flow

### Google Auth Flow
1. `auth.js: googleSignIn()` → triggers native Google picker → returns `idToken`
2. `auth.js: signInWithGoogle(idToken)` → POST `/api/auth/google/` → returns `{ key }`
3. `key` stored in `expo-secure-store` under `authToken`
4. Subsequent requests include `Authorization: Token <key>` header

### Recommendations Flow
1. `GET /api/recommendations/` — backend fetches user's latest complete `Measurement`
2. Scores all active `Shoe` records against measurement via `backend/services/fit_algorithm.py`
3. Returns ranked list with colorway options (`ShoeColorway` + `ShoeColorwaySize` availability)
4. Frontend filters by function, silhouette, and attributes client-side

---

## Development Setup

### Backend
```bash
# From repo root
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r backend/requirements.txt
cp .env.example .env   # fill in values
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Frontend
```bash
cd frontend
npm install
# Set EXPO_PUBLIC_API_URL if not using emulator defaults
npx expo start --tunnel   # or --dev-client for custom build
```

### Android Emulator URL
The frontend auto-selects `http://10.0.2.2:8000` on Android and `http://127.0.0.1:8000` on iOS. Override with `EXPO_PUBLIC_API_URL`.

### EAS Dev Build (for native modules like camera/sensors)
```bash
npx eas-cli build --profile development --platform android
npx expo start --dev-client
```

---

## Branch Strategy

- **`main`** — stable, use for PRs
- **`OrsBranch`** — current active dev branch
- **`codex/<task-id>-<slug>`** — branches where Codex implements task specs

Claude Code uses git worktrees (`.claude/worktrees/`). Do not modify files inside worktree paths from other sessions.

---

## Claude + Codex Pipeline

This repo uses a senior/junior AI pipeline:

| Role | Agent | Responsibilities |
|---|---|---|
| Senior | Claude Code | Architecture, task decomposition, spec writing, code review, merges, security/auth decisions |
| Junior | Codex CLI | Implementing specific well-scoped tasks from specs Claude writes |

### Workflow

```
Claude writes spec → .claude/tasks/<task-id>.md
      ↓
User runs: codex "implement the task described in .claude/tasks/<task-id>.md"
      ↓
Codex works on branch: codex/<task-id>-<slug>
      ↓
Codex commits with message starting [codex-done]
      ↓
Claude reviews diff → approves or writes follow-up correction spec
```

### Task Spec Format (`.claude/tasks/<task-id>.md`)
Each spec includes:
- **Goal** — what to build in one paragraph
- **Scope** — exact files Codex may touch
- **Acceptance criteria** — testable pass/fail assertions
- **Out of scope** — explicit list of what not to change

### Rules for Codex
- Only touch files listed in the spec's scope section
- Do not modify `AGENTS.md`, `CLAUDE.md`, unrelated migrations, `ar_debug/`, or `media/`
- If a model change is needed, include the migration in the same commit
- On ambiguity: make the conservative choice and note it in the commit message
- Run verification steps (see `AGENTS.md`) before marking done

---

## Backend Services

Key service files in `backend/services/`:

| File | Purpose |
|---|---|
| `fit_algorithm.py` | Scoring, size estimation, status labels, tolerance profiles, bias correction |
| `ar_measurement.py` | ARCore unprojection math for AR-based foot dimensions |
| `tolerance_learning.py` | Tolerance and feedback learning logic |
| `feedback_service.py` | User feedback processing |
| `tolerance_storage.py` | Persistence for tolerance data |

Prefer adding new business logic as service functions rather than bloating API views.

---

## Known Stubs / Incomplete Features

- `Wishlist.js` and `Closet.js` — wishlist/owned lists; `SavedShoesContext.js` / `OwnedShoesContext.js` (AsyncStorage, not backend-synced)
- `components/` — shared UI (`AppLogo`, `ShoeCardKeyFacts`, etc.) extracted from screens
- Recommendations — wired to `GET /api/recommendations/`; fit feedback UI in `feedback.js` is local-only (no API POST yet)
- Avatar/photo change in ProfileScreen — UI present, not implemented
- Paper size auto-detection uses IP geolocation as fallback (may be unreliable)
- No comprehensive automated frontend test suite — manual verification required for UI changes

---

## Common Gotchas

- **SQLite vs PostgreSQL**: `db.sqlite3` is committed (dev only). Production uses Supabase. Do not rely on local SQLite schema for production migrations.
- **`DATABASE_URL` shell override**: If set in the shell it overrides `.env`. Clear it when switching back to SQLite.
- **Expo Go limitations**: Native modules (`expo-camera`, `expo-sensors`, Google Sign-In) require a dev client build — they will NOT work in Expo Go.
- **Android emulator camera**: The physical camera does not work in most Android emulators. Use `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1` + `ENABLE_DEV_MOCK_MEASUREMENT` on the backend for emulator workflows.
- **Roboflow inference**: The `foot-measuring` project/workflow must be published in the `armaanai` workspace. Failures often come from unpublished workflows, missing API keys, poor lighting, no paper detection, bad AR tracking, or image orientation.
- **Token auth header**: Backend expects `Authorization: Token <key>` (DRF format), not `Bearer`.
- **CORS / ALLOWED_HOSTS**: When testing from a physical device on the same network, add the machine's LAN IP to `DJANGO_ALLOWED_HOSTS`.
- **Recommendation quality**: Depends heavily on `ShoeSize` insole dimensions and live `ShoeColorwaySize` availability.
- **ProxyImageView**: Intentionally limited to specific CDN hosts — do not turn it into an open proxy.
- **Dev client rebuild required**: When native dependencies, Expo plugins, Android package config, permissions, or ARCore plugin behavior changes.
