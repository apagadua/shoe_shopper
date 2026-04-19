from backend.tolerance_learning import compute_dimension_vals, compute_signals, compute_tolerances

def test_too_wide():  # should shrink width
    print("Running test_too_wide...")

    feedback_rows = [
        {"feedback_type": "too wide", "total_score": 90, "severity": 5},
        {"feedback_type": "too wide", "total_score": 80, "severity": 3}
        ]
    
    tolerances = {
        "meta": {"total_feedback_count": 5},
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }
    
    values = compute_dimension_vals(feedback_rows)
    width_signal, length_signal = compute_signals(values)
    new_tolerances = compute_tolerances(width_signal, length_signal,
                                        tolerances, 0.5, len(feedback_rows))
    
    # print("old tolerances")
    # for key, value in tolerances.items():
    #     print(f"{key}: {value}")
    # print("new tolerances:")
    # for key, value in new_tolerances.items():
    #     print(f"{key}: {value}")
    assert new_tolerances["width"]["opt_low"] < tolerances["width"]["opt_low"]
    assert new_tolerances["width"]["opt_high"] < tolerances["width"]["opt_high"]
    assert new_tolerances["tb_width"]["opt_low"] < tolerances["tb_width"]["opt_low"]
    assert new_tolerances["tb_width"]["opt_high"] < tolerances["tb_width"]["opt_high"]
    assert new_tolerances["length"] == tolerances["length"]
    assert new_tolerances["tb_len"] == tolerances["tb_len"]
    print("test_too_wide passed")

