# AGENTS.md - Shoe Shopper Dev

High-signal working notes for AI coding agents in this repository. Keep this file current when architecture, commands, environment variables, or workflow expectations change.

## Project Overview

Shoe Shopper is a Django REST API plus React Native/Expo mobile app for foot measurement and shoe recommendations.

Core flow:

1. The mobile app signs users in with Google and stores a DRF token in `expo-secure-store`.
2. Users measure a foot with either the paper flow (`expo-camera` + paper reference) or the experimental ARCore flow.
3. The backend sends the captured image to Roboflow, converts detections into inch measurements, and stores a `Measurement`.
4. `GET /api/recommendations/` scores active shoes and available colorways against the user's latest complete measurement.
5. The app renders ranked shoes, colorways, wishlist/owned state, fit details, and feedback screens.

## Repository Map

```text
.
|-- backend/                  Django app: API, models, services, management commands
|   |-- api/                  DRF views, serializers, urls
|   |-- models/__init__.py    All Django models live here
|   |-- services/             Fit, AR measurement, feedback/tolerance logic
|   |-- management/commands/  Shoe sync, seed, audit, and data commands
|   |-- migrations/           Commit migrations with model changes
|   `-- tests/                Current focused Python tests
|-- frontend/                 Expo SDK 54 React Native app
|   |-- App.js                Root navigation, providers, fonts
|   |-- screens/              Screen-level UI and flows
|   |-- components/           Shared UI components
|   |-- services/             Frontend service modules and caches
|   |-- config/api.js         Platform-aware backend base URL
|   |-- *ShoesContext.js      AsyncStorage-backed saved/owned shoe state
|   `-- plugins/withARCore.js Expo config plugin for Android ARCore
|-- shoeshopper/              Django project settings and root URLs
|-- docs/                     Architecture, setup, CV, ARCore, integration plans
|-- ar_debug/                 Generated AR debug images; do not treat as source
|-- media/                    Local uploaded media
|-- manage.py
`-- db.sqlite3                Local dev fallback database
```

## Commands

Run backend commands from the repo root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
python manage.py test
python backend\tests\test_tolerance_learning.py
```

Run frontend commands from `frontend/`:

```powershell
npm install
npm start          # expo start --tunnel
npm run android    # expo start --lan
npm run ios        # expo start --ios
npm run web        # limited; native modules will not work
```

Use two terminals for normal development: Django on port 8000 and Expo/Metro from `frontend/`.

## Environment

Never commit `.env` files or secrets. Backend env is read by `shoeshopper/settings.py`; frontend public env must use `EXPO_PUBLIC_`.

