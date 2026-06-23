"""
Test settings — always SQLite (in-memory), throttling disabled, temp media.

Used by pytest via pytest.ini (DJANGO_SETTINGS_MODULE = shoeshopper.test_settings).
Never used in production.
"""

import tempfile

import django.contrib.postgres.fields as _pg_fields
from django.db.models import JSONField as _JSONField

from shoeshopper.settings import *  # noqa: F401,F403


class _SQLiteArrayField(_JSONField):
    """ArrayField stand-in for SQLite tests.

    ArrayField emits Postgres-only SQL (`%s::text[]`), so Shoe rows cannot be
    written under SQLite. JSONField round-trips Python lists, which is all the
    code under test relies on (no array-specific lookups are used).
    """

    def __init__(self, base_field=None, size=None, **kwargs):
        kwargs.pop("base_field", None)
        kwargs.pop("size", None)
        super().__init__(**kwargs)


# Must happen before django.setup() imports backend.models, which does
# `from django.contrib.postgres.fields import ArrayField` at module level.
_pg_fields.ArrayField = _SQLiteArrayField

DEBUG = False

# Ignore DATABASE_URL / DB_HOST from the environment — tests run on SQLite.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Throttling interferes with tests that issue many requests as one user.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MEDIA_ROOT = tempfile.mkdtemp(prefix="shoe_shopper_test_media_")

# Deterministic external-service config for tests.
ROBOFLOW_API_KEY = "test-key"
ROBOFLOW_WORKSPACE = "test-workspace"
ROBOFLOW_PROJECT = "test-project"
ROBOFLOW_MODEL_ID = "test-workspace/test-project"
GOOGLE_CLIENT_ID = "test-google-client-id"
GOOGLE_ANDROID_CLIENT_ID = ""
ENABLE_DEV_MOCK_MEASUREMENT = False
