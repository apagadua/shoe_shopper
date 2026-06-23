"""Model-level behavior: tag round-trips and DB constraints."""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from backend.models import GuestSession, Measurement, ShoeSize
from backend.tests.conftest import make_shoe, make_size

pytestmark = pytest.mark.django_db


def test_shoe_tags_round_trip():
    shoe = make_shoe(function_tags=["Athletic", "Running", "Road"], style_tags=["Sneaker"])
    shoe.refresh_from_db()
    assert shoe.function_tags == ["Athletic", "Running", "Road"]
    assert shoe.style_tags == ["Sneaker"]


def test_measurement_must_have_exactly_one_owner():
    with pytest.raises(IntegrityError):
        Measurement.objects.create(status=Measurement.Status.UPLOADED, image_url="")


def test_measurement_rejects_both_owners(django_user_model):
    user = django_user_model.objects.create_user(username="dual@example.com")
    guest = GuestSession.objects.create(expires_at=timezone.now() + timedelta(days=1))
    with pytest.raises(IntegrityError):
        Measurement.objects.create(
            user=user, guest_session=guest,
            status=Measurement.Status.UPLOADED, image_url="",
        )


def test_measurement_rejects_non_positive_length(django_user_model):
    user = django_user_model.objects.create_user(username="neg@example.com")
    with pytest.raises(IntegrityError):
        Measurement.objects.create(
            user=user, status=Measurement.Status.COMPLETE,
            image_url="", length_in="-1.0",
        )


def test_shoe_size_unique_per_shoe_size_width():
    shoe = make_shoe()
    make_size(shoe, us_size="10.0", width=ShoeSize.Width.REGULAR)
    with pytest.raises(IntegrityError):
        make_size(shoe, us_size="10.0", width=ShoeSize.Width.REGULAR)
