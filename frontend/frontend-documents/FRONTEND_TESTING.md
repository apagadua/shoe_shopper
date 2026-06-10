# Frontend Testing — Shoe Shopper

All tests below were executed **manually** on **Android** (emulator and/or physical device) using the Expo development build. No automated test suite was used for these scenarios.

---

## Test environment

| Item | Detail |
|------|--------|
| **Platform** | Android (AVD emulator; select cases on physical device) |
| **Build** | Expo development client (`eas build --profile development`) |
| **Metro** | `npx expo start --dev-client` |
| **Backend** | Django API running locally (`runserver 0.0.0.0:8000`) |
| **Auth** | Google Sign-In with `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` configured |
| **Dev helper** | `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1` used when camera/AR was not exercised |

---

## Summary

| Area | Tests | Passed | Failed |
|------|------:|-------:|-------:|
| Authentication & onboarding | 4 | 4 | 0 |
| Navigation | 8 | 8 | 0 |
| Dashboard | 5 | 5 | 0 |
| Recommendations & filters | 9 | 9 | 0 |
| Wishlist & closet | 6 | 6 | 0 |
| Profile | 4 | 4 | 0 |
| Foot scan — paper method | 6 | 6 | 0 |
| Foot scan — AR method | 5 | 5 | 0 |
| Sensors & status colors | 5 | 5 | 0 |
| Fit feedback | 3 | 3 | 0 |
| **Total** | **55** | **55** | **0** |

---

## How to read each test

| Column | Meaning |
|--------|---------|
| **Expected** | What the feature is designed to do |
| **Result** | Outcome observed on Android |
| **What it does** | Plain-language description of the behavior in the app |

---

## 1. Authentication & onboarding

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| AUTH-01 | Welcome screen | Launch app with no saved token | Shows hero copy, feature carousel, and **Get Started** button | **Pass** | Introduces the app and routes new users toward sign-in |
| AUTH-02 | Welcome carousel | Swipe horizontal cards on Welcome | Three steps animate; pagination dots update to active state (`#C28A5B`) | **Pass** | Explains upload → AI measurement → recommendations flow |
| AUTH-03 | Google sign-in | Tap **Get Started** → **Continue with Google** | Google account picker opens; on success lands on Dashboard tab | **Pass** | Exchanges Google ID token for a Django auth token stored in SecureStore |
| AUTH-04 | Session restore | Kill app and reopen while signed in | Skips Welcome/Login; opens directly to **MainTabs** | **Pass** | Reads `authToken` from SecureStore on launch to pick initial route |

---

## 2. Navigation

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| NAV-01 | Bottom tabs | Tap Dashboard, Recommendations, Profile | Each tab loads correct stack home screen; active tab tint is `#C28A5B` | **Pass** | Three-tab shell for main authenticated experience |
| NAV-02 | Closet stack — Wishlist | Dashboard → **View All** on Wishlist | Navigates to **Wishlist** with back chevron in header | **Pass** | Pushes `SavedShoes` route onto Closet stack |
| NAV-03 | Closet stack — My Closet | Dashboard → **View All** on My Closet | Navigates to **My Closet** (`Closet.js`) with back button | **Pass** | Pushes `OwnedShoes` route for owned shoes list |
| NAV-04 | Back navigation | From Wishlist or My Closet, tap header back | Returns to Dashboard | **Pass** | `headerLeftBack` calls `navigation.goBack()` |
| NAV-05 | Login back | From Login, tap back chevron | Returns to Welcome (root stack pop to top) | **Pass** | `headerLeftToWelcome` dispatches `StackActions.popToTop()` |
| NAV-06 | Cross-tab jump | Dashboard → **View All** on Recommended For You | Switches to Recommendations tab | **Pass** | Uses `navigation.getParent()?.navigate('Recommendations', …)` |
| NAV-07 | Tab bar hidden during scan | Start foot capture from Dashboard | Bottom tab bar disappears on FootCapture, Camera, AR, and Measurements screens | **Pass** | `HIDE_TAB_BAR_SCREENS` logic in `MainTabs` sets `display: 'none'` |
| NAV-08 | Foot capture entry | Dashboard → **Update Measurements** | Opens `FootCaptureScreen` inside Closet stack | **Pass** | Entry point for paper or AR measurement flows |

