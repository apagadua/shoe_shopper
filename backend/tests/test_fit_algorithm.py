"""Tests for backend/services/fit_algorithm.py (pure logic, no DB)."""

import pytest

from backend.services.fit_algorithm import (
    LENGTH_BIAS_CORRECTION,
    WIDTH_BIAS_CORRECTION,
    _get_profile_name,
    _get_points,
    _get_zone,
    _score_dimension,
    estimate_us_size,
    score_shoe,
    status_label,
)

# Raw foot measurement used throughout. After bias correction:
#   length 10.0 + 0.508 = 10.508, width 4.0 - 0.371 = 3.629
FOOT = {
    "length_in": 10.0,
    "width_in": 4.0,
    "area_sq_in": 40.0,
    "toebox_length_in": 3.0,
    "toebox_width_in": 3.2,
}

ADJ_LEN = 10.0 + LENGTH_BIAS_CORRECTION
ADJ_WID = 4.0 - WIDTH_BIAS_CORRECTION


def make_shoe(**overrides):
    """A CASUAL shoe whose every dimension lands in the optimal zone for FOOT."""
    shoe = {
        "id": 1,
        "gender": "men",
        "function_tags": ["Casual"],
        "style_tags": [],
        # CASUAL length optimal zone is [0.39, 0.51] clearance
        "insole_length_in": round(ADJ_LEN + 0.45, 3),
        # CASUAL width optimal zone is [0.08, 0.12] per side
        "insole_width_in": round(ADJ_WID + 0.20, 3),
        "insole_area_sq_in": None,
        # toebox clearances: length 0.45 (optimal), width 0.10/side (optimal)
        "insole_toebox_length_in": 3.45,
        "insole_toebox_width_in": 3.40,
        "toe_shape": None,
        "cap_type": None,
        "attributes_json": {},
    }
    shoe.update(overrides)
    return shoe


# ---------------------------------------------------------------------------
# estimate_us_size
# ---------------------------------------------------------------------------

class TestEstimateUsSize:
    def test_mens_brannock(self):
        assert estimate_us_size(11.0, "men") == 11.0

    def test_womens_is_1_5_sizes_larger(self):
        assert estimate_us_size(11.0, "women") == 12.5

    @pytest.mark.parametrize("gender", ["women", "w", "female", "f", "WOMEN", "F"])
    def test_womens_gender_aliases(self, gender):
        assert estimate_us_size(10.5, gender) == 11.0

    @pytest.mark.parametrize("gender", ["men", "unisex", "kids", "", None, "unknown"])
    def test_everything_else_uses_mens_formula(self, gender):
        assert estimate_us_size(10.5, gender) == 9.5

    def test_rounds_to_nearest_half_size(self):
        # 3 * 10.6 - 22 = 9.8 -> nearest half is 10.0
        assert estimate_us_size(10.6, "men") == 10.0


# ---------------------------------------------------------------------------
# status_label
# ---------------------------------------------------------------------------

class TestStatusLabel:
    @pytest.mark.parametrize("status,label", [
        ("PERFECT", "Perfect fit"),
        ("GOOD", "Good fit"),
        ("ACCEPTABLE", "Acceptable fit"),
        ("MARGINAL", "Marginal fit"),
        ("POOR", "Poor fit"),
        ("REJECTED", "Not recommended"),
        ("UNSCORED", "No fit data yet"),
    ])
    def test_known_statuses(self, status, label):
        assert status_label(status) == label

    def test_unknown_status_passes_through(self):
        assert status_label("SOMETHING_ELSE") == "SOMETHING_ELSE"


# ---------------------------------------------------------------------------
# Profile routing
# ---------------------------------------------------------------------------

