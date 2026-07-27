"""Tests for GET /api/recommendations/ — scoring, sorting, sizes, colorways."""

import pytest
from django.urls import reverse

from backend.models import ShoeColorway, ShoeColorwaySize
from backend.tests.conftest import make_shoe, make_size

pytestmark = pytest.mark.django_db

URL_NAME = "recommendations"


def make_colorway(shoe, goat_id, name="Default", image_url=None, sizes=()):
    cw = ShoeColorway.objects.create(
        shoe=shoe, goat_id=goat_id, name=name, image_url=image_url,
        color_palette_hex=["#112233"],
    )
    for us_size, available, price in sizes:
        ShoeColorwaySize.objects.create(
            colorway=cw, us_size=us_size, is_available=available, price_usd=price,
        )
    return cw


def test_404_without_measurement(auth_client):
    response = auth_client.get(reverse(URL_NAME))
    assert response.status_code == 404


def test_scored_shoe_with_insole_data(auth_client, complete_measurement):
    shoe = make_shoe()
    make_size(shoe, us_size="10.0")

    response = auth_client.get(reverse(URL_NAME))
    assert response.status_code == 200
    assert response.data["measurement_id"] == complete_measurement.id
    assert response.data["has_toebox_data"] is True

    (result,) = response.data["results"]
    assert result["brand"] == "TestBrand"
    assert result["fit_status"] == "PERFECT"
    assert result["fit_status_label"] == "Perfect fit"
    assert result["fit_score"] == 100.0
    assert result["fit_profile"] == "CASUAL"
    # Brannock estimate for corrected 10.508" men's foot
    assert result["estimated_us_size"] == 9.5
    # no colorways -> falls back to the insole-measured size
    assert result["recommended_size"] == 10.0
    assert result["colorway_options"] == []


def test_unscored_when_no_insole_data(auth_client, complete_measurement):
    shoe = make_shoe()
    make_size(shoe, us_size="10.0", insole_length_in=None, insole_width_in=None)

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["fit_status"] == "UNSCORED"
    assert result["fit_score"] is None
    assert result["fit_status_label"] == "No fit data yet"
    assert result["recommended_size"] is None


def test_shoe_without_sizes_is_unscored(auth_client, complete_measurement):
    make_shoe()
    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["fit_status"] == "UNSCORED"


def test_inactive_shoes_excluded(auth_client, complete_measurement):
    make_shoe(is_active=False)
    response = auth_client.get(reverse(URL_NAME))
    assert response.data["results"] == []


def test_sort_order_scored_then_unscored_then_rejected(auth_client, complete_measurement):
    rejected = make_shoe(brand="Rejected")
    make_size(rejected, insole_length_in="14.000")  # way past length reject window

    unscored = make_shoe(brand="Unscored")
    make_size(unscored, insole_length_in=None, insole_width_in=None)

    good = make_shoe(brand="Good")
    make_size(good)

    response = auth_client.get(reverse(URL_NAME))
    brands = [r["brand"] for r in response.data["results"]]
    assert brands == ["Good", "Unscored", "Rejected"]
    assert response.data["results"][2]["reject_reason"] == "LENGTH_OUT_OF_RANGE"


def test_higher_scores_sort_first(auth_client, complete_measurement):
    okay = make_shoe(brand="Okay")
    # loose length: clearance 0.58 (CASUAL optimal tops out at 0.51)
    make_size(okay, insole_length_in="11.450", insole_toebox_length_in="3.950")

    perfect = make_shoe(brand="Perfect")
    make_size(perfect)

    response = auth_client.get(reverse(URL_NAME))
    brands = [r["brand"] for r in response.data["results"]]
    assert brands == ["Perfect", "Okay"]


def test_scoring_size_closest_to_estimate(auth_client, complete_measurement):
    """Estimate is 9.5 — the 9.0 size's insole should be used over 13.0."""
    shoe = make_shoe()
    make_size(shoe, us_size="13.0", insole_length_in="14.000")  # would reject
    make_size(shoe, us_size="9.0")  # optimal insole

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["fit_status"] == "PERFECT"
    assert result["recommended_size"] == 9.0