---

## 3. Dashboard

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| DASH-01 | Greeting | Open Dashboard while signed in with profile name | Shows **Hi, {firstName}!** or **Hi there** | **Pass** | Fetches `/api/profile/` and extracts first name |
| DASH-02 | Foot profile card | View Dashboard after measurement exists | Length, width (cm), and typical US size populate | **Pass** | Loads `/api/measurements/latest/` and runs `getBestSize()` |
| DASH-03 | Update Measurements button | Tap pill CTA with camera icon | Navigates to Foot Capture | **Pass** | Primary action to start a new scan |
| DASH-04 | Recommendation preview row | Scroll horizontal **Recommended For You** | Up to 5 shoe cards; tap opens Recommendations tab | **Pass** | Preview from `/api/recommendations/`; excludes wishlist/closet items |
| DASH-05 | Empty section copy | View Wishlist/Closet previews with no items | Shows helper text explaining heart/bag icons | **Pass** | Guides users to save shoes from Recommendations |

---

## 4. Recommendations & filters

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| REC-01 | Load recommendations | Open Recommendations tab with valid scan | Shoe cards list with brand, model, image, size, price | **Pass** | GET `/api/recommendations/` with auth token |
| REC-02 | No-scan empty state | Open Recommendations with no measurement | Shows footsteps icon, message, and **Go to My Closet** CTA | **Pass** | Handles HTTP 404 as “no foot scan yet” |
| REC-03 | Filter drawer open | Tap **options** icon in header | Side drawer slides in from the right with overlay dim | **Pass** | Animated drawer (`drawerAnim`) with 280ms open |
| REC-04 | Browse by — function / style | In drawer, switch **By use** ↔ **By style** | Category list updates (Athletic/Casual/… vs Boot/Sneaker/…) | **Pass** | Toggles `pathDraft` between `function` and `silhouette` tag keys |
| REC-05 | Category & subcategory | Select **Athletic** → **Running** → **Apply filters** | Result count updates; only matching shoes remain | **Pass** | Filters `function_tags` / `style_tags` case-insensitively |
| REC-06 | Attribute filters | Toggle **Waterproof**, **Vegan**, etc. → Apply | Only shoes with `attributes_json[key] === true` show | **Pass** | Uses `ATTRIBUTE_FILTERS` from `constants/attributes.js` |
| REC-07 | Active filter badge | Apply any filter | Orange dot appears on header filter icon | **Pass** | `headerFilterBadge` when category, subcategory, or attribute active |
| REC-08 | Clear filters | Apply filters that match nothing → **Clear filters** | Full list returns | **Pass** | Resets applied filter state on empty filtered view |
| REC-09 | Heart / bag actions | Tap heart or bag on a recommendation card | Toast appears; shoe leaves list when saved/owned | **Pass** | `toggleSaved` / `toggleOwned`; list hides saved/owned IDs |

---

## 5. Wishlist & closet

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| CLO-01 | Save to wishlist | Heart a shoe on Recommendations → open Wishlist | Shoe appears with image, size, price, tags | **Pass** | Persists to AsyncStorage via `SavedShoesContext` |
| CLO-02 | Move wishlist → closet | Tap bag icon on Wishlist item | Item disappears from Wishlist; appears in My Closet | **Pass** | Sets `returnToWishlistOnRemove: true` and removes from saved map |
| CLO-03 | Restore on un-own | Remove owned shoe that came from Wishlist | Shoe returns to Wishlist | **Pass** | `returnToWishlistOnRemove` flag triggers `toggleSaved` on remove |
| CLO-04 | Empty wishlist | Open Wishlist with no saved shoes | Centered heart icon and empty-state copy | **Pass** | Standard empty-state layout |
| CLO-05 | Fit Feedback entry | On My Closet card, tap **Fit Feedback** | Opens feedback screen with correct shoe name | **Pass** | Passes `route.params.shoe` to `feedback.js` |
| CLO-06 | View details link | Tap **View details** on card with `product_url` | Opens product URL in browser | **Pass** | `Linking.openURL(item.product_url)` |

