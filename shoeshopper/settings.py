import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"

# Refuse to start a non-debug server on the known dev key. (The test suite
# imports this module without a .env — test_settings.py sets a deterministic
# DJANGO_SECRET_KEY env var before importing.)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-secret-key"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off"
        )
# Allow POST /api/dev/mock-measurement/ when DEBUG is False (e.g. staging) — use sparingly.
ENABLE_DEV_MOCK_MEASUREMENT = os.getenv("ENABLE_DEV_MOCK_MEASUREMENT", "").lower() in ("1", "true", "yes")
# Save annotated AR capture images to ar_debug/ — these contain user foot
# photos, so keep this off outside local debugging sessions.
AR_DEBUG_IMAGES = os.getenv("AR_DEBUG_IMAGES", "").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_ANDROID_CLIENT_ID = os.getenv("GOOGLE_ANDROID_CLIENT_ID", "").strip()
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "")
ROBOFLOW_WORKSPACE = os.getenv("ROBOFLOW_WORKSPACE", "")
ROBOFLOW_PROJECT = os.getenv("ROBOFLOW_PROJECT", "")
# Direct model ID — bypasses the foot-measuring workflow (which filters out Wall Base).
# Must be set to "shoe-shopper/23" (the underlying segmentation model) in .env.
# The fallback constructs workspace/project which points at the workflow — don't rely on it.
ROBOFLOW_MODEL_ID = os.getenv(
    "ROBOFLOW_MODEL_ID",
    f"{os.getenv('ROBOFLOW_WORKSPACE', '')}/{os.getenv('ROBOFLOW_PROJECT', '')}",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework.authtoken",
    "backend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Compress JSON responses (recommendations payload shrinks ~85%).
    # Must sit above middleware that may modify the response body.
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "shoeshopper.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "shoeshopper.wsgi.application"
ASGI_APPLICATION = "shoeshopper.asgi.application"

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    parsed = urlparse(database_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or "5432"),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    }
elif os.getenv("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.getenv("DB_NAME", "postgres"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", ""),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "formatters": {
        "simple": {
            "format": "[%(levelname)s %(name)s] %(message)s",
        },
    },
    "loggers": {
        "backend": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth tokens older than this are rejected and deleted (client must sign in
# again). An explicit 0 disables expiry; unset or blank means the default.
AUTH_TOKEN_MAX_AGE_DAYS = int(os.getenv("AUTH_TOKEN_MAX_AGE_DAYS", "").strip() or "30")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "backend.api.authentication.ExpiringTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    # "user" is the global default (UserRateThrottle keys anon requests by IP).
    # The named scopes are applied per-view via ScopedRateThrottle: strict on
    # the expensive/abusable endpoints (Roboflow calls, auth, uploads), loose
    # on proxy-image because one recommendations screen loads dozens of images.
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/min",
        "auth": "10/min",
        "foot_measure": "10/min",
        "upload": "10/min",
        "proxy_image": "300/min",
    },
}

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Opt-in via env: enabling these blindly breaks plain-HTTP health checks
    # and deployments where TLS terminates at a proxy that isn't forwarding
    # X-Forwarded-Proto yet.
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0") or "0")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    if os.getenv("DJANGO_TRUST_PROXY_SSL_HEADER", "0") == "1":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
