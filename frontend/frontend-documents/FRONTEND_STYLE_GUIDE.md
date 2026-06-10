# Frontend Style Guide

Conventions for the Shoe Shopper Expo + React Native app. This document reflects how the code is written today — follow these patterns when adding or changing frontend code.

---

## Stack & entry point

| Layer | Choice |
|-------|--------|
| Runtime | Expo SDK 54, React Native 0.81, React 19 |
| Navigation | `@react-navigation/native` — root stack + bottom tabs + nested stacks |
| Fonts | Outfit (`Outfit_400Regular`, `Outfit_600SemiBold`) via `@expo-google-fonts/outfit` |
| Icons | `@expo/vector-icons` — mostly `Ionicons`; `WelcomeScreen` also uses `Feather` and `FontAwesome5` |
| Storage | `expo-secure-store` for auth token; `@react-native-async-storage/async-storage` for wishlist/closet |

- **Entry:** `index.js` registers `App.js`.
- **Bootstrap:** `App.js` loads fonts, reads `authToken` from SecureStore to pick the initial route, wraps the tree in context providers, and renders `NavigationContainer`.

---

## Project layout

```
frontend/
├── App.js                  # Navigation, fonts, providers, shared header options
├── SavedShoesContext.js    # Wishlist state (AsyncStorage)
├── OwnedShoesContext.js    # Owned / closet state (AsyncStorage)
├── config/
│   └── api.js              # API_BASE_URL
├── constants/
│   └── attributes.js       # ATTRIBUTE_FILTERS for recommendations drawer
├── screens/                # Full-screen views (see naming below)
├── services/               # auth.js, devMockMeasurement.js
├── styles/
│   └── emptyState.js       # Shared empty-state styles (currently unused — screens inline their own)
├── utils/
│   └── shoeSize.js         # US men's size helpers
├── assets/                 # Images, logo.svg, etc.
├── components/             # Placeholder — no shared components yet
└── plugins/                # Native config (e.g. withARCore.js)
```

---

## Navigation

All navigators are defined in `App.js` (not split into separate files).

### Root stack

| Route | Screen | Purpose |
|-------|--------|---------|
| `Welcome` | `WelcomeScreen` | Unauthenticated landing |
| `Login` | `LoginScreen` | Google sign-in |
| `MainTabs` | `MainTabs` | Authenticated tab shell (header hidden) |
| `FootCapture`, `Camera`, `ARFootCapture`, `ARCamera`, `Measurements`, `Recommendations` | Same-named screens | Also reachable from root for certain flows |

Initial route: `Welcome` if no `authToken`, else `MainTabs`.

### Bottom tabs (`MainTabs`)

| Tab name | Label | Stack | Home screen |
|----------|-------|-------|-------------|
| `Closet` | Dashboard | `ClosetStackNavigator` | `Dashboard` (`ClosetHome`) |
| `Recommendations` | Recommendations | `RecommendationsStackNavigator` | `RecommendationsScreen` |
| `Profile` | Profile | `ProfileStackNavigator` | `ProfileScreen` |

Tab bar colors: active `#C28A5B`, inactive `#6B5F52`, background `#FFFBF5`, border `#E2D4C0`.

The tab bar is **hidden** when the Closet stack is on: `FootCapture`, `Camera`, `ARFootCapture`, `ARCamera`, or `Measurements`.

### Closet stack routes

| Route | Component | Title |
|-------|-----------|-------|
| `ClosetHome` | `Dashboard` | Dashboard |
| `SavedShoes` | `Wishlist` | Wishlist |
| `OwnedShoes` | `Closet` | My Closet |
| `Feedback` | `FeedbackScreen` (`feedback.js`) | Fit Feedback |
| `FootCapture` | `FootCaptureScreen` | Capture Foot Photo |
| `Camera` | `CameraScreen` | Camera |
| `ARFootCapture` | `ARFootCaptureScreen` | Measure with AR |
| `ARCamera` | `ARCameraScreen` | AR Camera |
| `Measurements` | `MeasurementsScreen` | Your Measurements |

### Shared header config

```js
const sharedHeaderOptions = {
  headerStyle: { backgroundColor: '#F5EFE6' },
  headerShadowVisible: false,
  headerTitleStyle: { fontFamily: 'Outfit_600SemiBold' },
  contentStyle: { backgroundColor: '#FCFAF7' },
};
```

