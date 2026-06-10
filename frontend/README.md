# Shoe Shopper – Frontend

Expo + React Native mobile app for foot measurement, personalized shoe recommendations, wishlist/closet management, and fit feedback.

**Stack:** Expo SDK 54 · React Native 0.81 · React 19 · React Navigation 7

## Table of Contents

- [What the app does](#what-the-app-does)
- [Prerequisites](#prerequisites)
- [Environment variables](#environment-variables)
- [Install & run](#install--run)
- [Running on devices](#running-on-devices)
- [Project structure](#project-structure)
- [Development notes](#development-notes)
- [Troubleshooting](#troubleshooting)
- [Additional resources](#additional-resources)

---

## What the app does

| Area | Screens | Summary |
|------|---------|---------|
| Onboarding | `WelcomeScreen`, `LoginScreen` | Landing page and Google sign-in |
| Dashboard | `Dashboard` | Foot profile, recommendation/wishlist/closet previews |
| Recommendations | `RecommendationsScreen` | Filterable shoe cards with fit scores |
| Wishlist & closet | `Wishlist`, `Closet` | Saved shoes and owned shoes (local AsyncStorage) |
| Foot scan | `FootCaptureScreen`, `CameraScreen`, `ARFootCaptureScreen`, `ARCameraScreen`, `MeasurementsScreen` | Paper photo or AR measurement flow |
| Profile | `ProfileScreen` | Display name, sign out, delete account |
| Feedback | `feedback.js` | Per-shoe fit sliders (owned shoes) |

Navigation is defined entirely in `App.js`: a root stack (auth), bottom tabs (Dashboard / Recommendations / Profile), and a nested Closet stack for dashboard sub-screens and the measurement flow.

---

## Prerequisites

- **Node.js** v18+ ([nodejs.org](https://nodejs.org))
  ```bash
  node --version
  npm --version
  ```
- **Expo tooling** — use `npx expo …` (no global install required).
- **Backend running** — the Django API must be up for sign-in, scans, and recommendations. See the [repo root README](../README.md) for backend setup.

> **Native modules:** This app uses camera, sensors, Google Sign-In, and ARCore (Android). It does **not** work fully in Expo Go. Use an **EAS development build** on a device or the Android emulator for day-to-day development.

---

## Environment variables

Create `frontend/.env` (not committed to git). Restart Metro after any change.

```env
# Backend URL — leave blank on Android emulator (defaults to http://10.0.2.2:8000)
# or iOS simulator (defaults to http://127.0.0.1:8000)
EXPO_PUBLIC_API_URL=

# Required for Google sign-in
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com

# Optional — emulator dev workflow without a camera
# EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1
```

| Scenario | `EXPO_PUBLIC_API_URL` |
|----------|------------------------|
| Android emulator | Leave blank → `http://10.0.2.2:8000` |
| iOS simulator | Leave blank → `http://127.0.0.1:8000` |
| Physical device (same Wi‑Fi) | Your machine's LAN IP, e.g. `http://192.168.1.50:8000` |

Mock measurements require `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1` in this file **and** `DJANGO_DEBUG=1` or `ENABLE_DEV_MOCK_MEASUREMENT=1` in the root `.env`.

---

## Install & run

All commands run from the `frontend` folder.

```bash
cd frontend
npm install
```

If you hit peer dependency conflicts:

```bash
npm install --legacy-peer-deps
```

### Start Metro

```bash
# Default — tunnel mode (good for phones on different networks)
npm start

# Dev client (required for native modules)
npx expo start --dev-client

# Clear Metro cache
npx expo start --clear
```

With the dev server running, use terminal shortcuts:

```text
› Press a │ open Android
› Press i │ open iOS simulator
› Press w │ open web
› Press r │ reload app
```

### Typical two-terminal workflow

**Terminal 1** (repo root) — backend:

```bash
python manage.py runserver 0.0.0.0:8000
```

**Terminal 2** (`frontend/`) — Metro:

```bash
npx expo start --dev-client
```

Open the installed dev client app on your emulator or device.

---

## Running on devices

### Android emulator (development build) — recommended

1. **Install Android Studio** and create an AVD (Device Manager → Create Device).
2. **Build the dev client** (one-time, or when native deps/config change):
   ```bash
   npx eas-cli build --profile development --platform android
   ```
   Log in with an Expo account that has access to the **shoeshopper** org.
3. **Install the APK** — download from the EAS build page and drag the `.apk` onto the emulator window.
4. **Start Metro** with `npx expo start --dev-client`, start the emulator, press `a` or open the app from the drawer.

Rebuild the dev client only when you change native dependencies or `app.json` plugins. Normal JS/UI edits reload via Metro.

### Physical Android device

Same EAS development build as above — install the APK on the device. Set `EXPO_PUBLIC_API_URL` to your computer's LAN IP and ensure the backend is bound to `0.0.0.0:8000`.

### iOS

No iOS dev client is configured in this repo. Limited testing may work in **Expo Go** on a physical iPhone, but camera, AR, and Google Sign-In flows require native modules and are best tested on Android with the dev client.

---

## Project structure

```
frontend/
├── App.js                      # Navigation, fonts, context providers
├── index.js                    # Expo entry point
├── app.json                    # Expo config (plugins, package name, EAS project)
├── eas.json                    # EAS build profiles
├── SavedShoesContext.js        # Wishlist state (AsyncStorage)
├── OwnedShoesContext.js        # Owned / closet state (AsyncStorage)
├── assets/                     # logo.svg, app icons, splash, scan reference images
├── components/                 # Reserved for shared UI (empty today)
├── config/
│   └── api.js                  # API_BASE_URL
├── constants/
│   └── attributes.js           # Recommendation filter definitions
├── frontend-documents/
│   ├── FRONTEND_STYLE_GUIDE.md # Coding conventions (read before contributing)
│   ├── FRONTEND_FEATURES.md    # Feature map, data flow, line references
│   └── FRONTEND_TESTING.md     # Manual test results (Android emulator/device)
├── plugins/
│   └── withARCore.js           # Android ARCore native config
├── screens/
│   ├── WelcomeScreen.js
│   ├── LoginScreen.js
│   ├── Dashboard.js            # Tab home — foot profile + previews
│   ├── RecommendationsScreen.js
│   ├── Wishlist.js             # Saved shoes
│   ├── Closet.js               # Owned shoes
│   ├── ProfileScreen.js
│   ├── FootCaptureScreen.js    # Choose AR or paper scan
│   ├── CameraScreen.js         # Paper photo capture
│   ├── ARFootCaptureScreen.js
│   ├── ARCameraScreen.js
│   ├── MeasurementsScreen.js
│   └── feedback.js             # Fit feedback sliders
├── services/
│   ├── auth.js                 # Google Sign-In + backend token exchange
│   └── devMockMeasurement.js   # Dev-only mock scan helper
├── styles/
│   └── emptyState.js           # Shared empty-state styles
└── utils/
    └── shoeSize.js             # US men's size conversion helpers
```

---

## Development notes

- **Style guide:** [frontend-documents/FRONTEND_STYLE_GUIDE.md](./frontend-documents/FRONTEND_STYLE_GUIDE.md) — navigation, state, API patterns, colors, and naming conventions.
- **Feature map:** [frontend-documents/FRONTEND_FEATURES.md](./frontend-documents/FRONTEND_FEATURES.md) — major features, files, line refs, and backend data flow.
- **Manual QA:** [frontend-documents/FRONTEND_TESTING.md](./frontend-documents/FRONTEND_TESTING.md) — manual test cases and results from Android testing.
- **Backend:** API endpoints and Django setup live in [backend/README.md](../backend/README.md) and the [root README](../README.md).
- **Auth token:** Stored in `expo-secure-store` under `authToken`; sent as `Authorization: Token <key>`.
- **Local shoe lists:** Wishlist and closet persist in AsyncStorage via context providers — not synced to the backend yet.
---

## Troubleshooting

### "Unable to resolve module" / broken `node_modules`

```bash
# Mac / Linux
rm -rf node_modules package-lock.json && npm install

# Windows
rmdir /s /q node_modules
del package-lock.json
npm install
```

### Port 8081 already in use

Close other Metro instances, or on Windows:

```bash
netstat -ano | findstr :8081
taskkill /PID <PID> /F
```

### Can't connect to the dev server

- Phone and computer need network access (same Wi‑Fi, or use tunnel mode via `npm start`).
- Confirm `EXPO_PUBLIC_API_URL` matches how you're reaching the backend.
- Restart Metro: `npx expo start --dev-client --clear`

### "Unable to load script" (dev client)

- Ensure `npx expo start --dev-client` is running in `frontend/`.
- Start the emulator after Metro is up, then open the dev client app.

### Sign-in fails / missing Google client ID

Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in `frontend/.env` and restart Metro. The Web client ID must match `GOOGLE_CLIENT_ID` in the backend `.env`.

### Recommendations empty on emulator

Set `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1`, enable the backend dev mock route, sign in, and revisit the Dashboard or Recommendations tab.

### Dependency version mismatches

```bash
npm install
# or
npm install --legacy-peer-deps
```

This project pins React 19.1.0 for Expo SDK 54 — see `package.json`.

---

## Additional resources

- [Expo documentation](https://docs.expo.dev/)
- [React Native documentation](https://reactnative.dev/)
- [EAS Build](https://docs.expo.dev/build/introduction/)
- [React Navigation](https://reactnavigation.org/docs/getting-started)
