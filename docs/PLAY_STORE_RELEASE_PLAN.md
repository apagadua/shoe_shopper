# Google Play Store Release Plan — Shoe Shopper

Plan of record for getting Shoe Shopper from a development build to an approved listing on the Google Play Store. Scoped to Android (Play). iOS / App Store is out of scope and should be planned separately.

This document intentionally does not assign dates or durations. The work is ordered by dependency — earlier sections gate later ones.

---

## 1. Accounts, access, and external services

Everything below must be in place before a production build can be submitted. Capture owners and credentials in the team's secrets store — the Play Console account in particular needs an identifiable legal owner.

| Item | Notes |
|---|---|
| Google Play Console developer account | $25 one-time registration fee. Since late 2023 Google has required identity verification (government ID for personal accounts, D-U-N-S + registration docs for organizations). Personal developer accounts are additionally subject to the closed-testing cohort requirement before production is allowed — see §8. |
| Google Cloud project | Already used for Google Sign-In. The OAuth consent screen, the Android OAuth client (SHA-1 fingerprints), and Play Integrity API all attach to this project. |
| Expo / EAS account | `owner: "shoeshopper"` per [frontend/app.json](../frontend/app.json:3). Confirm team members have build permissions. The EAS project ID is pinned at [frontend/app.json:46](../frontend/app.json:46). |
| Backend hosting provider | See §3. |
| Registered domain | Required for the privacy-policy URL (Play mandates a public URL, not a file upload) and for a stable production API hostname. |
| Supabase project | Already provisioned for production Postgres. Verify tier, connection limits, and backup policy before traffic arrives. |
| Roboflow workspace | `armaanai / foot-measuring`. Confirm the monthly inference quota on the current plan covers expected review + launch traffic. |
| Crash-reporting provider | Not currently wired up. See §2. |

---

## 2. Code readiness (pre-flight)

Gating work. Each item below corresponds to something a Play reviewer is likely to probe, or a bug class we cannot afford to ship.

### 2.1 Android manifest permission audit (blocker)

[frontend/android/app/src/main/AndroidManifest.xml](../frontend/android/app/src/main/AndroidManifest.xml) currently declares permissions the app does not use:

- `READ_CALENDAR`, `WRITE_CALENDAR`
- `RECORD_AUDIO`
- `SYSTEM_ALERT_WINDOW` (draw-over-other-apps — a sensitive permission)
- `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE` (legacy; on API 33+ these are replaced by scoped storage / `READ_MEDIA_IMAGES`)

These almost certainly come from transitive Expo modules or leftover Android defaults. Each unnecessary permission is an independent rejection risk: Play's automated checks flag sensitive permissions that do not match declared functionality, and `SYSTEM_ALERT_WINDOW` in particular requires a dedicated in-policy justification.

Action: audit the dependency tree, remove unused modules (e.g. `@react-native-community/datetimepicker` pulls calendar permissions on some setups), and explicitly strip residual permissions via an Expo config plugin or by editing the prebuilt manifest. Verify the final AAB with `aapt2 dump permissions` before submission.

### 2.2 Django production hardening (blocker)

