"""Tests for the purge_guest_sessions management command."""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from backend.models import GuestSession, Measurement


@pytest.mark.django_db
class TestPurgeGuestSessions:
    def _make_sessions(self):
        expired = GuestSession.objects.create(
            expires_at=timezone.now() - timedelta(days=1)
        )
        live = GuestSession.objects.create(
            expires_at=timezone.now() + timedelta(days=1)
        )
        Measurement.objects.create(guest_session=expired, image_url="")
        Measurement.objects.create(guest_session=live, image_url="")
        return expired, live

    def test_deletes_expired_sessions_and_cascades_measurements(self):
        expired, live = self._make_sessions()
        out = StringIO()

        call_command("purge_guest_sessions", stdout=out)

        assert not GuestSession.objects.filter(pk=expired.pk).exists()
        assert GuestSession.objects.filter(pk=live.pk).exists()
        # Only the live session's measurement survives.
        assert Measurement.objects.count() == 1
        assert Measurement.objects.filter(guest_session=live).count() == 1
        assert "Deleted 1 expired guest session(s)" in out.getvalue()
        assert "1 associated measurement(s)" in out.getvalue()

    def test_dry_run_deletes_nothing(self):
        expired, live = self._make_sessions()
        out = StringIO()

        call_command("purge_guest_sessions", "--dry-run", stdout=out)

        assert GuestSession.objects.count() == 2
        assert Measurement.objects.count() == 2
        assert "Would delete 1 expired guest session(s)" in out.getvalue()

    def test_noop_when_nothing_expired(self):
        GuestSession.objects.create(expires_at=timezone.now() + timedelta(days=1))
        out = StringIO()

        call_command("purge_guest_sessions", stdout=out)

        assert GuestSession.objects.count() == 1
        assert "Deleted 0 expired guest session(s)" in out.getvalue()
