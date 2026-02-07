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