Custom back buttons use `headerLeftBack` (go back) or `headerLeftToWelcome` (pop to Welcome). Both use `Ionicons` `chevron-back` at `#2F2A25` with `hitSlop`.

### Cross-tab navigation

From a nested screen, reach another tab via the parent navigator:

```js
navigation.getParent()?.navigate('Recommendations', { screen: 'RecommendationsHome' });
```

Sign-out resets the root stack to `Welcome` via `CommonActions.reset`.

### Route params in use

| Param | Used by | Meaning |
|-------|---------|---------|
| `fromOnboarding` | Foot capture, camera, measurements | First-time scan flow; changes CTA copy and destinations |
| `measurements` | `MeasurementsScreen` | Foot scan result object |
| `galleryUri` | `CameraScreen` | Pre-selected image from gallery |
| `shoe` | `FeedbackScreen` | Owned shoe to rate |

---

## Screen file naming

Naming is **mixed** — prefer `SomethingScreen.js` for new screens, but existing files include:

| Pattern | Examples |
|---------|----------|
| `*Screen.js` | `LoginScreen.js`, `WelcomeScreen.js`, `RecommendationsScreen.js`, `FootCaptureScreen.js` |
| Short names | `Dashboard.js`, `Wishlist.js`, `Closet.js` |
| Lowercase | `feedback.js` → exports `FeedbackScreen` |

Default export per file: `export default function ScreenName({ navigation, route }) { ... }`.

Small helper components (e.g. `SectionHeader` in `Dashboard.js`, `FitSlider` in `feedback.js`) live in the same file as the screen that uses them.

---

## State & data flow

### React patterns

- **Functional components only** — no class components.
- **`useState`** — local UI state (`loading`, form inputs, filter drafts).
- **`useEffect`** — one-off setup (sensors, navigation options, cleanup).
- **`useFocusEffect`** — refetch when a screen gains focus (Dashboard, Recommendations, Profile). Always use a `cancelled` flag in the async cleanup:

```js
useFocusEffect(
  useCallback(() => {
    let cancelled = false;
    (async () => {
      // fetch...
      if (cancelled) return;
      setData(...);
    })();
    return () => { cancelled = true; };
  }, [])
);
```

- **`useMemo`** — derived/filtered lists (`RecommendationsScreen`).
- **`useCallback`** — stable handlers passed to children or scroll listeners.
- **`useRef`** — animation values, debounce timers, camera refs.

### Context providers

Both providers wrap the app in `App.js` (outer: `OwnedShoesProvider`, inner: `SavedShoesProvider`).

| Context | Hook | Storage key | Purpose |
|---------|------|-------------|---------|
| `SavedShoesContext` | `useSavedShoes()` | `savedShoes` | Wishlist — `savedMap`, `savedShoes`, `toggleSaved`, `isSaved` |
| `OwnedShoesContext` | `useOwnedShoes()` | `ownedShoes` | Closet — `ownedMap`, `ownedShoes`, `toggleOwned`, `isOwned` |

Shoes are stored as a **map keyed by `id`**; lists are `Object.values(map)`.

**Wishlist ↔ Closet moves** use a `returnToWishlistOnRemove` flag on the shoe object:

- Moving from Wishlist → Closet sets `returnToWishlistOnRemove: true` and removes from wishlist.
- Removing from Closet with that flag restores the shoe to the wishlist.

Items in the wishlist exclude shoes already in `ownedMap`. Recommendations hide shoes that are saved or owned.

### Auth token

- Stored in SecureStore under `authToken` (Django REST authtoken string).
- Read on app launch to set initial route; attached to API calls as `Authorization: Token ${token}`.
- Cleared on sign-out along with `GoogleSignin.signOut()`.

---

## API usage

### Base URL

`config/api.js`:

```js
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || defaultBaseUrl;
// defaultBaseUrl: Android emulator → 10.0.2.2:8000, else 127.0.0.1:8000
```

### Endpoints called from the app

| Endpoint | Method | Where |
|----------|--------|-------|
| `/api/auth/google/` | POST | `services/auth.js` |
| `/api/auth/delete/` | DELETE | `ProfileScreen` |
| `/api/profile/` | GET, PATCH | `ProfileScreen`, `Dashboard` |
| `/api/measurements/latest/` | GET | `Dashboard` |
| `/api/recommendations/` | GET | `Dashboard`, `RecommendationsScreen` |
| `/api/foot/measure/` | POST | `CameraScreen`, `ARCameraScreen` |
| `/api/dev/mock-measurement/` | POST | `services/devMockMeasurement.js` |

