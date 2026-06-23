"""API tests for auth, profile, health, shoe list, account deletion,
measurement upload/latest, dev mock measurement, and the image proxy."""

from unittest.mock import MagicMock, patch

import pytest
import requests as http_requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from backend.models import GuestSession, Measurement, Profile
from backend.tests.conftest import make_jpeg_bytes, make_shoe, make_size

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,url_name", [
    ("get", "profile"),
    ("patch", "profile"),
    ("get", "latest-measurement"),
    ("get", "recommendations"),
    ("post", "foot-measure"),
    ("post", "dev-mock-measurement"),
    ("delete", "delete-account"),
])
def test_endpoints_require_auth(api_client, method, url_name):
    response = getattr(api_client, method)(reverse(url_name))
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Health + shoe list
# ---------------------------------------------------------------------------

def test_health_is_public_and_counts_shoes(api_client):
    make_shoe()
    response = api_client.get(reverse("health"))
    assert response.status_code == 200
    assert response.data == {"status": "ok", "shoe_count": 1}


def test_shoe_list_returns_sizes_ordered_by_brand_model(api_client):
    b = make_shoe(brand="Brooks", model="Ghost")
    a = make_shoe(brand="Adidas", model="Samba")
    make_size(a, us_size="9.0")
    make_size(a, us_size="10.0")

    response = api_client.get(reverse("shoe-list"))
    assert response.status_code == 200
    assert [s["brand"] for s in response.data] == ["Adidas", "Brooks"]
    samba = response.data[0]
    assert {float(sz["us_size"]) for sz in samba["sizes"]} == {9.0, 10.0}
    assert samba["price_usd"] == "99.99"


# ---------------------------------------------------------------------------
# Google login
# ---------------------------------------------------------------------------

GOOGLE_URL_NAME = "google-login"


class TestGoogleLogin:
    def test_missing_token_400(self, api_client):
        response = api_client.post(reverse(GOOGLE_URL_NAME), {})
        assert response.status_code == 400

    def test_whitespace_token_400(self, api_client):
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "   "})
        assert response.status_code == 400

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_ANDROID_CLIENT_ID="")
    def test_server_missing_client_id_500(self, api_client):
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 500

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_first_login_creates_user_profile_and_token(self, mock_verify, api_client):
        mock_verify.return_value = {
            "email": "new.user@example.com",
            "given_name": "New",
            "family_name": "User",
            "name": "New User",
            "picture": "https://example.com/p.jpg",
        }
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 200

        user = User.objects.get(email="new.user@example.com")
        assert user.first_name == "New"
        assert user.profile.display_name == "New User"
        assert response.data["key"] == Token.objects.get(user=user).key
        # single configured client id is passed as a plain string audience
        assert mock_verify.call_args.args[2] == "test-google-client-id"

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_second_login_reuses_user_and_token(self, mock_verify, api_client):
        mock_verify.return_value = {"email": "repeat@example.com"}
        first = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        second = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert first.data["key"] == second.data["key"]
        assert User.objects.filter(email="repeat@example.com").count() == 1
        assert Profile.objects.filter(user__email="repeat@example.com").count() == 1

    @override_settings(GOOGLE_ANDROID_CLIENT_ID="android-client-id")
    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_two_client_ids_passed_as_list(self, mock_verify, api_client):
        mock_verify.return_value = {"email": "x@example.com"}
        api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert mock_verify.call_args.args[2] == ["test-google-client-id", "android-client-id"]

    @patch("backend.api.views.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token"))
    def test_invalid_token_400(self, _mock_verify, api_client):
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 400
        assert response.data["detail"] == "Invalid ID token"

    @override_settings(DEBUG=True)
    @patch("backend.api.views.google_id_token.verify_oauth2_token", side_effect=ValueError("expired"))
    def test_invalid_token_includes_debug_detail_in_debug_mode(self, _mock_verify, api_client):
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 400
        assert response.data["debug"] == "expired"

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_token_without_email_400(self, mock_verify, api_client):
        mock_verify.return_value = {"sub": "123"}
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 400
        assert response.data["detail"] == "No email in token"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class TestProfile:
    def test_get_creates_profile_on_demand(self, auth_client, user):
        assert not Profile.objects.filter(user=user).exists()
        response = auth_client.get(reverse("profile"))
        assert response.status_code == 200
        assert response.data == {"display_name": ""}
        assert Profile.objects.filter(user=user).exists()

    def test_patch_sets_display_name(self, auth_client, user):
        response = auth_client.patch(reverse("profile"), {"display_name": "  Ada  "}, format="json")
        assert response.status_code == 200
        assert response.data == {"display_name": "Ada"}
        assert Profile.objects.get(user=user).display_name == "Ada"

    def test_patch_missing_name_400(self, auth_client):
        response = auth_client.patch(reverse("profile"), {}, format="json")
        assert response.status_code == 400

    def test_patch_non_string_400(self, auth_client):
        response = auth_client.patch(reverse("profile"), {"display_name": ["x"]}, format="json")
        assert response.status_code == 400

    def test_patch_truncates_to_200_chars(self, auth_client, user):
        response = auth_client.patch(reverse("profile"), {"display_name": "x" * 300}, format="json")
        assert response.status_code == 200
        assert len(response.data["display_name"]) == 200

    def test_patch_empty_string_clears_name(self, auth_client, user):
        auth_client.patch(reverse("profile"), {"display_name": "Ada"}, format="json")
        response = auth_client.patch(reverse("profile"), {"display_name": "   "}, format="json")
        assert response.status_code == 200
        assert response.data == {"display_name": ""}
        assert Profile.objects.get(user=user).display_name is None


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------

