"""Token authentication with a maximum token age.

DRF's stock TokenAuthentication issues tokens that never expire, so a
leaked token grants access forever. ExpiringTokenAuthentication rejects
(and deletes) tokens older than AUTH_TOKEN_MAX_AGE_DAYS; the client gets
a 401 and must sign in again, which issues a fresh token
(GoogleLoginView rotates expired tokens on login).
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


def token_is_expired(token):
    """True if the token is older than AUTH_TOKEN_MAX_AGE_DAYS (0 = never)."""
    # Plain attribute access: settings.py always defines this, and a missing
    # setting should be a loud AttributeError, not a silent shadow default.
    max_age_days = settings.AUTH_TOKEN_MAX_AGE_DAYS
    if not max_age_days:
        return False
    return token.created < timezone.now() - timedelta(days=max_age_days)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token_is_expired(token):
            token.delete()
            raise AuthenticationFailed("Token has expired. Please sign in again.")
        return user, token
