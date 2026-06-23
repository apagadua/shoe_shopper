# Shoe Shopper — Backend Reference

> **Audience:** engineers working on the Django backend.
> **Scope:** configuration, request lifecycle, app structure, the view/service
> layers, management commands, external integrations, and security posture.
> The measurement → recommendation walkthrough lives in
> [`END_TO_END_FLOW.md`](./END_TO_END_FLOW.md) and is not repeated here.
>
> Written by reading the source. Where it contradicts older notes, the **code**
> wins (see Appendix B).

---

## 1. Stack & layout

- **Django + DRF**, token auth, `backend` as the single installed app.
- **CV** via Roboflow (HTTP); **color extraction** via Pillow.
- **Two data-access paths** (see §7): the Django ORM (Postgres/SQLite) for the
  main app, and a **separate Supabase client** used only by the
  tolerance/feedback services. Both may point at the same database.

```
shoeshopper/          Django project config (settings, urls, wsgi/asgi)
backend/
  api/                views.py, urls.py, serializers.py   (HTTP layer)
  models/__init__.py  all ORM models (single file by convention)
  services/           fit, AR, tolerance, feedback, color, supabase client
  management/commands/ catalog sync, seed, audit commands
  migrations/         0001–0013
  tests/              ar_measurement, color_extraction, tolerance_learning
```

---

## 2. Configuration (`shoeshopper/settings.py`)

### 2.1 DRF defaults — apply to every view unless overridden

| Setting | Value | Effect |
|---|---|---|
| Authentication | `TokenAuthentication` only | No session auth on the API; header `Authorization: Token <key>` |
| Permission | `IsAuthenticated` | **Auth-by-default**; public views must set `AllowAny` explicitly |
| Throttle | `UserRateThrottle`, `20/min` | Keyed by user id when authenticated, by IP when anonymous |

### 2.2 Database selection (priority order)

1. `DATABASE_URL` set → PostgreSQL (parsed; `sslmode` from `DB_SSLMODE`,
   default `require`). The Supabase prod path.
2. else `DB_HOST` set → PostgreSQL from discrete `DB_*` settings.
3. else → SQLite (`db.sqlite3` in the project root) — the dev fallback.

> A `DATABASE_URL` exported in the shell overrides the project `.env` — clear it
> to return to SQLite.

### 2.3 Other notable settings

- `DEBUG` (from `DJANGO_DEBUG`) defaults to **True**; set it off in production.
- `ENABLE_DEV_MOCK_MEASUREMENT` gates `/api/dev/mock-measurement/` when debug is
  off.
- `ROBOFLOW_MODEL_ID` must be the **direct segmentation model**
  (e.g. `shoe-shopper/23`). The fallback (`{workspace}/{project}`) points at the
  *workflow*, which filters out `Wall Base` and breaks the AR wall path.
- `LOGGING`: the `backend` logger → console at `INFO`, no propagation.
- **No CORS middleware is installed.** Clients are native apps, so CORS isn't
  needed; a browser client would require adding `django-cors-headers`.
- CSRF middleware is present but irrelevant to token auth (token auth is
  CSRF-exempt).

### 2.4 Environment variables (names only)

Read from the environment at startup. **Names and purposes only — never commit
the values.** The canonical list with examples lives in the project `.env` /
`CLAUDE.md`.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Core Django |
| `DATABASE_URL`, `DB_SSLMODE` (or `DB_HOST`/`DB_NAME`/…) | DB connection |
| `GOOGLE_CLIENT_ID`, `GOOGLE_ANDROID_CLIENT_ID` | Verify Google ID tokens |
| `ROBOFLOW_API_KEY`, `ROBOFLOW_WORKSPACE`, `ROBOFLOW_PROJECT`, `ROBOFLOW_MODEL_ID` | CV inference |
| `ENABLE_DEV_MOCK_MEASUREMENT` | Enable the dev mock route off-debug |
| `SUPABASE_URL`, `SUPABASE_KEY` | Supabase client for feedback/tolerance (separate from the ORM) |

---

## 3. Request lifecycle

```
HTTPS request
  → Django middleware (security, sessions, common, CSRF, auth, messages, clickjacking)
  → shoeshopper/urls.py  →  path("api/", include("backend.api.urls"))
  → DRF APIView: TokenAuthentication → IsAuthenticated (unless AllowAny) → throttle 20/min
  → view method → service functions → ORM (and/or Roboflow / Supabase)
  → JSON Response
```

All API views are class-based `APIView` subclasses in `backend/api/views.py`.

---

## 4. The HTTP layer (`backend/api/`)

### 4.1 Views

