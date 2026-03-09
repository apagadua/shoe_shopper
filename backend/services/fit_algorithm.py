"""
Shoe Fit Recommendation Algorithm — v1.0

Scores a shoe against a foot measurement on a 0–100 point scale.
Every shoe starts at 100 points; deviations from optimal clearance subtract points.
Three hard-reject conditions return status="REJECTED" before any scoring runs.

All measurements in inches.
"""

import copy

ALGORITHM_VERSION = "1.3"

# ---------------------------------------------------------------------------
# CV measurement error offsets — update here after retraining the model.
# Expand each measurement into a candidate range at match time:
#   foot  range = [foot_val  - FOOT_*_LO,  foot_val  + FOOT_*_HI]
#   shoe  range = [shoe_val  - SHOE_*_LO,  shoe_val  + SHOE_*_HI]
# A dimension matches if the two ranges overlap.
# ---------------------------------------------------------------------------

FOOT_LENGTH_LO = 0.31
FOOT_LENGTH_HI = 0.83
FOOT_WIDTH_LO  = 0.48
FOOT_WIDTH_HI  = 0.40

SHOE_LENGTH_LO = 0.68
SHOE_LENGTH_HI = 1.39
SHOE_WIDTH_LO  = 0.51
SHOE_WIDTH_HI  = 1.07

# ---------------------------------------------------------------------------
# Tolerance profiles
# Each profile: length, width, tb_len (toebox length), tb_width (toebox width)
# Width values are per-side (half of total clearance).
# ---------------------------------------------------------------------------

_PROFILES = {
    "ROAD_RUNNING": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "width":    {"min": 0.00, "opt_low": 0.12, "opt_high": 0.20, "max": 0.46},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "tb_width": {"min": 0.12, "opt_low": 0.16, "opt_high": 0.16, "max": 0.46},
    },
    "TRAIL_RUNNING": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "width":    {"min": 0.00, "opt_low": 0.12, "opt_high": 0.20, "max": 0.46},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "tb_width": {"min": 0.12, "opt_low": 0.16, "opt_high": 0.16, "max": 0.46},
    },
    "INDOOR_TRACK": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.51, "max": 0.63},
        "width":    {"min": 0.00, "opt_low": 0.12, "opt_high": 0.20, "max": 0.46},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.51, "max": 0.63},
        "tb_width": {"min": 0.12, "opt_low": 0.16, "opt_high": 0.16, "max": 0.43},
    },
    "TRAINING": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.51, "max": 0.59},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.16, "max": 0.39},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.51, "max": 0.59},
        "tb_width": {"min": 0.08, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39},
    },
    "BASKETBALL": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.67},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.20, "max": 0.43},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.67},
        "tb_width": {"min": 0.08, "opt_low": 0.12, "opt_high": 0.20, "max": 0.43},
    },
    "CLEATED_SPORT": {
        "length":   {"min": 0.20, "opt_low": 0.39, "opt_high": 0.47, "max": 0.55},
        "width":    {"min": 0.00, "opt_low": 0.04, "opt_high": 0.12, "max": 0.35},
        "tb_len":   {"min": 0.20, "opt_low": 0.39, "opt_high": 0.47, "max": 0.55},
        "tb_width": {"min": 0.00, "opt_low": 0.04, "opt_high": 0.08, "max": 0.31},
    },
    "TENNIS": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.16, "max": 0.39},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.55, "max": 0.67},
        "tb_width": {"min": 0.08, "opt_low": 0.12, "opt_high": 0.16, "max": 0.39},
    },
    "SKATE": {
        "length":   {"min": 0.20, "opt_low": 0.39, "opt_high": 0.39, "max": 0.55},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.12, "max": 0.31},
        "tb_len":   {"min": 0.20, "opt_low": 0.39, "opt_high": 0.39, "max": 0.55},
        "tb_width": {"min": 0.04, "opt_low": 0.08, "opt_high": 0.12, "max": 0.31},
    },
    "HIKING": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.16, "max": 0.39},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.79},
        "tb_width": {"min": 0.08, "opt_low": 0.12, "opt_high": 0.12, "max": 0.39},
    },
    "CASUAL": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.47, "max": 0.59},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.12, "max": 0.35},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.47, "max": 0.59},
        "tb_width": {"min": 0.04, "opt_low": 0.08, "opt_high": 0.12, "max": 0.35},
    },
    "CASUAL_SLIPON": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.47, "max": 0.59},
        "width":    {"min": 0.00, "opt_low": 0.12, "opt_high": 0.16, "max": 0.35},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.47, "max": 0.59},
        "tb_width": {"min": 0.04, "opt_low": 0.12, "opt_high": 0.16, "max": 0.35},
    },
    "WORK_INDOOR": {
        "length":   {"min": 0.24, "opt_low": 0.39, "opt_high": 0.49, "max": 0.59},
        "width":    {"min": 0.08, "opt_low": 0.16, "opt_high": 0.20, "max": 0.43},
        "tb_len":   {"min": 0.24, "opt_low": 0.39, "opt_high": 0.49, "max": 0.59},
        "tb_width": {"min": 0.08, "opt_low": 0.16, "opt_high": 0.20, "max": 0.39},
    },
    "WORK_OUTDOOR": {
        "length":   {"min": 0.24, "opt_low": 0.39, "opt_high": 0.49, "max": 0.59},
        "width":    {"min": 0.12, "opt_low": 0.20, "opt_high": 0.20, "max": 0.46},
        "tb_len":   {"min": 0.24, "opt_low": 0.39, "opt_high": 0.49, "max": 0.59},
        "tb_width": {"min": 0.12, "opt_low": 0.20, "opt_high": 0.20, "max": 0.43},
    },
    "DRESS": {
        "length":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.67},
        "width":    {"min": 0.00, "opt_low": 0.08, "opt_high": 0.12, "max": 0.35},
        "tb_len":   {"min": 0.20, "opt_low": 0.47, "opt_high": 0.59, "max": 0.67},
        "tb_width": {"min": 0.08, "opt_low": 0.12, "opt_high": 0.12, "max": 0.35},
    },
}

