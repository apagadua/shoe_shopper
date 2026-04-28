# Shoe Shopper — Complete Setup Guide

This guide walks you through getting the Shoe Shopper app running on a new computer and phone from scratch. Take it one section at a time — each step builds on the previous one.

---

## Before You Start — What You'll Need

Before touching any code, make sure you have the following:

- **A computer** running Windows, Mac, or Linux
- **An Android or iPhone** for testing (the app cannot be fully tested in a simulator)
- **The project files** (either a zip from a teammate, or git access to the repo)
- **The `.env` secrets file** — ask a teammate for this. It contains API keys that are never stored in the code. Without it, the backend will not work.
- **Internet connection** throughout setup

**Accounts you will need** (ask a teammate if you don't have credentials):

| Service | What it's for | Where to sign up |
|---|---|---|
| Roboflow | AI that reads foot photos | roboflow.com |
| Google Cloud | Powers Google Sign-In | console.cloud.google.com |
| Expo | Builds the mobile app | expo.dev |
| Supabase *(optional for dev)* | Production database | supabase.com |

> **Note for development**: You can skip Supabase and use a local SQLite database for testing. The app will work fine without it on your own machine.

---

## Part 1 — Install the Required Software

You only need to do this once per computer.

### Step 1.1 — Install Python

The backend runs on Python. You need version **3.10 or newer**.

1. Go to https://www.python.org/downloads/
2. Download the latest stable version
3. **On Windows**: During installation, check the box that says **"Add Python to PATH"** — this is easy to miss
4. Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.0`. If you see an error, Python did not install correctly — try again.

### Step 1.2 — Install Node.js

The frontend (the phone app) runs on JavaScript and needs Node.js.

1. Go to https://nodejs.org/
2. Download the **LTS** version (the one labeled "Recommended for Most Users")
3. Install it with all default options
4. Verify it worked:
   ```
   node --version
   npm --version
   ```
   Both commands should print a version number.

### Step 1.3 — Install Git

Git is used to download and manage the code.

1. Go to https://git-scm.com/downloads
2. Download and install for your operating system
3. Use all default options during installation
4. Verify:
   ```
   git --version
   ```

### Step 1.4 — Install the EAS CLI (Expo Build Tool)

This tool is needed to build the app for your phone.

Open a terminal and run:
```
npm install -g eas-cli
```

Then verify:
```
eas --version
```

---

## Part 2 — Get the Code

### Step 2.1 — Clone the Repository

Open a terminal, navigate to where you want to store the project (e.g., your Desktop), and run:

```
git clone <repo-url> shoe_shopper_dev
cd shoe_shopper_dev
```

Replace `<repo-url>` with the actual GitHub link from your teammate.

**Alternative**: If you received a `.zip` file instead, extract it and open a terminal inside that folder.

### Step 2.2 — Add the Secrets File

Ask a teammate for the `.env` file. Place it in the **root of the project** (the main `shoe_shopper_dev` folder, not inside `backend` or `frontend`).

The file should look something like this (with real values filled in):
```
GOOGLE_CLIENT_ID=your-google-client-id-here
DJANGO_SECRET_KEY=some-long-random-string
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=
ROBOFLOW_API_KEY=your-roboflow-key
ROBOFLOW_WORKSPACE=armaanai
ROBOFLOW_PROJECT=foot-measuring
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=your-google-client-id-here
```

> **Security reminder**: Never share this file publicly or commit it to GitHub. It contains private API keys.

---

## Part 3 — Set Up the Backend (Django Server)

The backend is the "brain" of the app — it processes foot photos and serves shoe recommendations. It runs on your computer.

### Step 3.1 — Create a Virtual Environment

A virtual environment keeps the project's Python packages separate from the rest of your computer. Think of it as a clean, isolated workspace for this project.

Open a terminal in the `shoe_shopper_dev` folder and run:

**Mac/Linux:**
```
python -m venv venv
source venv/bin/activate
```

**Windows:**
```
python -m venv venv
venv\Scripts\activate
```

You'll know it worked when you see `(venv)` at the start of your terminal prompt.

> **Important**: Every time you open a new terminal to work on the backend, you need to run the `activate` command again.

### Step 3.2 — Install Python Packages

With the virtual environment active, install everything the backend needs:

```
pip install -r backend/requirements.txt
```

This will take a minute or two. You'll see a lot of text scroll by — that's normal.

### Step 3.3 — Set Up the Database

Run these two commands in order. They create the database tables the app needs:

```
python manage.py migrate
```

You should see output like `Applying backend.0001_initial... OK` for each migration. If you see errors here, the most common cause is a missing `.env` file from Step 2.2.

### Step 3.4 — Start the Backend Server

```
python manage.py runserver 0.0.0.0:8000
```

If it works, you'll see:
```
Starting development server at http://0.0.0.0:8000/
Quit the server with CTRL-BREAK.
```

The `0.0.0.0` part is important — it makes the server accessible from your phone on the same Wi-Fi network, not just from your computer.

**Keep this terminal window open** while using the app. The server stops when you close it.

### Step 3.5 — Test That the Backend Works

Open a web browser and go to:
```
http://127.0.0.1:8000/api/health/
```

You should see a JSON response like `{"status": "ok", "shoe_count": 0}`. If you see this, the backend is running correctly.

---

## Part 4 — Set Up the Frontend (The Phone App)

### Step 4.1 — Install JavaScript Packages

Open a **new terminal** (keep the backend terminal running), navigate into the frontend folder, and install packages:

```
cd frontend
npm install
```

This will take a few minutes the first time.

### Step 4.2 — Create a Frontend Environment File

The frontend needs to know where your backend server is. Create a file called `.env` inside the `frontend` folder (so the path is `frontend/.env`).

Find your computer's local IP address:

- **Windows**: Open Command Prompt, type `ipconfig`, look for "IPv4 Address" (e.g., `192.168.1.42`)
- **Mac**: System Settings → Network → click your Wi-Fi connection → IP shown there
- **Linux**: Run `ip addr show`, look for `inet` followed by an address

Add this line to `frontend/.env`, replacing the IP with yours:

```
EXPO_PUBLIC_API_URL=http://192.168.1.42:8000
```

Also add your Google Sign-In client ID (get this from a teammate or your Google Cloud Console):
```
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=your-google-web-client-id-here
```

### Step 4.3 — Log in to Your Expo Account

If you don't have one, create a free account at https://expo.dev, then run:

```
eas login
```

Enter your Expo username and password when prompted.

---

## Part 5 — Build the App for Your Phone

> **Why can't I just use Expo Go?**
> The app uses features like the camera, sensors, and Google Sign-In that require a special "development build." Expo Go (the standard Expo app) doesn't support these. You need to build a custom version of the app for your phone.

This is a one-time process. After the build is on your phone, you only need to restart the Expo development server for code changes — you don't need to rebuild unless you add new native features.

### Step 5.1 — Configure the EAS Project

Inside the `frontend` folder, run:

```
eas build:configure
```

If it asks about the project, confirm you want to use the existing `app.json` settings.

### Step 5.2 — Build for Android

```
eas build --profile development --platform android
```

This uploads your code to Expo's build servers and compiles the Android app. It will take **10–20 minutes**. You can watch the progress in the terminal or at expo.dev in your browser.

When it finishes, it will give you a download link for a `.apk` file.

### Step 5.3 — Install the App on Your Android Phone

1. On your Android phone, go to **Settings → Security** (or Privacy) and enable **"Install unknown apps"** or **"Unknown sources"**. The exact location varies by phone brand.
2. Download the `.apk` file from the link provided (open the link on your phone, or transfer the file via USB/Google Drive)
3. Tap the `.apk` file on your phone to install it
4. If your phone warns about installing from unknown sources, tap "Install anyway" — this is your own app, it's safe

**For iPhone (iOS):** The process is more complex and requires an Apple Developer account ($99/year). For development purposes, Android is much easier. If you need iOS, ask a teammate who has the Apple account set up.

---

## Part 6 — Run the App

Now you have all the pieces in place. Here's how to run everything together.

### Every Time You Want to Use the App

**Step 1**: Start the backend server (in the `shoe_shopper_dev` folder):

**Mac/Linux:**
```
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

**Windows:**
```
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

**Step 2**: Start the Expo server (in the `frontend` folder):

```
npm start
```

This uses **tunnel mode** — it routes through the internet so the app can reach your computer from anywhere, even if your phone is on a different network. Wait about 10 seconds for the QR code to appear.

**Step 3**: Open the app on your phone (it's named "shoe_shopper" and has the shoe icon). Scan the QR code shown in the terminal with your phone's camera. The app will load.

**Step 4**: Sign in with Google in the app. The backend verifies your Google account.

That's it — the app should be fully functional.

---

## Troubleshooting Common Problems

### "Unable to load script" or app won't load after scanning QR code

- Make sure you ran `npm start` (not `npm run android`) — `npm start` uses tunnel mode which works on any network
- Make sure the Expo server has fully started and the QR code is visible before scanning
- Try closing and reopening the app on your phone, then scan again

### Backend API not working (foot scan or sign-in fails)

- Make sure the backend server is running (Step 3.4)
- Double-check the IP address in `frontend/.env` matches your computer's current IP — it can change when you switch networks

### Backend gives an error about the database

- Make sure you ran `python manage.py migrate` (Step 3.3)
- Make sure your virtual environment is active (you should see `(venv)` in the terminal)
- If you're using Supabase, make sure the `DATABASE_URL` in your `.env` is correct

### "Module not found" errors in the frontend

- Run `npm install` again inside the `frontend` folder
- Delete the `node_modules` folder and run `npm install` again (this fixes many mysterious errors)

### Google Sign-In fails

- The Google Client ID in `.env` must exactly match what's configured in Google Cloud Console
- Ask a teammate to verify the client ID is correct for your environment

### The foot photo measurement fails

- Check that the Roboflow API key in `.env` is correct and active
- The Roboflow `foot-measuring` project must be published in the `armaanai` workspace on Roboflow's site
- Check the backend terminal for error messages — they will tell you exactly what went wrong

### App crashes immediately on open

- Make sure you built with `--profile development` (Step 6.2)
- Make sure the Expo server is running (`npx expo start --dev-client`)
- Check that the app was installed correctly — try uninstalling and reinstalling

### "Command not found" for python, node, git, etc.

- The software may not have installed correctly, or may not be in your PATH
- On Windows, try restarting your computer after installing Python or Node.js
- On Mac, try closing and reopening Terminal

---

## Quick Reference — Which Terminal Does What

You'll have two terminals open when running the app:

| Terminal | Location | Command | Purpose |
|---|---|---|---|
| Terminal 1 | `shoe_shopper_dev/` | `python manage.py runserver 0.0.0.0:8000` | Runs the backend API |
| Terminal 2 | `shoe_shopper_dev/frontend/` | `npm start` | Serves the phone app |

Both must be running at the same time for the app to work.

---

## Summary of All Files You'll Create

| File | Location | Where to get it |
|---|---|---|
| `.env` | `shoe_shopper_dev/` | Ask a teammate |
| `frontend/.env` | `shoe_shopper_dev/frontend/` | Create it yourself (Part 5.2) |

Everything else is already in the code.