| View | Route | Permission | Notes |
|---|---|---|---|
| `HealthView` | `GET /health/` | AllowAny | `{status, shoe_count}` |
| `ShoeListView` | `GET /shoes/` | AllowAny | `prefetch_related("sizes")`, ordered brand/model |
| `GoogleLoginView` | `POST /auth/google/` | AllowAny | Google token → DRF token; creates User+Profile on first login |
| `DeleteAccountView` | `DELETE /auth/delete/` | Token | `request.user.delete()` (cascades) |
| `ProfileView` | `GET/PATCH /profile/` | Token | Display name only; PATCH trims to 200 chars |
| `FootMeasureView` | `POST /foot/measure/` | Token | Validates upload, branches paper vs AR, calls Roboflow + services |
| `MeasurementUploadView` | `POST /measurements/upload/` | AllowAny | Stores image + creates `GuestSession`; **no inference** |
| `LatestMeasurementView` | `GET /measurements/latest/` | Token | Latest `complete` measurement (404 if none) |
| `RecommendationsView` | `GET /recommendations/` | Token | Live-scores all active shoes; reads optional `sub_type` query param |
| `DevMockMeasurementView` | `POST /dev/mock-measurement/` | Token + gated | 404 unless `DEBUG` or `ENABLE_DEV_MOCK_MEASUREMENT` |
| `ProxyImageView` | `GET /proxy-image/` | AllowAny | Host-restricted CDN proxy (`converse.com`, `demandware.static`) |

Upload validation in `FootMeasureView.post` (before branching): ≤ 10 MB, MIME ∈
{jpeg, png, webp}. Measurement/AR internals: `END_TO_END_FLOW.md` §5–6.

### 4.2 Serializers

- `ShoeSerializer` / `ShoeSizeSerializer` — catalog output for `/shoes/`.
- `RecommendationSerializer` — a plain `Serializer` (not ModelSerializer) that
  flattens the `{shoe, fit, colorway_options}` dict from `RecommendationsView`
  into one card object (brand/model, fit score/status/profile, per-dimension
  breakdown, recommended size, colorway options).
- `MeasurementSerializer` / `MeasurementUploadSerializer` — guest upload path.

---

## 5. Models (`backend/models/__init__.py`)

All models live in one file by convention; migrations are committed alongside
changes. Compact reference (full fields in source):

| Model | Role | Key constraints |
|---|---|---|
| `Profile` | 1:1 with `User` | — |
| `GuestSession` | Anonymous owner of guest measurements | UUID pk, `expires_at` |
| `Measurement` | Foot dimensions + status | Owner is user **xor** guest (`chk_measurement_owner`); positive-value checks |
| `Shoe` | Catalog base | `is_active`; GIN indexes on tag arrays; unique `sku`, `kicks_id` |
| `ShoeSize` | Per-size **insole** geometry (scoring inputs) | unique `(shoe, us_size, width)` |
| `ShoeColorway` | Color variant | unique `goat_id`; dominant color + palette |
| `ShoeColorwaySize` | Live price/availability per colorway+size | unique `(colorway, us_size)` |
| `UserCollection` | Wishlist/owned (server side) | unique `(user, shoe, type)` |
| `Recommendation` | Persisted reco runs | unique `(user, run_id, rank)` — **table exists but unused by the live endpoint** |
| `TrainingImage` | ML training data | — |
| `UserFeedback` | Fit feedback (UUID pk) | drives tolerance learning (§6) |
| `ToleranceHistory` | Versioned learned tolerances (`tolerances` table) | one `active` row by convention (no DB constraint) |

> **Schema note:** insole dimensions live on **`ShoeSize`**, not `Shoe`
> (moved in migration 0007). They are the shoe-side inputs to the fit
> algorithm; recommendation quality depends on them plus live
> `ShoeColorwaySize`.

---

## 6. Services (`backend/services/`)

| Module | Purpose | Source |
|---|---|---|
| `fit_algorithm.py` | `score_shoe`, `estimate_us_size`, status labels, tolerance profiles, CV bias constants | pure |
| `ar_measurement.py` | Ray-cast Roboflow points to the floor plane; pairwise + wall-seam math (NumPy) | pure |
| `color_extraction.py` | Derive `dominant_color_hex` + palette from a colorway image (Pillow); neutral vs accent share thresholds | fetches image |
| `tolerance_learning.py` | Severity-weighted feedback → width/length signals → shifted tolerance bands (`K=0.05`) | pure |
| `feedback_service.py` | Fetch feedback rows newer than a timestamp | **Supabase** |
| `tolerance_storage.py` | Load the single active tolerance set / save a new active version | **Supabase** |
| `supabase_client.py` | `create_client(SUPABASE_URL, SUPABASE_KEY)` singleton | — |

> **Tolerance/feedback loop is built but not wired.** No feedback API endpoint
> exists; the live `score_shoe` uses the **static** profiles in
> `fit_algorithm.py`. `feedback_service`/`tolerance_storage` reach Supabase
> **directly**, bypassing the ORM. See `END_TO_END_FLOW.md` §11.

---

## 7. Data access: two parallel paths

The most important architectural caveat for new contributors:

1. **Django ORM** → Postgres (`DATABASE_URL`) or SQLite. Used by every view,
   model, and catalog command.