class TestProfileRouting:
    @pytest.mark.parametrize("tags,profile", [
        (["Athletic", "Running", "Road"], "ROAD_RUNNING"),
        (["Athletic", "Running", "Trail"], "TRAIL_RUNNING"),
        (["Athletic", "Running", "Indoor"], "INDOOR_TRACK"),
        (["Athletic", "Running"], "ROAD_RUNNING"),
        (["Athletic", "Training"], "TRAINING"),
        (["Athletic", "Basketball"], "BASKETBALL"),
        (["Athletic", "Field Sports"], "CLEATED_SPORT"),
        (["Athletic", "Soccer"], "CLEATED_SPORT"),
        (["Athletic", "Football"], "CLEATED_SPORT"),
        (["Athletic", "Lacrosse"], "CLEATED_SPORT"),
        (["Athletic", "Tennis"], "TENNIS"),
        (["Athletic", "Skate"], "SKATE"),
        (["Athletic", "Hiking"], "HIKING"),
        (["Casual", "Slip-ons"], "CASUAL_SLIPON"),
        (["Casual"], "CASUAL"),
        (["Work", "Indoor"], "WORK_INDOOR"),
        (["Work", "Outdoor"], "WORK_OUTDOOR"),
        (["Formal"], "DRESS"),
    ])
    def test_tag_routes(self, tags, profile):
        assert _get_profile_name(tags) == profile

    def test_case_insensitive(self):
        assert _get_profile_name(["athletic", "RUNNING", "road"]) == "ROAD_RUNNING"

    def test_unmatched_and_empty_default_to_casual(self):
        assert _get_profile_name(["Mystery"]) == "CASUAL"
        assert _get_profile_name([]) == "CASUAL"
        assert _get_profile_name(None) == "CASUAL"


# ---------------------------------------------------------------------------
# _score_dimension / _get_zone
# ---------------------------------------------------------------------------

