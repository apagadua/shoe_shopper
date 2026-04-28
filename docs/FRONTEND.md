# Frontend — Shoe Shopper

Deep dive into the React Native / Expo app: navigation, screens, state, storage, and services.

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
├── App.js                  ← root navigator + font loading + context providers
├── SavedShoesContext.js    ← wishlist state (AsyncStorage-backed)
├── index.js                ← Expo entry point (do not modify)
├── app.json                ← Expo config: SDK, plugins, android package, EAS project ID
├── eas.json                ← EAS build profiles (development, production)
├── package.json
├── screens/
│   ├── WelcomeScreen.js
│   ├── LoginScreen.js
│   ├── ClosetScreen.js
│   ├── FootCaptureScreen.js
│   ├── CameraScreen.js         ← most complex screen (~503 lines)
│   ├── MeasurementsScreen.js
│   ├── RecommendationsScreen.js ← largest screen (~1009 lines)
│   ├── ProfileScreen.js
│   ├── SavedShoesScreen.js     ← stub
│   └── OwnedShoesScreen.js     ← stub
├── services/
│   └── auth.js             ← Google Sign-In + token exchange
├── config/
│   └── api.js              ← platform-aware API_BASE_URL
├── constants/
│   └── attributes.js       ← filter attribute definitions
├── utils/
│   └── shoeSize.js         ← Brannock formula helpers
├── styles/
│   └── emptyState.js       ← reusable empty state styles
├── components/             ← empty; no shared components extracted yet
└── assets/                 ← images, icons, splash screen
```

---

## 2. Navigation Structure

**File:** `frontend/App.js`

```
Stack Navigator (root)
├── Welcome          WelcomeScreen.js   — hero + feature carousel
├── Login            LoginScreen.js     — Google Sign-In button
└── MainTabs         Bottom Tab Navigator
    ├── Closet tab   (Stack)
    │   ├── ClosetHome      ClosetScreen.js
    │   ├── SavedShoes      SavedShoesScreen.js  ← stub
    │   ├── OwnedShoes      OwnedShoesScreen.js  ← stub
    │   ├── FootCapture     FootCaptureScreen.js
    │   ├── Camera          CameraScreen.js
    │   └── Measurements    MeasurementsScreen.js
    ├── Recommendations tab (Stack)
    │   └── RecommendationsHome  RecommendationsScreen.js
    └── Profile tab  (Stack)
        └── ProfileHome     ProfileScreen.js
```

**Tab bar** is hidden on FootCapture, Camera, and Measurements screens. Style: beige background (`#FFFBF5`), brown border, brown active tint (`#C28A5B`).

**Auth gate:** On app load, `App.js` checks `expo-secure-store` for a saved token. If found, it skips to `MainTabs`; otherwise it starts at `Welcome`.

---

## 3. Screens

### WelcomeScreen

- Hero header: "Find Your Perfect Fit"
- 3-step feature carousel (Upload Photo → AI Measurement → Smart Recommendations)
- "Get Started" button → navigates to Login

---

### LoginScreen

- Single "Continue with Google" button
- Calls `googleSignIn()` (native Google picker) → gets `idToken`
- Calls `signInWithGoogle(idToken)` → POST `/api/auth/google/` → gets `{ key }`
- Saves `key` to `expo-secure-store`
- Navigates to `MainTabs`

---

### ClosetScreen

- Shows the user's latest foot measurements and estimated shoe size
- Fetches `GET /api/measurements/latest/` on every screen focus (`useFocusEffect`)
- Converts inches → cm for display
- Calls `getBestSize(length_in)` from `utils/shoeSize.js` for the size label
- Three action buttons: Saved Shoes, Owned Shoes, Capture Foot Photo

---

### FootCaptureScreen

- Instruction screen shown before the camera
- Displays a mockup diagram of the capture setup
- 4-point tips list (paper orientation, sock, phone height, lighting)
- "Open camera" button → navigates to CameraScreen
- "Skip for now" button (only shown when arriving from onboarding flow)

---

### CameraScreen

The most complex screen (~504 lines). Three phases: `camera` → `preview` → `processing`.

**Sensors:**

| Sensor | Behavior |
|---|---|
| Accelerometer | Updates every 200 ms; computes tilt from gravity vector; warns if >10° and blocks capture |
| Light sensor (Android only) | Warns if ambient lux < 50; guidance only, not blocking |

**Paper size toggle:** Letter (8.5" × 11") or A4 (210 mm × 297 mm). Sent as `paper_size` in the upload.

**Capture flow:**
1. User taps capture button → camera takes photo → enters `preview` phase
2. User taps "Use this photo" → enters `processing` phase
3. `FormData` POST to `/api/foot/measure/`:
   ```js
   const form = new FormData();
   form.append('image', { uri, type: 'image/jpeg', name: 'foot.jpg' });
   form.append('paper_size', paperSize);
   ```
4. Auth token read from `expo-secure-store` and added to `Authorization: Token <key>` header
5. On success → navigate to `MeasurementsScreen` with `{ measurements: responseData }`
6. On error → show error message in preview phase, allow retake

