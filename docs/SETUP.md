# Setup Guide — Shoe Shopper

Step-by-step guide to get the full stack running locally for the first time.

---

## Table of Contents

1. [Get Access to Shared Services](#1-get-access-to-shared-services)
2. [System Prerequisites](#2-system-prerequisites)
3. [Clone the Repo](#3-clone-the-repo)
4. [Backend Setup](#4-backend-setup)
5. [Frontend Setup](#5-frontend-setup)
6. [Android Dev Client Build (one-time)](#6-android-dev-client-build-one-time)
7. [Daily Development Workflow](#7-daily-development-workflow)
8. [Verifying Everything Works](#8-verifying-everything-works)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Get Access to Shared Services

Before you can run anything, ask a teammate for credentials to these four services:

| Service | What you need | Where it goes |
|---|---|---|
| **Supabase** | PostgreSQL connection string | `.env` → `DATABASE_URL` |
| **Roboflow** | API key + workspace/project slugs | `.env` → `ROBOFLOW_API_KEY`, etc. |
| **Google Cloud** | OAuth 2.0 Web Client ID | `.env` + `frontend/.env` |
| **Expo / EAS** | Invite to the **shoeshopper** org | Needed to run `eas build` |

You can start working against local SQLite without Supabase, but foot measurement requires a Roboflow key and Google Sign-In requires the Google Client ID.

---

## 2. System Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.14 also confirmed working |
| Node.js | 18+ | LTS recommended |
| npm | comes with Node | — |
| Android Studio | latest stable | For the Android emulator |
| Git | any | — |

**Windows users:** these docs use bash syntax. PowerShell equivalents are noted where they differ.

Install Android Studio from [developer.android.com/studio](https://developer.android.com/studio) and run the standard install (includes the Android SDK). Then create an Android Virtual Device (AVD):

1. Android Studio → **Device Manager** → **Create Device**
2. Choose a phone model (Pixel 6 or 7 recommended)
3. Choose a system image: API 36, Google Play, Intel x86_64
4. Finish the wizard

---

## 3. Clone the Repo

```bash
git clone <repo-url>
cd shoe_shopper_dev
```

---

## 4. Backend Setup

All backend commands run from the **repo root** (where `manage.py` lives).

### 4.1 Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (cmd)
venv\Scripts\activate.bat
```

You should see `(venv)` in your prompt. Run this every time you open a new terminal for backend work.

### 4.2 Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

### 4.3 Create the backend `.env` file

Create a file named `.env` in the **repo root** (same directory as `manage.py`). **Never commit this file.**

```
# Django core
DJANGO_SECRET_KEY=any-long-random-string-here
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,10.0.2.2

# Google OAuth — verify ID tokens from the mobile app
GOOGLE_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com

# Roboflow — foot measurement AI
ROBOFLOW_API_KEY=your-roboflow-api-key
ROBOFLOW_WORKSPACE=armaanai
ROBOFLOW_PROJECT=foot-measuring

# Database — leave blank to use local SQLite (fine for development)
DATABASE_URL=
DB_SSLMODE=require
```

To use the shared Supabase database instead of SQLite, set `DATABASE_URL` to the full connection string a teammate provides:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### 4.4 Run migrations

```bash
python manage.py migrate
```

### 4.5 (Optional) Seed demo data

```bash
python manage.py seed_demo_data
```

This populates the `Shoe` and `ShoeSize` tables with sample data so you can test recommendations without a real shoe catalog.

### 4.6 Start the dev server

```bash
python manage.py runserver 0.0.0.0:8000
```

The API is now available at `http://localhost:8000/api/`. Leave this terminal running.

**Quick sanity check:**

```bash
curl http://127.0.0.1:8000/api/health/
# Expected: {"status": "ok", "shoe_count": <number>}
```

---

## 5. Frontend Setup

All frontend commands run from the `frontend/` directory.

### 5.1 Install Node dependencies

```bash
cd frontend
npm install
```

If you see peer dependency errors:

```bash
npm install --legacy-peer-deps
```

### 5.2 Create the frontend `.env` file

Create a file named `.env` inside the `frontend/` directory. **Never commit this file.**

```
# Backend URL override
# Leave blank when using Android emulator (auto-resolves to http://10.0.2.2:8000)
# Set to your machine's LAN IP when testing on a physical device
EXPO_PUBLIC_API_URL=

# Google OAuth client ID for the mobile sign-in flow
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com
```

URL cheat-sheet:

| Target | EXPO_PUBLIC_API_URL value |
|---|---|
| Android emulator | *(leave blank)* |
| iOS simulator | *(leave blank)* |
| Physical device (same Wi-Fi) | `http://192.168.x.x:8000` (your machine's LAN IP) |
| Physical device (different network) | Use `npm start` (tunnel) + set to the printed tunnel URL |

---

## 6. Android Dev Client Build (one-time)

> **Why?** This app uses native modules (camera, accelerometer, light sensor, Google Sign-In) that do not work in Expo Go. You need a custom dev client APK installed on the emulator.

You only need to do this once per machine (or when native dependencies change).

### 6.1 Log in to EAS

```bash
npx eas-cli login
```

Use your Expo account that has been invited to the **shoeshopper** org.

### 6.2 Trigger the build

```bash
# From frontend/
npx eas-cli build --profile development --platform android
```

The build takes 10–25 minutes. When it finishes, EAS prints a build page URL.

### 6.3 Install the APK on the emulator

1. Start your Android emulator (Android Studio → Device Manager → Play ▶)
2. Open the EAS build page URL in your browser
3. Click **Download build** to download the `.apk` file
4. **Drag and drop the `.apk` onto the running emulator window**
5. Android will install the app — find it in the app drawer

---

## 7. Daily Development Workflow

You need **two terminals** running simultaneously.

**Terminal 1 — Backend:**

```bash
# From repo root
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
python manage.py runserver 0.0.0.0:8000
```

**Terminal 2 — Frontend:**

```bash
# From frontend/
npx expo start --dev-client
```

Then in the emulator, open the **Shoe Shopper** app. Metro will hot-reload JS changes automatically — no rebuild needed for UI/logic changes.

Press `a` in the Expo terminal to target the Android emulator if the app doesn't open automatically.

---

## 8. Verifying Everything Works

### Backend health check

```bash
curl http://127.0.0.1:8000/api/health/
```

Expected response:

```json
{"status": "ok", "shoe_count": 0}
```

`shoe_count` will be 0 until you seed data or connect to Supabase.

### In-app smoke test

Navigate to **Profile → Backend Smoke Test** in the app. This button hits `/api/health/` and `/api/shoes/` and displays results inline. If it shows a `shoe_count` and a list of brands, your full stack is wired correctly.

### End-to-end measurement test

1. Sign in with Google
2. Go to **Closet → Capture Foot Photo**
3. Follow the on-screen instructions (foot on paper, phone held level)
4. Take and confirm a photo
5. Verify the MeasurementsScreen shows length/width/area values

---

## 9. Troubleshooting

### "Unable to load script" in the emulator

Make sure:
- `npx expo start --dev-client` is running in `frontend/`
- The emulator is started before or while the dev server runs
- `EXPO_PUBLIC_API_URL` is blank for the emulator (not set to `localhost`)

### Backend returns 400 on `/api/foot/measure/`

Roboflow did not detect the paper class in the image. Common causes:
- Poor lighting (the light sensor on the capture screen warns about this)
- Phone tilted more than ~10°
- Paper not fully in frame

See [COMPUTER_VISION.md](./COMPUTER_VISION.md) for more detail.

### `pip install` fails on `psycopg2`

```bash
pip install psycopg2-binary   # use the pre-compiled binary
```

Then re-run `pip install -r backend/requirements.txt`.

### Metro bundler cache issues

```bash
npx expo start --clear
```

### Node module errors after pulling changes

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Django migration errors after pulling changes

```bash
python manage.py migrate
```

If you see `InconsistentMigrationHistory`, you may need to reset your local SQLite database:

```bash
rm db.sqlite3
python manage.py migrate
```

### Port 8000 already in use

```bash
# macOS / Linux
lsof -ti:8000 | xargs kill -9

# Windows PowerShell
netstat -ano | findstr :8000
# Then: taskkill /PID <pid> /F
```
