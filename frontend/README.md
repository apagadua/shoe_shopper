# Shoe Shopper - Setup Guide

This guide will help you set up and run the Expo application on both **Mac** and **Windows**.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Expo Go Setup](#expo-go-setup)
- [Running the App](#running-the-app)
- [Connecting to the Development Server](#connecting-to-the-development-server)
- [Troubleshooting](#troubleshooting)

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

3. **Expo Go App** (on your mobile device)
   - **iOS**: Download from [App Store](https://apps.apple.com/app/expo-go/id982107779)
   - **Android**: Download from [Google Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent)

---

## Setup

### Step 1: Navigate to Project Directory

**Windows (PowerShell/Command Prompt):**
```bash
cd C:\Users\alyss\shoe_shopper\frontend
```

**Mac (Terminal):**
```bash
cd ~/shoe_shopper/frontend
```

**Note:** All commands must be run from the `frontend` directory. There is no root `package.json` - all project files are in the `frontend` directory.

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

Check that `node_modules` directory was created:

**Windows:**
```bash
dir node_modules
```

**Mac:**
```bash
ls node_modules
```

---

## Expo Go Setup

### For iOS (iPhone/iPad)

1. **Download Expo Go**
   - Open the App Store on your iOS device
   - Search for "Expo Go"
   - Install the app (it's free)

2. **Connect to Same Network**
   - Ensure your computer and iOS device are on the **same Wi-Fi network**
   - This is required for local development

3. **Alternative: Use Tunnel Mode**
   - If you can't use the same network, the app is configured to use tunnel mode by default
   - This allows connection over the internet (slower but works from anywhere)

### For Android

1. **Download Expo Go**
   - Open Google Play Store on your Android device
   - Search for "Expo Go"
   - Install the app (it's free)

2. **Connect to Same Network**
   - Ensure your computer and Android device are on the **same Wi-Fi network**
   - Or use tunnel mode (configured by default)

---

## Running the App

**Windows:**
```bash
cd C:\Users\alyss\shoe_shopper\frontend
npm start
```

**Mac:**
```bash
cd ~/shoe_shopper/frontend
npm start
```

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

### Method 3: Using Tunnel Mode

The app is configured to use **tunnel mode** by default, which means:
- Works even if devices are on different networks
- Slower connection but more reliable
- URL will look like: `exp://kis3qp8-anonymous-8081.exp.direct`

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

**Note:** React version is set to **19.1.0** as required by Expo SDK 54. If you see React version conflicts, ensure `package.json` has `"react": "19.1.0"`.

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
├── .expo/            # Expo configuration (auto-generated)
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
├── package-lock.json # Locked dependency versions (committed to git)
└── README.md         # This file
```

---

## Additional Resources

- [Expo Documentation](https://docs.expo.dev/)
- [React Native Documentation](https://reactnative.dev/)
- [Expo Go Guide](https://docs.expo.dev/get-started/expo-go/)

---

## Notes

- **All commands must be run from the `frontend` directory** - there is no root `package.json`
- The `.expo` directory is auto-generated and should not be committed to git
- `package-lock.json` is committed to git to ensure consistent dependency versions
- Development server runs on port **8081** by default
- Tunnel mode is enabled by default for easier connection
- Hot reloading is enabled automatically - save files to see changes instantly
- React version: **19.1.0** (required by Expo SDK 54)
-
---

## Expo Development Build (Android Dev Client)

In addition to Expo Go, this project also supports an **Expo development build (dev client) on Android**, which runs in the Android Studio emulator. This is what the team refers to as **“Expo development”** (as opposed to Expo Go).

> **Note:** This section is for **Android only**. See the next section for the current iOS status.

### Android Dev Client – One‑Time Setup

1. **Install Android Studio (Windows)**
   - Download from `https://developer.android.com/studio`
   - Run the installer and complete the default **Standard** setup (this installs the Android SDK).

2. **Create an Android Virtual Device (AVD)**
   - Open **Android Studio** → **Device Manager** (or **More Actions → Virtual Device Manager**).
   - Click **Create Device**.
   - Recommended: choose a **Pixel 6 / Pixel 7** (or similar ~6" phone).
   - On the **System Image** screen:
     - Choose a recent image (e.g. **API 36 Baklava**).
     - Prefer **Google Play Intel x86_64 Atom System Image** (no need for the pre‑release variants).
   - Finish the wizard.

3. **Start the emulator**
   - In **Device Manager**, click the **Play ▶** button next to your device.
   - Wait for the Android home screen to appear.

4. **Build the Android dev client with EAS**
   - In a terminal:
     ```bash
     cd C:\Users\alyss\shoe_shopper\frontend
     npx eas-cli build --profile development --platform android
     ```
   - Sign in with your Expo account when prompted.
   - When the build finishes, EAS will show a **build page URL**.
   - Open that URL in your browser.
   - On the build page, click **Download build** to download the **.apk** file (ignore the QR‑code “Install” option; that’s for real devices).
   -This will take about 10-25 minutes to build so do it when you have time

5. **Install the APK into the emulator**
   - Start the emulator if it isn’t already running.
   - From Windows **File Explorer**, locate the downloaded `.apk` file.
   - **Drag and drop the `.apk` onto the emulator window**.
   - Android will install the app; you can find it in the **app drawer** and optionally drag it to the home screen.

After this, the Android dev client is installed and can be reused for daily development.

### Android Dev Client – Daily Development Workflow

1. **Start the dev server (Metro) for the dev client**
   - From the `frontend` directory:
     ```bash
     cd C:\Users\alyss\shoe_shopper\frontend
     npx expo start --dev-client
     ```
   - Leave this terminal running.

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

## Current iOS Status (No Dev Client Yet)

At the moment, this repo **does not use an Expo dev client for iOS**. iOS testing is still done via **Expo Go only**:

- Open the project with **Expo Go** on an iPhone (see the **Expo Go Setup** and **Running the App** sections above).
- This works on Windows because no Mac or Xcode is required.

To use an **iOS Expo dev client (development build) on a real iPhone**, you must:

- Enroll in the **Apple Developer Program** (currently **$99/year**), and
- Use EAS Build for iOS with Apple signing credentials, and
- Ideally have access to a **Mac** if you want to use the iOS Simulator (Xcode only runs on macOS).

Because the current developer only has a **Windows PC** and does **not** have a paid Apple Developer account, the iOS dev‑client workflow is **not configured** here.

- **Android** → uses an **Expo dev client** (development build) in the Android Studio emulator.
- **iOS** → uses **Expo Go** for now, until someone with a paid Apple Developer account and/or a Mac sets up the iOS dev‑client pipeline.

