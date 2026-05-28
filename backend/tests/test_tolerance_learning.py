import sys
import os

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
)
from services.tolerance_learning import (
    compute_dimension_vals,
    compute_signals,
    compute_tolerances
)

TEST_TOLERANCES = {
    "total_feedback_count": 5,
    "length":   {"type": "length", "min": 0.15, "opt_low": 0.42, "opt_high": 0.60, "max": 0.70},
    "width":    {"type": "width", "min": -0.30, "opt_low": 0.10, "opt_high": 0.25, "max": 0.40},
    "tb_len":   {"type": "length", "min": 0.15, "opt_low": 0.42, "opt_high": 0.60, "max": 0.70},
    "tb_width": {"type": "width", "min": -0.20, "opt_low": 0.10, "opt_high": 0.20, "max": 0.4}
}

def test_too_wide():  # should shrink width
    print("Running test_too_wide...")

    feedback_rows = [
        {"feedback_type": "too wide", "tolerances": TEST_TOLERANCES, "severity_rating": 5},
        {"feedback_type": "too wide", "tolerances": TEST_TOLERANCES, "severity_rating": 3}
        ]
    
    tolerances = {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }
    
    values = compute_dimension_vals(feedback_rows, tolerances)
    width_signal, length_signal = compute_signals(values)
    new_tolerances = compute_tolerances(
        width_signal,
        length_signal,
        tolerances,
        0.5,
        10,
        len(feedback_rows)
    )

    # Ensure width shrinks
    assert new_tolerances["width"]["opt_low"] < tolerances["width"]["opt_low"]
    assert new_tolerances["width"]["opt_high"] < tolerances["width"]["opt_high"]
    assert new_tolerances["tb_width"]["opt_low"] < tolerances["tb_width"]["opt_low"]
    assert new_tolerances["tb_width"]["opt_high"] < tolerances["tb_width"]["opt_high"]
    # And length stays the same
    assert abs(new_tolerances["length"]["opt_low"] - tolerances["length"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["length"]["opt_high"] - tolerances["length"]["opt_high"]) < 1e-9
    assert abs(new_tolerances["tb_len"]["opt_low"] - tolerances["tb_len"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["tb_len"]["opt_high"] - tolerances["tb_len"]["opt_high"]) < 1e-9 
    print("test_too_wide:   passed!")

def test_too_narrow():  # should expand width
    print("Running test_too_narrow...")

    tolerances = {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    feedback_rows = [
        {"feedback_type": "too narrow", "tolerances": TEST_TOLERANCES, "severity_rating": 5},
        {"feedback_type": "too narrow", "tolerances": TEST_TOLERANCES, "severity_rating": 3}
    ]

    values = compute_dimension_vals(feedback_rows, tolerances)
    width_signal, _ = compute_signals(values)

    new_tolerances = compute_tolerances(
        width_signal,
        0,
        tolerances,
        0.5,
        10,
        len(feedback_rows)
    )

    # Ensure width expands
    assert new_tolerances["width"]["opt_low"] > tolerances["width"]["opt_low"]
    assert new_tolerances["width"]["opt_high"] > tolerances["width"]["opt_high"]
    assert new_tolerances["tb_width"]["opt_low"] > tolerances["tb_width"]["opt_low"]
    assert new_tolerances["tb_width"]["opt_high"] > tolerances["tb_width"]["opt_high"]
    # And length stays the same
    assert abs(new_tolerances["length"]["opt_low"] - tolerances["length"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["length"]["opt_high"] - tolerances["length"]["opt_high"]) < 1e-9
    assert abs(new_tolerances["tb_len"]["opt_low"] - tolerances["tb_len"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["tb_len"]["opt_high"] - tolerances["tb_len"]["opt_high"]) < 1e-9
    print("test_too_narrow: passed!")

def test_too_long():  # should shrink length
    print("Running test_too_long...")

    tolerances = {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    feedback_rows = [
        {"feedback_type": "too long", "tolerances": TEST_TOLERANCES, "severity_rating": 5},
        {"feedback_type": "too long", "tolerances": TEST_TOLERANCES, "severity_rating": 3}
    ]

    values = compute_dimension_vals(feedback_rows, tolerances)
    _, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        0,
        length_signal,
        tolerances,
        0.5,
        10,
        len(feedback_rows)
    )


    # Ensure length shrinks
    assert new_tolerances["length"]["opt_low"] < tolerances["length"]["opt_low"]
    assert new_tolerances["length"]["opt_high"] < tolerances["length"]["opt_high"]
    assert new_tolerances["tb_len"]["opt_low"] < tolerances["tb_len"]["opt_low"]
    assert new_tolerances["tb_len"]["opt_high"] < tolerances["tb_len"]["opt_high"]
    # And width stays the same
    assert abs(new_tolerances["width"]["opt_low"] - tolerances["width"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["width"]["opt_high"] - tolerances["width"]["opt_high"]) < 1e-9
    assert abs(new_tolerances["tb_width"]["opt_low"] - tolerances["tb_width"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["tb_width"]["opt_high"] - tolerances["tb_width"]["opt_high"]) < 1e-9
    print("test_too_long:   passed!")

def test_too_short():  # should expand length
    print("Running test_too_short...")

    tolerances = {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    feedback_rows = [
        {"feedback_type": "too short", "tolerances": TEST_TOLERANCES, "severity_rating": 5},
        {"feedback_type": "too short", "tolerances": TEST_TOLERANCES, "severity_rating": 3}
    ]

    values = compute_dimension_vals(feedback_rows, tolerances)
    _, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        0,
        length_signal,
        tolerances,
        0.5,
        10,
        len(feedback_rows)
    )

    # Ensure length expands
    assert new_tolerances["length"]["opt_low"] > tolerances["length"]["opt_low"]
    assert new_tolerances["length"]["opt_high"] > tolerances["length"]["opt_high"]
    assert new_tolerances["tb_len"]["opt_low"] > tolerances["tb_len"]["opt_low"]
    assert new_tolerances["tb_len"]["opt_high"] > tolerances["tb_len"]["opt_high"]
    # And width stays the same
    assert abs(new_tolerances["width"]["opt_low"] - tolerances["width"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["width"]["opt_high"] - tolerances["width"]["opt_high"]) < 1e-9
    assert abs(new_tolerances["tb_width"]["opt_low"] - tolerances["tb_width"]["opt_low"]) < 1e-9
    assert abs(new_tolerances["tb_width"]["opt_high"] - tolerances["tb_width"]["opt_high"]) < 1e-9
    print("test_too_short:  passed!")

def test_balanced():  # shouldn't change things much
    print("Running test_balanced...")

    tolerances = {
        "total_feedback_count": 5,
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    feedback_rows = [
        {"feedback_type": "too wide", "tolerances": TEST_TOLERANCES, "severity_rating": 5},
        {"feedback_type": "too narrow", "tolerances": TEST_TOLERANCES, "severity_rating": 3},
        {"feedback_type": "perfect", "tolerances": TEST_TOLERANCES, "severity_rating": 0},
    ]

    values = compute_dimension_vals(feedback_rows, tolerances)
    width_signal, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        width_signal,
        length_signal,
        tolerances,
        0.5,
        10,
        len(feedback_rows)
    )

    # Ensure width and length don't change much (alpha=0.5 but signals should be small)
    assert abs(new_tolerances["width"]["opt_low"] - tolerances["width"]["opt_low"]) < 0.25
    assert abs(new_tolerances["width"]["opt_high"] - tolerances["width"]["opt_high"]) < 0.25
    assert abs(new_tolerances["length"]["opt_low"] - tolerances["length"]["opt_low"]) < 0.25
    assert abs(new_tolerances["length"]["opt_high"] - tolerances["length"]["opt_high"]) < 0.25
    assert abs(new_tolerances["tb_len"]["opt_low"] - tolerances["tb_len"]["opt_low"]) < 0.25
    assert abs(new_tolerances["tb_len"]["opt_high"] - tolerances["tb_len"]["opt_high"]) < 0.25
    assert abs(new_tolerances["tb_width"]["opt_low"] - tolerances["tb_width"]["opt_low"]) < 0.25
    assert abs(new_tolerances["tb_width"]["opt_high"] - tolerances["tb_width"]["opt_high"]) < 0.25
    print("test_balanced:   passed!")

if __name__ == "__main__":
    test_too_wide()
    test_too_narrow()
    test_too_long()
    test_too_short()
    test_balanced()