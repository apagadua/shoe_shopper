# Security & Quality Review — Shoe Shopper Dev

**Reviewed:** 2026-03-11
**Verified by:** 2 independent automated agents
**Status:** Open (unfixed)

---

## Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| High     | 3     | 1     |
| Medium   | 7     | 1     |
| Low      | 5     | 2     |
| **Total**| **15**| **4** |

> Two findings from the initial audit were determined to be **false positives** and are excluded:
> - `.env` committed with secrets — `.env` is in `.gitignore` and not on GitHub
> - Missing permission checks on user resources — both views correctly filter by `request.user`

---

## High Severity

---

### H1 — `DEBUG` defaults to `True` in production

**File:** `shoeshopper/settings.py:8`
**Status:** Open

```python
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
```

**Problem:** If `DJANGO_DEBUG` is unset in a production environment, Django runs in debug mode. Debug mode returns full stack traces — including local variable values, file paths, and settings — directly in HTTP error responses. An attacker who triggers any 500 error gets a detailed map of your server internals. It also disables certain security checks Django normally enforces.

**Fix:** Change the default to `"0"`:
```python
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
```

---

### H2 — No rate limiting on any endpoint

**File:** `shoeshopper/settings.py:107-114`, `backend/api/views.py`
**Status:** Open

No `DEFAULT_THROTTLE_CLASSES` or view-level `throttle_classes` are defined anywhere.

**Problem:**
- `/api/foot/measure/` calls Roboflow on every request — an attacker can drain the entire Roboflow API quota in minutes at no cost to them
- `/api/auth/google/` with no rate limit allows automated token-stuffing attempts
- `/api/recommendations/` runs a scored DB query per call — easy to overload

**Fix:** Add DRF throttling to `settings.py`:
```python
REST_FRAMEWORK = {
    ...
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/hour",
        "user": "100/hour",
    },
}
```
Apply stricter per-view throttling to `/api/foot/measure/`.

---

### H3 — No file size or MIME type validation on image upload

**File:** `backend/api/views.py:84-94`
**Status:** Fixed

File size validation (10 MB max) and MIME type validation (`image/jpeg`, `image/png`, `image/webp`) have been added to `FootMeasureView` before `image_file.read()` is called. Oversized files return 400; invalid MIME types return 415.

---

## Medium Severity

---

### M1 — `sub_type` query param passed to business logic without validation

**File:** `backend/api/views.py:291`
**Status:** Open

```python
sub_type = request.query_params.get("sub_type") or None
# ...
fit = score_shoe(foot, shoe_data, sub_type=sub_type)
```

**Problem:** Any arbitrary string can be passed as `sub_type`. Today the fit algorithm ignores unknown values, but there is no enforcement of that contract. If the parameter is ever used in a DB query, file path, or log entry, this becomes an injection vector. It also creates a maintenance trap — future developers may not realize this is untrusted input.

**Fix:** Validate against an explicit allowlist before use:
```python
VALID_SUB_TYPES = {"half_marathon", "marathon", "trail", ...}
sub_type = request.query_params.get("sub_type") or None
if sub_type and sub_type not in VALID_SUB_TYPES:
    return Response({"detail": "Invalid sub_type"}, status=400)
```

---

### M2 — Error message leaks service topology

**File:** `backend/api/views.py:96-98`
**Status:** Open

```python
return Response(
    {"detail": "Roboflow not configured"},
    status=503,
)
```

**Problem:** This tells any caller that Roboflow is the CV backend. An attacker now knows the specific vendor to target, can look for Roboflow-specific vulnerabilities, try to exhaust the API quota, or hunt for the API key. Error messages in production should never reveal internal dependency names.

**Fix:** Use a generic message for all backend configuration/connectivity errors:
```python
return Response({"detail": "Service temporarily unavailable"}, status=503)
```
Log the specific error server-side instead.

---

### M3 — `0` treated as falsy for measurement values

**File:** `backend/api/views.py:289`
**Status:** Fixed

The check now uses an explicit `is not None` comparison:
```python
raw_area = float(measurement.area_sq_in) if measurement.area_sq_in is not None else None
```

---

### M4 — No fetch timeout in frontend network requests

**Files:** `frontend/screens/CameraScreen.js:123`, `frontend/screens/RecommendationsScreen.js:92`
**Status:** Open

```javascript
const response = await fetch(`${API_BASE_URL}/api/foot/measure/`, {
    method: 'POST',
    headers: { Authorization: `Token ${token}` },
    body: formData,
    // No timeout
});
```

**Problem:** React Native's `fetch` has no built-in timeout. On a slow or dropped connection, these requests hang indefinitely. The loading spinner never stops, the user can't navigate away cleanly, and the camera or UI state may be left in a broken condition with no path to recovery.

**Fix:** Wrap fetch calls with `AbortController`:
```javascript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 30000); // 30s
try {
    const response = await fetch(url, { signal: controller.signal, ...options });
} catch (e) {
    if (e.name === 'AbortError') { /* show timeout message */ }
} finally {
    clearTimeout(timeout);
}
```

