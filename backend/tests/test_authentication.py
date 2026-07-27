"""Token expiry (backend/api/authentication.py) and rotation on login."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

pytestmark = pytest.mark.django_db


def _age_token(token, days):
    """Backdate a token's created timestamp (auto_now_add blocks direct save)."""
    Token.objects.filter(pk=token.pk).update(
        created=timezone.now() - timedelta(days=days)
    )


class TestExpiringTokenAuthentication:
    def test_fresh_token_authenticates(self, auth_client):
        response = auth_client.get(reverse("profile"))
        assert response.status_code == 200

    def test_expired_token_rejected_and_deleted(self, api_client, user):
        token = Token.objects.create(user=user)
        _age_token(token, days=31)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = api_client.get(reverse("profile"))

        assert response.status_code == 401
        assert "expired" in response.data["detail"].lower()
        assert not Token.objects.filter(pk=token.pk).exists()

    def test_token_just_inside_max_age_still_works(self, api_client, user):
        token = Token.objects.create(user=user)
        _age_token(token, days=29)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        assert api_client.get(reverse("profile")).status_code == 200

    @override_settings(AUTH_TOKEN_MAX_AGE_DAYS=0)
    def test_zero_max_age_disables_expiry(self, api_client, user):
        token = Token.objects.create(user=user)
        _age_token(token, days=365)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        assert api_client.get(reverse("profile")).status_code == 200

    def test_invalid_token_still_rejected(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        assert api_client.get(reverse("profile")).status_code == 401


class TestLoginRotatesExpiredToken:
    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_expired_token_replaced_on_login(self, mock_verify, api_client, user):
        mock_verify.return_value = {"email": user.email, "email_verified": True}
        old_token = Token.objects.create(user=user)
        _age_token(old_token, days=31)
        old_key = old_token.key

        response = api_client.post(reverse("google-login"), {"id_token": "tok"})

        assert response.status_code == 200
        assert response.data["key"] != old_key
        assert not Token.objects.filter(key=old_key).exists()
        # The new token works.
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['key']}")
        assert api_client.get(reverse("profile")).status_code == 200

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_fresh_token_kept_on_login(self, mock_verify, api_client, user):
        mock_verify.return_value = {"email": user.email, "email_verified": True}
        token = Token.objects.create(user=user)

        response = api_client.post(reverse("google-login"), {"id_token": "tok"})

        assert response.status_code == 200
        assert response.data["key"] == token.key
