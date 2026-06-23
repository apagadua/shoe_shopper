# Shoe Shopper — Testing Process

> **Audience:** anyone shipping a change to Shoe Shopper.
> **Scope:** how we test *today* — disciplined, manual, end-to-end verification
> of every changed behavior in **all** plausible scenarios before it is pushed.
> Automated unit/integration tests are a planned complement, not a replacement
> for this process. A few pure-function tests already exist in `backend/tests/`.
>
> Examples and the state inventory are grounded in the actual code; the
> process/checklists are the standard we hold changes to.

---

## 1. Principle

> **A change is not done when the happy path works. It is done when it behaves
> correctly in every state the system can be in — including teardown.**

Most real bugs are not in the feature's main logic; they are at the seams
between **state that lives in different places** (backend rows, the auth token,
local caches, in-memory React context) and across **lifecycle events** (sign
out, account delete, re-login, app relaunch, screen re-focus). So testing means
deliberately moving the system through those states, not just clicking the
feature once.

The wishlist-after-delete bug in §7 is the canonical example: every individual
piece works, but no one exercised *delete account → sign back in*, where local
state and backend state disagree.

---

## 2. The scenario matrix

For any change, walk the relevant axes below and test the **combinations** that
touch your code — not just one value per axis.

| Axis | Values to cover |
|---|---|
| **Identity lifecycle** | signed out · first-time sign-in (new user) · returning sign-in · after sign-out · **after account delete + re-sign-in** (same session *and* fresh launch) · second account on the same device · expired/invalid token |
| **Data state** | no measurement · has measurement · re-measured (new id) · empty catalog · catalog populated · empty wishlist/closet · populated wishlist/closet |
| **Local persistence** | fresh install (empty stores) · existing caches from a prior version · corrupted/oversized cache value |
| **Network** | online · offline · slow · backend 4xx · backend 5xx · request succeeds but returns unexpected shape |
| **Platform / runtime** | Android emulator (mock measurement) · physical Android · iOS · dev client vs Expo Go (native modules differ) |
| **Lifecycle / navigation** | background→foreground · screen blur→focus (triggers `useFocusEffect` refetch) · deep back-stack · rapid double-taps |

You do not need the full Cartesian product. You **do** need every combination
that your changed code can observe. If your function reads the auth token, you
own the whole Identity-lifecycle column.

---

## 3. State inventory — what to check and clear

A change is only fully tested if you verify **every store it touches**, and
confirm teardown clears what it should. Current persistence locations:

| Location | Keys / rows | Cleared on sign-out/delete today? |
|---|---|---|
| `expo-secure-store` | `authToken` | **Yes** (`signOutAndReset`) |
| `AsyncStorage` | `savedShoes` (wishlist) | **No** |
| `AsyncStorage` | `ownedShoes` (closet) | **No** |
| `AsyncStorage` | `rec_cache_v4` (recommendations) | **No** |
| Google session | native Google sign-in | Yes (`GoogleSignin.signOut()`) |
| Backend (cascade) | `Token`, `Measurement`, `UserCollection`, `Profile`, `Recommendation` | **Yes** on account delete (`user.delete()` cascade). Note: `GuestSession` has no user FK and is **not** cascaded. |
| Native (Android) | AR capture temp file | Cleaned via `ARCoreModule.cleanupCaptureFile` after upload/retake |

> **The mismatch in this table is the bug class to watch for.** Backend rows are
> wiped on account delete, but the three `AsyncStorage` keys and the in-memory
> React contexts are not — so the device keeps showing a deleted user's data.

---

## 4. Pre-push checklist (definition of done)

Before pushing any new or changed function:

1. **Map its state.** List every place it reads or writes: backend rows,
   `authToken`, each `AsyncStorage` key, in-memory context, native files.
2. **Exercise full CRUD and its inverse.** Create *and* remove; add to wishlist
   *and* remove; measure *and* re-measure. Confirm the inverse actually undoes
   the state, in every store from step 1.
3. **Exercise teardown.** Sign out, sign back in; delete account, sign in as a
   new user; relaunch the app. Confirm state that *should* be gone is gone, and
   state that *should* persist persists.
4. **Cross-check client vs server.** The UI and the backend must agree (see §6
   for how to inspect each).
5. **Force the unhappy paths.** Offline, backend error, empty data, corrupted
   cache, rapid taps, mid-flow backgrounding.
6. **Both platforms / both data sources** if the code path differs (emulator
   mock vs real camera; paper vs AR; cached vs fresh fetch).
7. **Regression sweep.** Re-run the test scripts for any flow that shares state
   with your change (anything touching auth or `AsyncStorage` touches many).

If any step is impractical to verify manually, say so explicitly in the PR.

---

## 5. Per-flow test scripts

Concrete walk-throughs. Run the ones your change can affect.

### 5.1 Auth lifecycle
1. Fresh install → launch → lands on **Welcome** (no token).
2. Sign in (new Google account) → token stored → **MainTabs**.
3. Kill and relaunch → lands directly on **MainTabs** (token persisted).
4. Sign out → **Welcome**; relaunch → still **Welcome** (token cleared).
5. Sign in again → verify **no stale data** from any prior account (wishlist,
   closet, recommendations, measurements).
6. Delete account → confirm backend rows gone (§6) **and** local state gone.
7. Sign in as a new account on the same device → clean slate.

### 5.2 Foot measurement (paper)
1. No measurement yet → Recommendations shows the "no scan" state.
2. Capture with tilt > 10° → capture blocked.
3. Capture valid → preview → submit → Measurements shows length/width/area.
4. Backend down / Roboflow error → graceful error, no crash, no partial row.
5. Re-measure → new measurement id → Recommendations re-fetches (cache busts).