2. **Supabase Python client** (`supabase_client.py`) → reached via
   `SUPABASE_URL`/`SUPABASE_KEY`, used **only** by `feedback_service` and
   `tolerance_storage` for the `user_feedback` and `tolerances` tables.

In a Supabase-backed prod deployment both may point at the **same** database,
but through different drivers and credentials — they share no connection
pooling, query logging, or migration awareness. Keep new feedback/tolerance
work on whichever path already owns that table.

---

## 8. Management commands (`backend/management/commands/`)

Catalog/data pipeline (see the `/sync-shoes` skill and `END_TO_END_FLOW.md` §9):

| Command | Purpose |
|---|---|
| `export_shoes_for_sync` | Emit a per-shoe work queue for the browser sync routine; excludes GOAT-managed shoes; routes scrape method (chrome vs pullmd) |
| `apply_shoe_sync` | Apply scraped payload JSON: upsert colorways/sizes, set `Shoe.is_active` by record status (`--dry-run`, `--shoe-id`) |
| `seed_kicks` | Refresh GOAT colorways via the `goat_id` slug (kicks.dev); roll up cheapest available price to the shoe |
| `probe_kicks_api` | Diagnostic probe of the kicks.dev GOAT search endpoint |
| `backfill_colorway_colors` | Populate `dominant_color_hex`/palette via `color_extraction` |
| `show_sync_status` | Human/JSON report of sync state per shoe (`--stale-only`, `--json`); reads via the Django ORM (`Shoe.objects.prefetch_related(...)`) |
| `dev_backfill_shoe_insoles` | **Dev-only:** placeholder insole dims so scoring runs (else everything is `UNSCORED`) |
| `seed_demo_data` | **Dev-only:** idempotent local demo seed |

---

## 9. External integrations

| Service | Used by | Notes |
|---|---|---|
| **Roboflow** | `FootMeasureView` | `POST serverless.roboflow.com/{ROBOFLOW_MODEL_ID}`, `confidence=0.25`, 30 s timeout; returns labeled polygons |
| **Google Identity** | `GoogleLoginView` | `verify_oauth2_token`, 120 s clock skew |
| **Supabase** | tolerance/feedback services | direct client, separate from ORM (catalog commands like `show_sync_status` use the ORM, not this client) |
| **kicks.dev (GOAT)** | `seed_kicks`, `probe_kicks_api` | colorway price/availability refresh |
| **CDN proxy** | `ProxyImageView` | host-restricted to Converse/Demandware; adds browser `Referer` |

---

## 10. Security posture

- **Auth-by-default** (`IsAuthenticated`); public routes opt out explicitly.
- **Rate limiting**: 20 req/min per user/IP globally.
- **Upload hardening**: size cap (10 MB), MIME allow-list, and for AR a 64 KB
  cap on `ar_snapshot` *before* `json.loads`, plus structural validation.
- **Proxy is not open**: `ProxyImageView` rejects URLs outside its host
  allow-list — do not generalize it.
- **`DEBUG` defaults on**; ensure `DJANGO_DEBUG` is off and real
  `DJANGO_SECRET_KEY` / `DJANGO_ALLOWED_HOSTS` are set in production.
- Account deletion is a hard cascade delete.

---

## 11. Tests

`backend/tests/` targets the pure-function services with the most math/edge
cases: `test_ar_measurement.py`, `test_color_extraction.py`,
`test_tolerance_learning.py`. **Verify current status before relying on these —
they are not run in CI.** In particular, `test_tolerance_learning.py` is **stale
against the current `tolerance_learning.py`**: its feedback rows use
`total_score`/`severity` keys (the service now reads `fit_score`/
`severity_rating`) and it calls `compute_tolerances(..., count=1)` (the signature
is now `(..., old_feedback_count, new_feedback_count)`), so it errors as written.
The view layer and Supabase-backed services have no automated tests — verify
those manually.

---

## Appendix A — Key files

| Area | File |
|---|---|
| Settings / URLs | `shoeshopper/settings.py`, `shoeshopper/urls.py`, `backend/api/urls.py` |
| Views / serializers | `backend/api/views.py`, `backend/api/serializers.py` |
| Models | `backend/models/__init__.py` |
| Services | `backend/services/*.py` |
| Commands | `backend/management/commands/*.py` |

## Appendix B — Discrepancies with older notes

1. **Insole dimensions are on `ShoeSize`, not `Shoe`** (migration 0007). The
   prior version of this doc listed them on `Shoe`.
2. **Model/view counts grew**: 12 models and 11 views (colorway, feedback, and
   tolerance models were added). `UserCollection` is real, not a stub.
3. **No CORS middleware** is configured, despite `CLAUDE.md` listing CORS.
4. **`SUPABASE_URL` / `SUPABASE_KEY`** are real backend env vars (used by the
   Supabase client) but are absent from the `CLAUDE.md` env table.
5. **`Recommendation` rows are never written** by the live endpoint; scoring is
   computed per request.
6. **The feedback/tolerance loop is not wired** to any endpoint or live scoring.
