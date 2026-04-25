# Shoe Fit Recommendation Algorithm — Design Document

**Version:** 1.0
**Status:** Ready for Implementation
**Last Updated:** 2026-03-04

---

## Overview

Every shoe starts at **100 points**. Deviations from the optimal clearance range for the shoe's category subtract points. Three hard-reject conditions return a `REJECTED` status — distinct from a low numeric score — before any scoring runs.

**Measurement basis:** All comparisons are foot scan measurements vs. **insole measurements**. Upper construction properties (waterproofing, leather, insulation) do not enter the algorithm — they do not change the insole's dimensional footprint.

**Single scan assumption:** The algorithm scores one foot at a time. The app should prompt the user to scan their larger foot. Asymmetry cannot be assessed.

**All measurements in inches.**

---

## 1. Inputs

### Foot (from scan)

| Field | Description |
|---|---|
| `foot.max_length` | Total foot length, heel to tip of longest toe |
| `foot.max_width` | Width at the widest point of the forefoot (ball) |
| `foot.toebox_max_length` | Length of the toebox region |
| `foot.toebox_max_width` | Width across the toebox |

### Shoe (from database — all insole measurements)

| Field | Description |
|---|---|
| `shoe.length` | Total insole length |
| `shoe.ball_width` | Insole width at ball |
| `shoe.toebox_length` | Insole toebox length |
| `shoe.toebox_width` | Insole toebox width |
| `shoe.function_tag` | Primary function category (see §2) |
| `shoe.silhouette_tag` | Silhouette type (see §4) |
| `shoe.toe_shape` | DRESS only: `round` / `almond` / `chisel` / `pointed` |
| `shoe.cap_type` | WORK only: `none` / `steel` / `composite` |
| `shoe.attributes.safety_toe` | Boolean — WORK_INDOOR: triggers cap deduction if true |

### User Context

| Field | Description |
|---|---|
| `sub_type` | Optional modifier: `marathon`, `half_marathon`, `hiit`, `olympic_lifting`, `clay_court`, `football_skill`, `football_lineman`, `comfort_mode` |

---

## 2. Category Routing

Map the shoe's function tag to a scoring profile:

```
Athletic > Running > Road       → ROAD_RUNNING
Athletic > Running > Trail      → TRAIL_RUNNING
Athletic > Running > Indoor     → INDOOR_TRACK
Athletic > Training             → TRAINING
Athletic > Basketball           → BASKETBALL
Athletic > Field Sports         → CLEATED_SPORT
Athletic > Tennis               → TENNIS
Athletic > Skate                → SKATE
Athletic > Hiking               → HIKING
Casual > Sneakers               → CASUAL
Casual > Boots                  → CASUAL
Casual > Slip-ons               → CASUAL_SLIPON
Work > Indoor                   → WORK_INDOOR
Work > Outdoor                  → WORK_OUTDOOR
Formal                          → DRESS
```

---

## 3. Tolerance Profiles

Each profile defines five values per dimension:
- `min` — hard-reject floor (below this = REJECTED)
- `opt_low` — start of zero-penalty zone
- `opt_high` — end of zero-penalty zone
- `max` — above this = loose-penalty zone begins

Width values are **per side** (half of the total clearance).
Toebox width values are also **per side**.

### 3.1 Running Family

**ROAD_RUNNING**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.59 | 0.79 |
| Foot Width Clearance/side | 0.00 | 0.12 | 0.20 | 0.31 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.59 | 0.79 |
| Toebox Width Clearance/side | 0.12 | 0.16 | 0.16 | 0.31 |

*Sources: APMA (9.5–12.7mm optimal); FootCareMD (max 17mm); Running Warehouse (15–20mm for >15 mi). Width inferred from Chaiwanichsiri 5mm total threshold in Buldt & Menz 2018.*

**TRAIL_RUNNING**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.47 | 0.47 | 0.59 | 0.79 |
| Foot Width Clearance/side | 0.00 | 0.12 | 0.20 | 0.31 |
| Toebox Length Clearance | 0.47 | 0.47 | 0.59 | 0.79 |
| Toebox Width Clearance/side | 0.12 | 0.16 | 0.16 | 0.31 |

*Minimum raised to 0.47" (12mm) to account for descent forward-slide exposure. Width same as road — trail shoe insoles are already wider by design.*

