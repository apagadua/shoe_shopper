# Integration Plan — Merging All Branches into Main

Last updated: 2026-04-26

> **Status (June 2026):** This merge is **complete** on `main`. Screen renames below (`Dashboard`, `Wishlist`, `Closet`, AR screens, `feedback.js`) are live. Keep this document for historical reference only — do not follow the step-by-step merge instructions unless reviving a similar integration.

---

## Goal

Merge all active feature branches into a single `integration` branch, resolve conflicts, then open one PR from `integration` → `main`.

---

## Branch Status Summary

### Dead / Already Subsumed — do NOT merge these

| Branch | Reason |
|---|---|
| `KicksDB` | All 4 commits fully contained inside `origin/FeedbackPage` |
| `origin/UpdateRecWishOwnedPages` | Subset of `origin/FeedbackPage` (7 of 9 commits) |
| `uploadPicture` | Subset of `feature/arcore-measurement` (same commits minus ARCore) |
| `origin/tanvi/backend-expodev` | 0 commits ahead of main |
| `origin/try-backend-with-gyro` | 0 commits ahead of main |
| `origin/tanvi/backend` | 1 very early initial commit, fully superseded |

### Backup Branches (WIP saves — do NOT merge, just reference if needed)

| Branch | Contents |
|---|---|
| `stash/main-wip` | Former stash@{0} — WIP on main: serializers, views, models, frontend screens |
| `stash/orsbranch-wip` | Former stash@{1} — WIP on OrsBranch: views, camera, screens, settings |

### Active — merge these in order

| # | Branch | Commits ahead of main | What it adds |
|---|---|---|---|
| 1 | `origin/FeedbackPage` | 9 | Fit algorithm, recommendations API, saved shoes context, closet/wishlist/owned screens, fit feedback UI with sliders, shoe size/price on cards |
| 2 | `origin/UserFeedbackLoop` | 9 | Backend tolerance learning: `feedback_service.py`, `tolerance_learning.py`, `supabase_client.py`, retrain task, test suite |
| 3 | `tanvi/photos-in-backend` | 1 unique commit (`58838e1`) | Image handling in backend — cherry-pick only this one commit |
| 4 | `feature/arcore-measurement` | 7 | ARCore native foot measurement module, GL renderer, backend math, management commands, docs |

---

## Conflict Hotspots

These files are touched by multiple branches and will need manual resolution:

| File | Touched by |
|---|---|
| `backend/api/views.py` | FeedbackPage, UserFeedbackLoop, tanvi/photos-in-backend, arcore |
| `backend/api/serializers.py` | FeedbackPage, tanvi/photos-in-backend |
| `backend/api/urls.py` | FeedbackPage, UserFeedbackLoop |
| `backend/models/__init__.py` | FeedbackPage, arcore |
| `backend/services/__init__.py` | FeedbackPage + UserFeedbackLoop |
| `backend/services/fit_algorithm.py` | FeedbackPage + UserFeedbackLoop |
| `shoeshopper/settings.py` | FeedbackPage + UserFeedbackLoop + arcore |
| `shoeshopper/urls.py` | tanvi/photos-in-backend only (additive — no conflict expected, just verify) |
| `frontend/App.js` | FeedbackPage (renames screens) + arcore (adds AR screens) |
| `frontend/screens/RecommendationsScreen.js` | FeedbackPage (major rewrite) |
| `frontend/screens/CameraScreen.js` | FeedbackPage + tanvi + arcore |
| `backend/migrations/` | FeedbackPage adds `0003`+`0004`; arcore adds `0003`–`0008` — **see migration note below** |

---

## ⚠️ Known Hard Problem: Migration Number Collision

This is the trickiest part of the integration and must be handled carefully in Step 5.

**What happened:**
- `main` currently has migrations `0001` and `0002`.
- `FeedbackPage` adds `0003_toebox_fields` and `0004_repair_shoe_columns`.
- `feature/arcore-measurement` (branched from older code) also adds `0003_toebox_fields` (identical file — no problem) but then adds `0004_kicks_fields` through `0008_measurement_method`.

