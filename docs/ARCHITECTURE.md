# Architecture — Shoe Shopper

High-level overview of how the system fits together. For deep dives see the sibling docs in this folder.

---

## System Overview

Shoe Shopper is a mobile app + REST API that uses computer vision to measure a user's foot from a photo and recommend shoes that fit.

```
┌──────────────────────────────────────────────────────────────┐
│                     Mobile App (Expo / RN)                   │
│  WelcomeScreen → LoginScreen → Closet → Camera → Results     │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS (REST)
                            │ Authorization: Token <key>
┌───────────────────────────▼──────────────────────────────────┐
│                  Django REST API (port 8000)                  │
│  /api/auth/google/   /api/foot/measure/   /api/recommendations│
└──────────┬──────────────────────┬────────────────────────────┘
           │                      │
  ┌────────▼────────┐    ┌────────▼────────────────────────────┐
  │   PostgreSQL    │    │        Roboflow Inference API        │
  │  (Supabase)     │    │  foot-measuring workflow             │
  │  Users, Shoes,  │    │  → paper bounding box (scale ref)    │
  │  Measurements,  │    │  → foot polygon (dimensions)         │
  │  Recommendations│    └─────────────────────────────────────┘
  └─────────────────┘
```

---

## Repositories & Top-Level Layout

```
shoe_shopper_dev/
├── backend/           Django REST API + business logic
│   ├── api/           Views, serializers, URL routing
│   ├── models/        All 8 database models (single __init__.py)
│   └── services/      Fit algorithm (fit_algorithm.py)
├── frontend/          React Native + Expo SDK 54
│   ├── screens/       10 screens (one file each)
│   ├── services/      auth.js (Google Sign-In)
│   └── config/        api.js (platform-aware base URL)
├── shoeshopper/       Django project config (settings.py, urls.py)
└── manage.py
```

Full directory trees are in [`BACKEND.md`](./BACKEND.md) and [`FRONTEND.md`](./FRONTEND.md).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile framework | React Native 0.81.5 + Expo SDK 54 |
| Navigation | React Navigation (Stack + Bottom Tabs) |
| Backend framework | Django 6.0.2 + Django REST Framework 3.16.1 |
| Auth | Google OAuth 2.0 → DRF Token auth |
| AI / CV | Roboflow (custom `foot-measuring` workflow) |
| Database (dev) | SQLite (`db.sqlite3`) |
| Database (prod) | PostgreSQL via Supabase |
| ML libs | scikit-learn, joblib, nltk |
| Storage (tokens) | expo-secure-store |
| Storage (data) | AsyncStorage (measurements, saved shoes) |
| Camera | expo-camera |
| Sensors | expo-sensors (accelerometer + light sensor) |

---

## Core User Flows

### 1. Foot Measurement Flow

```
User                 Mobile App              Django API           Roboflow
 │                       │                      │                    │
 │  Opens Camera tab      │                      │                    │
 │──────────────────────► │                      │                    │
 │                        │  live feed + tilt    │                    │
 │                        │  detection (≤10°)    │                    │
 │  Taps capture button   │                      │                    │
 │──────────────────────► │                      │                    │
 │                        │  shows preview       │                    │
 │  Confirms photo        │                      │                    │
 │──────────────────────► │                      │                    │
 │                        │  POST /api/foot/measure/                  │
 │                        │  FormData: image + paper_size             │
 │                        │─────────────────────►│                    │
 │                        │                      │  base64 image      │
 │                        │                      │───────────────────►│
 │                        │                      │  predictions JSON  │
 │                        │                      │◄───────────────────│
 │                        │                      │  compute PPI       │
 │                        │                      │  extract dimensions│
 │                        │                      │  save Measurement  │
 │                        │◄─────────────────────│                    │
 │                        │  { length_in,         │                    │
 │                        │    width_in,          │                    │
 │                        │    area_sq_in, ... }  │                    │
 │                        │  store in AsyncStorage│                    │
 │◄──────────────────────-│                      │                    │
 │  MeasurementsScreen     │                      │                    │
```

