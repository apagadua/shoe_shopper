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
            "email_verified": True,
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
        mock_verify.return_value = {"email": "repeat@example.com", "email_verified": True}
        first = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        second = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert first.data["key"] == second.data["key"]
        assert User.objects.filter(email="repeat@example.com").count() == 1
        assert Profile.objects.filter(user__email="repeat@example.com").count() == 1

    @override_settings(GOOGLE_ANDROID_CLIENT_ID="android-client-id")
    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_two_client_ids_passed_as_list(self, mock_verify, api_client):
        mock_verify.return_value = {"email": "x@example.com", "email_verified": True}
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

    @pytest.mark.parametrize("verified", [False, None, "true"])
    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_unverified_email_rejected_400(self, mock_verify, api_client, verified):
        idinfo = {"email": "victim@example.com"}
        if verified is not None:
            idinfo["email_verified"] = verified
        mock_verify.return_value = idinfo
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 400
        assert response.data["detail"] == "Google account email is not verified"
        assert not User.objects.filter(email="victim@example.com").exists()

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_login_matches_existing_user_by_username(self, mock_verify, api_client):
        # Users are keyed on username (unique); pre-existing accounts from the
        # old email-keyed flow always had username == email, so both match.
        existing = User.objects.create_user(username="old@example.com", email="old@example.com")
        mock_verify.return_value = {"email": "old@example.com", "email_verified": True}
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 200
        assert response.data["key"] == Token.objects.get(user=existing).key
        assert User.objects.filter(email="old@example.com").count() == 1

    @patch("backend.api.views.google_id_token.verify_oauth2_token")
    def test_login_matches_legacy_user_by_email(self, mock_verify, api_client):
        # Accounts created outside the Google flow (admin, createsuperuser)
        # can have username != email; the email fallback must claim them
        # rather than creating a duplicate account with the same email.
        existing = User.objects.create_user(username="bob", email="bob@example.com")
        mock_verify.return_value = {"email": "bob@example.com", "email_verified": True}
        response = api_client.post(reverse(GOOGLE_URL_NAME), {"id_token": "tok"})
        assert response.status_code == 200
        assert response.data["key"] == Token.objects.get(user=existing).key
        assert User.objects.filter(email="bob@example.com").count() == 1


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

    def test_non_image_payload_rejected_400(self, api_client):
        # Content-type header claims JPEG but the bytes aren't an image —
        # Pillow-backed validation must reject it (anonymous endpoint).
        fake = SimpleUploadedFile("evil.html", b"<script>alert(1)</script>", content_type="image/jpeg")
        response = api_client.post(
            reverse("measurement-upload"), {"image": fake}, format="multipart"
        )
        assert response.status_code == 400
        assert GuestSession.objects.count() == 0

    def test_hostile_extension_rejected_400(self, api_client):
        # Even with real JPEG bytes, a non-image extension is refused
        # (ImageField's extension validator), so nothing is ever stored
        # under a client-chosen .html/.svg name.
        image = SimpleUploadedFile("evil.html", make_jpeg_bytes(), content_type="image/jpeg")
        response = api_client.post(
            reverse("measurement-upload"), {"image": image}, format="multipart"
        )
        assert response.status_code == 400

    def test_stored_extension_comes_from_detected_format_not_filename(self, api_client):
        # JPEG bytes under a .png name — the stored path must use the
        # Pillow-detected extension, not the client's.
        image = SimpleUploadedFile("foot.png", make_jpeg_bytes(), content_type="image/png")
        response = api_client.post(
            reverse("measurement-upload"), {"image": image}, format="multipart"
        )
        assert response.status_code == 201
        assert response.data["image_url"].endswith(".jpg")


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

    @staticmethod
    def _mock_response(status_code=200, headers=None, chunks=()):
        resp = MagicMock(
            status_code=status_code,
            headers=headers or {},
            **{"iter_content.return_value": list(chunks)},
        )
        # The view consumes the response as a context manager.
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    @patch("backend.api.views.http_requests.get")
    def test_success_proxies_content_with_cache_header(self, mock_get, api_client):
        mock_get.return_value = self._mock_response(
            200, {"Content-Type": "image/png"}, [b"img", b"bytes"]
        )
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 200
        assert response.content == b"imgbytes"
        assert response["Content-Type"] == "image/png"
        assert response["Cache-Control"] == "public, max-age=86400"
        # Redirect-following must stay off — a redirect on the allowed host
        # would otherwise pivot the proxy anywhere.
        assert mock_get.call_args.kwargs["allow_redirects"] is False

    @patch("backend.api.views.http_requests.get")
    def test_legacy_http_url_upgraded_to_https(self, mock_get, api_client):
        # Shoe rows synced before the https-only rule may store http:// URLs;
        # the proxy upgrades them and always fetches over https.
        mock_get.return_value = self._mock_response(
            200, {"Content-Type": "image/jpeg"}, [b"img"]
        )
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "http://www.converse.com/img/shoe.jpg"},
        )
        assert response.status_code == 200
        assert mock_get.call_args.args[0] == "https://www.converse.com/img/shoe.jpg"

    @patch("backend.api.views.http_requests.get")
    def test_upstream_error_passes_status_without_body_or_cache(self, mock_get, api_client):
        mock_get.return_value = self._mock_response(404, {"Content-Type": "text/html"}, [b"<html>"])
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/on/demandware.static/img.jpg"},
        )
        assert response.status_code == 404
        assert response.content == b""
        assert not response.has_header("Cache-Control")

    @patch("backend.api.views.http_requests.get")
    def test_upstream_redirect_rejected_502(self, mock_get, api_client):
        mock_get.return_value = self._mock_response(302, {"Location": "http://evil.example.com/"})
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 502

    @patch("backend.api.views.http_requests.get")
    def test_non_image_content_type_rejected_502(self, mock_get, api_client):
        mock_get.return_value = self._mock_response(200, {"Content-Type": "text/html"}, [b"<html>"])
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 502

    @patch("backend.api.views.http_requests.get")
    def test_oversized_response_rejected_502(self, mock_get, api_client):
        big_chunk = b"x" * (1024 * 1024)
        mock_get.return_value = self._mock_response(
            200, {"Content-Type": "image/jpeg"}, [big_chunk] * 6  # 6 MB > 5 MB cap
        )
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 502

    @patch("backend.api.views.http_requests.get", side_effect=http_requests.ConnectionError("boom"))
    def test_fetch_exception_502(self, _mock_get, api_client):
        response = api_client.get(
            reverse("proxy-image"),
            {"url": "https://www.converse.com/img/shoe.png"},
        )
        assert response.status_code == 502