After merging FeedbackPage, the migration chain is:
```
0001 → 0002 → 0003_toebox_fields → 0004_repair_shoe_columns
```

When arcore is then merged, `0004_kicks_fields.py` will file-conflict with `0004_repair_shoe_columns.py`. Even after resolving the file conflict, Django will see a **fork** in the migration graph (two migrations both depending on `0003_toebox_fields`) and refuse to migrate.

**Resolution (do this immediately after merging arcore in Step 5):**

1. Keep `0003_toebox_fields.py` as-is (both branches have the identical file).
2. Keep `0004_repair_shoe_columns.py` as-is.
3. Rename arcore's chain so it continues from `0004_repair_shoe_columns`:

| Old filename | New filename | Update `dependencies` to |
|---|---|---|
| `0004_kicks_fields.py` | `0005_kicks_fields.py` | `("backend", "0004_repair_shoe_columns")` |
| `0005_insole_to_shoesize.py` | `0006_insole_to_shoesize.py` | `("backend", "0005_kicks_fields")` |
| `0006_shoe_is_active.py` | `0007_shoe_is_active.py` | `("backend", "0006_insole_to_shoesize")` |
| `0007_shoe_colorway_models.py` | `0008_shoe_colorway_models.py` | `("backend", "0007_shoe_is_active")` |
| `0008_measurement_method.py` | `0009_measurement_method.py` | `("backend", "0008_shoe_colorway_models")` |

In each renamed file, update the `dependencies` list to point to its new predecessor (column 3 above). The `operations` blocks are untouched.

After renaming, run `python manage.py migrate --run-syncdb` locally to verify the chain is linear.

---

## ⚠️ Known Hard Problem: App.js Screen Renames

FeedbackPage renamed several screens that arcore still references by their old names. When merging arcore onto FeedbackPage, `App.js` will conflict. The arcore diff was made against the old `main` before FeedbackPage landed, so its import lines reference the pre-rename filenames.

**FeedbackPage renames:**
| Old (main / arcore) | New (FeedbackPage) |
|---|---|
| `ClosetScreen` from `./screens/ClosetScreen` | `Dashboard` from `./screens/Dashboard` |
| `SavedShoesScreen` from `./screens/SavedShoesScreen` | `Wishlist` from `./screens/Wishlist` |
| `OwnedShoesScreen` from `./screens/OwnedShoesScreen` | `Closet` from `./screens/Closet` |

FeedbackPage also adds `FeedbackScreen`, `SavedShoesProvider`, and `OwnedShoesContext` providers.
Arcore adds `ARFootCaptureScreen` and `ARCameraScreen` with two new stack entries.

**Resolution strategy for App.js conflict:** Start from FeedbackPage's version (the more complete rewrite), then add arcore's two new `import` lines and two new `<ClosetStack.Screen>` entries on top of it. Do NOT reintroduce the old `ClosetScreen`/`SavedShoesScreen`/`OwnedShoesScreen` names.

---

## Step-by-Step Merge Plan

### Step 0 — Pull latest main

```bash
git checkout main
git pull
```

main is currently 1 commit behind origin/main (`0bac69e — Document frontend setup and style guide`). Pull this before branching.

### Step 1 — Create integration branch

```bash
git checkout main
git pull
git checkout -b integration
git push -u origin integration
```

### Step 2 — Merge origin/FeedbackPage

```bash
git merge origin/FeedbackPage
```

**Expected conflicts:** `views.py`, `serializers.py`, `models/__init__.py`, `settings.py`, `RecommendationsScreen.js`, `CameraScreen.js`, `fit_algorithm.py`

**Resolution strategy:** FeedbackPage's versions are the most complete frontend. Keep its screen logic and API wiring. Where conflicts arise with main's current state, prefer FeedbackPage — it builds on and extends everything already in main.