T = {"min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67}


class TestScoreDimension:
    def test_optimal_zone_full_points(self):
        assert _score_dimension(0.50, T, 30) == 30.0
        assert _score_dimension(0.47, T, 30) == 30.0
        assert _score_dimension(0.55, T, 30) == 30.0

    def test_tight_zone_linear_ramp(self):
        # halfway between min and opt_low
        mid = (0.20 + 0.47) / 2
        assert _score_dimension(mid, T, 30) == pytest.approx(15.0)

    def test_below_min_clamps_to_zero(self):
        assert _score_dimension(0.0, T, 30) == 0.0

    def test_degenerate_opt_low_at_min_returns_zero(self):
        t = {"min": 0.30, "opt_low": 0.30, "opt_high": 0.55, "max": 0.67}
        assert _score_dimension(0.25, t, 30) == 0.0

    def test_loose_zone_floor_is_70_percent(self):
        # at exactly max the floor applies: P * 0.70
        assert _score_dimension(0.67, T, 30) == pytest.approx(21.0)

    def test_loose_zone_interpolates_to_full(self):
        # just above opt_high, ratio ~1 -> ~full points
        assert _score_dimension(0.551, T, 30) == pytest.approx(30.0, abs=0.2)

    def test_degenerate_max_at_opt_high_full_points(self):
        t = {"min": 0.20, "opt_low": 0.47, "opt_high": 0.67, "max": 0.67}
        assert _score_dimension(0.67, t, 30) == 30.0

    def test_excessive_zone_decays_over_4x_band(self):
        # band = 0.12; at max + 2*band the decay is half spent
        score = _score_dimension(0.67 + 0.24, T, 30)
        assert score == pytest.approx(30 * 0.70 * 0.5)

    def test_excessive_zone_hits_zero(self):
        assert _score_dimension(0.67 + 0.48 + 0.1, T, 30) == 0.0

    def test_excessive_with_zero_interval_returns_zero(self):
        t = {"min": 0.20, "opt_low": 0.47, "opt_high": 0.67, "max": 0.67}
        assert _score_dimension(0.68, t, 30) == 0.0


class TestGetZone:
    @pytest.mark.parametrize("c,zone", [
        (0.10, "rejected"),
        (0.30, "tight"),
        (0.50, "optimal"),
        (0.60, "loose"),
        (0.80, "excessive"),
    ])
    def test_zones(self, c, zone):
        assert _get_zone(c, T) == zone


# ---------------------------------------------------------------------------
# _get_points budgets
# ---------------------------------------------------------------------------

class TestGetPoints:
    def test_toebox_budgets(self):
        assert _get_points("CASUAL", True) == {"length": 20, "width": 30, "tb_len": 20, "tb_width": 30}
        assert _get_points("SKATE", True) == {"length": 17, "width": 33, "tb_len": 17, "tb_width": 33}
        assert _get_points("CASUAL_SLIPON", True) == {"length": 18, "width": 32, "tb_len": 18, "tb_width": 32}

    def test_area_budgets(self):
        assert _get_points("CASUAL", False, has_area=True) == {"length": 35, "width": 40, "area": 25}
        assert _get_points("SKATE", False, has_area=True) == {"length": 30, "width": 45, "area": 25}
        assert _get_points("CASUAL_SLIPON", False, has_area=True) == {"length": 30, "width": 45, "area": 25}

    def test_bare_budgets(self):
        assert _get_points("CASUAL", False) == {"length": 50, "width": 50}
        assert _get_points("SKATE", False) == {"length": 40, "width": 60}
        assert _get_points("CASUAL_SLIPON", False) == {"length": 42, "width": 58}


# ---------------------------------------------------------------------------
# score_shoe — happy paths
# ---------------------------------------------------------------------------

class TestScoreShoeHappyPath:
    def test_perfect_fit_with_toebox(self):
        result = score_shoe(FOOT, make_shoe())
        assert result["status"] == "PERFECT"
        assert result["total_score"] == 100.0
        assert result["reject_reason"] is None
        assert result["profile_used"] == "CASUAL"
        assert result["has_toebox_data"] is True
        assert set(result["dimensions"]) == {"foot_length", "foot_width", "toebox_length", "toebox_width"}
        assert all(d["zone"] == "optimal" for d in result["dimensions"].values())

    def test_area_path_when_no_toebox(self):
        foot = dict(FOOT, toebox_length_in=None, toebox_width_in=None)
        shoe = make_shoe(insole_area_sq_in=48.0)  # ratio 1.2 — optimal [1.10, 1.35]
        result = score_shoe(foot, shoe)
        assert result["has_toebox_data"] is False
        assert result["has_area_data"] is True
        assert result["status"] == "PERFECT"
        assert result["total_score"] == 100.0
        area = result["dimensions"]["overall_area"]
        assert area["ratio"] == pytest.approx(1.2)
        assert area["zone"] == "optimal"

    def test_bare_path_no_toebox_no_area(self):
        foot = dict(FOOT, toebox_length_in=None, toebox_width_in=None, area_sq_in=None)
        result = score_shoe(foot, make_shoe())
        assert result["has_toebox_data"] is False
        assert result["has_area_data"] is False
        assert result["total_score"] == 100.0
        assert set(result["dimensions"]) == {"foot_length", "foot_width"}

    def test_shoe_missing_toebox_disables_toebox_scoring(self):
        shoe = make_shoe(insole_toebox_length_in=None, insole_toebox_width_in=None)
        result = score_shoe(FOOT, shoe)
        assert result["has_toebox_data"] is False

    def test_estimated_us_size_uses_corrected_length(self):
        result = score_shoe(FOOT, make_shoe())
        assert result["estimated_us_size"] == estimate_us_size(ADJ_LEN, "men")


# ---------------------------------------------------------------------------
# score_shoe — status tiers
# ---------------------------------------------------------------------------

def bare_foot():
    return dict(FOOT, toebox_length_in=None, toebox_width_in=None, area_sq_in=None)


def bare_shoe(c_length, c_width_per_side):
    return make_shoe(
        insole_length_in=round(ADJ_LEN + c_length, 4),
        insole_width_in=round(ADJ_WID + 2 * c_width_per_side, 4),
        insole_toebox_length_in=None,
        insole_toebox_width_in=None,
    )


class TestScoreShoeStatusTiers:
    """CASUAL no-toebox/no-area scoring: 50 pts length + 50 pts width.

    CASUAL tolerances: length [min .20, opt .39–.51, max .59],
    width per side [min -.29, opt .08–.12, max .35].
    """

    def test_good(self):
        # length optimal (50) + width tight c=0.0 -> 50 * (0+.29)/(0.08+.29) = 39.2
        result = score_shoe(bare_foot(), bare_shoe(0.45, 0.0))
        assert result["status"] == "GOOD"
        assert 75 <= result["total_score"] < 90

    def test_acceptable(self):
        # length optimal (50) + width tight c=-0.1 -> 50 * 0.19/0.37 = 25.7
        result = score_shoe(bare_foot(), bare_shoe(0.45, -0.10))
        assert result["status"] == "ACCEPTABLE"
        assert 60 <= result["total_score"] < 75

    def test_marginal(self):
        # length deep in excessive zone (0 pts), width optimal (50 pts);
        # 1.20 stays inside the reject window (rejects start at 1.34)
        result = score_shoe(bare_foot(), bare_shoe(1.20, 0.10))
        assert result["status"] == "MARGINAL"
        assert 40 <= result["total_score"] < 60
        assert result["dimensions"]["foot_length"]["zone"] == "excessive"

    def test_poor(self):
        # length excessive (0 pts) + width tight c=-0.2 -> 50*0.09/0.37 = 12.2
        result = score_shoe(bare_foot(), bare_shoe(1.20, -0.20))
        assert result["status"] == "POOR"
        assert result["total_score"] < 40


# ---------------------------------------------------------------------------
# score_shoe — hard rejects
# ---------------------------------------------------------------------------

class TestScoreShoeRejects:
    def test_toebox_width_compression(self):
        shoe = make_shoe(insole_toebox_width_in=FOOT["toebox_width_in"] - 1.2)
        result = score_shoe(FOOT, shoe)
        assert result["status"] == "REJECTED"
        assert result["reject_reason"] == "TOEBOX_WIDTH_COMPRESSION"
        assert result["total_score"] == 0.0
        assert result["dimensions"] == {}
        # estimated size still provided on reject
        assert result["estimated_us_size"] == estimate_us_size(ADJ_LEN, "men")

    def test_length_too_long_rejected(self):
        result = score_shoe(bare_foot(), bare_shoe(2.5, 0.10))
        assert result["reject_reason"] == "LENGTH_OUT_OF_RANGE"

    def test_length_too_short_rejected(self):
        result = score_shoe(bare_foot(), bare_shoe(-0.7, 0.10))
        assert result["reject_reason"] == "LENGTH_OUT_OF_RANGE"

    def test_width_too_wide_rejected(self):
        # shoe range low = W - 0.92 must exceed foot_wid_hi = 3.629 + 1.10
        shoe = bare_shoe(0.45, 0.0)
        shoe["insole_width_in"] = ADJ_WID + 1.10 + 0.92 + 0.1
        result = score_shoe(bare_foot(), shoe)
        assert result["reject_reason"] == "WIDTH_OUT_OF_RANGE"

    def test_width_too_narrow_rejected(self):
        # shoe range high = W + 1.25 must be below foot_wid_lo = 3.629 - 1.10
        shoe = bare_shoe(0.45, 0.0)
        shoe["insole_width_in"] = ADJ_WID - 1.10 - 1.25 - 0.1
        result = score_shoe(bare_foot(), shoe)
        assert result["reject_reason"] == "WIDTH_OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# score_shoe — pre-processing adjustments and flags
# ---------------------------------------------------------------------------

class TestScoreShoeAdjustments:
    def test_dress_fashion_allowance(self):
        shoe = make_shoe(function_tags=["Formal"], toe_shape="pointed")
        result = score_shoe(FOOT, shoe)
        assert result["profile_used"] == "DRESS"
        assert "FASHION_ALLOWANCE_APPLIED" in result["flags"]
        assert any("pointed" in adj for adj in result["adjustments_applied"])
        # 0.99" deduction shrinks effective length: clearance drops accordingly
        assert result["dimensions"]["foot_length"]["clearance"] == pytest.approx(0.45 - 0.99, abs=1e-3)

    def test_dress_round_toe_no_deduction(self):
        shoe = make_shoe(function_tags=["Formal"], toe_shape="round")
        result = score_shoe(FOOT, shoe)
        assert "FASHION_ALLOWANCE_APPLIED" not in result["flags"]

    def test_work_outdoor_cap_deduction(self):
        shoe = make_shoe(function_tags=["Work", "Outdoor"], cap_type="steel")
        result = score_shoe(FOOT, shoe)
        assert result["profile_used"] == "WORK_OUTDOOR"
        assert "CAP_WALL_DEDUCTED" in result["flags"]

    def test_work_indoor_cap_only_with_safety_toe(self):
        shoe = make_shoe(function_tags=["Work", "Indoor"], cap_type="steel")
        result = score_shoe(FOOT, shoe)
        assert "CAP_WALL_DEDUCTED" not in result["flags"]

        shoe = make_shoe(
            function_tags=["Work", "Indoor"],
            cap_type="composite",
            attributes_json={"safety_toe": True},
        )
        result = score_shoe(FOOT, shoe)
        assert "CAP_WALL_DEDUCTED" in result["flags"]

    def test_combat_style_raises_length_min(self):
        shoe = make_shoe(style_tags=["Combat"])
        result = score_shoe(FOOT, shoe)
        assert "COMBAT_TOE_MIN_RAISED" in result["flags"]

    def test_skate_feel_degraded_flag(self):
        shoe = make_shoe(
            function_tags=["Athletic", "Skate"],
            insole_length_in=round(ADJ_LEN + 0.50, 3),  # > 0.47 clearance
        )
        result = score_shoe(FOOT, shoe)
        assert result["profile_used"] == "SKATE"
        assert "FEEL_DEGRADED" in result["flags"]

    def test_skate_tight_fit_flag(self):
        # SKATE length min = 0.04; clearance < 0.08 flags a sport-tight fit
        shoe = make_shoe(
            function_tags=["Athletic", "Skate"],
            insole_length_in=round(ADJ_LEN + 0.05, 3),
        )
        result = score_shoe(FOOT, shoe)
        assert "SPORT_TIGHT_FIT" in result["flags"]


class TestScoreShoeSubTypes:
    def make_road_shoe(self, c_length=0.50):
        return make_shoe(
            function_tags=["Athletic", "Running", "Road"],
            insole_length_in=round(ADJ_LEN + c_length, 3),
        )

    def test_marathon_shifts_length_optimum_up(self):
        base = score_shoe(FOOT, self.make_road_shoe())
        marathon = score_shoe(FOOT, self.make_road_shoe(), sub_type="marathon")
        assert marathon["sub_type"] == "marathon"
        # 0.50 clearance was optimal; marathon wants opt_low 0.71 -> now tight
        assert base["dimensions"]["foot_length"]["zone"] == "optimal"
        assert marathon["dimensions"]["foot_length"]["zone"] == "tight"
        assert marathon["total_score"] < base["total_score"]

    def test_half_marathon_smaller_shift(self):
        half = score_shoe(FOOT, self.make_road_shoe(), sub_type="half_marathon")
        full = score_shoe(FOOT, self.make_road_shoe(), sub_type="marathon")
        assert half["total_score"] >= full["total_score"]

    def test_hiking_pack_modifier_flag(self):
        shoe = make_shoe(function_tags=["Athletic", "Hiking"])
        result = score_shoe(FOOT, shoe, sub_type="pack_over_55lbs")
        assert "PACK_MODIFIER_APPLIED" in result["flags"]

    def test_hiking_thick_socks_widens_width_optimum(self):
        shoe = make_shoe(function_tags=["Athletic", "Hiking"])
        base = score_shoe(FOOT, shoe)
        thick = score_shoe(FOOT, shoe, sub_type="thick_socks")
        # opt_low raised by 0.16 -> the 0.10/side clearance becomes tight
        assert thick["total_score"] <= base["total_score"]

    @pytest.mark.parametrize("tags,sub_type", [
        (["Athletic", "Training"], "olympic_lifting"),
        (["Athletic", "Training"], "hiit"),
        (["Athletic", "Soccer"], "football_lineman"),
        (["Athletic", "Tennis"], "clay_court"),
        (["Athletic", "Skate"], "comfort_mode"),
    ])
    def test_other_sub_types_run_clean(self, tags, sub_type):
        shoe = make_shoe(function_tags=tags)
        result = score_shoe(FOOT, shoe, sub_type=sub_type)
        assert result["sub_type"] == sub_type
        assert result["status"] in {"PERFECT", "GOOD", "ACCEPTABLE", "MARGINAL", "POOR", "REJECTED"}

    def test_unknown_sub_type_is_ignored(self):
        base = score_shoe(FOOT, make_shoe())
        weird = score_shoe(FOOT, make_shoe(), sub_type="zero_gravity")
        assert weird["total_score"] == base["total_score"]