**INDOOR_TRACK**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.51 | 0.63 |
| Foot Width Clearance/side | 0.00 | 0.12 | 0.20 | 0.31 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.51 | 0.63 |
| Toebox Width Clearance/side | 0.12 | 0.16 | 0.16 | 0.28 |

*Ceiling lowered — no long-distance swelling applies. Distance modifiers suppressed. Sprint spikes are outside algorithm scope (coach-fitted at ~6mm, intentionally at injury threshold per Running Warehouse).*

### 3.2 Athletic — Court, Field, Skate

**TRAINING**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.51 | 0.59 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.16 | 0.24 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.51 | 0.59 |
| Toebox Width Clearance/side | 0.08 | 0.12 | 0.16 | 0.24 |

*Sources: CrossFit/HIIT optimal 12–15mm (ThatFitFriend); 1mm foot shift degrades proprioception in lifting (RunRepeat). Olympic lifting sub-type tightens length window.*

**BASKETBALL** *(revised per PMC12391082, 2025)*
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.59 | 0.67 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.20 | 0.28 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.59 | 0.67 |
| Toebox Width Clearance/side | 0.08 | 0.12 | 0.20 | 0.28 |

*2025 study (n=30): +3mm toe box → −7.7% cut time, −6.5% sprint time, +27% propulsion impulse (all p<0.01). PMC9139072: forefoot constriction increases ankle inversion during cuts. Width weight is standard 1.5×.*

**CLEATED_SPORT** (Soccer, Football, Lacrosse)
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.39 | 0.47 | 0.55 |
| Foot Width Clearance/side | 0.00 | 0.04 | 0.12 | 0.20 |
| Toebox Length Clearance | 0.39 | 0.39 | 0.47 | 0.55 |
| Toebox Width Clearance/side | 0.00 | 0.04 | 0.08 | 0.16 |

*Cleat studs lock the foot to the ground, eliminating forward migration — allows optimal starting at the 10mm safety floor. Sources: Nike fit guide (5mm target); Adidas (6–12.7mm); hallux valgus risk rises every mm below 10mm. PMC6259463: 35% higher forefoot peak pressure vs. running shoes.*

**TENNIS**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.55 | 0.67 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.16 | 0.24 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.55 | 0.67 |
| Toebox Width Clearance/side | 0.08 | 0.12 | 0.16 | 0.24 |

*Sources: Mouratoglou Academy (10mm min); Tennis Warehouse Europe (10–15mm for long matches). Upper opt_high 0.55" accommodates multi-hour match duration swelling.*

**SKATE**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.39 | 0.39 | 0.55 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.12 | 0.16 |
| Toebox Length Clearance | 0.39 | 0.39 | 0.39 | 0.55 |
| Toebox Width Clearance/side | 0.04 | 0.08 | 0.12 | 0.16 |

*Optimal zone is a single point at the universal 10mm floor — reflects the skate community's performance-sizing practice. Podiatry Today survey (n=113): 39.8% cite brand inconsistency; 28.3% flat foot prevalence vs. 17% general population. Cup soles cannot break in for width → width weight elevated to 2.0×. Comfort mode sub-type opens length window.*

### 3.3 Hiking

**HIKING**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.47 | 0.47 | 0.59 | 0.79 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.16 | 0.24 |
| Toebox Length Clearance | 0.47 | 0.47 | 0.59 | 0.79 |
| Toebox Width Clearance/side | 0.08 | 0.12 | 0.12 | 0.24 |

