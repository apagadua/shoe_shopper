# Frontend — Shoe Shopper

Deep dive into the React Native / Expo app: navigation, screens, state, storage, and services.

For setup instructions see [`SETUP.md`](./SETUP.md). For coding conventions see [`frontend/frontend-documents/FRONTEND_STYLE_GUIDE.md`](../frontend/frontend-documents/FRONTEND_STYLE_GUIDE.md). For manual test results see [`frontend/frontend-documents/FRONTEND_TESTING.md`](../frontend/frontend-documents/FRONTEND_TESTING.md). For feature-level code map and data flow see [`frontend/frontend-documents/FRONTEND_FEATURES.md`](../frontend/frontend-documents/FRONTEND_FEATURES.md).

---

## Table of Contents

1. [Project Layout](#1-project-layout)
2. [Navigation Structure](#2-navigation-structure)
3. [Screens](#3-screens)
4. [State Management](#4-state-management)
5. [Services](#5-services)
6. [Config & Utilities](#6-config--utilities)
7. [Storage Strategy](#7-storage-strategy)
8. [Styling](#8-styling)
9. [Key Patterns](#9-key-patterns)
10. [Native Modules & Build Requirements](#10-native-modules--build-requirements)
11. [NPM Scripts](#11-npm-scripts)
12. [Package Dependencies](#12-package-dependencies)

---

## 1. Project Layout

```
frontend/
├── App.js                      ← root navigator, fonts, context providers
├── SavedShoesContext.js          ← wishlist state (AsyncStorage)
├── OwnedShoesContext.js          ← owned / closet state (AsyncStorage)
├── index.js                    ← Expo entry point
├── app.json                    ← Expo config, plugins, EAS project ID
├── eas.json                    ← EAS build profiles
├── package.json
├── frontend-documents/         ← style guide + manual QA report
├── screens/
│   ├── WelcomeScreen.js
│   ├── LoginScreen.js
│   ├── Dashboard.js            ← tab home (foot profile + previews)
│   ├── Wishlist.js             ← saved shoes
│   ├── Closet.js               ← owned shoes
│   ├── RecommendationsScreen.js
│   ├── ProfileScreen.js
│   ├── FootCaptureScreen.js    ← AR vs paper method chooser
│   ├── CameraScreen.js         ← paper photo capture
│   ├── ARFootCaptureScreen.js  ← AR instructions
│   ├── ARCameraScreen.js       ← ARCore capture + upload
│   ├── MeasurementsScreen.js
│   └── feedback.js             ← Fit Feedback sliders (exports FeedbackScreen)
├── services/
│   ├── auth.js                 ← Google Sign-In + token exchange
│   └── devMockMeasurement.js   ← dev-only mock scan helper
├── config/
│   └── api.js                  ← platform-aware API_BASE_URL
├── constants/
│   └── attributes.js           ← recommendation filter attributes
├── utils/
│   └── shoeSize.js             ← Brannock formula helpers
├── styles/
│   └── emptyState.js           ← shared empty-state styles (screens often inline their own)
├── plugins/
│   └── withARCore.js           ← Android ARCore native wiring
├── components/                 ← empty; no shared components extracted yet
└── assets/                     ← icons, splash, logo, scan reference images
```

---

## 2. Navigation Structure

**File:** `frontend/App.js`

```
Stack Navigator (root)
├── Welcome              WelcomeScreen.js
├── Login                LoginScreen.js
├── MainTabs             Bottom Tab Navigator
│   ├── Closet tab       ClosetStackNavigator
│   │   ├── ClosetHome       Dashboard.js
│   │   ├── SavedShoes       Wishlist.js
│   │   ├── OwnedShoes       Closet.js
│   │   ├── Feedback         feedback.js
│   │   ├── FootCapture      FootCaptureScreen.js
│   │   ├── Camera           CameraScreen.js
│   │   ├── ARFootCapture    ARFootCaptureScreen.js
│   │   ├── ARCamera         ARCameraScreen.js
│   │   └── Measurements     MeasurementsScreen.js
│   ├── Recommendations tab
│   │   └── RecommendationsHome  RecommendationsScreen.js
│   └── Profile tab
│       └── ProfileHome          ProfileScreen.js
├── FootCapture, Camera, ARFootCapture, ARCamera, Measurements, Recommendations
│   (also registered on root stack for certain flows)
```

**Tab bar** is hidden when the Closet stack is on `FootCapture`, `Camera`, `ARFootCapture`, `ARCamera`, or `Measurements`. Style: background `#FFFBF5`, border `#E2D4C0`, active tint `#C28A5B`.

**Auth gate:** On launch, `App.js` reads `authToken` from `expo-secure-store`. If present → `MainTabs`; otherwise → `Welcome`.

---

## 3. Screens

### WelcomeScreen

- Hero: "Find Your Perfect Fit"
- 3-step horizontal carousel (Upload Photo → AI Measurement → Smart Recommendations)
- **Get Started** → Login

### LoginScreen

- **Continue with Google** → `googleSignIn()` → `signInWithGoogle(idToken)` → POST `/api/auth/google/`
- Saves DRF token to SecureStore → `navigation.replace('MainTabs')`

### Dashboard (`ClosetHome`)

- Personalized greeting from `/api/profile/`
- **Your Foot Profile** card: length, width, typical US size from `/api/measurements/latest/`
- **Update Measurements** → FootCapture
- Horizontal previews: Recommended For You, Wishlist, My Closet (each **View All** deep-links)

### Wishlist (`SavedShoes` route)

- Lists shoes from `SavedShoesContext` (excludes items already in owned closet)
- Heart / bag actions, fit badges, **View details** (opens `product_url`)
- Bag moves item to My Closet with `returnToWishlistOnRemove: true`

### Closet (`OwnedShoes` route)

- Lists owned shoes from `OwnedShoesContext`
- **Fit Feedback** → `feedback.js` with `route.params.shoe`

### FootCaptureScreen

- **Primary:** AR method → `ARFootCapture`
- **Secondary:** Paper method (reference image, **Take Photo**, **Pick from gallery**)
- **Skip for now** when `fromOnboarding` is set

### CameraScreen

Paper capture flow. Phases: `camera` → `preview` → `processing`.

| Sensor | Behavior |
|---|---|
| Accelerometer | Updates every 200 ms; blocks capture if tilt > 10° |
| Light sensor (Android only) | Warns if lux < 50; guidance only |

Paper size toggle (Letter / A4) sent as `paper_size`. Gallery pick via `expo-image-picker`. POST multipart to `/api/foot/measure/` → Measurements.

### ARFootCaptureScreen / ARCameraScreen

AR path: instructions → live ARCore preview → capture → preview → upload with `measurement_method: arcore` and `ar_snapshot` JSON. Accelerometer tilt + floor-plane detection gate capture. Falls back to paper method when ARCore unavailable.

### MeasurementsScreen

- Displays length, width, area; `getBestSize` / `getSizeRange` for US men's sizes
- Onboarding CTA → `MainTabs`; otherwise → Recommendations or back to Dashboard

### RecommendationsScreen

- `useFocusEffect` → GET `/api/recommendations/`
- Animated filter drawer: browse by function or silhouette, category/subcategory, attribute toggles (draft → **Apply filters**)
- Shoe cards with fit badges, heart (wishlist), bag (closet), toasts, **View details**
- Hides `REJECTED` fits and shoes already saved/owned

### ProfileScreen

- Gradient hero, display name edit (PATCH `/api/profile/`)
- **Delete account** (DELETE `/api/auth/delete/`) and **Sign out**
- No backend smoke-test UI in the current build

### FeedbackScreen (`feedback.js`)

- Length and width fit sliders (−5…+5)
- Submit shows thank-you toast and navigates back (local-only; not persisted to API yet)

---

## 4. State Management

Local screen state uses React hooks (`useState`, `useEffect`, `useFocusEffect`, `useMemo`, `useCallback`). Cross-screen shoe lists use context providers (both wrapped in `App.js`):

### SavedShoesContext

Wishlist. AsyncStorage key `savedShoes`. Exposes `{ savedMap, savedShoes, toggleSaved, isSaved }`.

### OwnedShoesContext

Owned closet. AsyncStorage key `ownedShoes`. Exposes `{ ownedMap, ownedShoes, toggleOwned, isOwned }`.

Shoes are stored as maps keyed by `id`. Wishlist ↔ closet moves use a `returnToWishlistOnRemove` flag on the shoe object.

```js
import { useSavedShoes } from '../SavedShoesContext';
import { useOwnedShoes } from '../OwnedShoesContext';

const { isSaved, toggleSaved } = useSavedShoes();
const { isOwned, toggleOwned } = useOwnedShoes();
```

---

## 5. Services

### `frontend/services/auth.js`

```js
googleSignIn()              // native Google picker → idToken
signInWithGoogle(idToken)   // POST /api/auth/google/ → { key }
```

Requires `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in `frontend/.env`.

### `frontend/services/devMockMeasurement.js`

`ensureDevMockMeasurementIfNeeded()` — dev-only POST to `/api/dev/mock-measurement/` when `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1`. Called from Dashboard on focus.

Most other API calls (`profile`, `recommendations`, `foot/measure`) are inline in screens today. New endpoints should follow the `auth.js` pattern: `API_BASE_URL`, throw `Error` with a useful message.

---

## 6. Config & Utilities

### `frontend/config/api.js`

```js
// Android emulator → http://10.0.2.2:8000
// iOS simulator    → http://127.0.0.1:8000
// Override         → process.env.EXPO_PUBLIC_API_URL
```

### `frontend/utils/shoeSize.js`

```js
getBestSize(lengthIn)    // nearest US men's half-size string
getSizeRange(lengthIn)   // plausible sizes within ±0.5" tolerance
```

### `frontend/constants/attributes.js`

`ATTRIBUTE_FILTERS` — waterproof, vegan, slip resistant, safety toe, wide available.

---

## 7. Storage Strategy

| Data | Storage | Key / source |
|---|---|---|
| Auth token | `expo-secure-store` | `authToken` |
| Wishlist | `AsyncStorage` | `savedShoes` |
| Owned shoes | `AsyncStorage` | `ownedShoes` |
| Latest measurements | API (not cached locally) | `GET /api/measurements/latest/` (Dashboard) |

Measurements from a fresh scan are passed via `route.params` to `MeasurementsScreen`. They are not written to AsyncStorage.

**Note:** Wishlist/closet are local-only today — not synced to the backend `UserCollection` model.

---

## 8. Styling

`StyleSheet.create` at the bottom of each screen. No global theme file.

Common palette:

| Role | Hex |
|---|---|
| Page background | `#F5EFE6`, `#FCFAF7`, `#FAF9F6` |
| Card surface | `#FFFBF5` |
| Card border | `#E2D4C0` |
| Primary accent | `#C28A5B` |
| Primary text | `#2F2A25` |
| Muted text | `#6B5F52` |

Font: **Outfit** (`Outfit_400Regular`, `Outfit_600SemiBold`) loaded in `App.js`. Headers and Profile use `fontFamily`; other screens use system font + `fontWeight`.

`frontend/styles/emptyState.js` exports shared empty-state styles; most screens duplicate the same values inline today.

---

## 9. Key Patterns

### Authenticated API call

```js
import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL } from '../config/api';

const token = await SecureStore.getItemAsync('authToken');
const response = await fetch(`${API_BASE_URL}/api/some-endpoint/`, {
  headers: { Authorization: `Token ${token}` },
});
```

Token format is `Token <key>` (DRF), not `Bearer`.

### Fetch on screen focus

```js
useFocusEffect(
  useCallback(() => {
    let cancelled = false;
    (async () => { /* fetch; if (cancelled) return; */ })();
    return () => { cancelled = true; };
  }, [])
);
```

### Cross-tab navigation

```js
navigation.getParent()?.navigate('Recommendations', { screen: 'RecommendationsHome' });
```

---

## 10. Native Modules & Build Requirements

Native modules **do not work in Expo Go**. Use an EAS development build:

| Module | Purpose |
|---|---|
| `expo-camera` | Paper photo capture |
| `expo-sensors` | Accelerometer + Android light sensor |
| `expo-image-picker` | Gallery pick on Foot Capture / Camera |
| `@react-native-google-signin/google-signin` | Google Sign-In |
| ARCore (via `plugins/withARCore.js`) | AR foot measurement on Android |

Rebuild the dev client when native dependencies or `app.json` plugins change. JS/UI changes hot-reload via Metro.

See [`SETUP.md`](./SETUP.md#6-android-dev-client-build-one-time).

---

## 11. NPM Scripts

Run from `frontend/`:

| Script | Command | Use |
|---|---|---|
| `npm start` | `expo start --tunnel` | Tunnel mode (physical devices) |
| `npm run android` | `expo start --lan` | Android emulator on same machine |
| `npm run ios` | `expo start --ios` | iOS simulator (Mac only) |
| `npm run web` | `expo start --web` | Web preview (no native modules) |

Daily dev with the dev client: `npx expo start --dev-client`.

---

## 12. Package Dependencies

| Package | Purpose |
|---|---|
| `expo` ~54 | Expo SDK |
| `react` 19.1.0 | Required by SDK 54 |
| `react-native` 0.81.5 | Mobile framework |
| `@react-navigation/*` | Stack + bottom tabs |
| `expo-camera` | Camera capture |
| `expo-sensors` | Accelerometer, light sensor |
| `expo-secure-store` | Auth token |
| `@react-native-async-storage/async-storage` | Wishlist / closet |
| `@react-native-google-signin/google-signin` | Google Sign-In |
| `@expo-google-fonts/outfit` | Outfit font |
| `expo-linear-gradient` | Profile hero gradient |
| `expo-image-picker` | Gallery selection |
| `expo-dev-client` | Custom development build |
| `@expo/vector-icons` | Ionicons (and Feather/FontAwesome5 on Welcome) |