**App.js note:** FeedbackPage renames `ClosetScreen`→`Dashboard`, `SavedShoesScreen`→`Wishlist`, `OwnedShoesScreen`→`Closet` and wraps the app in provider components. Accept these renames — they carry through to all later steps.

### Step 3 — Merge origin/UserFeedbackLoop

```bash
git merge origin/UserFeedbackLoop
```

**Expected conflicts:** `backend/services/__init__.py`, `backend/services/fit_algorithm.py`, `shoeshopper/settings.py`

**Resolution strategy:** UserFeedbackLoop adds entirely new files (`feedback_service.py`, `tolerance_learning.py`, `supabase_client.py`, `retrain.py`). Conflicts are mostly in `__init__.py` (import additions) and `settings.py` (new config keys). Combine both sets of additions — nothing should need to be discarded.

**Cleanup:** UserFeedbackLoop accidentally committed a `diff.txt` file at the repo root. Delete it before committing:
```bash
rm diff.txt
git rm diff.txt
```

### Step 4 — Cherry-pick tanvi/photos-in-backend unique commit

```bash
git cherry-pick 58838e1
```

Only 1 commit is unique to this branch (image handling in backend). Cherry-pick is cleaner than a full merge since the other 3 commits on that branch are already present via other merges.

This commit touches: `backend/api/serializers.py`, `backend/api/urls.py`, `backend/api/views.py`, `frontend/screens/CameraScreen.js`, `shoeshopper/settings.py`, `shoeshopper/urls.py`.

**If conflict:** likely in `views.py` or `serializers.py`. Combine image-handling additions with whatever is already there. `shoeshopper/urls.py` is only touched by this commit so it should apply cleanly.

### Step 5 — Merge feature/arcore-measurement

```bash
git merge feature/arcore-measurement
```

**Expected conflicts:** `CameraScreen.js`, `settings.py`, `views.py`, `models/__init__.py`, `App.js`, `backend/migrations/0004_*.py`

**Resolution strategy:**
- **App.js:** See "App.js Screen Renames" section above. Keep FeedbackPage's version plus arcore's two new AR screens.
- **CameraScreen.js:** Keep both the FeedbackPage camera flow AND arcore additions — they serve different purposes (standard photo vs. ARCore live measurement).
- **migrations:** See "Migration Number Collision" section above — renaming is required after this merge resolves.
- **Management commands and `docs/`:** Additive, no conflicts expected.

**After resolving merge conflicts, immediately do the migration renaming described above before committing.**

### Step 6 — Final review

- Run `python manage.py migrate --run-syncdb` — verify migration chain is linear and clean
- Run `python manage.py check` — verify Django config is clean
- Review `backend/migrations/` — confirm filenames are sequential 0001–0009 with no gaps or forks
- Review `shoeshopper/settings.py` — confirm all env vars from all branches are present
- Review `frontend/App.js` — confirm all screens are registered (Dashboard, Wishlist, Closet, FeedbackScreen, ARFootCaptureScreen, ARCameraScreen)
- Smoke-test key API endpoints if possible

### Step 7 — Push and open PR

```bash
git push origin integration
# Then open PR: integration → main on GitHub
```

---

## Key Files to Verify After Integration

- `backend/models/__init__.py` — all models intact, no duplicate fields
- `backend/migrations/` — linear chain 0001→0009, no forks or gaps
- `backend/services/fit_algorithm.py` — tolerance profiles and scoring logic combined correctly
- `frontend/App.js` — navigation tree includes all screens from all branches; no old screen names
- `shoeshopper/settings.py` — all required env vars documented and present
- `frontend/screens/CameraScreen.js` — standard capture flow works alongside ARCore screen

---

## Notes

- The `stash/main-wip` and `stash/orsbranch-wip` branches on GitHub are safety backups only. Review them after integration to check if any work wasn't captured by the 4 active branches.
- `payload.json` and `queue.json` are in `.gitignore` — runtime sync data, never commit.
- `db.sqlite3` is already in `.gitignore` — use only for local dev.
- All branches were fully pushed to GitHub before starting integration. No local-only work exists.