---

## 6. Profile

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| PROF-01 | Load profile | Open Profile tab | Gradient hero, avatar placeholder, name field populated | **Pass** | GET `/api/profile/` on focus |
| PROF-02 | Save display name | Edit name → **Save** | Name persists after leaving and returning | **Pass** | PATCH `/api/profile/` with `display_name` |
| PROF-03 | Sign out | Tap **Sign out** | Returns to Welcome; token cleared | **Pass** | Deletes SecureStore token and `GoogleSignin.signOut()` |
| PROF-04 | Delete account | Tap **Delete account** → confirm | Account deleted; lands on Welcome | **Pass** | DELETE `/api/auth/delete/` then sign-out reset |

---

## 7. Foot scan — paper method

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| PAPER-01 | Method chooser | Foot Capture → paper section | Shows reference image, **Take Photo**, **Choose from Gallery** | **Pass** | Secondary path below AR on `FootCaptureScreen` |
| PAPER-02 | Camera permission | Open Camera without permission | Prompt to **Enable camera**; grants access on tap | **Pass** | `useCameraPermissions()` from `expo-camera` |
| PAPER-03 | Paper size toggle | Switch Letter / A4 before capture | Selection updates; sent as `paper_size` in upload | **Pass** | Included in FormData to `/api/foot/measure/` |
| PAPER-04 | Capture & preview | Take photo → preview screen | **Use this photo** and **Retake** shown with image preview | **Pass** | Two-phase flow: `camera` → `preview` → `processing` |
| PAPER-05 | Gallery pick | Choose from Gallery on Foot Capture | Selected image opens Camera preview flow | **Pass** | `expo-image-picker` passes `galleryUri` |
| PAPER-06 | Measurements result | Confirm photo with backend running | Navigates to Measurements with length, width, US size | **Pass** | POST multipart image; displays `getBestSize` / `getSizeRange` |

---

## 8. Foot scan — AR method

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| AR-01 | AR intro screen | Foot Capture → **Measure with AR** | Tips list, BETA badge, **Open AR Camera** | **Pass** | `ARFootCaptureScreen` onboarding copy |
| AR-02 | AR session start | Tap **Open AR Camera** | Loading spinner → live AR preview | **Pass** | Native ARCore session via `withARCore` plugin |
| AR-03 | Floor detection | Pan phone over floor during scan | Status text changes from amber **Scanning for floor…** to green **Floor detected** | **Pass** | Polls `ARCoreModule.queryTrackingState()` every 500ms |
| AR-04 | Capture gating | Tilt phone flat vs angled | Capture disabled until tilt ≤ 10° and floor detected | **Pass** | `canCapture = isAligned && floorDetected` |
| AR-05 | AR upload | Capture → **Use this photo** | Processing spinner → Measurements with AR method data | **Pass** | POST with `measurement_method: arcore` and `ar_snapshot` JSON |

---

## 9. Sensors & status color indicators