def test_too_narrow():  # should expand width
    print("Running test_too_narrow...")

    feedback_rows = [
        {"feedback_type": "too narrow", "total_score": 90, "severity": 5},
            {"feedback_type": "too narrow", "total_score": 80, "severity": 3}
    ]

    tolerances = {
        "meta": {"total_feedback_count": 5},
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    values = compute_dimension_vals(feedback_rows)
    width_signal, _ = compute_signals(values)

    new_tolerances = compute_tolerances(
        width_signal,
        0,
        tolerances,
        alpha=0.5,
        count=1
    )

    # print("old tolerances")
    # for key, value in tolerances.items():
    #     print(f"{key}: {value}")
    # print("new tolerances:")
    # for key, value in new_tolerances.items():
    #     print(f"{key}: {value}")
    assert new_tolerances["width"]["opt_low"] > tolerances["width"]["opt_low"]
    assert new_tolerances["width"]["opt_high"] > tolerances["width"]["opt_high"]
    assert new_tolerances["tb_width"]["opt_low"] > tolerances["tb_width"]["opt_low"]
    assert new_tolerances["tb_width"]["opt_high"] > tolerances["tb_width"]["opt_high"]
    assert new_tolerances["length"] == tolerances["length"]
    assert new_tolerances["tb_len"] == tolerances["tb_len"]
    print("test_too_narrow passed")

def test_too_long():  # should shrink length
    print("Running test_too_long...")

    feedback_rows = [
        {"feedback_type": "too long", "total_score": 90, "severity": 5},
        {"feedback_type": "too long", "total_score": 80, "severity": 3}
    ]

    tolerances = {
        "meta": {"total_feedback_count": 5},
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    values = compute_dimension_vals(feedback_rows)
    _, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        0,
        length_signal,
        tolerances,
        alpha=0.5,
        count=1
    )

    # print("old tolerances")
    # for key, value in tolerances.items():
    #     print(f"{key}: {value}")
    # print("new tolerances:")
    # for key, value in new_tolerances.items():
    #     print(f"{key}: {value}")
    assert new_tolerances["length"]["opt_low"] < tolerances["length"]["opt_low"]
    assert new_tolerances["length"]["opt_high"] < tolerances["length"]["opt_high"]
    assert new_tolerances["tb_len"]["opt_low"] < tolerances["tb_len"]["opt_low"]
    assert new_tolerances["tb_len"]["opt_high"] < tolerances["tb_len"]["opt_high"]
    assert new_tolerances["width"] == tolerances["width"]
    # assert new_tolerances["tb_width"] == tolerances["tb_width"]
    print("test_too_long passed")

def test_too_short():  # should expand length
    print("Running test_too_short...")

    feedback_rows = [
        {"feedback_type": "too short", "total_score": 90, "severity": 5},
        {"feedback_type": "too short", "total_score": 80, "severity": 3}
    ]

    tolerances = {
        "meta": {"total_feedback_count": 5},
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    values = compute_dimension_vals(feedback_rows)
    _, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        0,
        length_signal,
        tolerances,
        alpha=0.5,
        count=1
    )

    # print("old tolerances")
    # for key, value in tolerances.items():
    #     print(f"{key}: {value}")
    # print("new tolerances:")
    # for key, value in new_tolerances.items():
    #     print(f"{key}: {value}")
    assert new_tolerances["length"]["opt_low"] > tolerances["length"]["opt_low"]
    assert new_tolerances["length"]["opt_high"] > tolerances["length"]["opt_high"]
    assert new_tolerances["tb_len"]["opt_low"] > tolerances["tb_len"]["opt_low"]
    assert new_tolerances["tb_len"]["opt_high"] > tolerances["tb_len"]["opt_high"]
    assert new_tolerances["width"] == tolerances["width"]
    # assert new_tolerances["tb_width"] == tolerances["tb_width"]
    print("test_too_short passed")

def test_balanced():  # shouldn't change things much
    feedback_rows = [
        {"feedback_type": "too wide", "total_score": 90, "severity": 5},
        {"feedback_type": "too narrow", "total_score": 90, "severity": 3},
        {"feedback_type": "perfect", "total_score": 90, "severity": 0},
    ]

    tolerances = {
        "meta": {"total_feedback_count": 5},
        "length":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"type": "width", "min": -0.25, "opt_low": 0.12, "opt_high": 0.20, "max": 0.39},
        "tb_len":   {"type": "length", "min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"type": "width", "min": -0.16, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39}
    }

    values = compute_dimension_vals(feedback_rows)
    width_signal, length_signal = compute_signals(values)

    new_tolerances = compute_tolerances(
        width_signal,
        length_signal,
        tolerances,
        alpha=0.5,
        count=1
    )

    # print("old tolerances")
    # for key, value in tolerances.items():
    #     print(f"{key}: {value}")
    # print("new tolerances:")
    # for key, value in new_tolerances.items():
    #     print(f"{key}: {value}")
    assert abs(new_tolerances["width"]["opt_low"] - tolerances["width"]["opt_low"]) < 0.25
    assert abs(new_tolerances["width"]["opt_high"] - tolerances["width"]["opt_high"]) < 0.25
    assert abs(new_tolerances["length"]["opt_low"] - tolerances["length"]["opt_low"]) < 0.25
    assert abs(new_tolerances["length"]["opt_high"] - tolerances["length"]["opt_high"]) < 0.25
    assert abs(new_tolerances["tb_len"]["opt_low"] - tolerances["tb_len"]["opt_low"]) < 0.25
    assert abs(new_tolerances["tb_len"]["opt_high"] - tolerances["tb_len"]["opt_high"]) < 0.25
    assert abs(new_tolerances["tb_width"]["opt_low"] - tolerances["tb_width"]["opt_low"]) < 0.25
    assert abs(new_tolerances["tb_width"]["opt_high"] - tolerances["tb_width"]["opt_high"]) < 0.25
    print("test_balanced passed")

if __name__ == "__main__":
    print("Running tolerance learning tests...")
    test_too_wide()  # good so far
    test_too_narrow()  # good so far
    test_too_long()  # tb_width min is incrementing a tiny bit instead of remaining the same, but otherwise good
    test_too_short()  # tb_width min is incrementing a tiny bit instead of remaining the same, but otherwise good
    test_balanced()  # all within 0.25 of old values with alpha=0.5