def test_colorway_options_scoped_to_recommended_size(auth_client, complete_measurement):
    shoe = make_shoe()
    make_size(shoe, us_size="10.0")
    make_colorway(
        shoe, "goat-1", name="Black", image_url="https://img/black.jpg",
        sizes=[("10.0", True, "120.00"), ("9.0", True, "110.00")],
    )

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["recommended_size"] == 10.0
    (option,) = result["colorway_options"]
    assert option["goat_id"] == "goat-1"
    assert option["color_palette_hex"] == ["#112233"]
    # only the recommended size is listed
    assert [s["us_size"] for s in option["sizes"]] == [10.0]
    assert option["sizes"][0]["price_usd"] == "120.00"


def test_recommended_size_requires_live_colorway(auth_client, complete_measurement):
    """Sizes 9 and 10 measured, but only 9.0 is purchasable in a colorway."""
    shoe = make_shoe()
    make_size(shoe, us_size="10.0")
    make_size(shoe, us_size="9.0")
    make_colorway(shoe, "goat-2", sizes=[("9.0", True, "99.00"), ("10.0", False, "99.00")])

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["recommended_size"] == 9.0


def test_no_insole_size_matches_live_colorways(auth_client, complete_measurement):
    """Colorways are purchasable only at sizes with no insole data —
    recommended_size is None and options list all available sizes."""
    shoe = make_shoe()
    make_size(shoe, us_size="10.0")
    make_colorway(shoe, "goat-3", sizes=[("8.0", True, "89.00"), ("7.0", False, "79.00")])

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["recommended_size"] is None
    (option,) = result["colorway_options"]
    assert [s["us_size"] for s in option["sizes"]] == [8.0]


def test_colorways_with_images_sort_first(auth_client, complete_measurement):
    shoe = make_shoe()
    make_size(shoe, us_size="10.0")
    make_colorway(shoe, "goat-noimg", name="Alpha", image_url=None)
    make_colorway(shoe, "goat-img", name="Zulu", image_url="https://img/z.jpg")

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert [o["goat_id"] for o in result["colorway_options"]] == ["goat-img", "goat-noimg"]


def test_attributes_json_list_normalized_to_dict(auth_client, complete_measurement):
    shoe = make_shoe(attributes_json=["vegan", "waterproof"])
    make_size(shoe, us_size="10.0")

    response = auth_client.get(reverse(URL_NAME))
    (result,) = response.data["results"]
    assert result["attributes_json"] == {"vegan": True, "waterproof": True}


def test_sub_type_query_param_changes_scoring(auth_client, complete_measurement):
    shoe = make_shoe(function_tags=["Athletic", "Running", "Road"])
    make_size(shoe, us_size="10.0")

    base = auth_client.get(reverse(URL_NAME)).data["results"][0]
    marathon = auth_client.get(reverse(URL_NAME), {"sub_type": "marathon"}).data["results"][0]
    assert marathon["fit_score"] < base["fit_score"]


def test_unknown_sub_type_rejected_400(auth_client, complete_measurement):
    response = auth_client.get(reverse(URL_NAME), {"sub_type": "'; DROP TABLE shoe;--"})
    assert response.status_code == 400
    assert response.data["detail"] == "Invalid sub_type"


def test_measurement_without_toebox(auth_client, complete_measurement):
    complete_measurement.toebox_length_in = None
    complete_measurement.toebox_width_in = None
    complete_measurement.save()

    shoe = make_shoe()
    make_size(shoe, us_size="10.0")

    response = auth_client.get(reverse(URL_NAME))
    assert response.data["has_toebox_data"] is False
    (result,) = response.data["results"]
    # falls back to the area-ratio scoring path (insole 48 / foot 40 = 1.2)
    assert result["fit_status"] == "PERFECT"
    assert "overall_area" in result["fit_dimensions"]
