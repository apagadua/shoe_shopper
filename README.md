# Shoe Shopper

A mobile app that uses computer vision to measure your foot from a photo and recommend shoes that fit. You place your foot on a standard sheet of paper, take a photo in-app, and the backend runs AI inference to extract your foot dimensions. Those measurements drive personalized shoe recommendations.

---

## How It Works

1. Sign in with Google
2. Go to **Closet → Capture Foot Photo**
3. Place your foot on an A4 or Letter sheet of paper and take a photo
4. The app measures your foot (length, width, area) in inches
5. Go to **Recommendations** to see shoes scored and ranked for your foot shape

---

## Project Structure

```
shoe_shopper_dev/
├── backend/          # Django REST API
├── frontend/         # React Native (Expo) app
├── shoeshopper/      # Django project settings
├── manage.py
└── .env              # Secrets — never commit this file
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- A Roboflow account with the `foot-measuring` workflow published
- A Google Cloud project with an OAuth 2.0 Web Client ID
- (Optional for prod) A Supabase PostgreSQL database

---

## Backend Setup

### 1. Create and activate a virtual environment

```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Create the `.env` file

Create a file named `.env` in the **repo root** (next to `manage.py`). Never commit this file.

```
# Django core
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Google OAuth (verify ID tokens from the mobile app)
GOOGLE_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com

# Roboflow (foot measurement AI)
ROBOFLOW_API_KEY=your-roboflow-api-key
ROBOFLOW_WORKSPACE=your-roboflow-workspace-slug
ROBOFLOW_PROJECT=your-roboflow-project-slug

# Database — leave blank to use SQLite for local dev
DATABASE_URL=
DB_SSLMODE=require
```

**Database options:**
- Leave `DATABASE_URL` blank → uses `db.sqlite3` locally (fine for development)
- Set `DATABASE_URL` to a full PostgreSQL connection string → uses that database (required for production)
  - Example: `DATABASE_URL=postgresql://user:password@host:5432/dbname`

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Start the server

```bash
python manage.py runserver 0.0.0.0:8000
```

The API will be available at `http://localhost:8000/api/`.

---

## Frontend Setup

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Create the frontend environment file

Create a file named `.env` inside the `frontend/` directory.

```
# Override the backend URL (required when testing on a physical device)
# Leave blank when using an Android emulator — it auto-resolves to http://10.0.2.2:8000
EXPO_PUBLIC_API_URL=http://YOUR_MACHINE_LAN_IP:8000

# Google OAuth client ID for the mobile app
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com
```

**URL guidance:**
| Scenario | Value to use |
|---|---|
| Android emulator | Leave `EXPO_PUBLIC_API_URL` blank (defaults to `http://10.0.2.2:8000`) |
| iOS simulator | Leave blank (defaults to `http://127.0.0.1:8000`) |
| Physical device on same Wi-Fi | Set to your machine's LAN IP, e.g. `http://192.168.1.50:8000` |
| Tunnel mode (`--tunnel`) | Set to the tunnel URL printed by Expo |

### 3. Start the app

> **Important:** This app uses native modules (camera, sensors, Google Sign-In). It will **not** work in Expo Go. You need an EAS dev client build on a real device, or the Android emulator via a dev client.

```bash
# Standard start (tunnel — works on physical devices)
npm start

# Android emulator
npm run android

# iOS simulator
npm run ios
```

To build a dev client (needed for native modules on a real device):

```bash
npx eas-cli build --profile development --platform android
npx expo start --dev-client
```

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health/` | None | Status check + shoe count |
| GET | `/api/shoes/` | None | List all shoes |
| POST | `/api/auth/google/` | None | Exchange Google ID token → auth token |
| DELETE | `/api/auth/delete/` | Token | Delete authenticated user account |
| POST | `/api/foot/measure/` | Optional | Upload foot photo → measurements in inches |
| GET | `/api/measurements/latest/` | Token | Get user's most recent measurement |
| GET | `/api/recommendations/` | Token | Score all shoes against latest measurement |

All authenticated requests require the header:
```
Authorization: Token <your-token>
```

---

## Environment Variables Reference

### Backend (`.env` in repo root)

| Variable | Required | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes (prod) | Django secret key — any long random string |
| `DJANGO_DEBUG` | No | Set to `1` for debug mode, `0` for production |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated list of allowed hostnames |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth Web Client ID for token verification |
| `ROBOFLOW_API_KEY` | Yes | Your Roboflow API key |
| `ROBOFLOW_WORKSPACE` | Yes | Roboflow workspace slug |
| `ROBOFLOW_PROJECT` | Yes | Roboflow project slug |
| `DATABASE_URL` | No | Full PostgreSQL URL — omit to use SQLite |
| `DB_SSLMODE` | No | SSL mode for PostgreSQL, default `require` |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | No | Backend URL override — needed for physical devices |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Yes | Google OAuth client ID for the mobile sign-in flow |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 + Django REST Framework |
| Database | SQLite (dev) / PostgreSQL via Supabase (prod) |
| Auth | Google Sign-In + DRF Token Auth |
| AI / CV | Roboflow (foot measurement inference) |
| Frontend | React Native + Expo SDK 54 |
| Navigation | React Navigation (Stack + Bottom Tabs) |
