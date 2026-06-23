"""Tests for backend/services/tolerance_learning.py.

Note: the service expects feedback rows shaped like the user_feedback table
({"feedback_type", "fit_score", "severity_rating"}) with space-separated
feedback types ("too wide"), and compute_tolerances takes
(width_signal, length_signal, tolerances, alpha, old_count, new_count).
"""

import pytest

from backend.services.tolerance_learning import (
    MAX_SEVERITY,
    compute_dimension_vals,
    compute_signals,
    compute_tolerances,
)


def base_tolerances():
    return {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width",  "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width",  "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39},
    }


def rows(feedback_type, *scores_and_severities):
    return [
        {"feedback_type": feedback_type, "fit_score": score, "severity_rating": sev}
        for score, sev in scores_and_severities
    ]


def signals_for(feedback_rows):
    return compute_signals(compute_dimension_vals(feedback_rows))


# ---------------------------------------------------------------------------
# compute_dimension_vals
# ---------------------------------------------------------------------------

class TestComputeDimensionVals:
    def test_aggregates_severity_weighted_scores(self):
        values = compute_dimension_vals(rows("too wide", (90, 5), (80, 3)))
        # adjusted = (90*5 + 80*3) / 2 = 345; value = 2 * 345/100
        assert values["too wide"] == pytest.approx(2 * 3.45)
        assert values["perfect"] == 0

    def test_perfect_feedback_uses_max_severity(self):
        values = compute_dimension_vals([
            {"feedback_type": "perfect", "fit_score": 90, "severity_rating": None},
        ])
        assert values["perfect"] == pytest.approx(90 * MAX_SEVERITY / 100)

    def test_skips_rows_with_missing_fit_score(self):
        values = compute_dimension_vals([
            {"feedback_type": "too wide", "fit_score": None, "severity_rating": 4},
        ])
        assert values["too wide"] == 0

    def test_skips_non_perfect_rows_with_missing_severity(self):
        values = compute_dimension_vals([
            {"feedback_type": "too long", "fit_score": 80, "severity_rating": None},
        ])
        assert values["too long"] == 0


# ---------------------------------------------------------------------------
# compute_signals
# ---------------------------------------------------------------------------

class TestComputeSignals:
    def test_too_wide_gives_negative_width_signal(self):
        width_signal, length_signal = signals_for(rows("too wide", (90, 5)))
        assert width_signal < 0
        assert length_signal == 0

    def test_too_narrow_gives_positive_width_signal(self):
        width_signal, _ = signals_for(rows("too narrow", (90, 5)))
        assert width_signal > 0

    def test_too_long_gives_negative_length_signal(self):
        _, length_signal = signals_for(rows("too long", (90, 5)))
        assert length_signal < 0

    def test_too_short_gives_positive_length_signal(self):
        _, length_signal = signals_for(rows("too short", (90, 5)))
        assert length_signal > 0

    def test_balanced_feedback_keeps_signals_small(self):
        feedback = rows("too wide", (90, 3)) + rows("too narrow", (90, 3)) + [
            {"feedback_type": "perfect", "fit_score": 90, "severity_rating": None},
        ]
        width_signal, length_signal = signals_for(feedback)
        assert abs(width_signal) < 0.05
        assert length_signal == 0

    def test_signals_bounded_by_one(self):
        width_signal, length_signal = signals_for(rows("too narrow", (100, 5), (100, 5)))
        assert -1 <= width_signal <= 1
        assert -1 <= length_signal <= 1


# ---------------------------------------------------------------------------
# compute_tolerances
# ---------------------------------------------------------------------------

class TestComputeTolerances:
    def test_too_wide_shrinks_width_only(self):
        tolerances = base_tolerances()
        width_signal, length_signal = signals_for(rows("too wide", (90, 5), (80, 3)))
        updated = compute_tolerances(width_signal, length_signal, tolerances, 0.5, 5, 2)

        for dim in ("width", "tb_width"):
            assert updated[dim]["opt_low"] < tolerances[dim]["opt_low"]
            assert updated[dim]["opt_high"] < tolerances[dim]["opt_high"]
        for dim in ("length", "tb_len"):
            assert updated[dim]["opt_low"] == pytest.approx(tolerances[dim]["opt_low"])
            assert updated[dim]["opt_high"] == pytest.approx(tolerances[dim]["opt_high"])

    def test_too_short_expands_length_only(self):
        tolerances = base_tolerances()
        width_signal, length_signal = signals_for(rows("too short", (90, 5), (80, 3)))
        updated = compute_tolerances(width_signal, length_signal, tolerances, 0.5, 5, 2)

        for dim in ("length", "tb_len"):
            assert updated[dim]["opt_low"] > tolerances[dim]["opt_low"]
        for dim in ("width", "tb_width"):
            assert updated[dim]["opt_low"] == pytest.approx(tolerances[dim]["opt_low"])

    def test_min_max_deltas_preserved(self):
        tolerances = base_tolerances()
        width_signal, length_signal = signals_for(rows("too narrow", (90, 5)))
        updated = compute_tolerances(width_signal, length_signal, tolerances, 0.5, 5, 1)

        for dim in ("length", "width", "tb_len", "tb_width"):
            old, new = tolerances[dim], updated[dim]
            assert new["opt_low"] - new["min"] == pytest.approx(old["opt_low"] - old["min"])
            assert new["max"] - new["opt_high"] == pytest.approx(old["max"] - old["opt_high"])

    def test_feedback_count_accumulates(self):
        updated = compute_tolerances(0.1, 0.0, base_tolerances(), 0.5, 5, 3)
        assert updated["total_feedback_count"] == 8

    def test_type_field_preserved(self):
        updated = compute_tolerances(0.1, -0.1, base_tolerances(), 0.5, 5, 1)
        assert updated["width"]["type"] == "width"
        assert updated["length"]["type"] == "length"

    def test_invalid_tolerance_type_raises(self):
        tolerances = base_tolerances()
        tolerances["bogus"] = {"type": "diagonal", "min": 0, "opt_low": 0.1, "opt_high": 0.2, "max": 0.3}
        with pytest.raises(ValueError, match="Invalid tolerance type"):
            compute_tolerances(0.1, 0.1, tolerances, 0.5, 5, 1)

    def test_huge_shift_cannot_flip_optimal_range(self):
        tolerances = base_tolerances()
        # narrow optimal band so a large negative shift would invert it
        tolerances["width"].update(opt_low=0.12, opt_high=0.13)
        updated = compute_tolerances(-1.0, 0.0, tolerances, 1000.0, 0, 1)
        assert updated["width"]["opt_low"] <= updated["width"]["opt_high"]

    def test_zero_signals_change_nothing(self):
        tolerances = base_tolerances()
        updated = compute_tolerances(0.0, 0.0, tolerances, 0.5, 5, 0)
        for dim in ("length", "width", "tb_len", "tb_width"):
            assert updated[dim]["opt_low"] == pytest.approx(tolerances[dim]["opt_low"])
            assert updated[dim]["opt_high"] == pytest.approx(tolerances[dim]["opt_high"])