# ---------------------------------------------------------------------------
# Point budgets
# ---------------------------------------------------------------------------

# Full toebox data available (tb area key = toebox area)
_POINTS_DEFAULT     = {"length": 18, "width": 27, "tb_len": 18, "tb_width": 27, "area": 10}
_POINTS_SKATE       = {"length": 15, "width": 31, "tb_len": 15, "tb_width": 31, "area": 8}
_POINTS_CASUAL_SLIP = {"length": 16, "width": 29, "tb_len": 16, "tb_width": 29, "area": 10}

# No toebox, with overall foot area (area = insole_area / foot_area ratio)
_POINTS_NO_TOEBOX_WITH_AREA_DEFAULT     = {"length": 35, "width": 40, "area": 25}
_POINTS_NO_TOEBOX_WITH_AREA_SKATE       = {"length": 30, "width": 45, "area": 25}
_POINTS_NO_TOEBOX_WITH_AREA_CASUAL_SLIP = {"length": 30, "width": 45, "area": 25}

# No toebox, no area — equal weight since CV width measurements are noisy
_POINTS_NO_TOEBOX_DEFAULT     = {"length": 50, "width": 50}
_POINTS_NO_TOEBOX_SKATE       = {"length": 40, "width": 60}
_POINTS_NO_TOEBOX_CASUAL_SLIP = {"length": 42, "width": 58}


def _get_points(profile_name, has_toebox, has_area=False):
    if has_toebox:
        if profile_name == "SKATE":
            return _POINTS_SKATE
        if profile_name == "CASUAL_SLIPON":
            return _POINTS_CASUAL_SLIP
        return _POINTS_DEFAULT
    elif has_area:
        if profile_name == "SKATE":
            return _POINTS_NO_TOEBOX_WITH_AREA_SKATE
        if profile_name == "CASUAL_SLIPON":
            return _POINTS_NO_TOEBOX_WITH_AREA_CASUAL_SLIP
        return _POINTS_NO_TOEBOX_WITH_AREA_DEFAULT
    else:
        if profile_name == "SKATE":
            return _POINTS_NO_TOEBOX_SKATE
        if profile_name == "CASUAL_SLIPON":
            return _POINTS_NO_TOEBOX_CASUAL_SLIP
        return _POINTS_NO_TOEBOX_DEFAULT


