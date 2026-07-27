# Codebase Review — Shoe Shopper Dev

**Reviewed:** 2026-07-06
**Scope:** Full repo — backend (Django/DRF), frontend (React Native/Expo), dependencies, config.
**Relation to prior review:** Builds on `SECURITY_REVIEW.md` (2026-03-11). Status of those findings is re-verified below; new findings are numbered N1+.

---

## Remediation Status (fixed 2026-07-06, same session)

Fixed and verified (302 backend tests passing):

- **H1 + N1** — `DEBUG` now defaults off; server refuses to start on the fallback `SECRET_KEY` when not in debug (pytest exempted; local `.env` got `DJANGO_DEBUG=1` + a generated key)
- **N2** — Google login rejects ID tokens without `email_verified: true`
- **N3** — user lookup keyed on `username` (unique) instead of `email`
- **N11 + N14** — `supabase` + `numpy` added to requirements; scikit-learn/joblib/nltk removed (and uninstalled); `django-allauth` dropped from requirements-minimal; requests→2.32.4, Pillow→11.3.0, google-auth pinned
- **N7** — AR debug images gated behind `DEBUG` or new `AR_DEBUG_IMAGES` env flag
- **N12 + H2 residual** — scoped throttles: `foot_measure` 10/min, `auth` 10/min, `upload` 10/min, `proxy_image` 300/min, default 60/min
- **N4 + N5 (upload path)** — `MeasurementUploadView` now uses Pillow-validated `ImageField`, 10 MB cap, stored extension derived from detected format (never the client filename)
- **N6** — proxy: https-only, redirects refused, 5 MB response cap, `image/*` content-type whitelist, error bodies never relayed
- **N8** — prod security settings block (secure cookies, referrer policy; SSL-redirect/HSTS/proxy-header via env toggles)
- **M1** — `sub_type` validated against `VALID_SUB_TYPES` allowlist (exported from `fit_algorithm.py`)
- **M2** — vendor name removed from client-facing config error; AR failure details no longer echo raw exception text
- **M4 + N13 (partial)** — `frontend/services/http.js` `fetchWithTimeout` wrapper (30s default, 60s uploads) adopted at every API call site; PhotoPreviewScreen json-before-ok bug fixed
- Bonus: `-created_at, -id` deterministic ordering in latest-measurement queries (fixes a real tie-break edge and a flaky test)

## Remediation Status — Batch 2 (fixed 2026-07-07)

Fixed and verified (317 backend tests passing, incl. 15 new; plus a clean-venv install proof that requirements.txt + requirements-dev.txt alone reproduce the full passing suite):