def test_delete_account_removes_user(auth_client, user):
    response = auth_client.delete(reverse("delete-account"))
    assert response.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()


# ---------------------------------------------------------------------------
# Latest measurement
# ---------------------------------------------------------------------------

class TestLatestMeasurement:
    def test_404_when_none(self, auth_client):
        response = auth_client.get(reverse("latest-measurement"))
        assert response.status_code == 404

    def test_returns_latest_complete_only(self, auth_client, user, complete_measurement):
        Measurement.objects.create(
            user=user, status=Measurement.Status.ERROR, image_url="",
        )
        newer = Measurement.objects.create(
            user=user,
            status=Measurement.Status.COMPLETE,
            image_url="",
            length_in="11.000",
            width_in="4.200",
            area_sq_in="42.000",
        )
        response = auth_client.get(reverse("latest-measurement"))
        assert response.status_code == 200
        assert response.data["id"] == newer.id
        assert response.data["length_in"] == 11.0
        assert response.data["width_in"] == 4.2

    def test_does_not_leak_other_users_measurements(self, auth_client, complete_measurement):
        other = User.objects.create_user(username="other@example.com")
        complete_measurement.user = other
        complete_measurement.save()
        response = auth_client.get(reverse("latest-measurement"))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Dev mock measurement
# ---------------------------------------------------------------------------

class TestDevMockMeasurement:
    def test_disabled_returns_404(self, auth_client):
        response = auth_client.post(reverse("dev-mock-measurement"))
        assert response.status_code == 404

    @override_settings(ENABLE_DEV_MOCK_MEASUREMENT=True)
    def test_creates_then_skips(self, auth_client, user):
        first = auth_client.post(reverse("dev-mock-measurement"))
        assert first.status_code == 201
        assert Measurement.objects.filter(user=user).count() == 1

        second = auth_client.post(reverse("dev-mock-measurement"))
        assert second.status_code == 200
        assert second.data["skipped"] is True
        assert Measurement.objects.filter(user=user).count() == 1

    @override_settings(DEBUG=True)
    def test_debug_mode_also_enables(self, auth_client):
        response = auth_client.post(reverse("dev-mock-measurement"))
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# Measurement upload (guest path)
# ---------------------------------------------------------------------------

class TestMeasurementUpload:
    def test_upload_creates_guest_session_and_measurement(self, api_client):
        image = SimpleUploadedFile("foot.jpg", make_jpeg_bytes(), content_type="image/jpeg")
        response = api_client.post(
            reverse("measurement-upload"),
            {"image": image, "image_width_px": 640, "image_height_px": 480},
            format="multipart",
        )
        assert response.status_code == 201
        assert GuestSession.objects.count() == 1
        measurement = Measurement.objects.get()
        assert measurement.status == Measurement.Status.UPLOADED
        assert measurement.guest_session is not None
        assert measurement.image_width_px == 640
        assert response.data["image_url"].startswith("http")

    def test_missing_image_400(self, api_client):
        response = api_client.post(reverse("measurement-upload"), {}, format="multipart")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Image proxy
# ---------------------------------------------------------------------------

class TestProxyImage:
    def test_missing_url_400(self, api_client):
        response = api_client.get(reverse("proxy-image"))
        assert response.status_code == 400

    def test_non_whitelisted_host_400(self, api_client):
        response = api_client.get(reverse("proxy-image"), {"url": "https://evil.example.com/x.jpg"})
        assert response.status_code == 400

    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/?x=converse.com",  # SSRF via query
            "http://converse.com.attacker.com/x.jpg",                   # suffix spoof
            "http://attacker.com/converse.com/x.jpg",                   # path contains host
            "file:///etc/passwd?converse.com",                          # non-http scheme
        ],
    )
    def test_ssrf_substring_bypass_rejected_400(self, api_client, url):
        response = api_client.get(reverse("proxy-image"), {"url": url})
        assert response.status_code == 400

    @patch("backend.api.views.http_requests.get")
    def test_success_proxies_content_with_cache_header(self, mock_get, api_client):
        mock_get.return_value = MagicMock(
            status_code=200, content=b"imgbytes", headers={"Content-Type": "image/png"}
        )
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 200
        assert response.content == b"imgbytes"
        assert response["Content-Type"] == "image/png"
        assert response["Cache-Control"] == "public, max-age=86400"

    @patch("backend.api.views.http_requests.get")
    def test_upstream_error_passes_through_without_cache(self, mock_get, api_client):
        mock_get.return_value = MagicMock(status_code=404, content=b"", headers={})
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/on/demandware.static/img.jpg"},
        )
        assert response.status_code == 404
        assert not response.has_header("Cache-Control")

    @patch("backend.api.views.http_requests.get", side_effect=http_requests.ConnectionError("boom"))
    def test_fetch_exception_502(self, _mock_get, api_client):
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 502