Important backend variables:

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`, `DB_SSLMODE`; blank `DATABASE_URL` uses SQLite
- `GOOGLE_CLIENT_ID`, `GOOGLE_ANDROID_CLIENT_ID`
- `ROBOFLOW_API_KEY`, `ROBOFLOW_WORKSPACE`, `ROBOFLOW_PROJECT`
- `ENABLE_DEV_MOCK_MEASUREMENT`

Important frontend variables:

- `EXPO_PUBLIC_API_URL`
- `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`
- `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT`
- `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` if using Supabase client features

`frontend/app.config.js` loads the repo root `.env` first, then `frontend/.env` with frontend values winning.

## Backend Architecture

- Django app code is under `backend/`; project config is under `shoeshopper/`.
- All API routes are mounted under `/api/` from `backend/api/urls.py`.
- Most view logic is currently in `backend/api/views.py`; put reusable business logic in `backend/services/`.
- All models live in `backend/models/__init__.py`; do not split models into separate files unless the project explicitly changes that convention.
- `REST_FRAMEWORK` defaults to token auth and `IsAuthenticated`; use `AllowAny` only for intentionally public endpoints.
- `FootMeasureView` handles both paper and ARCore measurement methods through `POST /api/foot/measure/`.
- `RecommendationsView` fetches the authenticated user's latest complete measurement, scores active shoes, and includes colorway options.
- Shoe catalog data now includes base shoes, `ShoeSize`, `ShoeColorway`, and `ShoeColorwaySize`; preserve these relationships when editing recommendations or sync commands.

Key endpoints:

```text
GET     /api/health/                  public status + shoe count
GET     /api/shoes/                   public shoe list
POST    /api/auth/google/             exchange Google ID token for DRF token
DELETE  /api/auth/delete/             delete authenticated user
GET/PATCH /api/profile/               read/update display name
POST    /api/foot/measure/            authenticated paper or ARCore measurement
POST    /api/measurements/upload/     simple upload/guest session path
GET     /api/measurements/latest/     latest complete measurement for user
GET     /api/recommendations/         scored shoes for latest measurement
POST    /api/dev/mock-measurement/    authenticated dev-only mock measurement
GET     /api/proxy-image/             limited CDN image proxy
```

Authenticated requests use:

```text
Authorization: Token <key>
```

## Frontend Architecture

- `frontend/App.js` owns root stack navigation, tab navigation, screen registration, font loading, and context providers.
- Main user tabs are Dashboard/Closet, Recommendations, and Profile.
- Measurement screens include paper flow (`FootCaptureScreen.js`, `CameraScreen.js`) and AR flow (`ARFootCaptureScreen.js`, `ARCameraScreen.js`).
- `Dashboard.js`, `Wishlist.js`, `Closet.js`, `RecommendationsScreen.js`, `ProfileScreen.js`, and `feedback.js` are active product surfaces.
- Use `frontend/config/api.js` for backend URLs; do not hard-code localhost or LAN IPs in screens.
- Store auth tokens only in `expo-secure-store` under `authToken`.
- Saved and owned shoe state is AsyncStorage-backed via `SavedShoesContext.js` and `OwnedShoesContext.js`.
- Use `useFocusEffect` for screen data that should refresh when the user returns to a screen.
- Keep frontend network logic in `frontend/services/` when adding new API access; screens should orchestrate UI state rather than own every fetch detail.

## Native App Notes

- The app uses native modules and does not work fully in Expo Go.
- Camera, sensors, Google Sign-In, SecureStore, and ARCore require an Expo dev client or native build.
- Rebuild the dev client when native dependencies, Expo plugins, Android package config, permissions, or ARCore plugin behavior changes.
- Android emulator cameras are unreliable; use `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1` plus the backend mock route for emulator workflows.

## Computer Vision And Fit Logic

- Roboflow workspace/project are expected to point at the `foot-measuring` workflow.
- Paper flow uses a detected paper bounding box for pixels-per-inch and a foot/insole polygon for dimensions.
- ARCore flow sends `measurement_method=arcore` plus `ar_snapshot`; backend validates tracking state and computes dimensions using AR geometry.
- `backend/services/fit_algorithm.py` owns scoring, size estimation, status labels, tolerance profiles, and bias correction constants.
- `backend/services/ar_measurement.py` owns AR unprojection math.
- Tolerance and feedback logic lives in `backend/services/tolerance_learning.py`, `feedback_service.py`, `tolerance_storage.py`, and `backend/tolerances/`.

## Coding Conventions

Backend:

- Prefer small service functions over adding more complex logic to API views.
- Add migrations when models change, and commit the generated migration.
- Keep API response shapes backward-compatible with current frontend consumers unless intentionally updating both sides.
- Use `Decimal` or explicit rounding for persisted inch/price fields where existing code does.
- Avoid network calls in tests; mock Roboflow, Google, and external shoe APIs.

Frontend:

- Use functional components and hooks only.
- Define screen styles with `StyleSheet.create` at the bottom of each screen unless a shared style already exists.
- Match the existing warm neutral palette and Outfit font usage.
- Use `@expo/vector-icons/Ionicons` for icons.
- Use shared empty state styles from `frontend/styles/emptyState.js`.
- Keep large screens from growing further when practical: extract components/services/helpers for new substantial behavior.
- Do not introduce new global state when existing contexts or navigation params are sufficient.

General:

- Keep diffs focused; avoid broad formatting churn.
- Do not modify generated/debug artifacts such as `ar_debug/`, `media/`, audit HTML/JSON, or local SQLite data unless the task explicitly requires it.
- Treat existing uncommitted changes as user work. Do not revert or overwrite unrelated changes.

## Verification

Before finishing a change, run the smallest useful checks:

- Backend model/API/service changes: `python manage.py test` or targeted Python tests.
- Fit/tolerance changes: run `python backend\tests\test_tolerance_learning.py` and add focused tests where practical.
- Migration changes: run `python manage.py makemigrations --check` after generating/committing migrations, then `python manage.py migrate` locally when appropriate.
- Frontend changes: run the relevant Expo command and manually verify the touched screen/flow in a dev client when native modules are involved.
- API contract changes: verify both the backend endpoint and the frontend consumer.

There is no comprehensive automated frontend test suite yet, so record manual verification steps in the final response or PR notes.

## Known Gotchas

- `DATABASE_URL` in the shell overrides `.env`; clear it when switching back to SQLite.
- DRF auth uses `Token`, not `Bearer`.
- Physical device testing often requires adding the machine LAN IP to `DJANGO_ALLOWED_HOSTS` and using `EXPO_PUBLIC_API_URL`.
- Roboflow failures often come from unpublished workflows, missing API keys, poor lighting, no paper detection, bad AR tracking, or image orientation issues.
- Recommendation quality depends heavily on `ShoeSize` insole dimensions and live `ShoeColorwaySize` availability.
- `ProxyImageView` is intentionally limited to specific CDN hosts; do not turn it into an open proxy.
- `DJANGO_DEBUG` defaults to development behavior; be careful when changing settings used in production.

## Documentation To Check

- `README.md` for setup and endpoint overview.
- `docs/ARCHITECTURE.md` for system-level flow.
- `docs/BACKEND.md` and `docs/FRONTEND.md` for deeper implementation notes.
- `docs/COMPUTER_VISION.md` for Roboflow and fit algorithm details.
- `docs/ARCORE_MEASUREMENT_PLAN.md` for ARCore design intent.
- `SECURITY_REVIEW.md` before touching auth, uploads, proxies, tokens, CORS, rate limits, or account deletion.

---

## Git and Branching

- `main` is the stable baseline. Never commit directly to `main`.
- All work goes on a feature branch. Branch names should be descriptive: `feature/colorway-filter`, `fix/ar-measurement-drift`.
- Claude Code uses git worktrees for parallel work. If you see a `.claude/worktrees/` directory, those are isolated Claude sessions — do not modify files inside worktree paths.
- Commit migrations alongside the model changes that require them in the same commit.
- Keep commits focused. One logical change per commit; avoid broad formatting churn mixed with functional changes.
- When done with a task, leave the branch in a clean state (all tests passing, no debug prints, no uncommitted changes) so Claude can review and merge.

---

## Claude + Codex Pipeline

This repo uses a senior/junior AI pipeline:

- **Claude Code (senior)** — architecture decisions, task decomposition, spec writing, code review, merges, and anything touching auth/security/data models.
- **Codex (junior)** — implements specific, well-scoped tasks from specs Claude writes.

### How tasks are handed off

1. Claude writes a task spec at `.claude/tasks/<task-id>.md` with: goal, files to touch, acceptance criteria (testable pass/fail), and explicit out-of-scope boundaries.
2. Codex picks up the spec: `codex "implement the task described in .claude/tasks/<task-id>.md"`
3. Codex works on a dedicated branch named after the task id (e.g. `codex/task-001-colorway-filter`).
4. When complete, Codex leaves the branch clean and signals done via a commit message starting with `[codex-done]`.
5. Claude reviews the diff, approves, or writes a follow-up correction spec.

### Rules for Codex

- Only touch files listed in the task spec's scope section.
- Do not modify `AGENTS.md`, `CLAUDE.md`, migrations outside the task scope, or anything in `ar_debug/` / `media/`.
- If a task requires a model change, write the migration and include it — do not leave schema changes unmigrated.
- If you hit an ambiguity that the spec doesn't cover, make the conservative choice and note it in the commit message rather than guessing broadly.
- Run the verification steps from the **Verification** section above before marking a task done.