[shoeshopper/settings.py:8](../shoeshopper/settings.py#L8) defaults `DEBUG` to `True` when `DJANGO_DEBUG` is unset. [shoeshopper/settings.py:9](../shoeshopper/settings.py#L9) defaults `ALLOWED_HOSTS` to localhost only. [shoeshopper/settings.py:7](../shoeshopper/settings.py#L7) uses a fallback `SECRET_KEY` literal.

For production:

- `DJANGO_DEBUG=0` must be explicitly set. Consider inverting the default to `"0"` so a missing env var fails closed rather than leaking stack traces.
- `DJANGO_SECRET_KEY` must be set to a strong random value. Remove the `"dev-only-secret-key"` fallback or raise on missing value in production.
- `DJANGO_ALLOWED_HOSTS` must include only the production hostname.
- Add `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_HSTS_SECONDS` (start with a small value, raise after verification), `SECURE_PROXY_SSL_HEADER` if behind a TLS-terminating proxy.
- Install and configure structured logging.

### 2.3 Remove debug surface from ProfileScreen (blocker)

[frontend/screens/ProfileScreen.js:137-148](../frontend/screens/ProfileScreen.js#L137) renders a visible "Backend Smoke Test" card that prints `API_BASE_URL`, status, and shoe previews. This is production-visible today. Gate behind `__DEV__` or remove for production builds.

### 2.4 OwnedShoesScreen is a stub (blocker)

[frontend/screens/OwnedShoesScreen.js](../frontend/screens/OwnedShoesScreen.js) renders an empty state with no data binding. Either implement real functionality or remove the entry point from navigation for v1. Reviewers reject apps with non-functional features reachable from the UI.

(Note: `SavedShoesScreen` is real and works — the original plan flagged it incorrectly.)

### 2.5 Account deletion verification

[backend/api/views.py](../backend/api/views.py) (`DeleteAccountView`) calls `request.user.delete()`. The Django ORM cascades through `on_delete=models.CASCADE` on `Measurement`, `UserCollection`, `Recommendation`, and `Profile` as defined in [backend/models/__init__.py](../backend/models/__init__.py), so related rows are removed.

Action: write an integration test that creates a user with rows in every user-linked table, calls the endpoint, and asserts zero orphan rows. Play now enforces in-app account deletion and cross-checks it against the URL we supply in the store listing — it must actually work.

### 2.6 Foot photo retention (documentation, not code)

The `/api/foot/measure/` handler in [backend/api/views.py](../backend/api/views.py) explicitly sets `image_url=""` after processing. Photos are not retained on disk or in the DB. This is a favorable posture for the Data safety form (§6.1) — but confirm it is also true of any logging or error-capture paths before declaring it publicly. If Sentry/crash reporting is added (§2.8), ensure request bodies containing image uploads are scrubbed.

### 2.7 Security review items

[SECURITY_REVIEW.md](../SECURITY_REVIEW.md) tracks findings. Walk the list and close or explicitly accept each one. Items touching authentication, token storage, or PII are hard blockers.

### 2.8 Crash and error reporting

Not currently wired up. Add Sentry (or equivalent) to both:

- React Native app — surfaces JS crashes, native crashes, unhandled promise rejections. Tag releases with the `versionCode` so we can correlate post-launch.
- Django backend — surfaces unhandled 500s with stack traces. Scrub request bodies (foot images, tokens) from events.

Without this, we are flying blind during the Play review round when reviewers will install, poke, and bounce within minutes.

### 2.9 Branding assets

Current icons in [frontend/assets/](../frontend/assets) are placeholder-grade. Finalize:

- `icon.png` — 1024×1024 master, no transparency
- `adaptive-icon.png` — foreground layer, safe zone per Android spec
- `splash-icon.png` — must render correctly at the configured background `#ffffff`
- Favicon (used for the Expo web target; low priority)

### 2.10 Version discipline

`versionName` should be driven by `expo.version` in [frontend/app.json](../frontend/app.json). `versionCode` is auto-incremented by EAS — [frontend/eas.json:15](../frontend/eas.json#L15) already sets `autoIncrement: true` on the production profile, and `cli.appVersionSource: "remote"` means EAS owns the counter. Document the bump convention (semver for `versionName`) and avoid hand-editing `versionCode`.

---

## 3. Backend hosting

Play reviewers hit the production API during testing. We need a stable HTTPS hostname backed by Supabase Postgres, not local SQLite.

### 3.1 Provider comparison

| Option | Pros | Cons |
|---|---|---|
| **Fly.io** (recommended) | Dockerfile deploys, free Let's Encrypt on custom domains, region selection close to Supabase, straightforward Django story | Smaller free tier than competitors; regions matter for Roboflow and Supabase latency |
| **Railway** | Easiest onboarding, good logs UI | Pricing scales quickly with traffic; fewer regions |
| **Render** | Managed Postgres option if we wanted to move off Supabase, free tier | Free tier sleeps; cold starts hurt first-request latency |
| **AWS (ECS/Fargate + ALB)** | Production-grade at any scale | Significant setup and ongoing operational burden |

Recommendation: **Fly.io** for the first production deployment. Revisit if traffic or compliance requires otherwise.

### 3.2 Deploy checklist

- Write a production `Dockerfile` for the backend: gunicorn (multi-worker), whitenoise for static files (admin etc.), non-root user, multi-stage build.
- Add `fly.toml` with: healthcheck on `/api/health/`, auto-scaling minimums, region placement near Supabase.
- Set secrets via `fly secrets set …`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `DB_SSLMODE=require`, `ROBOFLOW_API_KEY`, `ROBOFLOW_WORKSPACE`, `ROBOFLOW_PROJECT`, `GOOGLE_CLIENT_ID`.
- Register a domain and point an `A`/`AAAA` (or `CNAME`) record at Fly. Issue the LE cert via Fly's managed certs.
- Run `python manage.py migrate` against Supabase from the release command. Confirm schema parity with local.
- Smoke test: `curl https://<prod-host>/api/health/` returns `200` with a non-zero shoe count.
- Set `EXPO_PUBLIC_API_URL=https://<prod-host>` in the EAS production build env (§4.1).
- Verify CORS / DRF settings allow the mobile client and reject browser origins we do not own.

### 3.3 Database considerations

- Supabase backups: verify automated backups are on and test a restore once before launch.
- Connection pooling: Supabase's PgBouncer is recommended for short-lived serverless-style connections. Use the pooler connection string for Django if we deploy to a runtime with ephemeral workers.
- `db.sqlite3` is checked in for dev convenience — confirm it is never used in the production container (no `DATABASE_URL` → Django will fall through to SQLite, which is how we get data loss on deploy). Fail-closed logic in `settings.py` would prevent this.

---

## 4. Android build pipeline

### 4.1 Harden `eas.json`

[frontend/eas.json](../frontend/eas.json) currently defines three profiles but the production profile is minimal. At minimum add:

- `distribution: "store"` and `android.buildType: "app-bundle"` to guarantee an AAB (Play requires AAB for new apps).
- An `env` block containing the production values of `EXPO_PUBLIC_API_URL` and `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
- A `channel` for Expo Updates if we decide to use OTA updates (note: Expo Updates are currently disabled via manifest metadata — see [AndroidManifest.xml:26](../frontend/android/app/src/main/AndroidManifest.xml#L26)).

The preview profile should point at the staging/dev backend and produce an APK for sideloaded tester builds.

### 4.2 Signing and Play App Signing

- Let EAS manage the upload keystore (default). After the first production build, export and back up the upload keystore via `eas credentials` to offline storage — loss of the upload key permanently severs our ability to update the listing.
- Enroll in **Play App Signing** on the first upload. Google holds the app-signing key; we hold only the upload key. This is mandatory for new apps and enables key rotation.
- Register the **release** SHA-1 (Google's app-signing key fingerprint, visible in Play Console → Setup → App signing) as an authorized Android OAuth client in Google Cloud Console. Without this step, Google Sign-In fails on Play-installed builds because the signing identity differs from the dev keystore.

### 4.3 Local verification of the production AAB

Before upload:

1. `eas build --profile production --platform android` → signed AAB.
2. `bundletool build-apks --bundle=app.aab --output=app.apks --mode=universal` → installable APK.
3. Install on a physical device (emulator camera does not work — per [CLAUDE.md](../CLAUDE.md)).
4. Walk every flow end-to-end: welcome → Google Sign-In → camera capture (both A4 and Letter) → measurement result → recommendations → saved shoes → account deletion → sign out.
5. Monitor `adb logcat` for crashes and unhandled promise rejections.
6. Verify the production API hostname is baked in (grep the unpacked APK for localhost strings — there should be none).

---

## 5. Pre-prompt screens and permission UX

Play's policy and reviewer instinct both prefer that runtime permission prompts are preceded by an in-app explanation. Today:

- Camera permission string is declared in [frontend/app.json:39](../frontend/app.json#L39). Surface an in-app screen *before* the OS camera prompt explaining why (foot measurement).
- If sensor-based tilt guidance remains in CameraScreen, confirm it does not require a runtime permission on current Android versions.
- ARCore is set to `required="false"` via [frontend/plugins/withARCore.js](../frontend/plugins/withARCore.js) and confirmed in [AndroidManifest.xml:16,25](../frontend/android/app/src/main/AndroidManifest.xml#L16), so the app remains installable on non-ARCore devices. Verify the runtime code path falls back cleanly when ARCore is unavailable — reviewers test on a range of devices.

---

## 6. Play Console configuration

Everything in this section is Play Console UI work. Final text should also be captured in the repo (e.g. `docs/store_listing/`) so we can revise without diffing through screenshots.

### 6.1 App content declarations

| Item | Notes for this app |
|---|---|
| Privacy policy URL | Required. Must be a live public URL on a domain we own. Must cover: data categories collected (email + profile name from Google, foot measurements derived from photos), purpose, retention, deletion process (`DELETE /api/auth/delete/`), third-party processors (Google, Roboflow, Supabase, hosting provider, crash reporting). |
| Data safety form | Declare: **Personal info** — name, email address (collected, linked to user, required). **Photos** — foot photo (collected for processing, **not stored**, not linked to user, per §2.6). **App activity** — measurement history and saved shoes (collected, linked, required). Declare no data is sold. Declare encryption in transit. Declare deletion mechanism. Google cross-checks declarations against runtime behavior — be accurate. |
| Permissions declarations | After the audit in §2.1, only declare what remains. Each sensitive permission needs a rationale in the listing. |
| Account deletion URL | Required. Host a web page that describes the in-app path (Profile → Delete account) and provides an email fallback. |
| Target audience | 18+ recommended. Avoid "children" categories — triggers Play's Families policy and Google Sign-In consent complications. |
| Content rating | Complete the IARC questionnaire. Expected result: PEGI 3 / ESRB Everyone. |
| Ads declaration | No ads currently — declare accordingly. Changing this later requires a listing update. |
| Government app / financial features | No. |
| Health and fitness category | If we pick this category, some jurisdictions impose additional requirements. Consider "Shopping" instead — foot measurement is a means, not the product. |

### 6.2 Store listing assets

- App name: "Shoe Shopper" (≤30 chars).
- Short description: ≤80 chars.
- Full description: ≤4000 chars. Describe foot-measurement-by-photo and recommendations. Avoid medical or accuracy claims (§7.5).
- App icon: 512×512 PNG (non-transparent).
- Feature graphic: 1024×500 PNG (no text-only — Google rejects pure-text feature graphics).
- Phone screenshots: 2–8, minimum 1080px on the short side. Only screenshot shipped, working flows.
- Tablet screenshots: optional but improve ranking on tablets.
- Promo video: optional YouTube link.

---

## 7. Likely review snags (pre-empt)

Based on the app's behavior, these are the items most likely to come back from review.

### 7.1 Unused sensitive permissions
See §2.1. This is the single most likely automated rejection vector.

### 7.2 Photos of body parts
Feet are borderline-biometric. Be explicit in the privacy policy and data safety form about what happens to the image: transmitted over TLS to our backend → forwarded to Roboflow → discarded. Confirm this is true in all paths (including error/retry paths and any crash-reporting payloads) before declaring it.

### 7.3 Google Sign-In consent screen
Reviewers click through the OAuth consent screen. Verify in Google Cloud Console that it shows the final app name, final logo, and links to the live privacy policy. Unverified / test-mode apps will fail review.

### 7.4 Account deletion
Do not bury the flow. Current path (Profile → Delete account) is fine in principle, but the label must be explicit ("Delete account and data") and the confirmation screen must state what gets removed. Reviewers will try it.

### 7.5 Accuracy and health claims
The product measures feet, which invites medical-adjacent language. Avoid any claim that implies medical grade, diagnostic use, or precision beyond what the Roboflow model delivers. "Fit guidance" is safe; "accurate measurement" is borderline; "medical-grade" is a rejection.

### 7.6 Broken or placeholder features in screenshots
Do not screenshot OwnedShoesScreen until it ships. Every flow visible in the listing must be functional in the submitted build.

### 7.7 Google Sign-In on the signed build
Google Sign-In fails silently if the SHA-1 registered in Google Cloud does not match the keystore that signed the installed build. After enrolling in Play App Signing (§4.2), register the Play-issued signing key's SHA-1 — otherwise reviewers will see a login failure.

---

## 8. Release track strategy

Play offers four tracks, progressing from private to public. Each can be used independently; progression is by convention.

1. **Internal testing** — up to 100 testers invited by email or Google Group. No review delay; builds are available to testers within minutes. Use for engineering and stakeholder validation.
2. **Closed testing** — larger cohort, reviewed before distribution but faster than production. For new personal developer accounts, Play currently requires a closed-testing cohort of at least 12 testers opted in for at least 14 continuous days before a production release is accepted. Organization accounts may be exempt but should plan for it regardless.
3. **Open testing** — optional. Public opt-in, visible from the Play listing. Useful for broader beta before production; skippable if closed testing is sufficient.
4. **Production** — full review, public availability. Use **staged rollout** (start at 10–20%, increase after confirming crash-free rate and Play Vitals).

Every track (including internal) requires the same store-listing completeness as production, so §6 blocks the first internal build as well.

---

## 9. Submission checklist

A reviewer-style pass before the first upload. Each must be true.

- [ ] Play Console developer account verified
- [ ] Android OAuth client registered with both dev-keystore SHA-1 and Play App Signing SHA-1
- [ ] Production backend deployed, `DEBUG=0`, HTTPS only, healthcheck green
- [ ] Supabase migrations run; admin account disabled or hardened
- [ ] `DJANGO_ALLOWED_HOSTS` contains only the production hostname
- [ ] `EXPO_PUBLIC_API_URL` in the EAS production profile points at the production backend
- [ ] AndroidManifest contains no unused sensitive permissions (verified via `aapt2 dump permissions`)
- [ ] ProfileScreen smoke-test card removed or gated behind `__DEV__`
- [ ] OwnedShoesScreen either implemented or removed from navigation
- [ ] Account deletion tested end-to-end; all user-linked rows removed
- [ ] Crash reporting live in both backend and app
- [ ] Privacy policy URL live and accurate
- [ ] Data safety form matches runtime behavior
- [ ] Store listing assets finalized (icon, feature graphic, screenshots, copy)
- [ ] Content rating questionnaire submitted
- [ ] Signed AAB tested on a physical device end-to-end
- [ ] `versionCode` and `versionName` set correctly
- [ ] Release notes drafted

---

## 10. Post-launch operations

Once the app is live, ongoing work to keep it there.

- **Play Vitals monitoring** — ANR rate, crash rate, excessive wakeups, battery drain. Thresholds exceeded → the listing is down-ranked and, in extreme cases, delisted. Set up alerts on the Play Console.
- **Crash reporting** — weekly triage of top issues. Regressions block the next release.
- **Policy change monitoring** — Play policy updates (typically announced with a multi-week compliance deadline) can require app changes. Subscribe to the Play Console developer newsletter.
- **Release notes** — every production release requires localized release notes for every supported locale.
- **Staged rollout discipline** — default to 10% or 20% first, hold for a cohort of real usage, then expand. Halt at any sign of regression and issue a patch.
- **Key custody** — upload keystore and its passphrase belong in the team secrets store plus an offline backup. Document the recovery path.
- **Roboflow quota / Supabase usage** — both will grow with DAU. Wire usage into an alerting dashboard before they cause a user-visible outage.
- **Account-deletion SLA** — if we ever batch or delay deletion (e.g. soft-delete + nightly purge), the privacy policy must say so and the delay must be short. Today it is synchronous via ORM cascade.

---

## 11. Open questions

Before starting on §2, decide these. Each answer changes downstream work.

- **Publishing entity** — personal or organization developer account? Drives the verification flow, the closed-testing requirement, and the name shown on the listing.
- **Photo retention in logs / crash reports** — we confirm photos are not persisted by the measurement handler, but once Sentry is wired up (§2.8), must confirm no crash payload ever contains an uploaded image. Policy: strip multipart bodies from all error capture.
- **Domain** — is one registered? We need it for privacy policy, account-deletion URL, and API hostname. Subdomains are fine (`api.`, `www.`).
- **Marketing site vs single privacy page** — minimum viable is a single static page hosting the privacy policy and deletion policy. A full marketing site is nice-to-have, not required.
- **OwnedShoesScreen** — implement for v1 or cut from navigation? Affects the listing (screenshots, description) either way.
- **iOS / App Store** — out of scope here, but worth deciding early whether we are shipping parallel or Android-first.
