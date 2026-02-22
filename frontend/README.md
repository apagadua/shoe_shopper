# Shoe Shopper - Setup Guide

This guide will help you set up and run the Expo application on both **Mac** and **Windows**.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Expo Go Setup](#expo-go-setup)
- [Running the App](#running-the-app)
- [Connecting to the Development Server](#connecting-to-the-development-server)
- [Troubleshooting](#troubleshooting)
- [Expo Development Build (Android)](#expo-development-build-android-dev-client)
- [iOS (Expo Go only)](#ios-expo-go-only)
- [Project Structure](#project-structure)

---

## Prerequisites

### Required Software

1. **Node.js** (v18 or higher)
   - **Windows/Mac**: Download from [nodejs.org](https://nodejs.org/)
   - Verify installation:
     ```bash
     node --version
     npm --version
     ```

2. **npm** (comes with Node.js)
   - Verify installation:
     ```bash
     npm --version
     ```

3. **Expo Go** (for running on a physical phone via QR code)
   - [iOS](https://apps.apple.com/app/expo-go/id982107779) · [Android](https://play.google.com/store/apps/details?id=host.exp.exponent)  
   - Optional if you only use the Android emulator with the dev client.

---

## Setup

### Step 1: Navigate to Project Directory

From the repo root, go into `frontend` (all commands in this guide run from `frontend`; there is no root `package.json`):

```bash
cd frontend
```

### Step 2: Install Dependencies

Install all required packages:

```bash
npm install
```

This will install all dependencies listed in `package.json`. Wait for the installation to complete (this may take a few minutes).

**Note:** If you encounter peer dependency conflicts, try:
```bash
npm install --legacy-peer-deps
```

### Step 3: Verify Installation

Check that `node_modules` was created: run `dir node_modules` (Windows) or `ls node_modules` (Mac).

---

## Expo Go Setup

1. **Install Expo Go** on your phone: [iOS App Store](https://apps.apple.com/app/expo-go/id982107779) or [Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent).
2. **Network:** Phone and computer on the same Wi‑Fi works best. The app uses **tunnel mode** by default (`npm start`), so it can connect from different networks too (slower).

---

## Running the App

From the `frontend` directory:

```bash
npm start
```

This starts Metro with **tunnel mode** by default (so your phone can connect even on a different network).

### What Happens Next

After running `npm start`, you should see:

1. **Metro Bundler starting** - This is the JavaScript bundler
2. **QR Code** - A QR code will appear in your terminal
3. **Connection options** - You'll see options like:
   ```
   › Press a │ open Android
   › Press i │ open iOS simulator
   › Press w │ open web
   › Press r │ reload app
   ```

---

## Connecting to the Development Server

### Method 1: Scan QR Code (Recommended)

#### iOS:
1. Open the **Camera app** on your iPhone/iPad
2. Point the camera at the QR code in your terminal
3. Tap the notification that appears
4. Expo Go will open and load your app

#### Android:
1. Open the **Expo Go app** on your Android device
2. Tap **"Scan QR code"**
3. Point your camera at the QR code in your terminal
4. The app will load automatically

### Method 2: Manual Connection

If QR code scanning doesn't work:

#### iOS:
1. Open Expo Go app
2. Tap **"Enter URL manually"**
3. Enter the URL shown in your terminal (e.g., `exp://192.168.1.100:8081`)

#### Android:
1. Open Expo Go app
2. Tap **"Enter URL manually"**
3. Enter the URL shown in your terminal

### Method 3: Tunnel mode

`npm start` uses tunnel mode by default, so the URL will look like `exp://….exp.direct`. Works across different networks; a bit slower than LAN.

---

## Using Expo Go

### Hot Reloading

- **Automatic**: Changes to your code automatically reload in the app
- **Manual Reload**: Shake your device and tap "Reload" (or press `r` in terminal)

### Developer Menu

#### iOS:
- Shake your device to open the developer menu
- Or use a three-finger tap

#### Android:
- Shake your device to open the developer menu
- Or press the menu button

### Common Actions

- **Reload App**: Shake device → "Reload"
- **Debug**: Shake device → "Debug Remote JS"
- **Performance Monitor**: Shake device → "Show Performance Monitor"

### Keyboard Shortcuts (in Terminal)

While the dev server is running:
- `r` - Reload the app
- `m` - Toggle menu
- `a` - Open on Android emulator (if installed)
- `i` - Open on iOS simulator (Mac only)
- `w` - Open in web browser
- `j` - Open debugger
- `Ctrl+C` - Stop the server

---

## Troubleshooting

### Issue: "Unable to resolve module"

**Solution:**
```bash
rm -rf node_modules package-lock.json  # Mac
# OR
rmdir /s node_modules  # Windows
del package-lock.json   # Windows

npm install
```

### Issue: "Port 8081 already in use"

**Solution:**
- Close other Expo/Metro bundler instances
- Or kill the process:
  ```bash
  # Mac
  lsof -ti:8081 | xargs kill -9
  
  # Windows
  netstat -ano | findstr :8081
  taskkill /PID <PID> /F
  ```

### Issue: "Can't connect to development server"

**Solutions:**
1. **Check Network Connection**
   - Ensure device and computer are on same Wi-Fi
   - Try tunnel mode (already enabled by default)

2. **Firewall Issues (Windows)**
   - Allow Node.js through Windows Firewall
   - Settings → Firewall → Allow an app → Node.js

3. **Check IP Address**
   - Terminal shows the connection URL
   - Verify it matches your computer's local IP

### Issue: "Expo Go can't find the app"

**Solutions:**
1. Make sure you're scanning the correct QR code
2. Try entering the URL manually in Expo Go
3. Restart the development server:
   ```bash
   # Press Ctrl+C to stop, then:
   npm start
   ```

### Issue: "Metro bundler cache issues"

**Solution:**
```bash
npx expo start --clear
```

### Issue: "Package version mismatches" or "ERESOLVE could not resolve"

**Solution:**
```bash
npm install
# If that doesn't work:
npm install --legacy-peer-deps
```

If you see React version conflicts, ensure `package.json` has `"react": "19.1.0"` (required by Expo SDK 54).

### Issue: "expo-modules-core errors"

**Solution:**
```bash
rm -rf node_modules package-lock.json  # Mac
# OR
rmdir /s node_modules  # Windows
del package-lock.json   # Windows

npm install
```

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

