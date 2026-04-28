# Backend — Shoe Shopper

Deep dive into the Django REST API: project layout, models, endpoints, serializers, and services.

---

## Table of Contents

1. [Project Layout](#1-project-layout)
2. [Django Configuration](#2-django-configuration)
3. [Database Models](#3-database-models)
4. [API Endpoints](#4-api-endpoints)
5. [Serializers](#5-serializers)
6. [Services](#6-services)
7. [Environment Variables](#7-environment-variables)
8. [Running Locally](#8-running-locally)
9. [Management Commands](#9-management-commands)
10. [Python Dependencies](#10-python-dependencies)

---

## 1. Project Layout

```
shoe_shopper_dev/          ← repo root (also Django project root)
├── manage.py
├── .env                   ← secrets — never commit
├── shoeshopper/           ← Django project config
│   ├── settings.py        ← all settings, reads from .env
│   ├── urls.py            ← mounts /api/ → backend/api/urls.py
│   ├── asgi.py
│   └── wsgi.py
└── backend/               ← the single Django app
    ├── api/
    │   ├── views.py       ← all 7 API view classes
    │   ├── urls.py        ← URL patterns for /api/
    │   └── serializers.py ← 3 DRF serializer classes
    ├── models/
    │   └── __init__.py    ← all 8 models defined here (do not split)
    ├── services/
    │   └── fit_algorithm.py  ← shoe scoring engine (see COMPUTER_VISION.md)
    ├── migrations/        ← auto-generated, always commit
    ├── management/
    │   └── commands/
    │       └── seed_demo_data.py
    ├── utils/             ← placeholder (empty)
    ├── roboflow/          ← placeholder (empty; Roboflow logic is in views.py)
    ├── requirements.txt
    ├── admin.py
    └── apps.py
```

---

## 2. Django Configuration

**File:** `shoeshopper/settings.py`

Key settings and where they come from:

| Setting | Source | Notes |
|---|---|---|
| `SECRET_KEY` | `DJANGO_SECRET_KEY` env var | Required in production |
| `DEBUG` | `DJANGO_DEBUG` env var | Defaults to `"1"` — **set to `"0"` in production** |
| `ALLOWED_HOSTS` | `DJANGO_ALLOWED_HOSTS` env var | CSV string; defaults to `127.0.0.1,localhost` |
| `DATABASES` | `DATABASE_URL` env var | Blank → SQLite; set for PostgreSQL |
| `REST_FRAMEWORK` auth | — | `TokenAuthentication` + `IsAuthenticated` by default |

**URL routing** (`shoeshopper/urls.py`):

```python
/api/   →   backend.api.urls
/admin/ →   Django admin
```

---

## 3. Database Models

All models live in `backend/models/__init__.py`. Do not create separate model files — keep everything in this one file.

### Profile

Extends Django's built-in `User` with a 1-to-1 relationship.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOneField(User) | Primary relation |
| `display_name` | TextField | nullable |
| `avatar_url` | TextField | nullable |
| `created_at` / `updated_at` | DateTimeField | auto-managed |

### GuestSession

Tracks anonymous usage sessions (not currently wired in the frontend).

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField | primary key |
| `created_at` / `last_accessed` / `expires_at` | DateTimeField | — |

Index on `expires_at` for expiry lookups.

### Measurement

Stores the result of a foot photo analysis.

| Field | Type | Notes |
|---|---|---|
| `user` | FK(User, null=True) | Mutually exclusive with guest_session |
| `guest_session` | FK(GuestSession, null=True) | — |
| `status` | CharField choices | `uploaded` / `processing` / `complete` / `error` |
| `image_url` | TextField | blank (image not currently stored) |
| `image_width_px` / `image_height_px` | IntegerField | nullable; original image dimensions |
| `length_in` | DecimalField | nullable |
| `width_in` | DecimalField | nullable |
| `toebox_length_in` | DecimalField | nullable |
| `toebox_width_in` | DecimalField | nullable |
| `area_sq_in` | DecimalField | nullable |
| `perimeter_in` | DecimalField | nullable (not currently populated) |
| `paper_type` | CharField choices | `letter` / `a4` |
| `confidence` | DecimalField | Roboflow detection confidence |
| `algorithm_version` | TextField | e.g. `"1.5"` |
| `error_message` | TextField | populated if status=error |
| `created_at` / `updated_at` | DateTimeField | auto-managed |

Constraints: dimensions must be positive. DB-level CHECK enforced that exactly one of `user` / `guest_session` is set.

Indexes: `(user, created_at)`, `(guest_session, created_at)`, `status`.

### Shoe

The shoe catalog. Each row is a shoe model (not a specific size — sizes are in `ShoeSize`).

| Field | Type | Notes |
|---|---|---|
| `brand` | TextField | e.g. `"Nike"` |
| `model` | TextField | e.g. `"Air Zoom Pegasus 40"` |
| `gender` | CharField choices | `women` / `men` / `unisex` / `kids` / `unknown` |
| `function_tags` | ArrayField(TextField) | e.g. `["Athletic", "Running", "Road"]` — see COMPUTER_VISION.md for tag routes |
| `style_tags` | ArrayField(TextField) | e.g. `["sneaker"]` |
| `attributes_json` | JSONField | e.g. `{"waterproof": true, "vegan": false}` |
| `insole_length_in` | DecimalField | inches; used by fit algorithm |
| `insole_width_in` | DecimalField | inches; used by fit algorithm |
| `insole_area_sq_in` | DecimalField | sq inches; nullable |
| `insole_perimeter_in` | DecimalField | inches; nullable |
| `insole_toebox_length_in` | DecimalField | inches; nullable |
| `insole_toebox_width_in` | DecimalField | inches; nullable |
| `toe_shape` | CharField | `round` / `almond` / `chisel` / `pointed` |
| `cap_type` | CharField | `none` / `steel` / `composite` |
| `shoe_image_url` | TextField | nullable |
| `product_url` | TextField | nullable |
| `price_usd` | DecimalField | nullable |
| `created_at` / `updated_at` | DateTimeField | auto-managed |

Indexes: `(brand, model)`, GIN indexes on `function_tags` and `style_tags` for array containment queries.

### ShoeSize

Available sizes for a given shoe.

| Field | Type | Notes |
|---|---|---|
| `shoe` | FK(Shoe) | — |
| `us_size` | DecimalField | e.g. `10.0`, `10.5` |
| `width` | CharField choices | `narrow` / `regular` / `wide` / `extra_wide` |
| `is_available` | BooleanField | `True` = in stock |
| `created_at` | DateTimeField | — |

Unique constraint: `(shoe, us_size, width)`. Index: `(shoe, us_size, width, is_available)`.

### UserCollection

Tracks shoes a user has saved (wishlist) or owns. The model exists but **no frontend screens are wired to it yet** — `SavedShoesScreen` and `OwnedShoesScreen` are stubs.

| Field | Type | Notes |
|---|---|---|
| `user` | FK(User) | — |
| `shoe` | FK(Shoe) | — |
| `type` | CharField choices | `wishlist` / `owned` |
| `size` | TextField | nullable; user-recorded size, e.g. `"10.5W"` |
| `color` | TextField | nullable |
| `notes` | TextField | nullable |
| `created_at` / `updated_at` | DateTimeField | auto-managed |

Unique constraint: `(user, shoe, type)`.

### Recommendation

Persists a recommendation run so results can be replayed or audited.

| Field | Type | Notes |
|---|---|---|
| `user` | FK(User) | — |
| `shoe` | FK(Shoe) | — |
| `measurement` | FK(Measurement, null=True) | — |
| `run_id` | UUIDField | Groups a single run together |
| `rank` | IntegerField | 1 = best match; DB check constraint enforces > 0 |
| `score` | DecimalField | nullable; algorithm produces 0–100 |
| `algorithm_version` | CharField | — |
| `created_at` | DateTimeField | — |

Unique constraint: `(user, run_id, rank)`.

### TrainingImage

Stores foot photo metadata for future ML training.

| Field | Type | Notes |
|---|---|---|
| `user` | FK(User, null=True) | nullable for anonymized data |
| `image_url` | TextField | — |
| `label_json` | JSONField | Roboflow-format annotation |
| `in_dataset` | BooleanField | Whether this image is in a training set |
| `created_at` | DateTimeField | — |

---

## 4. API Endpoints

All endpoints are under `/api/`. Full URL routing lives in `backend/api/urls.py`.

### GET `/api/health/`

- **Auth:** None
- **Response:** `{ "status": "ok", "shoe_count": <int> }`
- **Purpose:** Liveness check + quick inventory count.

---

### GET `/api/shoes/`

- **Auth:** None
- **Response:** Array of shoe objects with nested sizes (see `ShoeSerializer`)
- **Ordering:** `brand`, `model`

---

### POST `/api/auth/google/`

- **Auth:** None
- **Request body:** `{ "id_token": "<Google ID token from mobile app>" }`
- **Flow:**
  1. Verify the ID token against Google's public keys using `google.oauth2.id_token`
  2. Extract `email`, `given_name`, `family_name`, `picture`
  3. `get_or_create` Django User by email
  4. `get_or_create` Profile
  5. `get_or_create` DRF Token
- **Response:** `{ "key": "<DRF auth token>" }`

---

### DELETE `/api/auth/delete/`

- **Auth:** Token required
- **Action:** `request.user.delete()` — cascading hard delete of all user data
- **Response:** 204 No Content
- **Note:** This is permanent and instant. See `SECURITY_REVIEW.md` finding L4 for the planned soft-delete improvement.

---

### POST `/api/foot/measure/`

- **Auth:** Token required
- **Request:** `multipart/form-data` with:
  - `image` — JPEG, PNG, or WebP file (max 10 MB)
  - `paper_size` — `"letter"` or `"a4"` (optional, defaults to `"letter"`)
- **Process:** Sends image to Roboflow, parses predictions, computes foot dimensions. See [`COMPUTER_VISION.md`](./COMPUTER_VISION.md) for the full pipeline.
- **Response:**
  ```json
  {
    "id": 42,
    "length_in": 10.23,
    "width_in": 3.71,
    "toebox_length_in": 2.10,
    "toebox_width_in": 3.45,
    "area_sq_in": 28.4,
    "ppi": 118.5,
    "paper_size": "letter"
  }
  ```
- **Common 400 causes:** Roboflow did not detect the paper class (poor lighting, tilt, paper out of frame).

---

### GET `/api/measurements/latest/`

- **Auth:** Token required
- **Response:** Most recent `COMPLETE` measurement for the authenticated user, or 404.
- **Fields:** `id`, `length_in`, `width_in`, `area_sq_in`, `paper_size`, `created_at`

---

### GET `/api/recommendations/`

- **Auth:** Token required
- **Query params:** `sub_type` (optional) — activity sub-type modifier for the scoring algorithm (e.g. `"marathon"`, `"clay_court"`)
- **Process:**
  1. Fetch user's latest `COMPLETE` measurement
  2. Fetch all `Shoe` objects with `prefetch_related('sizes')`
  3. For each shoe with `insole_length` + `insole_width`: run `score_shoe(foot, shoe_data, sub_type)`
  4. For each shoe without insole data: mark as `UNSCORED`, still estimate size
  5. Sort: scored (descending by score) → UNSCORED → REJECTED
- **Response:**
  ```json
  {
    "measurement_id": 42,
    "algorithm_version": "1.5",
    "has_toebox_data": true,
    "results": [ { ...RecommendationSerializer fields... } ]
  }
  ```

See [`COMPUTER_VISION.md`](./COMPUTER_VISION.md) for scoring details and [`BACKEND.md#5-serializers`](#5-serializers) for the response shape.

---

## 5. Serializers

**File:** `backend/api/serializers.py`

### ShoeSizeSerializer

Fields: `id`, `us_size`, `width`, `is_available`

### ShoeSerializer

Fields: `id`, `brand`, `model`, `gender`, `price_usd`, `shoe_image_url`, `product_url`, `sizes` (nested `ShoeSizeSerializer`, many=True, read_only)

### RecommendationSerializer

Input is a dict (not a model instance) assembled by `RecommendationsView`. Output fields:

| Field | Source |
|---|---|
| `id`, `brand`, `model`, `gender`, `price_usd`, `shoe_image_url`, `product_url` | From `shoe` (Shoe model) |
| `sizes` | Nested ShoeSizeSerializer |
| `function_tags`, `style_tags`, `attributes_json` | From `shoe` |
| `fit_score` | From `fit["total_score"]` |
| `fit_status` | From `fit["status"]` — `PERFECT / GOOD / ACCEPTABLE / MARGINAL / POOR / REJECTED / UNSCORED` |
| `fit_status_label` | Human-readable label |
| `fit_profile` | Tolerance profile used (e.g. `ROAD_RUNNING`) |
| `fit_flags` | Array of descriptive flags (e.g. `["SPORT_TIGHT_FIT"]`) |
| `fit_dimensions` | Per-dimension breakdown: clearance, zone, points |
| `reject_reason` | Populated when `fit_status == REJECTED` |
| `recommended_size` | Closest available size to `estimated_us_size` |
| `estimated_us_size` | Brannock formula result |

---

## 6. Services

### `backend/services/fit_algorithm.py`

The shoe scoring engine. See [`COMPUTER_VISION.md`](./COMPUTER_VISION.md) for a full walkthrough. Briefly:

- `score_shoe(foot_data, shoe_data, sub_type=None)` → returns a fit dict
- `estimate_us_size(length_in, gender)` → returns a float (Brannock formula)
- Shoes are scored 0–100 with possible hard-reject outcomes

---

## 7. Environment Variables

Stored in `.env` at the repo root. Never commit this file.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes (prod) | — | Django secret key |
| `DJANGO_DEBUG` | No | `"1"` | `"1"` = debug on, `"0"` = off. **Must be `"0"` in production.** |
| `DJANGO_ALLOWED_HOSTS` | No | `"127.0.0.1,localhost"` | Comma-separated hostnames |
| `GOOGLE_CLIENT_ID` | Yes | — | Google OAuth Web Client ID |
| `ROBOFLOW_API_KEY` | Yes | — | Roboflow API key |
| `ROBOFLOW_WORKSPACE` | Yes | `""` (empty) | Roboflow workspace slug (set to `armaanai`) |
| `ROBOFLOW_PROJECT` | Yes | `""` (empty) | Roboflow project slug (set to `foot-measuring`) |
| `DATABASE_URL` | No | — | PostgreSQL URL; blank = SQLite |
| `DB_SSLMODE` | No | `require` | SSL mode for PostgreSQL |

---

## 8. Running Locally

```bash
# From repo root, with venv active
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

For Windows PowerShell with explicit environment variables (useful when switching between SQLite and Supabase):

```powershell
$env:DATABASE_URL = 'postgresql://...'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'
python manage.py runserver 0.0.0.0:8000
```

---

## 9. Management Commands

### `seed_demo_data`

Populates the database with sample shoes and sizes for local testing.

```bash
python manage.py seed_demo_data
```

---

## 10. Python Dependencies

**File:** `backend/requirements.txt`

| Package | Purpose |
|---|---|
| `django` | Web framework |
| `djangorestframework` | REST API |
| `psycopg2-binary` | PostgreSQL driver |
| `python-dotenv` | Load `.env` file |
| `google-auth` | Verify Google ID tokens |
| `requests` | HTTP calls to Roboflow |
| `scikit-learn` | ML utilities (fit algorithm) |
| `joblib` | Model serialization |
| `nltk` | NLP utilities (installed; reserved for future use) |

Note: `DATABASE_URL` is parsed using Python's built-in `urllib.parse.urlparse` — no `dj-database-url` package is required.