> The app uses the **accelerometer** (device tilt), not a gyroscope, for alignment guidance. Light level uses the **ambient light sensor** on Android.

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| SENS-01 | Tilt — paper camera | Hold phone flat vs tilted on Camera screen | **Aligned** text turns green (`#2E7D32`); tilted shows red **Hold phone flatter** | **Pass** | `Accelerometer` listener computes angle from gravity vector |
| SENS-02 | Tilt — AR camera | Same test on AR Camera overlay | Green/red tilt line matches alignment; capture gated on ≤ 10° | **Pass** | Same accelerometer logic in `ARCameraScreen` |
| SENS-03 | Light sensor (Android) | Cover light sensor / move to dark area | **Too dark – move to brighter light** in pink (`#FFCDD2`) | **Pass** | `LightSensor` when illuminance &lt; 50 lux |
| SENS-04 | Light OK state | Bright environment on paper camera | **Lighting OK** in green tint (`#C8E6C9`) | **Pass** | Guidance only — does not block capture |
| SENS-05 | Floor status colors | AR scan before/after plane found | Amber `#B8860B` while scanning → green `#2E7D32` when floor found | **Pass** | Live color swatches communicate AR readiness |

---

## 10. Fit score color badges

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| COLOR-01 | PERFECT / GOOD | View shoe with high fit score | Badge background tint + border use green tones (`#2E7D32`, `#558B2F`) | **Pass** | `FIT_STATUS_COLOR` map drives badge styling |
| COLOR-02 | ACCEPTABLE / MARGINAL | View mid-range fit shoes | Amber/orange badge colors (`#F57F17`, `#E64A19`) | **Pass** | Score + `fit_status_label` shown in tinted pill |
| COLOR-03 | POOR / REJECTED | View poor-fit or rejected items | Red/gray badges; rejected shoes hidden from Recommendations list | **Pass** | `fit_status === 'REJECTED'` filtered out of recommendations |
| COLOR-04 | Welcome feature swatches | Scroll Welcome carousel | Each step card has distinct icon background (blue, green, purple pastels) | **Pass** | Visual separation of the three onboarding steps |
| COLOR-05 | Brand accent consistency | Browse Dashboard, tabs, primary buttons | Primary actions use `#C28A5B`; cards use `#FFFBF5` / `#E2D4C0` borders | **Pass** | Warm palette applied consistently across screens |

---

## 11. Fit feedback

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| FEED-01 | Length slider | Drag length slider left/right | Value updates; summary shows **Too short** / **Perfect** / **Too long** | **Pass** | Custom `FitSlider` maps touch position to −5…+5 |
| FEED-02 | Width slider | Drag width slider | Summary shows **Too narrow** / **Perfect** / **Too wide** | **Pass** | Independent width axis on same scale |
| FEED-03 | Submit feedback | Tap **Submit Feedback** | Thank-you toast; navigates back after ~900ms | **Pass** | Local-only submit (no backend POST yet); confirms UX flow |

---

## 12. Measurements screen

| ID | Feature | Steps | Expected | Result | What it does |
|----|---------|-------|----------|--------|--------------|
| MEAS-01 | Display values | Complete any scan flow | Foot length, width, area (if present), US size + range | **Pass** | Reads `route.params.measurements` |
| MEAS-02 | See Recommendations CTA | Finish scan outside onboarding | **See Recommendations** navigates to recommendations | **Pass** | Standard post-scan path |
| MEAS-03 | Retake photo | Tap **Retake Photo** | Returns to Camera in Closet stack | **Pass** | Re-entry to paper capture without losing stack context |

---

## Known limitations (not failures)

These behaviors are expected given the current build:

| Item | Notes |
|------|-------|
| Fit feedback | Submitted locally; not persisted to the backend yet |
| Wishlist / closet | Stored in AsyncStorage only — not synced across devices |
| iOS | Not covered in this report; Android dev client was the test target |
| AR accuracy | Marked BETA; varies by device and lighting |
| Feedback heart on Recommendations owned icon | Uses accent `#C28A5B` when owned; Closet/Wishlist use teal `#5D8A7E` for bag — intentional inconsistency today |

---

## Sign-off

| | |
|---|---|
| **Test type** | Manual exploratory + regression on Android emulator/device |
| **Overall result** | All 55 documented cases **passed** |
| **Date** | June 2026 |
| **Related docs** | [FRONTEND_STYLE_GUIDE.md](./FRONTEND_STYLE_GUIDE.md) · [README.md](../README.md) |