**Known issue:** No fetch timeout — a slow or dropped network connection will hang indefinitely. See `SECURITY_REVIEW.md` M4.

---

### MeasurementsScreen

- Receives `route.params.measurements` from CameraScreen (the raw API response)
- Displays length, width, area in both inches and cm
- **Size estimation:**
  - `getBestSize(length_in)` — single best Brannock size (men's only)
  - `getSizeRange(length_in)` — plausible range (±0.5" tolerance)
- Navigation: "Go to My Closet" (onboarding) or "See Recommendations" (post-capture)
- Measurements are **not** persisted locally — they are re-fetched from the API when needed (e.g. by ClosetScreen)

---

### RecommendationsScreen

The largest screen (~1010 lines). Fully wired to the live API.

**Data fetching:** `useFocusEffect` → `GET /api/recommendations/?sub_type=<optional>`

**Filter drawer** (animated right-slide panel):
- **Browse by:** Function (use case) or Silhouette (style)
- **Function categories:** Athletic, Casual, Work, Formal
- **Silhouette categories:** Boot, Sneaker, Slip-on, Dress Shoe
- **Attribute filters:** Waterproof, Vegan, Slip Resistant, Safety Toe, Wide Available
- Draft/apply workflow: filter changes only commit when user taps "Apply filters"
- Filters are applied client-side against the API response

**Shoe cards:**
- Brand name + heart icon (toggles `SavedShoesContext`)
- Model name
- Fit score badge (color-coded by status: PERFECT=green, GOOD=light green, ACCEPTABLE=orange, MARGINAL=red, POOR=dark red, REJECTED=gray)
- Shoe image or placeholder box
- Function/style/attribute tag chips
- "View details" button → opens `product_url` in browser (if available)

**Toast:** "Added/Removed from Saved Shoes" (1.8s auto-dismiss)

**Empty states:** no measurement yet, fetch error, no results after filtering

---

### ProfileScreen

- Avatar display with "Change photo" button (UI only — not implemented)
- **Delete account:** Alert confirmation → `DELETE /api/auth/delete/` → clear token → Google sign-out → navigate to Welcome
- **Sign out:** Clear token + Google sign-out → navigate to Welcome
- **Backend smoke test:** Parallel fetch to `/api/health/` + `/api/shoes/` → shows connection status, shoe count, first 3 brands

---

### SavedShoesScreen *(stub)*

Empty state placeholder. `UserCollection` model and `SavedShoesContext` already exist — the screen just needs its UI and API wiring.

---

### OwnedShoesScreen *(stub)*

Same situation as SavedShoesScreen.

---

## 4. State Management

The app uses React hooks (`useState`, `useEffect`, `useFocusEffect`) for local screen state and a single Context for cross-screen state.

### SavedShoesContext (`frontend/SavedShoesContext.js`)

Manages the user's wishlist (heart-saved shoes from RecommendationsScreen).

**Note:** This file currently has unresolved merge conflicts with two implementations:

- **HEAD version:** In-memory array (`savedShoes`), no persistence, exposes `{ savedShoes, toggleSaved(shoe), isSaved(id) }`
- **OrsBranch version:** `AsyncStorage`-backed map under the key `savedShoes`, exposes `{ savedMap, toggleSaved(shoe), isSaved(id) }` where `savedMap` is `{ [shoe.id]: shoe }`

Resolve to the OrsBranch version per the guidance in [CONTRIBUTING.md](./CONTRIBUTING.md).

**Usage:**

```js
import { useSavedShoes } from '../SavedShoesContext';

const { isSaved, toggleSaved } = useSavedShoes();

// In a shoe card:
<TouchableOpacity onPress={() => toggleSaved(shoe)}>
  <Ionicons name={isSaved(shoe.id) ? 'heart' : 'heart-outline'} />
</TouchableOpacity>
```

---

## 5. Services

### `frontend/services/auth.js`

```js
googleSignIn()              // triggers native Google picker → returns idToken
signInWithGoogle(idToken)   // POST /api/auth/google/ → returns { key }
```

Configure `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in `frontend/.env`.

---

## 6. Config & Utilities

### `frontend/config/api.js`

Exports a single `API_BASE_URL` string. Platform-aware:

```js
// Android emulator → http://10.0.2.2:8000
// iOS simulator    → http://127.0.0.1:8000
// Override         → process.env.EXPO_PUBLIC_API_URL
```

Always import from here — never hard-code backend URLs in screens.

### `frontend/utils/shoeSize.js`

Brannock formula helpers (men's sizes only — no women's formula in the frontend):

```js
getBestSize(lengthIn)       // → string, nearest US men's half-size (e.g. "9.5")
getSizeRange(lengthIn)      // → string[], sizes within ±0.5" tolerance (e.g. ["8.5", "9", "9.5"])
sizeToLength(size)          // → float, inverse formula
```

Formula (men's / unisex only): `size = 3 × lengthIn − 22`

The women's formula (`3 × lengthIn − 20.5`) exists only in the backend fit algorithm (`backend/services/fit_algorithm.py`).

### `frontend/constants/attributes.js`

Defines the `ATTRIBUTE_FILTERS` array used by the filter drawer in `RecommendationsScreen`. Each entry has `key`, `label`.

---

## 7. Storage Strategy

| Data | Storage | Key / Source |
|---|---|---|
| Auth token | `expo-secure-store` | `authToken` |
| Latest measurements | API (not persisted locally) | `GET /api/measurements/latest/` on every screen focus |
| Saved shoes (wishlist) | `AsyncStorage` (OrsBranch) | `savedShoes` |

`expo-secure-store` is hardware-backed on Android (uses the Android Keystore) and uses iOS Keychain on iOS. Use it for any sensitive value.

`AsyncStorage` is plaintext key-value storage. Suitable for non-sensitive data like shoe lists.

**Note:** Measurements are fetched from the API each time — they are not cached in AsyncStorage. `ClosetScreen` calls `GET /api/measurements/latest/` via `useFocusEffect`, and `MeasurementsScreen` receives measurements via `route.params` from `CameraScreen`.

---

## 8. Styling

Styles are defined inline with `StyleSheet.create` at the bottom of each screen file. There is no global theme file yet.

Common colors in use:
- Background: `#FFFBF5` (warm off-white)
- Primary accent: `#C28A5B` (warm brown)
- Text: `#1A1A1A` (near-black)
- Muted text: `#888` (gray)

**`frontend/styles/emptyState.js`** exports shared styles for empty-state UI (icon, title, subtitle). Use this whenever adding a new empty state instead of defining your own.

Font: **Outfit** (loaded via `expo-font` in `App.js`). Weights: Regular (400), Medium (500), SemiBold (600), Bold (700).

---

## 9. Key Patterns

### Authenticated API call

Every request to a protected endpoint follows this pattern (CameraScreen is the reference):

```js
import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL } from '../config/api';

const token = await SecureStore.getItemAsync('authToken');
const response = await fetch(`${API_BASE_URL}/api/some-endpoint/`, {
  method: 'GET',
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json',
  },
});
const data = await response.json();
```

Note: the token format is `Token <key>` (DRF format), not `Bearer`.

### Fetch on screen focus

Use `useFocusEffect` (from `@react-navigation/native`) instead of `useEffect` when data should refresh every time the user navigates back to a screen:

```js
import { useFocusEffect } from '@react-navigation/native';

useFocusEffect(
  React.useCallback(() => {
    fetchData();
  }, [])
);
```

### Platform-specific sensor code

```js
import { Platform } from 'react-native';

if (Platform.OS === 'android') {
  // Android-only: LightSensor
}
```

---

## 10. Native Modules & Build Requirements

This app uses native modules that **do not work in Expo Go**. A custom dev client (EAS build) is required:

| Module | Purpose | Requires dev client |
|---|---|---|
| `expo-camera` | Camera feed + photo capture | Yes |
| `expo-sensors` | Accelerometer + light sensor | Yes |
| `@react-native-google-signin/google-signin` | Native Google Sign-In | Yes |

See [`SETUP.md`](./SETUP.md#6-android-dev-client-build-one-time) for the one-time build process.

You only need to rebuild the dev client when:
- A new native dependency is added
- `app.json` plugins are changed
- Native config (android package name, permissions) changes

For all other changes (UI, logic, styles), Metro hot-reload handles it with no rebuild.

---

## 11. NPM Scripts

Run from the `frontend/` directory:

| Script | Command | Use |
|---|---|---|
| `npm start` | `expo start --tunnel` | Physical device or different-network testing |
| `npm run android` | `expo start --lan` | Android emulator on same machine |
| `npm run ios` | `expo start --ios` | iOS simulator (Mac only) |
| `npm run web` | `expo start --web` | Web preview (limited — no native modules) |

---

## 12. Package Dependencies

Key dependencies and why they're there:

| Package | Version | Purpose |
|---|---|---|
| `react` | 19.1.0 | Required by Expo SDK 54 |
| `react-native` | 0.81.5 | Mobile framework |
| `expo` | ~54.0.0 | Expo SDK |
| `@react-navigation/native` | — | Navigation core |
| `@react-navigation/native-stack` | — | Stack navigator |
| `@react-navigation/bottom-tabs` | — | Tab bar |
| `expo-camera` | — | Camera feed + capture |
| `expo-sensors` | — | Accelerometer + light sensor |
| `expo-secure-store` | — | Hardware-backed token storage |
| `@react-native-async-storage/async-storage` | — | Plaintext key-value storage |
| `@react-native-google-signin/google-signin` | — | Native Google Sign-In |
| `expo-font` | — | Load Outfit font |
| `@expo/vector-icons` | — | Ionicons |
| `expo-linear-gradient` | — | Gradient backgrounds |
| `react-native-safe-area-context` | — | Safe area insets |
| `react-native-svg` | — | SVG rendering |
| `expo-image-picker` | — | (installed; not yet used) |
