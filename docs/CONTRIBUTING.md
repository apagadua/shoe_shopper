# Contributing — Shoe Shopper

Development workflow, PR process, code conventions, and current known debt to be aware of before writing code.

---

## Table of Contents

1. [Getting Access](#1-getting-access)
2. [Branching Strategy](#2-branching-strategy)
3. [Development Workflow](#3-development-workflow)
4. [Commit Message Style](#4-commit-message-style)
5. [Making a Pull Request](#5-making-a-pull-request)
6. [Code Conventions](#6-code-conventions)
7. [Current Known Debt](#7-current-known-debt)
8. [Secrets Handling](#8-secrets-handling)

---

## 1. Getting Access

Before you can run or contribute to the project, request the following from a teammate:

| Service | What you need |
|---|---|
| **Supabase** | PostgreSQL connection string (`DATABASE_URL`) |
| **Roboflow** | API key + workspace/project slugs |
| **Google Cloud** | OAuth 2.0 Web Client ID |
| **Expo / EAS** | Invite to the **shoeshopper** Expo organization |
| **Git repository** | Write access |

For setup instructions, see [`SETUP.md`](./SETUP.md).

---

## 2. Branching Strategy

```
main          ← stable; all PRs target this branch
OrsBranch     ← current active development branch
feature/*     ← new features (cut from main)
fix/*         ← bug fixes (cut from main)
```

Always cut your branch from the latest `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

---

## 3. Development Workflow

1. **Cut a branch** from `main` (see above)
2. **Make changes** — keep commits focused and atomic
3. **Test your changes** manually (see [Testing](#testing) below)
4. **Push your branch** and open a pull request targeting `main`
5. **Request a review** from at least one teammate
6. **Reviewer tests it on their end** — they must pull your branch and verify it works on their local setup before approving
7. **Merge** only after approval

### Testing

There are no automated tests yet. Before opening a PR, manually verify the flows your change touches:

| Flow | How to test |
|---|---|
| Backend health | `curl http://127.0.0.1:8000/api/health/` |
| Auth | Sign in with Google; confirm token is saved and MainTabs loads |
| Foot measurement | Capture a photo in-app; verify MeasurementsScreen shows values |
| Recommendations | After a measurement, confirm scored results load |
| Wishlist / closet | Heart and bag icons on Recommendations; confirm items appear on Wishlist and My Closet |
| Profile | Edit display name, save, sign out, and return to Welcome |
| Sign out / delete | Verify both flows return to WelcomeScreen cleanly |

If you add a backend service or utility function, write a `django.test.TestCase` in `backend/tests.py` (create the file if it doesn't exist).

---

## 4. Commit Message Style

Use a short imperative prefix followed by a concise description:

```
feat: add waterproof filter to recommendations
fix: handle null measurement on Dashboard
chore: bump expo-camera to 15.0.3
docs: add CONTRIBUTING guide
refactor: extract shoe card into shared component
test: add unit tests for fit_algorithm score_shoe
```

- Subject line: under 72 characters
- Add a body if the "why" isn't obvious from the diff
- Reference issue numbers where applicable: `fix: handle null measurement (#42)`

---

## 5. Making a Pull Request

### Before opening the PR

- [ ] Branch is up to date with `main` (`git rebase main` or `git merge main`)
- [ ] No merge conflict markers in any file (`<<<<<<`, `=======`, `>>>>>>>`)
- [ ] Manually tested the flows affected by your change
- [ ] New environment variables documented in `README.md` and `CLAUDE.md`
- [ ] Database migrations committed if models changed

### PR description

Include:
- **What changed** — brief summary of the diff
- **Why** — motivation or issue being solved
- **How to test** — steps for the reviewer to verify it on their end
- **Any new environment variables or migrations required**

### Review process

1. Assign at least one reviewer
2. The reviewer must:
   - Read the diff
   - Pull your branch locally
   - Run the app and test the affected flows on their own machine
   - Leave feedback or approve
3. Address all feedback before merging
4. Merge only after at least one approval

---

## 6. Code Conventions

### Backend (Django / Python)

- **Views** go in `backend/api/views.py`. One class per endpoint, extending `APIView`.
- **Models** all go in `backend/models/__init__.py`. Do not create separate model files.
- **Business logic** belongs in `backend/services/`, not in views.
- **New environment variables** are read in `shoeshopper/settings.py`. Document them in `README.md` and `CLAUDE.md`.
- Use `AllowAny` permission only for genuinely public endpoints. Default to `IsAuthenticated`.
- Auth header format is `Authorization: Token <key>` (DRF format — not `Bearer`).
- Always commit generated migration files with your model changes.

### Frontend (React Native / JavaScript)

- **One screen per file** in `frontend/screens/`.
- **API base URL** is always imported from `frontend/config/api.js` — never hard-code backend URLs.
- **Auth token** is stored and retrieved via `expo-secure-store`. See `CameraScreen.js` for the reference pattern.
- **Wishlist state** comes from `SavedShoesContext`; **owned closet state** from `OwnedShoesContext` — do not maintain duplicate copies in screens.
- **Screen names on disk:** `Dashboard.js`, `Wishlist.js`, `Closet.js` (not the older `ClosetScreen` / `SavedShoesScreen` / `OwnedShoesScreen` names).
- **Platform-specific code** uses `Platform.OS === 'android'` / `'ios'` checks.
- New env vars must be prefixed `EXPO_PUBLIC_` to be accessible in JS.
- Add new empty states using the shared `frontend/styles/emptyState.js` styles.

---

## 7. Current Known Debt

Read this before working on any of the affected areas.

### Frontend gaps

- Wishlist and closet persist in **AsyncStorage only** — not synced to the backend `UserCollection` model yet.
- Fit feedback (`feedback.js`) submits locally; no API persistence yet.
- `frontend/styles/emptyState.js` exists but most screens inline duplicate empty-state styles.

### Open security findings

`SECURITY_REVIEW.md` documents 15 findings (3 high, 7 medium, 5 low). Some have been fixed; the review file tracks current status. Before adding features in affected areas, check whether a related finding should be fixed first:

- **H1** — `DJANGO_DEBUG` defaults to `"1"` in `settings.py`
- **H2** — No rate limiting on `/api/foot/measure/`
- **H3** — ~~No file size or MIME type validation on image upload~~ (fixed: validation now in `FootMeasureView`)
- **M4** — No fetch timeout in frontend requests (can hang indefinitely)
- **M6** — No CORS configuration
- **M7** — DRF tokens never expire

### No automated tests

Zero test coverage exists. New code should include tests where practical; at minimum, don't remove existing logic without manual verification.

### Large screens

`RecommendationsScreen.js` (~1009 lines) and `CameraScreen.js` (~503 lines) have most logic inline. When modifying them, extract helpers rather than making them larger.

---

## 8. Secrets Handling

- **Never commit `.env`** files — both are in `.gitignore`. If you accidentally stage one, unstage it immediately and rotate the exposed keys.
- **Never hard-code secrets** in source files. If you find one, move it to `.env` and open a PR.
- The Supabase connection string and Roboflow API key are shared — treat them like passwords. Do not paste them into Slack messages, commit messages, or issue comments.
- If a key is compromised: rotate it in the service dashboard first, then update the team.