- **M7** — DRF tokens now expire: `ExpiringTokenAuthentication` (`backend/api/authentication.py`) rejects and deletes tokens older than `AUTH_TOKEN_MAX_AGE_DAYS` (env, default 30; `0` disables). Google login rotates an expired token instead of returning a dead key. Frontend `App.js` validates the stored token against `/api/profile/` at boot and clears it on 401 (network errors fall through to the app, so offline start still works).
- **N9** — Roboflow failure logging now records only the exception class + HTTP status; `requests` exception messages embed the full URL including `?api_key=`. (The query-param placement itself is a Roboflow serverless API requirement — key can't move to a header.)
- **N10 (lazy init)** — `supabase_client.py` no longer calls `create_client` at import time; a thread-safe lazy proxy raises a clear `RuntimeError` on first *use* without `SUPABASE_URL`/`SUPABASE_KEY`, so processes that never touch feedback/tolerance services boot fine without Supabase env.
- **N3 (guest sessions)** — new `purge_guest_sessions` management command deletes expired `GuestSession` rows (measurements cascade); supports `--dry-run`. Intended for a cron/scheduled job.
- **CI workflow** — `.github/workflows/ci.yml`: pip-cached install of both requirements files, `pip check`, `manage.py check` (test settings + dummy secret), full pytest run with coverage. Triggers on push to main/OrsBranch and all PRs.
- **N15** — frontend dep prune: removed 9 unused dependencies (`@react-navigation/stack`, `crypto-js`, `expo-auth-session`, `expo-calendar`, `firebase`, `react-hook-form`, `react-native-get-random-values`, `react-native-keyboard-aware-scroll-view`, `uuid`); `@expo/ngrok` moved to devDependencies. `npm install` regenerated the lockfile (−83 packages). Kept `@react-native-community/datetimepicker` (referenced in `app.json` plugins) and `@supabase/supabase-js` (used by `frontend/config/supabase.js`). **Native dependency set changed → dev-client rebuild required.**
- New backend files: `backend/api/authentication.py`, `backend/management/commands/purge_guest_sessions.py`, `backend/requirements-dev.txt`; new tests: `test_authentication.py` (7), `test_purge_guest_sessions.py` (3), `test_supabase_client.py` (5).

Still open (deliberately deferred, with reasons): M5 (store images — privacy call, foot photos), M6 (CORS — no web client exists yet), L4 (soft delete — product decision), N10 residual (Supabase RLS audit — needs dashboard access), P1 (recommendations caching), P2 (pagination — `/api/shoes/` has no frontend consumer today), P3–P4, Django patch-level currency check (needs a network lookup at upgrade time). Frontend changes (App.js boot validation, dep prune) need a manual dev-client smoke test — no jest infra.

---

## Status of March 2026 Findings

| ID | Finding | Status today |
|----|---------|--------------|
| H1 | `DEBUG` defaults to `True` | **Still open** — `settings.py:8` still defaults `DJANGO_DEBUG` to `"1"` |
| H2 | No rate limiting | **Mostly fixed** — `UserRateThrottle 20/min` is now the global default (throttles anon by IP too). But see N12: the flat rate breaks image proxying and is too blunt |
| H3 | No upload validation | Fixed (10 MB + MIME check in `FootMeasureView`) — but MIME check trusts the client header (see N5) and `MeasurementUploadView` got no equivalent fix (see N4) |
| M1 | `sub_type` unvalidated | **Still open** — `views.py:910` |
| M2 | "Roboflow not configured" leaks topology | **Still open** — `views.py:738-741`; also `AR measurement failed: {exc}` leaks raw exception text (`views.py:598,605`) |
| M4 | No frontend fetch timeouts | **Still open** — zero `AbortController`/timeout usage anywhere in `frontend/` |
| M5 | Uploaded image discarded | Still open (`image_url=""`) — partially by design; note the AR path *does* save images, unconditionally, to `ar_debug/` (see N7) |
| M6 | No CORS config | Still open — acceptable while clients are native-only; required before any web client |
| M7 | DRF tokens never expire | **Still open** |
| L1 | `res.json()` without guard | Partially fixed — ProfileScreen now checks `res.ok` first, but `await response.json()` before checking `ok` in `PhotoPreviewScreen.js:69` will throw on non-JSON error pages |
| L3 | No audit logging | Improved — `views.py` now logs extensively (AR flow); auth success/failure and account deletion still unlogged |
| L4 | Hard account delete | **Still open** |

---

## New Findings — Security

### N1 (High) — `SECRET_KEY` falls back to a hardcoded dev value
`shoeshopper/settings.py:7` — `SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")`. If the env var is missing in production, every session/CSRF/password-reset signature is forgeable with a publicly known key. Combined with H1 (DEBUG defaulting on), a mis-provisioned deploy is fully compromised.
**Fix:** fail hard when `DEBUG` is false and the key is unset:
```python
if not DEBUG and SECRET_KEY == "dev-only-secret-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")
```

### N2 (High) — Google login does not check `email_verified`
`views.py:1160` uses `idinfo.get('email')` to find-or-create the account but never checks `idinfo.get('email_verified')`. Google ID tokens can carry unverified emails (Workspace / non-Gmail identities). An attacker who controls a Google identity claiming `victim@example.com` (unverified) gets a valid ID token, and the backend links them to the victim's existing account — full account takeover including measurements and profile.
**Fix:** reject tokens where `email_verified` is not `True`.

### N3 (Medium) — `get_or_create(email=...)` on a non-unique field
`views.py:1168` — Django's `User.email` has no unique constraint. Two concurrent first logins can create duplicate users with the same email; after that, `get_or_create(email=...)` raises `MultipleObjectsReturned` and the account is permanently unable to log in. `transaction.atomic()` does not prevent this (no row to lock on first login).
**Fix:** look up case-insensitively by `username=email` (which *is* unique), or add a unique constraint / use `iexact` + `IntegrityError` retry.

### N4 (Medium) — `MeasurementUploadView` accepts arbitrary anonymous file uploads
`views.py:1230-1264` — `AllowAny`, and `MeasurementUploadSerializer.image` is a plain `FileField`: no size cap, no MIME/content validation, and the stored filename uses the client-supplied extension (`.svg`, `.html`, anything). Files land in `media/measurements/` which Django serves directly under DEBUG → stored-XSS vector; in prod it's disk-exhaustion plus one `GuestSession` + `Measurement` DB row per anonymous request. The only brake is the 20/min/IP throttle.
**Fix:** switch to `ImageField` (Pillow-verifies content), cap size, whitelist extensions to `.jpg/.png/.webp` derived from the *validated* type — or remove the endpoint if the app no longer uses it.

### N5 (Low) — Upload MIME check trusts the client header
`FootMeasureView` validates `image_file.content_type`, which is attacker-controlled. The paper path forwards bytes to Roboflow unopened, so anything survives the check.
**Fix:** open with Pillow (`Image.open` + `verify()`) as the gate for both paths.

### N6 (Medium) — `ProxyImageView` hardening gaps
`views.py:1267-1336` — host allowlist is solid, but:
- `requests.get` follows redirects by default. A redirect on `converse.com` (open-redirect or compromised CDN rule) pivots the proxy to an arbitrary/internal URL. Pass `allow_redirects=False` (or re-validate each hop).
- Plain `http://` is accepted; require `https`.
- `resp.content` buffers the entire upstream body into memory with no size cap — stream and cap (~5 MB).
- Upstream `Content-Type` is passed through verbatim; whitelist `image/*` so the proxy can never serve `text/html` from a compromised upstream.

### N7 (Medium, privacy) — Every AR capture writes the user's foot photo to disk, unconditionally
`views.py:423` — `_save_ar_debug_image()` runs on every AR measurement in all environments, saving the photo labeled with the user ID to `ar_debug/`. That's silent retention of biometric-adjacent user images with no flag, no cleanup, and unbounded disk growth — while the privacy-friendly claim elsewhere is that images are discarded.
**Fix:** gate behind `settings.DEBUG` or an explicit `AR_DEBUG_IMAGES` env flag; document retention.

### N8 (Medium) — Missing production security settings
`settings.py` has none of: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`, `SECURE_REFERRER_POLICY`. Django admin is mounted at `/admin/` with no throttling or 2FA. Add a `if not DEBUG:` block setting these, and consider `django-axes` or IP-restricting admin.

### N9 (Low) — Roboflow API key sent as a URL query parameter
`views.py:748-749` — `params={"api_key": ...}` puts the key in the request line, where upstream proxies/CDN logs can capture it. Roboflow's serverless API accepts this, but if a header-based option exists, prefer it. (The local `logger.info` of `rf_url` is safe — params aren't included.)

### N10 (Info) — Supabase service client
`backend/services/supabase_client.py` calls `create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))` at import time — crashes with an opaque error if unset, and `SUPABASE_KEY` (presumably service-role) is undocumented in CLAUDE.md's env table. Lazy-initialize and document. Frontend `config/supabase.js` correctly uses the anon key — make sure the tables it reads (`shoe`, `shoe_colorway*`) have RLS allowing read-only anon access and nothing else, since `user_feedback`/`tolerances` live in the same project.

---

## New Findings — Correctness / Reliability

### N11 (High for prod deploys) — `supabase` package is imported but not in requirements.txt
`backend/services/supabase_client.py` imports `from supabase import create_client`, and `feedback_service.py` / `tolerance_storage.py` / `tasks/retrain.py` import it transitively. Neither `requirements.txt` nor `requirements-minimal.txt` lists `supabase`. A clean prod install passes until the first feedback/retrain call, then `ImportError`. Tests don't catch it because they stub the module. Similarly `numpy` (used by `ar_measurement.py` and `views.py`) is not pinned — it currently arrives only as a transitive dep of scikit-learn, which is itself unused (N14).
**Fix:** add `supabase` and `numpy` to requirements explicitly.

### N12 (Medium) — Flat 20/min throttle will break the image proxy and normal browsing
The global `UserRateThrottle "20/min"` covers *every* endpoint, including `/api/proxy-image/`. `frontend/utils/resolveImageUrl.js` routes Converse images through the proxy, and RecommendationsScreen renders many cards — more than 20 proxied images/minute is easy to hit, after which images (and every other API call from that user/IP) 429 for the rest of the minute. Dashboard also fires 3 parallel fetches per focus.
**Fix:** use `ScopedRateThrottle`: strict on `foot/measure` (e.g. 10/min) and `auth/google` (e.g. 10/min), generous or exempt on `proxy-image` and read endpoints.

### N13 (Low) — Misc correctness
- `PhotoPreviewScreen.js:69` — `await response.json()` before `response.ok` check throws on HTML error pages (502 from a proxy), masking the real error.
- `LatestMeasurementView` omits `toebox_*` and `measurement_method` fields that the rest of the system now produces/uses — response shape drifted.
- The `Recommendation` model (`run_id`, `rank`, `score`) is never written by `RecommendationsView` — either dead schema or an unimplemented feature; decide which.
- `GuestSession.expires_at` is set but nothing ever purges expired sessions or their cascade of `Measurement` rows.
- CLAUDE.md says `db.sqlite3` is committed; it's actually gitignored and untracked — update the doc.

---

## Dependencies

### N14 (Medium) — Dead heavyweight backend deps; stale pins
`requirements.txt` ships `scikit-learn`, `joblib`, and `nltk` — **none are imported anywhere in `backend/`**. nltk 3.8.1 additionally has a known unsafe-deserialization CVE (CVE-2024-39705). Removing all three shrinks the install and the attack surface (then pin `numpy` directly, per N11). `requirements-minimal.txt` lists `django-allauth`, also unused.

Version notes (verify against advisories before bumping):
- `requests==2.32.3` → 2.32.4+ fixed CVE-2024-47081 (`.netrc` credential leak).
- `Pillow==10.4.0` → 11.x has since shipped security fixes (e.g. 2025 DDS heap overflow); upgrade.
- `Django==6.0.2` → check for the latest 6.0.x security patch and track monthly.
- `google-auth[requests]` is unpinned — pin it for reproducible builds.
- `psycopg2-binary` is not recommended for production (wheel/libpq mismatch issues) — prefer `psycopg[binary]` (v3) or build `psycopg2` from source in the deploy image.

### N15 (Medium) — Frontend bundle bloat: unused dependencies
Imported nowhere under `frontend/` (excluding node_modules): **`firebase`** (very large), `crypto-js`, `expo-calendar`, `expo-auth-session`, `expo-web-browser` (only if unused — verify), `react-hook-form`, `uuid`, `react-native-get-random-values`, `react-native-keyboard-aware-scroll-view`. Also `@expo/ngrok` belongs in `devDependencies`. `@react-native-community/datetimepicker` is referenced in `app.json` plugins — remove from both or keep both, but not half. Pruning these cuts install time, dev-build size, and native-module surface.

---

## Performance

### P1 — RecommendationsView does full-catalog Python scoring per request
Every call loads *all* active shoes with three levels of prefetch (`sizes`, `colorways`, `colorways__sizes`), scores each in Python, builds colorway payloads, sorts, and serializes — no pagination, no caching. Fine at ~10² shoes; degrades linearly and the payload (already needing gzip to shrink 85%) grows with the catalog.
Options, in order of effort: (a) cache the response per `(measurement_id, algorithm_version, sub_type)` — it's fully deterministic — with invalidation on shoe sync; (b) persist results into the existing `Recommendation` model on first compute and serve from there; (c) paginate.

### P2 — `/api/shoes/` is unpaginated
Returns the whole catalog with all sizes. Add DRF pagination before the catalog grows.

### P3 — `_foot_dimensions_px` is O(n²) over polygon vertices
`views.py:104-126` — fine for typical Roboflow polygons (tens to hundreds of points), but a hostile/degenerate polygon with thousands of points burns CPU. Cheap guard: cap accepted polygon size, or use a convex-hull + rotating-calipers approach (O(n log n)).

### P4 — Frontend request behavior
No timeouts (M4), no retry/backoff, and Dashboard/Recommendations refetch on every focus without an if-modified/ETag or short-lived client cache. A tiny `fetchWithTimeout` wrapper module shared by all screens fixes M4 and centralizes auth headers (currently duplicated in ~10 call sites).

---

## Best Practices / Maintainability

- **`views.py` is 1,337 lines**, dominated by AR measurement math and diagnostics. CLAUDE.md's own rule is "prefer service functions over bloating API views" — move `_measure_with_ar`'s geometry/diagnostic body into `backend/services/` and slim the view to request parsing + response shaping.
- **No CI** — no `.github/workflows`. The backend suite is strong (281 tests, ~99% coverage) but only runs when someone remembers. A minimal GitHub Actions workflow running `pytest backend/tests` + `pip check` on PRs would catch things like N11 automatically (a `pip install -r requirements.txt` step would have failed on the missing `supabase` package).
- **No frontend tests** (known) — at minimum add jest + a few pure-logic tests (`resolveImageUrl`, contexts, fit-label mapping).
- **Auth/security events unlogged** — Google login success/failure and account deletion should log user id + IP for forensics (L3 residual).
- **API versioning** — endpoints are unversioned; `algorithm_version` exists for the fit algorithm but not the API contract. Cheap to add `/api/v1/` now, painful later.
- **Env docs drift** — `SUPABASE_URL`/`SUPABASE_KEY` (backend) and `ROBOFLOW_MODEL_ID` are load-bearing but missing from CLAUDE.md's env table.

---

## Prioritized Action List

**Do first (small, high-impact):**
1. Flip `DEBUG` default to off + fail on default `SECRET_KEY` in prod (H1, N1)
2. Check `email_verified` in Google login (N2)
3. Add `supabase` + `numpy` to requirements; delete sklearn/joblib/nltk (N11, N14)
4. Gate `_save_ar_debug_image` behind a flag (N7)
5. Scoped throttles — unbreak the image proxy before it bites (N12)

**Next:**
6. Harden `MeasurementUploadView` or delete it (N4)
7. Proxy: no redirects, https-only, size cap, image/* content-type whitelist (N6)
8. Production security-header block in settings (N8)
9. `fetchWithTimeout` wrapper + fix PhotoPreviewScreen json-before-ok (M4, N13)
10. Dependency bumps: requests, Pillow, Django patch; pin google-auth (N14)

**Planned work:**
11. Token expiry/rotation (M7), soft-delete accounts (L4)
12. Recommendations caching or persistence via `Recommendation` model (P1)
13. CI workflow (pytest + pip check), frontend dep prune (N15)
14. Fix `get_or_create` email race (N3), guest-session purge command, pagination (P2)
