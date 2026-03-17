## Frontend Style Guide

This reflects how the current frontend is written so new code matches existing patterns.

### Architecture

- **Entry & navigation**
  - `index.js` → `App.js` sets up fonts, `SavedShoesProvider`, and a stack + bottom tab navigator.
  - Nested stacks (`ClosetStack`, `RecommendationsStack`, `ProfileStack`) live in `App.js`, not separate files.
- **Screens**
  - Live in `screens/` and are named with the `SomethingScreen.js` pattern (for example `LoginScreen.js`, `ClosetScreen.js`).
  - Each screen:
    - Owns screen-level state (loading flags, filters, local UI state).
    - Uses navigation props (e.g. `navigation.navigate`, `navigation.setOptions`) directly.
    - Defines a `StyleSheet` at the bottom of the file.
- **Context**
  - Shared shoe state is in `SavedShoesContext.js` and exposed via `useSavedShoes`.
  - New cross-screen shared state should follow this pattern: context file + provider in `App.js`.
- **Services & config**
  - `services/auth.js` encapsulates Google sign-in and backend auth (`googleSignIn`, `signInWithGoogle`).
  - `config/api.js` owns API base URL logic (including `EXPO_PUBLIC_API_URL`).
  - New backend access should go into `services/` modules that build on `API_BASE_URL`.

### Naming

- **Files**
  - Screens: `SomethingScreen.js` in `screens/` (`LoginScreen.js`, `ClosetScreen.js`, `RecommendationsScreen.js`, etc.).
  - Context: `SavedShoesContext.js` (and future contexts: `SomethingContext.js`).
  - Services: feature-based files in `services/` (`auth.js`, future `shoes.js`, etc.).
- **Components**
  - Default export per screen file (for example `export default function LoginScreen(...) { ... }`).
  - Use **PascalCase** for components (`LoginScreen`, `RecommendationsScreen`).
- **Functions & variables**
  - Use **camelCase** (`handleGooglePress`, `toggleSaved`, `showToast`).
  - Booleans start with `is` / `has` / `should` (`isLoading`, `hasActiveFilters`, `shouldShowEmptyState`).

### Styling & Layout

- Each screen defines a `const styles = StyleSheet.create({...})` at the bottom of the file.
- Colors and typography:
  - Use the existing palette seen in current screens (`#F5EFE6`, `#FFFBF5`, `#C28A5B`, `#2F2A25`, `#6B5F52`, etc.).
  - Match font usage (system fonts + Outfit from `App.js` where relevant).
- Layout:
  - Screens use `flex: 1` containers with padding and background colors matching existing screens.
  - Use `ScrollView` with `contentContainerStyle` for long content (see `ClosetScreen` and `RecommendationsScreen`).
  - For interactive elements, follow the existing button styles (`actionButton`, `googleButton`, pill-shaped primary buttons).

### State & Data Flow

- Use React hooks (no class components):
  - `useState` for local state (e.g. `loading`, filter selections).
  - `useEffect` for side effects (e.g. reading `authToken` from `SecureStore`, setting navigation options).
  - `useMemo` for derived data and filtered arrays (see `RecommendationsScreen`).
- Shared state:
  - Use context + provider pattern (see `SavedShoesContext` + `SavedShoesProvider`).
  - New global UI or data state should follow the same pattern and be wired into `App.js`.

### API Usage

- Use `API_BASE_URL` from `config/api.js` for all backend endpoints.
- Put network logic in `services/`:
  - `auth.js` is the template: `googleSignIn()` for client-side Google flow, `signInWithGoogle()` for hitting the backend.
  - New features should add service functions (for example `fetchRecommendations`, `saveOwnedShoe`) instead of calling `fetch` directly in screens.
- Error handling:
  - Service functions throw `Error` instances with a message derived from the response when possible.
  - Screens catch errors and surface them via `Alert` or UI state (`Alert.alert('Sign-in failed', err.message)` in `LoginScreen` is the current pattern).

### Imports & Organization

- Follow the import order used in `App.js` and screens:
  1. React / hooks (`React`, `useState`, `useEffect`, etc.).
  2. React Native primitives (`View`, `Text`, `ScrollView`, etc.).
  3. Expo / third-party libs (`expo-secure-store`, `@expo/vector-icons`, navigation imports).
  4. Internal modules (`SavedShoesContext`, `ATTRIBUTE_FILTERS`, `services/auth`, `config/api`).
  5. Local components (when added).
  6. Styles (where separated).
- Keep navigation-related helpers (like `headerLeftBack` in `App.js`) near the navigation definitions.

### Frontend Commit & Branch Conventions

- Commits should group related UI or flow changes (for example “Tweak closet dashboard cards”, “Add recommendations filter drawer animation”).
- For frontend-only work, prefer branch names like `fe/recommendations-filters`, `fe/login-copy`, `fe/profile-layout` so it’s obvious this is app UI/UX work.