---

### M5 — Uploaded image discarded after inference

**File:** `backend/api/views.py:216`
**Status:** Open

```python
measurement = Measurement.objects.create(
    ...
    image_url="",  # Image is not stored
    ...
)
```

**Problem:** The foot image is read, sent to Roboflow, and then discarded. This means:
- No ability to audit why a measurement was incorrect
- No training data accumulation from real user uploads
- Users cannot retrieve their original photo
- Every upload is a permanent data loss

**Fix:** Store the image to a file storage backend (e.g. Supabase Storage, S3) and save the resulting URL in `image_url`.

---

### M6 — No CORS configuration

**File:** `shoeshopper/settings.py`, `backend/requirements.txt`
**Status:** Open

`django-cors-headers` is not installed and no CORS middleware is present in `MIDDLEWARE`.

**Problem:** Without an explicit CORS policy, browser-based clients will be blocked by default. More importantly, there is no defined security boundary — if a web client is added later without this already configured, the temptation is to allow `*` as a quick fix, which is a significant vulnerability.

**Fix:** Install `django-cors-headers`, add to `MIDDLEWARE`, and configure `CORS_ALLOWED_ORIGINS` with the specific frontend origins.

---

### M7 — DRF auth tokens never expire

**File:** `shoeshopper/settings.py:107-114`
**Status:** Open

DRF's built-in `TokenAuthentication` issues static tokens with no expiration date. Once issued via `Token.objects.get_or_create()`, a token is valid indefinitely unless manually deleted.

**Problem:** A stolen token (from a compromised device, leaked log, or network intercept) grants permanent access. There is no "log out everywhere" capability and no forced re-authentication.

**Fix:** Replace DRF's static token auth with `djangorestframework-simplejwt`, which supports short-lived access tokens and refresh tokens. Alternatively, implement periodic token rotation.

---

## Low Severity

---

### L1 — `res.json()` called without try/catch in ProfileScreen

**File:** `frontend/screens/ProfileScreen.js:75-76`
**Status:** Open

```javascript
const healthJson = await healthRes.json();
const shoesJson = await shoesRes.json();
```

**Problem:** If the backend returns an HTML error page instead of JSON (common during deploys, Nginx misconfigs, or 502s from a proxy), `.json()` throws and the screen crashes silently. The outer `catch` block catches it but loses all diagnostic context.

**Fix:** Wrap `.json()` calls in try/catch or check `Content-Type` before parsing.

---

### L2 — Silent failure in `SavedShoesContext`

**File:** `frontend/SavedShoesContext.js`
**Status:** Fixed (OrsBranch version)

The OrsBranch version of the file now logs the error and resets to a clean state:
```javascript
.catch(err => {
    console.error('Failed to load saved shoes:', err);
    setSavedMap({});
});
```
Note: this file still has unresolved merge conflicts. The fix is present in the OrsBranch side.

---

### L3 — No audit logging for sensitive operations

**File:** `backend/api/views.py`
**Status:** Open

No `logging` module is used anywhere in `views.py`. Key events leave no server-side trace:
- User authentication (success and failure)
- Foot image uploads
- Measurement creation
- Account deletion

**Problem:** When something goes wrong in production — a user reports incorrect measurements, suspicious account activity, or data loss — there is zero forensic trail. It becomes impossible to answer "what happened to this account" or "when was this data created and from where."

**Fix:** Add Python's `logging` module and log at appropriate levels for each of the above events.

---

### L4 — Account deletion is an immediate, unrecoverable hard delete

**File:** `backend/api/views.py:382-384`
**Status:** Open

```python
def delete(self, request):
    request.user.delete()  # Cascades to all related records instantly
    return Response(status=204)
```

**Problem:** One API call permanently destroys a user's account and all associated data (measurements, recommendations, saved shoes) with no confirmation, no grace period, and no recovery mechanism. If a token is stolen, an attacker can silently wipe the account.

**Fix:** Implement a soft-delete pattern — mark the account as `pending_deletion` with a timestamp, run a scheduled job to purge after a grace period (e.g. 30 days), and allow reactivation within that window.

---

### L5 — Duplicate field declaration in serializer

**File:** `backend/api/serializers.py`
**Status:** Fixed

The duplicate `attributes_json` field declaration has been removed. Only one declaration remains (line 43).

---

## Remediation Order

Already fixed: ~~H3~~, ~~M3~~, ~~L2~~ (OrsBranch), ~~L5~~

Remaining (in priority order):

1. **H1** — Fix `DEBUG` default (one-line change, zero risk)
2. **H2** — Add rate limiting (protects Roboflow quota and auth endpoint)
3. **M2** — Sanitize error messages
4. **M1** — Validate `sub_type` allowlist
5. **L1** — Add try/catch around `res.json()`
6. **M4** — Add fetch timeouts in frontend
7. **L3** — Add audit logging
8. **M6** — Configure CORS
9. **M5** — Store uploaded images
10. **L4** — Implement soft delete
11. **M7** — Migrate to JWT / token expiry