# ---------------------------------------------------------------------------
# Function tag → profile routing (checked in order, most specific first)
# ---------------------------------------------------------------------------

_TAG_ROUTES = [
    (["Athletic", "Running", "Road"],   "ROAD_RUNNING"),
    (["Athletic", "Running", "Trail"],  "TRAIL_RUNNING"),
    (["Athletic", "Running", "Indoor"], "INDOOR_TRACK"),
    (["Athletic", "Running"],           "ROAD_RUNNING"),
    (["Athletic", "Training"],          "TRAINING"),
    (["Athletic", "Basketball"],        "BASKETBALL"),
    (["Athletic", "Field Sports"],      "CLEATED_SPORT"),
    (["Athletic", "Soccer"],            "CLEATED_SPORT"),
    (["Athletic", "Football"],          "CLEATED_SPORT"),
    (["Athletic", "Lacrosse"],          "CLEATED_SPORT"),
    (["Athletic", "Tennis"],            "TENNIS"),
    (["Athletic", "Skate"],             "SKATE"),
    (["Athletic", "Hiking"],            "HIKING"),
    (["Casual", "Slip-ons"],            "CASUAL_SLIPON"),
    (["Casual"],                        "CASUAL"),
    (["Work", "Indoor"],                "WORK_INDOOR"),
    (["Work", "Outdoor"],               "WORK_OUTDOOR"),
    (["Formal"],                        "DRESS"),
]


def _get_profile_name(function_tags):
    lower_tags = {t.lower() for t in (function_tags or [])}
    for required, profile in _TAG_ROUTES:
        if all(r.lower() in lower_tags for r in required):
            return profile
    return "CASUAL"


# ---------------------------------------------------------------------------
# Fashion allowance deductions (DRESS only, applied to effective shoe length)
# ---------------------------------------------------------------------------

_FASHION_DEDUCTION = {
    "round":   0.00,
    "almond":  0.39,
    "chisel":  0.70,
    "pointed": 0.99,
}

# Cap wall deductions per side (WORK only)
_CAP_DEDUCTION_PER_SIDE = {
    "none":      0.00,
    "steel":     0.079,
    "composite": 0.157,
}


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

def _score_dimension(c, T, P):
    """Score clearance c against tolerance T for P max points."""
    opt_low  = T["opt_low"]
    opt_high = T["opt_high"]
    t_min    = T["min"]
    t_max    = T["max"]

    if c < opt_low:
        if opt_low <= t_min:
            return 0.0
        ratio = (c - t_min) / (opt_low - t_min)
        return max(0.0, P * ratio)

    if c <= opt_high:
        return float(P)

    if c <= t_max:
        if t_max <= opt_high:
            return float(P)
        ratio = (t_max - c) / (t_max - opt_high)
        # Floor raised to 0.65 — a shoe at max clearance is still a decent fit
        return P * (0.65 + 0.35 * ratio)

    # Zone 5 — excessively loose; decay over 2× the band to account for CV noise
    interval = t_max - opt_high
    if interval <= 0:
        return 0.0
    overage = c - t_max
    return max(0.0, P * 0.65 - (P * 0.65 * (overage / (interval * 2))))