*LOWA official adult standard: 15mm (0.59"). Industry consensus: 12–15mm. Opt_high raised to 0.59" to include LOWA standard in zero-penalty zone. Max 0.79" accommodates B3 mountaineering range (15–20mm). Sources: LOWA Task Force Fitting; REI; AMC; Cotswold Outdoor.*

### 3.4 Casual Family

**CASUAL** (Sneakers, Boots)
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.47 | 0.59 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.12 | 0.20 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.47 | 0.59 |
| Toebox Width Clearance/side | 0.04 | 0.08 | 0.12 | 0.20 |

*Sources: APMA 9.5–12.7mm; Buldt & Menz 2018 (width dominant misfit, median 58% too narrow).*

**CASUAL_SLIPON** (Slip-ons, Loafers)
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.47 | 0.59 |
| Foot Width Clearance/side | 0.00 | 0.12 | 0.16 | 0.20 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.47 | 0.59 |
| Toebox Width Clearance/side | 0.04 | 0.12 | 0.16 | 0.20 |

*No lacing means the shoe cannot be tightened if the foot swells — width optimal raised to 0.12"–0.16"/side. Width weight elevated to 1.75×. Heel slip hard constraint: 0.00" (flagged, not scored).*

### 3.5 Work Family

**WORK_INDOOR**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.24 | 0.39 | 0.49 | 0.59 |
| Foot Width Clearance/side | 0.08 | 0.16 | 0.20 | 0.28 |
| Toebox Length Clearance | 0.24 | 0.39 | 0.49 | 0.59 |
| Toebox Width Clearance/side | 0.08 | 0.16 | 0.20 | 0.24 |

*Cap deduction applies only when `shoe.attributes.safety_toe == true`. ASTM post-impact residual: men 12.7mm (0.50"), women 11.9mm (0.468") — ASTM F2413-18. Occupational swelling: 1.6–1.8% volume for healthy standing workers (Krijnen 1998).*

**WORK_OUTDOOR**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.24 | 0.39 | 0.49 | 0.59 |
| Foot Width Clearance/side | 0.12 | 0.20 | 0.20 | 0.31 |
| Toebox Length Clearance | 0.24 | 0.39 | 0.49 | 0.59 |
| Toebox Width Clearance/side | 0.12 | 0.20 | 0.20 | 0.28 |

*Cap deduction always applies. Width minimum raised to 0.12"/side (WORK_OUTDOOR hard floor). EN ISO 20345:2021 post-impact residual: 12.5–15.0mm size-graduated.*

### 3.6 Dress/Formal

**DRESS**
| Dimension | min | opt_low | opt_high | max |
|---|---|---|---|---|
| Foot Length Clearance | 0.39 | 0.47 | 0.59 | 0.67 |
| Foot Width Clearance/side | 0.00 | 0.08 | 0.12 | 0.20 |
| Toebox Length Clearance | 0.39 | 0.47 | 0.59 | 0.67 |
| Toebox Width Clearance/side | 0.08 | 0.12 | 0.12 | 0.20 |

*Sources: APMA 9.5–12.7mm; FootCareMD podiatric guidelines. Fashion allowance pre-processing strips non-functional toe extension before scoring.*

---

## 4. Pre-Processing Pipeline

Applied in this exact order before any clearance is computed. Each step modifies effective shoe measurements — not the tolerance values.

```
Step 1 — Fashion allowance (DRESS only)
  fashion_deduction = {
    round:   0.00,
    almond:  0.39,   // midpoint of 0.20–0.59" range
    chisel:  0.70,   // midpoint of 0.39–1.00"
    pointed: 0.99    // midpoint of 0.59–1.38"
  }
  effective_shoe_length = shoe.length - fashion_deduction[shoe.toe_shape]

Step 2 — Cap wall deduction (WORK only)
  apply when: profile == WORK_OUTDOOR
           OR (profile == WORK_INDOOR AND shoe.attributes.safety_toe == true)
  cap_per_side = {
    none:      0.00,
    steel:     0.079,   // 2.0mm — industry datasheet midpoint
    composite: 0.157    // 4.0mm — industry datasheet midpoint
  }
  effective_toebox_width = shoe.toebox_width - (2 × cap_per_side[shoe.cap_type])

Step 3 — Silhouette tag modifiers
  Slip-on Sneaker, Loafer:
    → heel_slip_flag = "HARD_ZERO" (flag only, not scored)
  Clog:
    → heel_slip_scoring = "DISABLED"
  Chelsea boot:
    → heel_slip_flag = "STRICT" (flag only)
  Combat boot:
    → T.length.min  = max(T.length.min, 0.47)
    → T.tb_len.min  = max(T.tb_len.min, 0.47)
    → add flag: COMBAT_TOE_MIN_RAISED
  High-top silhouette (Athletic function only):
    → heel_slip_flag = "RELAXED"

Step 4 — Sub-type tolerance adjustments
  ROAD_RUNNING + half_marathon:
    → T.length.opt_low  += 0.16
    → T.length.opt_high += 0.16
    → T.tb_len.opt_low  += 0.16
    → T.tb_len.opt_high += 0.16

  ROAD_RUNNING + marathon:
    → T.length.opt_low  += 0.24
    → T.length.opt_high += 0.24
    → T.tb_len.opt_low  += 0.24
    → T.tb_len.opt_high += 0.24

  HIKING + thick_socks:
    → T.width.opt_low    += 0.16
    → T.tb_width.opt_low += 0.16

  HIKING + pack_over_55lbs:
    → T.length.opt_low  += 0.20
    → T.length.opt_high += 0.20

  TRAINING + olympic_lifting:
    → T.length = { min: 0.39, opt_low: 0.39, opt_high: 0.47, max: 0.47 }
    → T.tb_len = { min: 0.39, opt_low: 0.39, opt_high: 0.47, max: 0.47 }

  TRAINING + hiit:
    → use opt_high values as the scoring target (treat opt_high as opt_low)

  CLEATED_SPORT + football_lineman:
    → T.width    = { min: 0.00, opt_low: 0.16, opt_high: 0.24, max: 0.28 }
    → T.tb_width = { min: 0.00, opt_low: 0.12, opt_high: 0.20, max: 0.24 }

  TENNIS + clay_court:
    → T.length.opt_high    = 0.59
    → T.tb_len.opt_high    = 0.59

  SKATE + comfort_mode:
    → T.length  = { min: 0.39, opt_low: 0.47, opt_high: 0.47, max: 0.59 }
    → T.tb_len  = { min: 0.39, opt_low: 0.47, opt_high: 0.47, max: 0.59 }
```

---

## 5. Clearance Computation

Using effective values after pre-processing:

```
c_length    = effective_shoe_length   - foot.max_length
c_width     = (shoe.ball_width        - foot.max_width)       / 2
c_tb_length = shoe.toebox_length      - foot.toebox_max_length
c_tb_width  = (effective_toebox_width - foot.toebox_max_width) / 2

shoe_tb_area = shoe.toebox_length × effective_toebox_width
foot_tb_area = foot.toebox_max_length × foot.toebox_max_width
```

---

## 6. Hard Reject Checks

Evaluated in priority order. On any match, return `status: "REJECTED"` immediately. No scoring runs.

| Priority | Condition | Reason Code |
|---|---|---|
| 1 | `c_tb_width < 0` | `TOEBOX_WIDTH_COMPRESSION` |
| 2 | `c_length < T.length.min` | `INSUFFICIENT_LENGTH` |
| 3 | `c_tb_length < T.tb_len.min` | `INSUFFICIENT_TOEBOX_LENGTH` |
| 4 | `c_width < T.width.min` | `INSUFFICIENT_WIDTH` |

Rule 1 (toebox width compression) is universal with zero tolerance — supported by all sources.
Rule 4 catches the WORK_OUTDOOR 0.12"/side minimum and any width compression.

---

## 7. Point Budget

Width is weighted **1.5× relative to length** across all profiles except where noted. This ratio is directly validated by Buldt & Menz 2018: width misfitting affects a median 58% of study participants vs. 38% for length (ratio = 1.53×).

### Default (applies to all profiles except SKATE and CASUAL_SLIPON)

| Dimension | Points |
|---|---|
| Foot Length Clearance | 18 |
| Foot Width Clearance | 27 |
| Toebox Length Clearance | 18 |
| Toebox Width Clearance | 27 |
| Toebox Area | 10 |
| **Total** | **100** |

Width (54) ÷ Length (36) = **1.50** ✓

### SKATE (2.0× width — cup soles cannot stretch; compression is permanent)

| Dimension | Points |
|---|---|
| Foot Length Clearance | 15 |
| Foot Width Clearance | 31 |
| Toebox Length Clearance | 15 |
| Toebox Width Clearance | 31 |
| Toebox Area | 8 |
| **Total** | **100** |

Width (62) ÷ Length (30) = **2.07** ≈ 2.0 ✓

### CASUAL_SLIPON (1.75× width — no lacing adjustment possible)

| Dimension | Points |
|---|---|
| Foot Length Clearance | 16 |
| Foot Width Clearance | 29 |
| Toebox Length Clearance | 16 |
| Toebox Width Clearance | 29 |
| Toebox Area | 10 |
| **Total** | **100** |

Width (58) ÷ Length (32) = **1.81** ≈ 1.75 ✓

---

## 8. Dimension Scoring Function

Applied identically to all four primary clearance dimensions.
`c` = clearance value, `T` = tolerance struct, `P` = max points for this dimension.

```
function score_dimension(c, T, P):

  // Zone 2: Too tight — below optimal, linear ramp from 0 to P
  if c < T.opt_low:
    ratio = (c - T.min) / (T.opt_low - T.min)
    return P × ratio

  // Zone 3: Optimal — full points, no penalty
  if c <= T.opt_high:
    return P

  // Zone 4: Slightly loose — 50% penalty slope
  // Being too loose costs half as many points as being too tight
  if c <= T.max:
    ratio = (T.max - c) / (T.max - T.opt_high)
    return P × (0.50 + 0.50 × ratio)

  // Zone 5: Excessively loose — continues at same slope, floored at 0
  overage  = c - T.max
  interval = T.max - T.opt_high
  return max(0, P × 0.50 - (P × 0.50 × (overage / interval)))
```

**Zone summary:**
```
P pts  ─┤
        │╲ Zone 2: full penalty slope (tight)
        │  ╲
0.5P   ─┤    ╲__[Zone 3: optimal]__╱ Zone 4: half slope (loose)
        │                            ╲
0 pts  ─┤──────────────────────────────╲── Zone 5: continues to 0
        T.min         T.opt_low  T.opt_high  T.max  →
```

---

## 9. Toebox Area Scoring

Area is scored as a **ratio** against the expected shoe toebox area derived from the tolerance midpoints. This catches combined inadequacy (e.g., both length and width slightly short of optimal) that the individual dimension scores might partially miss.

```
// Compute optimal shoe toebox area from tolerance midpoints
opt_tb_len_mid   = (T.tb_len.opt_low  + T.tb_len.opt_high) / 2
opt_tb_width_mid = (T.tb_width.opt_low + T.tb_width.opt_high) / 2

expected_area = (foot.toebox_max_length + opt_tb_len_mid)
              × (foot.toebox_max_width  + 2 × opt_tb_width_mid)

min_area = (foot.toebox_max_length + T.tb_len.min)
         × (foot.toebox_max_width  + 2 × T.tb_width.min)

max_area = (foot.toebox_max_length + T.tb_len.max)
         × (foot.toebox_max_width  + 2 × T.tb_width.max)

area_ratio = shoe_tb_area / expected_area

T_area = {
  min:      min_area  / expected_area,
  opt_low:  1.00,
  opt_high: 1.00,
  max:      max_area  / expected_area
}

area_score = score_dimension(area_ratio, T_area, area_points)
// area_points = 10 (default) or 8 (SKATE/CASUAL_SLIPON)
```

---

## 10. Total Score

```
total_score = score_dimension(c_length,    T.length,   length_pts)
            + score_dimension(c_width,     T.width,    width_pts)
            + score_dimension(c_tb_length, T.tb_len,   tb_len_pts)
            + score_dimension(c_tb_width,  T.tb_width, tb_width_pts)
            + area_score

total_score = clamp(round(total_score, 1), 0.0, 100.0)
```

---

## 11. Score Thresholds

| Score | Status | Meaning |
|---|---|---|
| 90–100 | PERFECT | Optimal fit across all dimensions |
| 75–89 | GOOD | Minor deviations, comfortable for intended use |
| 60–74 | ACCEPTABLE | Noticeable but tolerable; consider adjacent size |
| 40–59 | MARGINAL | Multiple dimensions out of range; not recommended |
| < 40 | POOR | Significant mismatch; surface specific failures |
| REJECTED | — | Hard reject; display reason code prominently |

---

## 12. Flags

Non-scoring warnings appended to every non-rejected result.

| Flag | Trigger |
|---|---|
| `DIURNAL_SWELLING` | Scan taken before noon — shoe may feel tighter by evening |
| `SPORT_TIGHT_FIT` | CLEATED_SPORT or SKATE when `c_length` is within 0.04" of `T.length.min` |
| `FEEL_DEGRADED` | SKATE performance mode + `c_length > 0.47"` |
| `CAP_WALL_DEDUCTED` | WORK — cap deduction was applied |
| `HEEL_SLIP_HARD_ZERO` | CASUAL_SLIPON, Loafer, Slip-on Sneaker silhouette |
| `HEEL_SLIP_STRICT` | Chelsea boot silhouette |
| `HEEL_SLIP_RELAXED` | High-top Athletic silhouette |
| `HEEL_SCORING_DISABLED` | Clog (open heel) |
| `COMBAT_TOE_MIN_RAISED` | Combat boot silhouette — minimum raised to 0.47" |
| `FASHION_ALLOWANCE_APPLIED` | DRESS — non-functional toe length subtracted before scoring |
| `PACK_MODIFIER_APPLIED` | HIKING + pack_over_55lbs sub-type |

---

## 13. Output Object

```json
{
  "status": "REJECTED | POOR | MARGINAL | ACCEPTABLE | GOOD | PERFECT",
  "total_score": 0.0,
  "reject_reason": null,

  "profile_used": "BASKETBALL",
  "sub_type": "hiit | null",
  "adjustments_applied": ["cap_deduction: steel 0.079\"/side"],

  "dimensions": {
    "foot_length": {
      "clearance": 0.0,
      "zone": "optimal | tight | loose | excessive",
      "points_earned": 0.0,
      "points_max": 18
    },
    "foot_width": {
      "clearance_per_side": 0.0,
      "zone": "...",
      "points_earned": 0.0,
      "points_max": 27
    },
    "toebox_length": {
      "clearance": 0.0,
      "zone": "...",
      "points_earned": 0.0,
      "points_max": 18
    },
    "toebox_width": {
      "clearance_per_side": 0.0,
      "zone": "...",
      "points_earned": 0.0,
      "points_max": 27
    },
    "toebox_area": {
      "shoe_area": 0.0,
      "expected_area": 0.0,
      "ratio": 0.0,
      "zone": "...",
      "points_earned": 0.0,
      "points_max": 10
    }
  },

  "flags": []
}
```

---

## 14. Evidence Summary

| Claim | Source | Confidence |
|---|---|---|
| Universal 10mm minimum (hallux valgus risk) | 2009 study in Buldt & Menz 2018 review (PMC6064070) | High |
| Width mismatch dominant (58% vs 38%) | Buldt & Menz 2018, J Foot Ankle Res 11:43 | High — confirms 1.5× weight |
| APMA optimal clearance 9.5–12.7mm | APMA official guidelines | High |
| Marathon length increase 4–8mm | Sidas/Maligorne; navicular drop PMC3668212, PMC9520164 | High |
| Ball width decreases over 10km run | Song et al. 2024, PMC10800341 | High — width modifier not needed for distance |
| Basketball wider box improves performance | PMC12391082 (2025), n=30 | Moderate (small sample, single study) |
| Forefoot constriction increases ankle inversion | PMC9139072 | Moderate |
| LOWA adult standard 15mm | LOWA Task Force Fitting (official) | High |
| CLEATED_SPORT 10mm floor | Hallux valgus threshold; Nike/Adidas fit guides | High |
| Soccer cleat forward migration 5–10mm | Frederick 1986, J Sports Sciences | Moderate |
| ASTM F2413-18 women's 11.9mm | ASTM F2413-18 Table 1 | High |
| EN ISO 20345 size-graduated 12.5–15mm | EN ISO 20345:2021 Table 6 | High |
| Work shift swelling 1.6–1.8% standing | Krijnen 1998 | High |
| Skate flat foot prevalence 28.3% vs 17% | Podiatry Today survey, n=113 | Moderate |
| Width per-side values (all profiles) | Inferred from Chaiwanichsiri 5mm total threshold | Low — directionally correct, not directly cited |
| Sprint spikes at ~6mm injury boundary | Running Warehouse Spike Fit Guide | Industry consensus |

---

## 15. Known Limitations

1. **Width per-side values** — No peer-reviewed study publishes a validated per-side clearance number. All width/side values are inferred from total-width threshold data. The direction is correct; the exact numbers should be treated as best estimates pending further literature.

2. **Toebox area** — Scored as a derived cross-check. No study measures toebox area as a standalone fit metric. It catches combined inadequacy that individual dimension scores may partially miss.

3. **Heel slip** — Cannot be assessed from insole measurements. Flagged qualitatively only; not scored.

4. **Toebox height** — Not measurable from a top-down scan or standard insole measurement. Flagged as an unmeasured dimension in the output; not scored.

5. **Basketball profile** — Based primarily on a 2025 study with n=30. The revised tolerance values are directionally supported but the evidence base is newer and narrower than for running or hiking.

6. **Sport spikes** — Intentionally excluded. Sprint spikes are fitted at ~6mm, at the toenail-loss boundary, by coaches. Outside app scope.

7. **Single foot scan** — Asymmetry cannot be detected. The app should prompt the user to scan their larger foot.
