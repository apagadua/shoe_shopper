## Running the backend with the shared Supabase database

These steps cover running the Django backend pointed at the shared Supabase PostgreSQL database alongside the Expo dev client on an Android emulator.

> **Note:** The backend does not work with Expo Go. It is wired for the **Expo dev client** (Android emulator) using `EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`.

The workflow uses **two terminals** (a third is optional for smoke-testing):

- One for the **frontend (Expo dev client)**
- One for the **backend (Django)**
- One optional terminal to **smoke-test the backend** directly

---

### 1. Frontend terminal (Expo dev client)

```bash
cd frontend

# Set environment variables (or add these to frontend/.env)
export DATABASE_URL='<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
export DB_SSLMODE='require'
export DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost,10.0.2.2'
export EXPO_PUBLIC_API_URL='http://10.0.2.2:8000'

npx expo start --dev-client
```

**Windows PowerShell:**

```powershell
cd frontend

$env:DATABASE_URL = '<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'
$env:EXPO_PUBLIC_API_URL = 'http://10.0.2.2:8000'

npx expo start --dev-client
```

This starts Metro for the Expo dev client so the Android emulator can talk to your local backend on port **8000**.

---

### 2. Backend terminal (Django + Supabase)

From the **repo root** (where `manage.py` lives), with your virtual environment activated:

```bash
# Set environment variables (or add these to .env at repo root)
export DATABASE_URL='<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
export DB_SSLMODE='require'
export DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost,10.0.2.2'

python manage.py runserver 0.0.0.0:8000
```

**Windows PowerShell:**

```powershell
$env:DATABASE_URL = '<YOUR_POSTGRES_DATABASE_URL_FROM_SUPABASE>'
$env:DB_SSLMODE = 'require'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost,10.0.2.2'

python manage.py runserver 0.0.0.0:8000
```

This starts Django bound to `0.0.0.0:8000` and pointed at the shared Supabase database.

> Ask a teammate or check your secrets manager for the real Supabase connection string — never commit it.

---

### 3. Optional: backend smoke test

In a third terminal (while both servers are running):

```bash
curl http://127.0.0.1:8000/api/health/
```

Expected response:

```json
{"status": "ok", "shoe_count": <some number>}
```

The **Profile → Backend Smoke Test** button in the app should show a matching `shoe_count` and a list of shoes.
