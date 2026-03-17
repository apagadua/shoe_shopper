# Shoe Shopper – Frontend

Expo + React Native app for the Shoe Shopper experience.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Install & Run](#install--run)
- [Running on Devices](#running-on-devices)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Development Notes](#development-notes)

---

## Prerequisites

- **Node.js** v18+ (includes `npm`)
  - Download from `https://nodejs.org`
  - Verify:
    ```bash
    node --version
    npm --version
    ```
- **Expo CLI tooling**
  - We use `npx expo …` (no global install required).
- **Expo Go** (optional, for physical devices)
  - iOS: App Store → “Expo Go”
  - Android: Play Store → “Expo Go”

---

## Install & Run

All commands below run from the `frontend` folder.

```bash
cd frontend
```

### Install dependencies

```bash
npm install
```

If you hit peer dependency conflicts:

```bash
npm install --legacy-peer-deps
```

### Start the development server

Standard Expo dev server with tunnel (good for phones on different networks):

```bash
npm start
```

or explicitly:

```bash
npx expo start
```

You’ll see Metro start, a QR code, and shortcuts like:

```text
› Press a │ open Android
› Press i │ open iOS simulator
› Press w │ open web
› Press r │ reload app
```

To clear the Metro cache:

```bash
npx expo start --clear
```

---

## Running on Devices

### Using Expo Go (physical devices)

1. Install **Expo Go** on your phone.
2. Make sure phone and computer have network connectivity (same Wi‑Fi works best).
3. From `frontend` run `npm start` / `npx expo start`.
4. In the terminal or Expo Dev Tools:
   - Scan the QR code with your phone’s camera (iOS) or Expo Go app (Android), **or**
   - Manually enter the URL shown (usually `exp://…exp.direct` when using tunnel).

### Using the Android emulator (dev client)

This project also supports an **Expo development build** for Android via EAS. High‑level flow:

1. Install Android Studio and create an AVD.
2. Build the dev client from `frontend`:
   ```bash
   npx eas-cli build --profile development --platform android
   ```
3. Download the APK from the EAS build page and drag‑and‑drop it onto the emulator.
4. Run the dev server for the dev client:
   ```bash
   npx expo start --dev-client
   ```
5. With the emulator running, press `a` in the terminal or open the installed app icon directly.

You only need to rebuild the dev client when native config/dependencies change; normal JS changes just use Metro.

### iOS

Currently **iOS uses Expo Go only** (no iOS dev client in this repo). Follow the Expo Go steps above.

---

## Troubleshooting

### “Unable to resolve module” / broken `node_modules`

```bash
rm -rf node_modules package-lock.json  # Mac

:: Windows
rmdir /s node_modules
del package-lock.json

npm install
```

### “Port 8081 already in use”

- Close other Expo/Metro instances, or:

```bash
:: Windows
netstat -ano | findstr :8081
taskkill /PID <PID> /F
```

### “Can’t connect to development server” / Expo Go cannot load app

- Ensure device and computer are on the same network (or use tunnel mode).
- Check the URL shown in the terminal matches your machine’s IP / tunnel URL.
- Restart the dev server:
  ```bash
  npm start
  ```

### Metro cache issues

```bash
npx expo start --clear
```

### Dependency / version mismatches

```bash
npm install
# If that doesn't work:
npm install --legacy-peer-deps
```

Expo SDK 54 in this project expects `"react": "19.1.0"` as configured in `package.json`.

---

## Project Structure

```
frontend/
├── .expo/            # Expo cache (auto-generated, gitignored)
├── App.js            # Main app component
├── app.json          # Expo configuration
├── assets/           # Images, fonts, etc.
│   ├── adaptive-icon.png
│   ├── favicon.png
│   ├── icon.png
│   └── splash-icon.png
├── components/       # Reusable UI components
├── screens/          # Screen components (Login, Upload, Recommendations, etc.)
├── services/         # API service files (backend API calls, authentication)
├── styles/           # Styling files (theme files, global styles)
├── utils/            # Utility functions (helpers, formatters, validators)
├── index.js          # Entry point
├── package.json      # Dependencies and scripts
├── package-lock.json # Locked dependency versions
└── README.md         # This file
```

---

## Development Notes

- Frontend coding conventions and patterns live in `FRONTEND_STYLE_GUIDE.md`.
- Backend and environment configuration are documented in the backend README and `.env` files (at the repo root and in `frontend/.env`).

---

## Additional Resources

- [Expo Documentation](https://docs.expo.dev/)
- [React Native Documentation](https://reactnative.dev/)
- [Expo Go Guide](https://docs.expo.dev/get-started/expo-go/)

---

## Expo Development Build (Android Dev Client)

Besides Expo Go, you can run an **Expo development build (dev client)** in the **Android Studio emulator**. The project is under the **shoeshopper** Expo organization; teammates must be invited to that org to run EAS builds. **“Expo development”** (as opposed to Expo Go).

**Android only.** iOS uses Expo Go only (see next section).

### One-time setup

1. **Install Android Studio** (Windows or Mac)  
   - [developer.android.com/studio](https://developer.android.com/studio) → Standard install (installs the Android SDK).

2. **Create an Android Virtual Device (AVD)**
   - Android Studio → **Device Manager** → **Create Device**.
   - Pick a phone (e.g. Pixel 6/7), then a **System Image** (e.g. API 36, Google Play Intel x86_64). Finish the wizard.

3. **Start the emulator**
   - In **Device Manager**, click the **Play ▶** button next to your device.
   - Wait for the Android home screen to appear.

4. **Build the dev client with EAS**  
   From the `frontend` directory:
   ```bash
   npx eas-cli build --profile development --platform android
   ```
   - Log in with your Expo account (must be a member of the **shoeshopper** org).
   - When the build finishes, EAS will show a **build page URL**.
   - Open that URL in your browser.
   - On the build page, click **Download build** to download the **.apk** file (ignore the QR‑code “Install” option; that’s for real devices).
   - Build takes about **10–25 minutes**; do it when you have time.

5. **Install the APK into the emulator**
   - Start the emulator if it isn’t already running.
   - Locate the downloaded `.apk` file (e.g. in your Downloads folder).
   - **Drag and drop the `.apk` onto the emulator window**.
   - Android will install the app; you can find it in the **app drawer** and optionally drag it to the home screen.

You only need to run this build again if you add native dependencies or change native config. For normal JS/UI changes, no rebuild needed—use the daily workflow below.

### Daily development (dev client)

1. **Start the dev server**  
   From `frontend`:
   ```bash
   npx expo start --dev-client
   ```
   Leave this running.

2. **Open the Android emulator**
   - Start your AVD from Android Studio (Device Manager → Play).

3. **Launch the app in the emulator**
   - With `expo start --dev-client` running, press **`a`** in the terminal to target Android, **then**
   - Open the installed app icon (e.g. `Shoe Shopper`) in the emulator’s app drawer / home screen.

4. **Iterate**
   - Edit code in the `frontend` project.
   - The dev client will reload changes via Metro (fast refresh / hot reload).
   - Use the usual shortcuts (reload, dev menu, etc.).

If you see **“Unable to load script”** in the emulator, make sure:
- `npx expo start --dev-client` is running in `frontend`, and
- The emulator is started **after** (or while) the dev server is running.

---

## iOS (Expo Go only)

This repo does **not** use an Expo dev client for iOS. Use **Expo Go** on an iPhone (see Expo Go Setup and Running the App). No Mac or Xcode required.

To add an iOS dev client later you’d need the Apple Developer Program ($99/year), EAS Build for iOS, and ideally a Mac for the simulator.