### 5.3 Foot measurement (AR)
1. Tracking not `TRACKING` → capture rejected with guidance.
2. Camera too close/far (outside 12–35″) → rejected with the right message.
3. Valid capture with/without a wall in frame → result within 3–13″.
4. Retake → previous temp file cleaned; new session starts.

### 5.4 Recommendations + cache
1. First load → spinner → results; re-enter tab → instant from `rec_cache_v4`
   (only when the cached result set is non-empty; an empty cache shows the
   spinner and refetches).
2. Re-measure → returning to tab refetches (measurement id changed).
3. Catalog count changes → refetch (shoe_count changed).
4. Offline with a cache → shows cache; offline without → error state.
5. Filters: function/silhouette/attributes; REJECTED and saved/owned shoes are
   hidden.

### 5.5 Wishlist / Closet
1. Add a shoe to wishlist → appears in Wishlist, hidden from Recommendations.
2. Move to closet → leaves wishlist, appears in closet.
3. Remove → returns to Recommendations.
4. Relaunch → lists persist (AsyncStorage).
5. **Sign out → sign in as a different account → lists MUST be empty** (see §7).

### 5.6 Profile
1. Edit display name → persists after relaunch and matches backend.
2. Sign out and delete account behave as in §5.1 steps 4–7.

---

## 6. Inspecting state while testing

- **Backend rows:** Django admin, `python manage.py shell`, or
  `GET /api/health/` (shoe count) and `GET /api/measurements/latest/`. After an
  account delete, confirm the user's `Measurement` / `UserCollection` / `Token`
  rows are gone.
- **Auth token:** present/absent in `expo-secure-store` under `authToken`
  (drives the Welcome vs MainTabs decision on launch).
- **Local caches:** inspect `AsyncStorage` keys `savedShoes`, `ownedShoes`,
  `rec_cache_v4` (e.g. via a dev log or React Native debugger).
- **Logs:** the backend `backend` logger prints CV/AR diagnostics at `INFO`;
  the AR path also dumps overlay images to `ar_debug/`.

The rule: never trust the UI alone — confirm the underlying store.

---

## 7. Case study — wishlist/closet survive account deletion

**Symptom.** Delete the account, sign in again (new or same Google account); the
Wishlist and Closet still show the previous user's shoes.

**Root cause (verified in code).**
- `SavedShoesContext.js` and `OwnedShoesContext.js` persist to **static**
  `AsyncStorage` keys (`savedShoes`, `ownedShoes`) with **no per-user
  namespacing**, and load once on provider mount.
- `ProfileScreen.signOutAndReset()` clears only the `authToken` and the Google
  session, then resets navigation to **Welcome**. It does **not** clear
  `savedShoes`, `ownedShoes`, or `rec_cache_v4`.
- Both providers wrap the whole app in `App.js`, so the navigation reset does
  **not** unmount them — the in-memory maps survive a sign-out→sign-in within
  the same session, and `AsyncStorage` preserves them across a relaunch.
- Account delete cascades on the **server** (`UserCollection` rows are deleted),
  so backend and device now disagree.

**Scenario that would have caught it.** §4 step 3 (teardown) combined with the
Identity-lifecycle axis value *"after account delete + re-sign-in"* — exactly
the §5.5 step 5 assertion.

**Fix direction (for the implementing change, then re-test this script).**
- Clear `savedShoes`, `ownedShoes`, and `rec_cache_v4` inside `signOutAndReset`
  (and reset the in-memory context state), **or**
- Namespace these keys by user id so a different account never reads another's
  data, **or**
- Make wishlist/closet server-backed via `UserCollection` so deletion is
  authoritative.

**Regression test after the fix.**
1. Account A: save 2 shoes, own 1.
2. Delete account A → sign in as account B → Wishlist and Closet are **empty**.
3. Sign out B → sign in A again → confirm no resurrected data.
4. Relaunch the app between each step and re-verify.

---

## 8. Reporting & tracking

When a scenario fails, capture it so it becomes a permanent check:

- **Title:** the failing scenario in one line (e.g. "wishlist persists after
  account delete + re-sign-in").
- **Repro:** the exact axis values from §2 and steps.
- **Expected vs actual**, with the **state stores** involved (§3).
- **Root cause** once known, and the **regression script** to re-run.

Add the regression script to the relevant §5 flow so future changes re-cover it.

---

## Appendix A — Persistence quick reference

| Store | Key / table | Owner module |
|---|---|---|
| SecureStore | `authToken` | `App.js`, `ProfileScreen`, all authed fetches |
| AsyncStorage | `savedShoes` | `SavedShoesContext.js` |
| AsyncStorage | `ownedShoes` | `OwnedShoesContext.js` |
| AsyncStorage | `rec_cache_v4` | `services/recommendationsCache.js` |
| Backend | `Measurement`, `UserCollection`, `Token`, `Profile`, `GuestSession` | Django ORM |

## Appendix B — Key files

| Area | File |
|---|---|
| Auth teardown | `frontend/screens/ProfileScreen.js` (`signOutAndReset`) |
| Wishlist / closet state | `frontend/SavedShoesContext.js`, `frontend/OwnedShoesContext.js` |
| Recommendations cache | `frontend/services/recommendationsCache.js` |
| Account delete (server) | `backend/api/views.py` (`DeleteAccountView`) |
| Existing pure-function tests | `backend/tests/` |
