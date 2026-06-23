"""Shared fixtures for the backend test suite."""

import io

import pytest
from django.contrib.auth import get_user_model
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from backend.models import Measurement, Shoe, ShoeSize

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tester@example.com", email="tester@example.com")


@pytest.fixture
def auth_client(api_client, user):
    token, _ = Token.objects.get_or_create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return api_client


@pytest.fixture
def complete_measurement(user):
    return Measurement.objects.create(
        user=user,
        status=Measurement.Status.COMPLETE,
        image_url="",
        length_in="10.000",
        width_in="4.000",
        area_sq_in="40.000",
        toebox_length_in="3.000",
        toebox_width_in="3.200",
        paper_type=Measurement.PaperType.LETTER,
    )


def make_shoe(**overrides):
    defaults = dict(
        brand="TestBrand",
        model="TestModel",
        gender=Shoe.Gender.MEN,
        function_tags=["Casual"],
        style_tags=["Sneaker"],
        attributes_json={},
        price_usd="99.99",
        is_active=True,
    )
    defaults.update(overrides)
    return Shoe.objects.create(**defaults)


def make_size(shoe, us_size="10.0", **overrides):
    defaults = dict(
        insole_length_in="10.958",
        insole_width_in="3.829",
        insole_area_sq_in="48.000",
        insole_toebox_length_in="3.450",
        insole_toebox_width_in="3.400",
        is_available=True,
    )
    defaults.update(overrides)
    return ShoeSize.objects.create(shoe=shoe, us_size=us_size, **defaults)


def make_jpeg_bytes(size=(64, 64), color=(120, 90, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def make_ar_snapshot(camera_height_m=0.7, fx=700.0, fy=700.0, cx=320.0, cy=240.0,
                     width=640, height=480, tracking_state="TRACKING"):
    """A geometrically valid straight-down AR snapshot.

    Camera sits at (0, h, 0) above the floor plane y=0, with local axes
    +X -> world +X, +Y(up) -> world +Z, -Z(forward) -> world -Y, matching the
    ARCore camera-pose convention used by the unprojection math. A sensor
    pixel (px, py) lands on the floor at:
        world_x = h * (px - cx) / fx
        world_z = -h * (py - cy) / fy
    """
    h = camera_height_m
    return {
        "camera_intrinsics": [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
        "camera_pose": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, h],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "plane_center": [0.0, 0.0, 0.0],
        "plane_normal": [0.0, 1.0, 0.0],
        "image_dimensions": [width, height],
        "tracking_state": tracking_state,
    }


def floor_point_to_pixel(world_x, world_z, camera_height_m=0.7,
                         fx=700.0, fy=700.0, cx=320.0, cy=240.0):
    """Inverse of the mapping in make_ar_snapshot — floor coords to sensor pixel."""
    px = cx + world_x * fx / camera_height_m
    py = cy - world_z * fy / camera_height_m
    return px, py


class FakeRoboflowResponse:
    """Stands in for requests.Response from the Roboflow serverless API."""

    def __init__(self, predictions=None, status_code=200):
        self._predictions = predictions or []
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return {"predictions": self._predictions}


def polygon_pred(cls, points, confidence=0.9):
    return {
        "class": cls,
        "confidence": confidence,
        "points": [{"x": float(x), "y": float(y)} for x, y in points],
    }


def bbox_pred(cls, x, y, width, height, confidence=0.9):
    return {
        "class": cls,
        "confidence": confidence,
        "x": float(x),
        "y": float(y),
        "width": float(width),
        "height": float(height),
    }
