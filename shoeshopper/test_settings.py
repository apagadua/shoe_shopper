"""
Test settings — always SQLite (in-memory), throttling disabled, temp media.

Used by pytest via pytest.ini (DJANGO_SETTINGS_MODULE = shoeshopper.test_settings).
Never used in production.
"""

import os
import tempfile

import django.contrib.postgres.fields as _pg_fields
from django.db.models import JSONField as _JSONField

# settings.py fails hard without a secret key when DEBUG is off; give the
# test run a deterministic one before importing it.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from shoeshopper.settings import *  # noqa: E402,F401,F403


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
# The scoped rates must exist (views set throttle_scope) but None disables
# them. Derived from the imported config so auth/permission classes and the
# scope list can never drift from production settings.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        scope: None
        for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]  # noqa: F405
    },
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Deterministic token expiry regardless of the host's AUTH_TOKEN_MAX_AGE_DAYS.
AUTH_TOKEN_MAX_AGE_DAYS = 30

MEDIA_ROOT = tempfile.mkdtemp(prefix="shoe_shopper_test_media_")

# Deterministic external-service config for tests.
ROBOFLOW_API_KEY = "test-key"
ROBOFLOW_WORKSPACE = "test-workspace"
ROBOFLOW_PROJECT = "test-project"
ROBOFLOW_MODEL_ID = "test-workspace/test-project"
GOOGLE_CLIENT_ID = "test-google-client-id"
GOOGLE_ANDROID_CLIENT_ID = ""
ENABLE_DEV_MOCK_MEASUREMENT = False