def _get_zone(c, T):
    if c < T["min"]:
        return "rejected"
    if c < T["opt_low"]:
        return "tight"
    if c <= T["opt_high"]:
        return "optimal"
    if c <= T["max"]:
        return "loose"
    return "excessive"


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_shoe(foot, shoe, sub_type=None):
    """
    Score a shoe against a foot measurement.

    foot: {
        'length_in': float,
        'width_in': float,
        'area_sq_in': float | None,        # foot polygon area
        'toebox_length_in': float | None,
        'toebox_width_in': float | None,
    }

    shoe: {
        'id': int,
        'gender': str | None,
        'function_tags': list[str],
        'style_tags': list[str],
        'insole_length_in': float,
        'insole_width_in': float,          # treated as ball width
        'insole_area_sq_in': float | None, # insole polygon area
        'insole_toebox_length_in': float | None,
        'insole_toebox_width_in': float | None,
        'toe_shape': str | None,
        'cap_type': str | None,
        'attributes_json': dict,
    }

    sub_type: str | None  (marathon, half_marathon, hiit, olympic_lifting,
                            clay_court, football_lineman, comfort_mode)

    Returns a dict matching the Output Object from the design doc.
    """
    flags = []
    adjustments = []

    # -----------------------------------------------------------------------
    # Step 1 — Determine profile
    # -----------------------------------------------------------------------
    profile_name = _get_profile_name(shoe.get("function_tags") or [])
    T = copy.deepcopy(_PROFILES[profile_name])

    # -----------------------------------------------------------------------
    # Step 2 — Effective shoe dimensions (pre-processing)
    # -----------------------------------------------------------------------
    eff_shoe_length       = float(shoe["insole_length_in"] or 0)
    eff_shoe_ball_width   = float(shoe["insole_width_in"] or 0)
    eff_shoe_tb_length    = float(shoe.get("insole_toebox_length_in") or 0) or None
    eff_shoe_tb_width     = float(shoe.get("insole_toebox_width_in") or 0) or None

    # Pre-processing Step 1 — Fashion allowance (DRESS only)
    if profile_name == "DRESS":
        toe_shape = (shoe.get("toe_shape") or "round").lower()
        deduction = _FASHION_DEDUCTION.get(toe_shape, 0.00)
        if deduction > 0:
            eff_shoe_length -= deduction
            flags.append("FASHION_ALLOWANCE_APPLIED")
            adjustments.append(f"fashion_deduction: {toe_shape} {deduction}\"")

    # Pre-processing Step 2 — Cap wall deduction (WORK only)
    apply_cap = (
        profile_name == "WORK_OUTDOOR"
        or (profile_name == "WORK_INDOOR" and shoe.get("attributes_json", {}).get("safety_toe"))
    )
    if apply_cap:
        cap_type = (shoe.get("cap_type") or "none").lower()
        cap_per_side = _CAP_DEDUCTION_PER_SIDE.get(cap_type, 0.00)
        if eff_shoe_tb_width is not None:
            eff_shoe_tb_width -= 2 * cap_per_side
        if cap_per_side > 0:
            flags.append("CAP_WALL_DEDUCTED")
            adjustments.append(f"cap_deduction: {cap_type} {cap_per_side}\"/side")

    # Pre-processing Step 3 — Silhouette tag modifiers
    style_tags_lower = {t.lower() for t in (shoe.get("style_tags") or [])}

    if "slip-on sneaker" in style_tags_lower or "loafer" in style_tags_lower:
        flags.append("HEEL_SLIP_HARD_ZERO")
    elif "clog" in style_tags_lower:
        flags.append("HEEL_SCORING_DISABLED")
    elif "chelsea" in style_tags_lower:
        flags.append("HEEL_SLIP_STRICT")
    elif "high-top" in style_tags_lower and profile_name not in ("CASUAL", "CASUAL_SLIPON"):
        flags.append("HEEL_SLIP_RELAXED")

    if "combat" in style_tags_lower:
        T["length"]["min"]  = max(T["length"]["min"],  0.47)
        T["tb_len"]["min"]  = max(T["tb_len"]["min"],  0.47)
        flags.append("COMBAT_TOE_MIN_RAISED")

    # Pre-processing Step 4 — Sub-type tolerance adjustments
    if sub_type:
        st = sub_type.lower()

        if profile_name == "ROAD_RUNNING" and st == "half_marathon":
            for key in ("length", "tb_len"):
                T[key]["opt_low"]  += 0.16
                T[key]["opt_high"] += 0.16

        elif profile_name == "ROAD_RUNNING" and st == "marathon":
            for key in ("length", "tb_len"):
                T[key]["opt_low"]  += 0.24
                T[key]["opt_high"] += 0.24

        elif profile_name == "HIKING" and st == "thick_socks":
            T["width"]["opt_low"]    += 0.16
            T["tb_width"]["opt_low"] += 0.16

        elif profile_name == "HIKING" and st == "pack_over_55lbs":
            for key in ("length", "tb_len"):
                T[key]["opt_low"]  += 0.20
                T[key]["opt_high"] += 0.20
            flags.append("PACK_MODIFIER_APPLIED")

        elif profile_name == "TRAINING" and st == "olympic_lifting":
            for key in ("length", "tb_len"):
                T[key] = {"min": 0.20, "opt_low": 0.39, "opt_high": 0.47, "max": 0.47}

        elif profile_name == "TRAINING" and st == "hiit":
            T["length"]["opt_low"]  = T["length"]["opt_high"]
            T["tb_len"]["opt_low"]  = T["tb_len"]["opt_high"]

        elif profile_name == "CLEATED_SPORT" and st == "football_lineman":
            T["width"]    = {"min": 0.00, "opt_low": 0.16, "opt_high": 0.24, "max": 0.28}
            T["tb_width"] = {"min": 0.00, "opt_low": 0.12, "opt_high": 0.20, "max": 0.24}

        elif profile_name == "TENNIS" and st == "clay_court":
            T["length"]["opt_high"]  = 0.59
            T["tb_len"]["opt_high"]  = 0.59

        elif profile_name == "SKATE" and st == "comfort_mode":
            for key in ("length", "tb_len"):
                T[key] = {"min": 0.20, "opt_low": 0.47, "opt_high": 0.47, "max": 0.59}

    # -----------------------------------------------------------------------
    # Step 3 — Clearance computation
    # -----------------------------------------------------------------------
    foot_length      = float(foot["length_in"])
    foot_width       = float(foot["width_in"])
    foot_area        = float(foot["area_sq_in"]) if foot.get("area_sq_in") is not None else None
    foot_tb_length   = foot.get("toebox_length_in")
    foot_tb_width    = foot.get("toebox_width_in")

    if foot_tb_length is not None:
        foot_tb_length = float(foot_tb_length)
    if foot_tb_width is not None:
        foot_tb_width = float(foot_tb_width)

    shoe_insole_area = float(shoe["insole_area_sq_in"]) if float(shoe.get("insole_area_sq_in") or 0) > 0 else None

    c_length = eff_shoe_length - foot_length
    c_width  = (eff_shoe_ball_width - foot_width) / 2

    has_toebox = (
        foot_tb_length is not None and foot_tb_width is not None
        and eff_shoe_tb_length is not None and eff_shoe_tb_width is not None
    )
    has_area = foot_area is not None and foot_area > 0 and shoe_insole_area is not None

    if has_toebox:
        c_tb_length = eff_shoe_tb_length - foot_tb_length
        c_tb_width  = (eff_shoe_tb_width - foot_tb_width) / 2
    else:
        c_tb_length = None
        c_tb_width  = None

    # -----------------------------------------------------------------------
    # Step 4 — Hard reject checks
    # -----------------------------------------------------------------------
    def _reject(reason):
        return {
            "status": "REJECTED",
            "total_score": 0.0,
            "reject_reason": reason,
            "profile_used": profile_name,
            "sub_type": sub_type,
            "adjustments_applied": adjustments,
            "has_toebox_data": has_toebox,
            "has_area_data": has_area,
            "estimated_us_size": estimate_us_size(foot_length, shoe.get("gender", "")),
            "dimensions": {},
            "flags": flags,
        }

    # Priority 1: toebox width compression (universal)
    if c_tb_width is not None and c_tb_width < 0:
        return _reject("TOEBOX_WIDTH_COMPRESSION")

    # Priority 2: length range overlap
    foot_len_lo = foot_length - FOOT_LENGTH_LO
    foot_len_hi = foot_length + FOOT_LENGTH_HI
    shoe_len_lo = eff_shoe_length - SHOE_LENGTH_LO
    shoe_len_hi = eff_shoe_length + SHOE_LENGTH_HI
    if not (foot_len_lo <= shoe_len_hi and shoe_len_lo <= foot_len_hi):
        return _reject("LENGTH_OUT_OF_RANGE")

    # Priority 3: insufficient toebox length
    if c_tb_length is not None and c_tb_length < T["tb_len"]["min"]:
        return _reject("INSUFFICIENT_TOEBOX_LENGTH")

    # Priority 4: width range overlap
    foot_wid_lo = foot_width - FOOT_WIDTH_LO
    foot_wid_hi = foot_width + FOOT_WIDTH_HI
    shoe_wid_lo = eff_shoe_ball_width - SHOE_WIDTH_LO
    shoe_wid_hi = eff_shoe_ball_width + SHOE_WIDTH_HI
    if not (foot_wid_lo <= shoe_wid_hi and shoe_wid_lo <= foot_wid_hi):
        return _reject("WIDTH_OUT_OF_RANGE")

    # -----------------------------------------------------------------------
    # Step 5 — Scoring
    # -----------------------------------------------------------------------
    pts = _get_points(profile_name, has_toebox, has_area)

    len_score  = _score_dimension(c_length, T["length"], pts["length"])
    wid_score  = _score_dimension(c_width,  T["width"],  pts["width"])

    overall_area_ratio = None
    overall_area_score = None

    if has_toebox:
        tb_len_score = _score_dimension(c_tb_length, T["tb_len"],   pts["tb_len"])
        tb_wid_score = _score_dimension(c_tb_width,  T["tb_width"], pts["tb_width"])

        # Toebox area score
        opt_tb_len_mid   = (T["tb_len"]["opt_low"]   + T["tb_len"]["opt_high"])   / 2
        opt_tb_wid_mid   = (T["tb_width"]["opt_low"] + T["tb_width"]["opt_high"]) / 2
        expected_area    = (foot_tb_length + opt_tb_len_mid) * (foot_tb_width + 2 * opt_tb_wid_mid)
        shoe_tb_area     = eff_shoe_tb_length * eff_shoe_tb_width

        min_area = (foot_tb_length + T["tb_len"]["min"]) * (foot_tb_width + 2 * T["tb_width"]["min"])
        max_area = (foot_tb_length + T["tb_len"]["max"]) * (foot_tb_width + 2 * T["tb_width"]["max"])

        if expected_area > 0:
            area_ratio = shoe_tb_area / expected_area
            T_area = {
                "min":      min_area / expected_area if expected_area else 0,
                "opt_low":  1.00,
                "opt_high": 1.00,
                "max":      max_area / expected_area if expected_area else 2,
            }
            area_score = _score_dimension(area_ratio, T_area, pts["area"])
        else:
            area_score = pts["area"]
            area_ratio = 1.0
            shoe_tb_area = 0.0

        total = len_score + wid_score + tb_len_score + tb_wid_score + area_score
    else:
        tb_len_score = None
        tb_wid_score = None
        area_score   = None
        area_ratio   = None
        shoe_tb_area = None

        if has_area:
            # Overall foot area vs insole area ratio
            # Optimal: insole is 10–35% larger than foot (accommodates foot with room)
            # Lenient bounds given CV area noise
            overall_area_ratio = shoe_insole_area / foot_area
            T_area_overall = {"min": 0.90, "opt_low": 1.10, "opt_high": 1.35, "max": 2.00}
            overall_area_score = _score_dimension(overall_area_ratio, T_area_overall, pts["area"])
            total = len_score + wid_score + overall_area_score
        else:
            total = len_score + wid_score

    total = round(min(max(total, 0.0), 100.0), 1)

    # -----------------------------------------------------------------------
    # Step 6 — Status thresholds
    # -----------------------------------------------------------------------
    if total >= 90:
        status = "PERFECT"
    elif total >= 75:
        status = "GOOD"
    elif total >= 60:
        status = "ACCEPTABLE"
    elif total >= 40:
        status = "MARGINAL"
    else:
        status = "POOR"

    # -----------------------------------------------------------------------
    # Step 7 — Sport-specific flags
    # -----------------------------------------------------------------------
    if profile_name in ("CLEATED_SPORT", "SKATE") and c_length < T["length"]["min"] + 0.04:
        flags.append("SPORT_TIGHT_FIT")
    if profile_name == "SKATE" and c_length > 0.47:
        flags.append("FEEL_DEGRADED")

    # -----------------------------------------------------------------------
    # Build output
    # -----------------------------------------------------------------------
    dimensions = {
        "foot_length": {
            "clearance": round(c_length, 4),
            "zone": _get_zone(c_length, T["length"]),
            "points_earned": round(len_score, 2),
            "points_max": pts["length"],
        },
        "foot_width": {
            "clearance_per_side": round(c_width, 4),
            "zone": _get_zone(c_width, T["width"]),
            "points_earned": round(wid_score, 2),
            "points_max": pts["width"],
        },
    }

    if has_toebox:
        dimensions["toebox_length"] = {
            "clearance": round(c_tb_length, 4),
            "zone": _get_zone(c_tb_length, T["tb_len"]),
            "points_earned": round(tb_len_score, 2),
            "points_max": pts["tb_len"],
        }
        dimensions["toebox_width"] = {
            "clearance_per_side": round(c_tb_width, 4),
            "zone": _get_zone(c_tb_width, T["tb_width"]),
            "points_earned": round(tb_wid_score, 2),
            "points_max": pts["tb_width"],
        }
        dimensions["toebox_area"] = {
            "shoe_area": round(shoe_tb_area, 4),
            "expected_area": round(expected_area, 4),
            "ratio": round(area_ratio, 4),
            "zone": _get_zone(area_ratio, T_area),
            "points_earned": round(area_score, 2),
            "points_max": pts["area"],
        }
    elif has_area:
        T_area_overall = {"min": 0.90, "opt_low": 1.10, "opt_high": 1.35, "max": 2.00}
        dimensions["overall_area"] = {
            "foot_area": round(foot_area, 4),
            "shoe_area": round(shoe_insole_area, 4),
            "ratio": round(overall_area_ratio, 4),
            "zone": _get_zone(overall_area_ratio, T_area_overall),
            "points_earned": round(overall_area_score, 2),
            "points_max": pts["area"],
        }

    return {
        "status": status,
        "total_score": total,
        "reject_reason": None,
        "profile_used": profile_name,
        "sub_type": sub_type,
        "adjustments_applied": adjustments,
        "has_toebox_data": has_toebox,
        "has_area_data": has_area,
        "estimated_us_size": estimate_us_size(foot_length, shoe.get("gender", "")),
        "dimensions": dimensions,
        "flags": flags,
    }


def estimate_us_size(foot_length_in, gender):
    """
    Estimate US shoe size from foot length using the Brannock formula.
      Men's/unisex: size = 3 × foot_length_in − 22
      Women's:      1.5 sizes larger for same foot length
    Returns a float rounded to the nearest half size.
    """
    gender_lower = (gender or "").lower()
    if gender_lower in ("women", "w", "female", "f"):
        raw = foot_length_in * 3.0 - 20.5
    else:
        raw = foot_length_in * 3.0 - 22.0
    return round(raw * 2) / 2


def status_label(status):
    """Human-readable label for a status string."""
    return {
        "PERFECT":    "Perfect fit",
        "GOOD":       "Good fit",
        "ACCEPTABLE": "Acceptable fit",
        "MARGINAL":   "Marginal fit",
        "POOR":       "Poor fit",
        "REJECTED":   "Not recommended",
        "UNSCORED":   "No fit data yet",
    }.get(status, status)
