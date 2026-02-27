## Running the backend with shared Supabase database (Windows / PowerShell)

These steps assume:
- You are on **Windows** using **PowerShell**
- Python 3.14 is installed at `C:\Users\alyss\AppData\Local\Programs\Python\Python314\python.exe`
- You want the backend to talk to the **shared Supabase Postgres** database and the Expo dev client on the Android emulator
- **Important:** The backend **does not work with Expo Go** in this setup. It is wired for the **Expo dev client** (Android emulator) using `EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`.

The workflow uses **three terminals**:
- One for the **frontend (Expo dev client)**
- One for the **backend (Django)**
- One optional terminal to **smoke‑test the backend** directly

### 1. Frontend terminal (Expo dev client)

In a new PowerShell terminal:

```powershell
cd C:\Users\alyss\shoe_shopper\frontend

# Ask a teammate / check your secrets manager for the real connection string.
$env:DATABASE_URL = '<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'
$env:EXPO_PUBLIC_API_URL = 'http://10.0.2.2:8000'

npx expo start --dev-client
```

This starts Metro for the Expo **dev client** so the Android emulator can talk to your local backend on port **8000**.

### 2. Backend terminal (Django + Supabase)

In a second PowerShell terminal:

```powershell
cd C:\Users\alyss\shoe_shopper\backend

# Ask a teammate / check your secrets manager for the real connection string.
$env:DATABASE_URL = '<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'
$env:EXPO_PUBLIC_API_URL = 'http://10.0.2.2:8000'

& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" ../manage.py runserver 0.0.0.0:8000
```

This starts Django bound to `0.0.0.0:8000` and pointed at the shared Supabase Postgres database.

### 3. Optional: direct backend smoke test (health endpoint)

In a third PowerShell terminal (while frontend and backend are both running):

```powershell
cd C:\Users\alyss\shoe_shopper

# Ask a teammate / check your secrets manager for the real connection string.
$env:DATABASE_URL = '<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'
$env:EXPO_PUBLIC_API_URL = 'http://10.0.2.2:8000'

curl http://127.0.0.1:8000/api/health/
```

If everything is wired correctly, this should return JSON similar to:

```json
{"status": "ok", "shoe_count": <some number>}
```

The **Profile → Backend Smoke Test** button in the app should then show a matching `shoe_count` and list of shoes.