### 2. Google Auth Flow

```
User            Mobile App              Django API          Google
 │                  │                       │                  │
 │  Taps Sign In     │                       │                  │
 │─────────────────►│                       │                  │
 │                  │  Google Sign-In popup  │                  │
 │                  │──────────────────────────────────────────►│
 │  Picks account   │                       │                  │
 │─────────────────────────────────────────────────────────────►│
 │                  │◄──────────────────────────────────────────│
 │                  │  { idToken }           │                  │
 │                  │  POST /api/auth/google/│                  │
 │                  │  { id_token }          │                  │
 │                  │──────────────────────►│                  │
 │                  │                       │  verify token    │
 │                  │                       │──────────────────►│
 │                  │                       │◄──────────────────│
 │                  │                       │  get-or-create   │
 │                  │                       │  User + Profile  │
 │                  │                       │  get-or-create   │
 │                  │                       │  DRF Token       │
 │                  │◄──────────────────────│                  │
 │                  │  { key: "<token>" }    │                  │
 │                  │  save to SecureStore   │                  │
 │◄─────────────────│                       │                  │
 │  MainTabs        │                       │                  │
```

### 3. Recommendation Flow

```
Mobile App                           Django API
    │                                    │
    │  GET /api/recommendations/          │
    │  Authorization: Token <key>         │
    │────────────────────────────────────►│
    │                                    │  fetch latest Measurement
    │                                    │  fetch all Shoes (+ sizes)
    │                                    │  for each shoe:
    │                                    │    score_shoe(foot, shoe)
    │                                    │    find best available size
    │                                    │  sort: scored (desc) → UNSCORED → REJECTED
    │◄────────────────────────────────────│
    │  { results: [ { shoe, fit,          │
    │    recommended_size, ... }, ... ] } │
    │  render scored cards + filter UI   │
```

---

## Authentication Model

Every user authenticates via Google Sign-In. The backend verifies the Google ID token and issues a DRF Token (opaque string). All subsequent API calls include:

```
Authorization: Token <key>
```

DRF tokens are per-user, stored in the `authtoken_token` table, and do not expire (see `SECURITY_REVIEW.md` finding M7 for the planned fix).

---

## Database Schema (simplified)

```
User (Django built-in)
 └─► Profile (1-to-1)

Measurement ──► User
ShoeSize    ──► Shoe
UserCollection ──► User, Shoe
Recommendation ──► User, Shoe, Measurement
TrainingImage  ──► User (nullable)
GuestSession   (standalone)
```

Full field-level schema is in [`BACKEND.md`](./BACKEND.md).

---

## Environment Boundaries

| Boundary | What crosses it | How secured |
|---|---|---|
| Mobile → Django | REST calls (JSON + FormData) | DRF token header |
| Django → Roboflow | HTTPS POST with base64 image | `ROBOFLOW_API_KEY` env var |
| Django → PostgreSQL | TCP (Supabase) | `DATABASE_URL` + SSL (`DB_SSLMODE=require`) |
| Django → Google | HTTPS token verification | `GOOGLE_CLIENT_ID` env var |
| User → Google | Native OAuth picker | Handled by Google SDK |

---

## Known Architecture Gaps

These are documented more fully in [`SECURITY_REVIEW.md`](../SECURITY_REVIEW.md) and [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md):

- No rate limiting on any endpoint (especially `/api/foot/measure/`)
- No CORS configuration
- DRF auth tokens never expire
- No automated tests (unit or integration)
- `SavedShoesScreen` and `OwnedShoesScreen` are stub placeholders
- No shared component library — UI logic is duplicated across screens
- 6 files have unresolved git merge conflicts (see [`CONTRIBUTING.md`](./CONTRIBUTING.md))
