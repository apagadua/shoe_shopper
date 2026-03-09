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
│   │   └── __init__.py   # All DB models defined here
│   ├── migrations/
│   ├── services/         # Business logic
│   ├── utils/
│   ├── roboflow/         # Roboflow AI integration helpers
│   ├── requirements.txt
│   └── README.md
├── frontend/             # React Native (Expo) app
│   ├── App.js            # Root navigation setup
│   ├── app.json          # Expo config (plugins, android package)
│   ├── package.json
│   ├── screens/          # One file per screen
│   ├── services/
│   │   └── auth.js       # Google Sign-In + token exchange
│   ├── config/
│   │   └── api.js        # API_BASE_URL (platform-aware)
│   ├── components/       # Reusable UI (currently mostly empty)
│   ├── styles/
│   ├── utils/
│   └── assets/
├── shoeshopper/          # Django project config
│   ├── settings.py
│   └── urls.py           # Mounts /api/ → backend/api/urls.py
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

Stored in `.env` at the repo root (never commit).

| Variable | Used By | Purpose |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Backend | Verify Google ID tokens |
| `DJANGO_SECRET_KEY` | Backend | Django secret |
| `DJANGO_DEBUG` | Backend | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | Backend | Comma-separated allowed hosts |
| `DATABASE_URL` | Backend | PostgreSQL connection string |
| `DB_SSLMODE` | Backend | `require` for Supabase |
| `ROBOFLOW_API_KEY` | Backend | Roboflow inference API |
| `ROBOFLOW_WORKSPACE` | Backend | `armaanai` |
| `ROBOFLOW_PROJECT` | Backend | `foot-measuring` |
| `EXPO_PUBLIC_API_URL` | Frontend | Override default backend URL |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Frontend | Google OAuth client ID |

---

## Database Models (`backend/models/__init__.py`)

| Model | Key Fields | Notes |
|---|---|---|
| `Profile` | `user`, `display_name`, `avatar_url` | 1-to-1 with Django User |
| `GuestSession` | `session_uuid`, `expires_at` | Anonymous usage |
| `Measurement` | `length_in`, `width_in`, `area_sq_in`, `status` | Status: uploaded/processing/complete/error |
| `Shoe` | `brand`, `model`, `gender`, `price_usd`, `insole_*` dimensions | Arrays: `function_tags`, `style_tags` |
| `ShoeSize` | `shoe`, `us_size`, `width`, `is_available` | Unique on (shoe, us_size, width) |
| `UserCollection` | `type` (wishlist/owned), `size`, `color`, `notes` | |
| `Recommendation` | `run_id`, `rank`, `score`, `algorithm_version` | Links user ↔ shoe ↔ measurement |
| `TrainingImage` | `image_url`, `label_json`, `in_dataset` | ML training data |

---

## API Endpoints (`/api/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health/` | None | Status + shoe count |
| GET | `/api/shoes/` | None | List all shoes with sizes |
| POST | `/api/auth/google/` | None | Exchange Google ID token → auth key |
| DELETE | `/api/auth/delete/` | Token | Delete authenticated user's account |
| POST | `/api/foot/measure/` | Optional | Upload foot photo → measurements in inches |

---

## Frontend Screens

### Navigation Tree
```
Stack Navigator
├── Welcome          (WelcomeScreen.js)   — hero + carousel
├── Login            (LoginScreen.js)     — Google Sign-In
└── MainTabs (Bottom Tab Navigator)
    ├── Closet tab
    │   ├── ClosetHome  (ClosetScreen.js)
    │   ├── SavedShoes  (SavedShoesScreen.js)
    │   ├── OwnedShoes  (OwnedShoesScreen.js)
    │   ├── FootCapture (FootCaptureScreen.js) — instructions
    │   ├── Camera      (CameraScreen.js)      — live capture
    │   └── Measurements (MeasurementsScreen.js)
    ├── Recommendations tab (RecommendationsScreen.js)
    └── Profile tab         (ProfileScreen.js)
```

### Screen Responsibilities
- **CameraScreen** — Most complex screen. Accelerometer tilt detection (≤10° optimal), Android light sensor, paper-size toggle (A4/Letter/Auto), FormData upload to `/api/foot/measure/`, preview phase before submit.
- **MeasurementsScreen** — Displays results in inches + cm; persists to AsyncStorage as JSON.
- **RecommendationsScreen** — Filtering UI: function (Athletic/Casual/Work/Formal), silhouette (Boot/Sneaker/Slip-on/Dress), attributes (waterproof, vegan, etc.). Currently uses mock data.
- **ProfileScreen** — Delete account, sign out, backend smoke test (health + shoes endpoints).

---

## Key Flows

### Foot Measurement Flow
1. User navigates: Closet → FootCapture (instructions) → Camera
2. Camera screen shows live feed with overlay guides
3. Accelerometer warns if phone is tilted > 10°
4. User taps capture → preview shown → user confirms
5. `FormData` POST to `/api/foot/measure/` with `image` + optional `paper_size`
6. Backend sends image to Roboflow; detects paper (scale) + foot outline
7. Backend returns `{ length_in, width_in, area_sq_in, pixels_per_inch }`
8. Frontend stores in AsyncStorage; navigates to MeasurementsScreen

### Google Auth Flow
1. `auth.js: googleSignIn()` → triggers native Google picker → returns `idToken`
2. `auth.js: signInWithGoogle(idToken)` → POST `/api/auth/google/` → returns `{ key }`
3. `key` stored in `expo-secure-store`
4. Subsequent requests include `Authorization: Token <key>` header

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

---

## Known Stubs / Incomplete Features

- `SavedShoesScreen` and `OwnedShoesScreen` — exist but are placeholder screens
- `components/` directory — empty; no shared UI components extracted yet
- Recommendations — fully wired to real API (`GET /api/recommendations/`); scores DB shoes against the user's latest measurement
- Avatar/photo change in ProfileScreen — UI present, not implemented
- Paper size auto-detection uses IP geolocation as fallback (may be unreliable)

---

## Common Gotchas

- **SQLite vs PostgreSQL**: `db.sqlite3` is committed (dev only). Production uses Supabase. Do not rely on local SQLite schema for production migrations.
- **Expo Go limitations**: Native modules (`expo-camera`, `expo-sensors`, Google Sign-In) require a dev client build — they will NOT work in Expo Go.
- **Android emulator camera**: The physical camera does not work in most Android emulators; test on a real device.
- **Roboflow inference**: The `foot-measuring` project/workflow must be published in the `armaanai` workspace. Check the workspace dashboard if inference fails.
- **Token auth header**: Backend expects `Authorization: Token <key>` (DRF token format), not `Bearer`.
- **CORS / ALLOWED_HOSTS**: When testing from a physical device on the same network, add the machine's LAN IP to `DJANGO_ALLOWED_HOSTS`.