### Service vs inline fetch

- **In `services/` today:** Google auth (`auth.js`), dev mock measurement (`devMockMeasurement.js`).
- **Inline in screens:** profile, recommendations, measurements, foot scan upload.

When adding new backend calls, prefer a `services/` module that uses `API_BASE_URL` and throws `Error` with a useful message. Existing screens often catch errors and show `Alert.alert` or inline error text — match the surrounding screen.

### Error handling patterns

| Situation | Pattern |
|-----------|---------|
| Auth failure | `Alert.alert('Sign-in failed', err.message)` (`LoginScreen`) |
| Profile save | `Alert.alert('Could not save', e.message)` |
| List fetch failure | Inline message or centered empty state (`Dashboard`, `RecommendationsScreen`) |
| 404 on recommendations/measurements | Treated as "no scan yet", not a hard error |

---

## Environment variables

Set in `frontend/.env` (restart Metro after changes):

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_API_URL` | Backend base URL (overrides platform default) |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Google Sign-In web client ID |
| `EXPO_PUBLIC_EMULATOR_MOCK_MEASUREMENT=1` | Dev only — auto-posts mock measurement so Recommendations works without a camera |

---

## Visual design

### Color palette

| Role | Hex | Usage |
|------|-----|-------|
| Page background (warm) | `#F5EFE6` | Welcome, Login, Closet stack screens, Profile |
| Page background (neutral) | `#FAF9F6` / `#FCFAF7` | Dashboard, stack content |
| Card surface | `#FFFBF5` | Cards, tab bar |
| Card border | `#E2D4C0` | Card outlines, secondary buttons |
| Image placeholder | `#F0E2D0` | Shoe photo backgrounds |
| Primary text | `#2F2A25` | Headings, body emphasis |
| Secondary text | `#6B5F52` | Subtitles, labels |
| Muted / placeholder | `#B0A499`, `#A39380` | Icons, placeholders |
| Brand accent | `#C28A5B` | Primary buttons, active tab, hearts |
| Accent deep | `#9A6645` | Profile gradient, key-fact labels |
| Owned icon active | `#5D8A7E` | Filled bag icon on Closet/Wishlist |
| Error / danger | `#B3513D` | Load errors, destructive actions |
| White | `#FFFFFF` | Button text, card sections |

`ProfileScreen` defines local aliases (`ACCENT`, `MUTED`, `FG`, etc.) — same values as above.

### Fit status colors

Duplicated as `FIT_STATUS_COLOR` in `Closet.js`, `Wishlist.js`, and `RecommendationsScreen.js`:

| Status | Color |
|--------|-------|
| PERFECT | `#2E7D32` |
| GOOD | `#558B2F` |
| ACCEPTABLE | `#F57F17` |
| MARGINAL | `#E64A19` |
| POOR | `#B71C1C` |
| REJECTED | `#9E9E9E` |

Badges use `backgroundColor: statusColor + '20'` with a matching border.

### Typography

- **Outfit** for navigation headers, tab labels, Dashboard greeting, and Profile screen text (`fontFamily: 'Outfit_600SemiBold'` or `'Outfit_400Regular'`).
- **System font + `fontWeight`** everywhere else (`'700'`, `'600'` for headings; `'400'` for body).
- Typical sizes: titles 24–30, section titles 18–20, body 14–16, small labels 11–13.

### Layout conventions

- Root container: `flex: 1` with a background color.
- Horizontal padding: **24px** on most screens (`paddingHorizontal: 24`).
- Scrollable content: `ScrollView` with `contentContainerStyle` and `showsVerticalScrollIndicator={false}`.
- Cards: `borderRadius: 20`, `padding: 18`, `borderWidth: 1`, `borderColor: '#E2D4C0'`.
- **Primary CTA:** `backgroundColor: '#C28A5B'`, white text, `borderRadius: 999` (pill) or `12` (rectangular card button).
- **Secondary CTA:** cream fill `#FFFBF5` with `#E2D4C0` border (e.g. Google button on Login).
- **Disabled state:** `opacity: 0.5` or `0.45`.
- Touch targets: `hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}` on icon buttons.
- Responsive widths: `Dimensions.get('window')` for carousels and card sizing.

### Shoe cards (shared UI pattern)

Wishlist, Closet, Recommendations, and Dashboard previews share a common card vocabulary:

- Brand (small, `#4F453C`) + model name (bold, 17px)
- Optional colorway, fit badge, shoe image or dashed placeholder
- **Key facts row** (Wishlist / Recommendations): size + price in a tinted `#C28A5B` panel
- **Attribute tags:** `#F0E2D0` pills
- **Actions:** heart (wishlist) and bag-handle (owned) in the card header
- **View details:** `Linking.openURL(item.product_url)` when URL present

### Empty states

Centered column: large `Ionicons` outline icon (`#B0A499`), title (`fontSize: 18`, `fontWeight: '600'`), subtitle (`fontSize: 14`, `#6B5F52`, centered). `styles/emptyState.js` exports this pattern but screens currently duplicate it inline — either import `emptyStateStyles` or copy the same values.

### Toasts

`RecommendationsScreen` shows brief feedback with local state + `setTimeout` (~1.8s) — not a global toast library.

---

## Styling approach

1. **`StyleSheet.create({ ... })` at the bottom of each screen file** — no global theme object yet.
2. **Screen-level color constants** at the top when a file uses many repeats (e.g. `ProfileScreen`).
3. **Module-level layout constants** for responsive math (`SCREEN_WIDTH`, `H_PAD`, `PREVIEW_LIMIT` in `Dashboard.js`).
4. **No shared component library** — `components/` is empty; reuse patterns by copying card/empty-state structure.

When extracting shared styles, prefer `styles/` modules (like `emptyState.js`) over a new components folder unless the UI is genuinely reusable.

---

## Imports

Typical order (not strict everywhere, but `App.js` and larger screens follow it):

1. React / hooks
2. React Native primitives
3. Expo modules (`expo-secure-store`, `expo-camera`, etc.)
4. Third-party (`@react-navigation/*`, `@expo/vector-icons`)
5. Internal: contexts, `config/api`, `constants/*`, `services/*`, `utils/*`
6. Relative assets (`require('../assets/...')`)

Use **relative paths** from screens (`../SavedShoesContext`, `../config/api`).

---

## Domain helpers

### `utils/shoeSize.js`

- `getBestSize(lengthIn)` — closest US men's size for a foot length in inches.
- `getSizeRange(lengthIn)` — plausible sizes within ±0.5" measurement deviation.

Used by `MeasurementsScreen` and `Dashboard`.

### `constants/attributes.js`

`ATTRIBUTE_FILTERS` — boolean attribute keys for the recommendations filter drawer (`waterproof`, `vegan`, etc.). Filter logic checks `item.attributes_json[key]`.

---

## Foot measurement flows

Two paths from `FootCaptureScreen`:

1. **AR (primary):** `ARFootCapture` → `ARCamera` → POST `/api/foot/measure/` → `Measurements`
2. **Paper (secondary):** `Camera` (live or gallery via `expo-image-picker`) → POST `/api/foot/measure/` → `Measurements`

`CameraScreen` uses tilt (`Accelerometer`) and light (`LightSensor`, Android) guidance during capture.

After scan, `MeasurementsScreen` shows length/width/area and estimated US size. With `fromOnboarding`, CTA goes to `MainTabs`; otherwise to Recommendations or back to Closet stack.

---

## Naming conventions

| Kind | Convention | Examples |
|------|------------|----------|
| Components | PascalCase | `Dashboard`, `RecommendationsScreen` |
| Functions / variables | camelCase | `handleGooglePress`, `toggleSaved`, `formatUsd` |
| Booleans | `is` / `has` / `should` / `can` | `isLoading`, `hasActiveFilters`, `canSave` |
| Constants | UPPER_SNAKE | `API_BASE_URL`, `FIT_STATUS_COLOR`, `ATTRIBUTE_FILTERS` |
| Context hooks | `use` + noun | `useSavedShoes`, `useOwnedShoes` |

---

## Known duplication (acceptable for now)

These are copy-pasted across screens today. When touching multiple files, consider extracting:

- `formatUsd(price)` — Dashboard, Wishlist, Recommendations
- `FIT_STATUS_COLOR` — Closet, Wishlist, Recommendations
- Empty-state styles — Closet, Wishlist, Recommendations (vs `styles/emptyState.js`)
- Shoe card layout — Wishlist and Recommendations are nearly identical

Do not refactor unrelated files just to dedupe — extract when you're already changing that area.

---

## Git conventions (frontend)

- Group related UI/flow changes in one commit.
- For frontend-only branches, prefer names like `fe/recommendations-filters`, `fe/login-copy`, `fe/dashboard-cards`.
