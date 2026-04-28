# Shoe Fit Recommendation Algorithm

**Current version:** 1.5
**Source files:** `backend/services/fit_algorithm.py`, `backend/api/views.py`

---

## Overview

The algorithm scores every shoe in the database against a user's foot measurement on a **0–100 point scale**. The score represents how well the shoe's insole geometry accommodates the foot, accounting for the type of use the shoe is designed for. Shoes are then sorted and returned to the client ranked best-to-worst.

The pipeline has eight stages:

```
1. CV measurement   2. Bias correction   3. Profile selection   4. Pre-processing
5. Hard reject      6. Scoring           7. Status thresholds   8. US size estimate
```

---

## Stage 1 — Foot Measurement (Computer Vision)

**Endpoint:** `POST /api/foot/measure/`
**Source:** `FootMeasureView` in `views.py`

1. The user places their foot on a standard sheet of paper (Letter or A4) and uploads a photo.
2. The image is sent to the **Roboflow** `foot-measuring` workflow (workspace: `armaanai`).
3. Roboflow returns polygon predictions for three classes:
   - `paper` — the reference sheet used to establish scale
   - `foot` / `insole` — the foot outline
   - `toe box` *(optional)* — the front portion of the foot
4. **PPI (pixels-per-inch)** is derived from the paper's bounding box, averaging the PPI calculated from both the short and long sides to handle portrait/landscape orientation.
5. **Foot dimensions** are extracted from the polygon:
   - **Length** — maximum vertex-to-vertex distance (heel to toe).
   - **Width** — 95th-percentile perpendicular span (filters polygon outlier points).
   - **Area** — shoelace formula on the polygon. If only a bounding box is available (no polygon), area is approximated as `length × width × 0.70`.
   - **Toebox length/width** — same method applied to the `toe box` polygon, if detected.
6. All pixel values are divided by PPI to produce **inch measurements**, which are stored in the `Measurement` model.

---

## Stage 2 — Bias Correction

**Source:** Constants at the top of `fit_algorithm.py`

The CV model has a systematic bias calibrated from 24 captures against a known true foot (11.55" × 5.05"):

| Dimension | Bias | Correction applied |
|-----------|------|--------------------|
| Length    | underestimates by −0.508" | +0.508" added to raw measurement |
| Width     | overestimates by +0.371"  | −0.371" subtracted from raw measurement |

These corrections are applied **once**, at the start of `score_shoe()`, before any clearance or reject logic runs. The residual uncertainty after correction is ±0.47" (length) and ±0.77" (width) at 1 StdDev — these are sample standard deviations from the same 24-capture dataset.

> **Note:** The calibration dataset is small (24 captures, one foot) so the bias constants are approximations. The algorithm compensates downstream via wide reject windows and a 0.70 score floor rather than relying on precise bias removal.

---

## Stage 3 — Profile Selection

Each shoe is assigned a **tolerance profile** based on its `function_tags`. The router checks a priority-ordered list of tag combinations and picks the first match:

| Tags (all must be present) | Profile |
|---|---|
| Athletic + Running + Road | `ROAD_RUNNING` |
| Athletic + Running + Trail | `TRAIL_RUNNING` |
| Athletic + Running + Indoor | `INDOOR_TRACK` |
| Athletic + Running | `ROAD_RUNNING` |
| Athletic + Training | `TRAINING` |
| Athletic + Basketball | `BASKETBALL` |
| Athletic + `Field Sports` | `CLEATED_SPORT` |
| Athletic + `Soccer` | `CLEATED_SPORT` |
| Athletic + `Football` | `CLEATED_SPORT` |
| Athletic + `Lacrosse` | `CLEATED_SPORT` |
| Athletic + Tennis | `TENNIS` |
| Athletic + Skate | `SKATE` |
| Athletic + Hiking | `HIKING` |
| Casual + Slip-ons | `CASUAL_SLIPON` |
| Casual | `CASUAL` |
| Work + Indoor | `WORK_INDOOR` |
| Work + Outdoor | `WORK_OUTDOOR` |
| Formal | `DRESS` |
| *(no match)* | `CASUAL` (default) |

Each profile defines four **tolerance bands** — `length`, `width`, `tb_len`, `tb_width` — each with four thresholds: `min`, `opt_low`, `opt_high`, `max`. Width values are **per-side** (half the total clearance gap). Some profiles differ in how tight they expect fit:

- **Cleated / Skate** — snug; lower optimal clearance.
- **Running / Hiking** — longer; more toe clearance expected.
- **Work** — tighter overhang limits (`min` raised to −0.12/side vs −0.25 elsewhere) for sustained-wear safety.

---

## Stage 4 — Pre-Processing (Shoe Dimension Adjustments)

Before scoring, effective shoe dimensions are adjusted for three factors:

### 4a. Fashion Allowance (DRESS only)
Pointed and chisel-toe dress shoes waste usable length on aesthetics. The insole length (and toebox length if available) is reduced by a fixed deduction before scoring:

| Toe shape | Deduction |
|-----------|-----------|
| Round     | 0.00"  |
| Almond    | 0.39"  |
| Chisel    | 0.70"  |
| Pointed   | 0.99"  |

Flag emitted: `FASHION_ALLOWANCE_APPLIED`

### 4b. Cap Wall Deduction (WORK only)
Safety toe caps consume internal width. The toebox width is reduced by 2× the per-side cap deduction:

| Cap type  | Deduction/side |
|-----------|----------------|
| None      | 0.000"         |
| Steel     | 0.079"         |
| Composite | 0.157"         |

Flag emitted: `CAP_WALL_DEDUCTED`

### 4c. Silhouette Modifiers
- **Combat boots** — minimum length tolerance raised to 0.47" (combat toe box demands more clearance).

### 4d. Sub-type Adjustments
An optional `sub_type` query parameter on `GET /api/recommendations/?sub_type=<value>` shifts the tolerance band for specific use cases. Any unrecognized value is silently ignored and the base profile is used unchanged. Valid values:

| Profile | Sub-type | Adjustment |
|---|---|---|
| ROAD_RUNNING | `half_marathon` | opt window +0.16" longer |
| ROAD_RUNNING | `marathon` | opt window +0.24" longer |
| HIKING | `thick_socks` | width opt_low +0.16"/side |
| HIKING | `pack_over_55lbs` | opt window +0.20" longer |
| TRAINING | `olympic_lifting` | tighter length band (max 0.47") |
| TRAINING | `hiit` | opt_low raised to opt_high (narrow optimal band) |
| CLEATED_SPORT | `football_lineman` | wider width tolerance |
| TENNIS | `clay_court` | opt_high +0.04" longer |
| SKATE | `comfort_mode` | length loosened to 0.47–0.59" range |

---

## Stage 5 — Hard Reject Checks

Three conditions return `status = "REJECTED"` immediately, before any scoring:

1. **TOEBOX_WIDTH_COMPRESSION** — toebox width clearance per side is worse than `−(FOOT_WIDTH_LO / 2)` = −0.55". This means the shoe actively compresses the toe.

2. **LENGTH_OUT_OF_RANGE** — the foot's length range `[foot_adj − 0.55", foot_adj + 0.55"]` and the shoe's length range `[insole_length − 0.79", insole_length + 0.00"]` do not overlap. Derived: a shoe is rejected if `insole_length < foot_adj − 0.55"` (shoe too short) or `insole_length > foot_adj + 0.55" + 0.79" = foot_adj + 1.34"` (shoe too long). The `0.79"` upper bound on shoe tolerance comes from the maximum length clearance across all profiles (`SHOE_LENGTH_LO` constant).

3. **WIDTH_OUT_OF_RANGE** — the foot's width range `[foot_adj ± 1.10"]` and the shoe's width range `[insole_width − 0.92", insole_width + 1.25"]` do not overlap. The width window is intentionally wide (residual CV noise is 0.77" StdDev); hard rejects are reserved for clear mismatches only.

---

## Stage 6 — Scoring

### Clearance computation

```
c_length = insole_length_eff − foot_length_corrected
c_width  = (insole_width_eff − foot_width_corrected) / 2   # per side
c_tb_len = insole_toebox_length_eff − foot_toebox_length    # if available
c_tb_wid = (insole_toebox_width_eff − foot_toebox_width) / 2
```

### Dimension scoring (`_score_dimension`)

Each clearance `c` is scored against its tolerance band for `P` maximum points:

| Zone | Clearance range | Points |
|------|----------------|--------|
| Too tight | `c < min` | 0 |
| Tight | `min ≤ c < opt_low` | Linear from 0 → P |
| **Optimal** | `opt_low ≤ c ≤ opt_high` | **P (full)** |
| Loose | `opt_high < c ≤ max` | `P × (0.70 + 0.30 × (max − c) / (max − opt_high))` — floor at 0.70P |
| Excessive | `c > max` | `max(0, P × 0.70 − P × 0.70 × (c − max) / ((max − opt_high) × 4))` — linear decay to 0 |

The 0.70 floor in the loose/excessive zones reflects that a slightly roomy shoe is still wearable, and guards against CV measurement noise making a good shoe appear too loose.

### Point budgets

Points are allocated differently depending on what data is available:

**Full toebox data (4 dimensions):**

| Profile | length | width | tb_len | tb_width |
|---------|--------|-------|--------|----------|
| Default | 20 | 30 | 20 | 30 |
| SKATE | 17 | 33 | 17 | 33 |
| CASUAL_SLIPON | 18 | 32 | 18 | 32 |

**No toebox, area available (3 dimensions):**

| Profile | length | width | area |
|---------|--------|-------|------|
| Default | 35 | 40 | 25 |
| SKATE | 30 | 45 | 25 |
| CASUAL_SLIPON | 30 | 45 | 25 |

**No toebox, no area (2 dimensions):**

| Profile | length | width |
|---------|--------|-------|
| Default | 50 | 50 |
| SKATE | 40 | 60 |
| CASUAL_SLIPON | 42 | 58 |

Width is always weighted the same or higher than length. Skate and slip-on profiles weight width more heavily because lateral fit is especially critical in those shoe types.

**Area scoring** (fallback when toebox is unavailable): the ratio `insole_area / foot_area` is scored against a fixed band — optimal range is 1.10–1.35 (insole 10–35% larger than foot). This range is a heuristic based on standard footwear fit guidelines: a well-fitting insole should have some room beyond the foot silhouette. The wide acceptable band (0.90–2.00) reflects high CV area noise.

---

## Stage 7 — Status Thresholds

| Score | Status |
|-------|--------|
| ≥ 90 | `PERFECT` |
| ≥ 75 | `GOOD` |
| ≥ 60 | `ACCEPTABLE` |
| ≥ 40 | `MARGINAL` |
| < 40 | `POOR` |
| — | `REJECTED` |
| — | `UNSCORED` (shoe lacks insole dimensions in DB) |

---

## Stage 8 — US Size Estimation

US size is estimated from corrected foot length using the **Brannock formula**:

```
Men's / unisex:  size = foot_length_in × 3.0 − 22.0
Women's:         size = foot_length_in × 3.0 − 20.5   (1.5 sizes larger)
```

The result is rounded to the nearest half size. This is used to find the closest available size from the shoe's `ShoeSize` records.

---

## Recommendations Endpoint

**Endpoint:** `GET /api/recommendations/`
**Query param:** `sub_type` (optional) — valid values: `half_marathon`, `marathon`, `thick_socks`, `pack_over_55lbs`, `olympic_lifting`, `hiit`, `football_lineman`, `clay_court`, `comfort_mode`. Unrecognized values are silently ignored. See Stage 4d for per-value behavior.

1. Loads the user's most recent `COMPLETE` measurement.
2. Iterates every `Shoe` in the database.
3. Calls `score_shoe()` for shoes that have `insole_length_in` and `insole_width_in`; marks others `UNSCORED`.
4. Finds the closest available size to `estimated_us_size` by minimizing `|available_size − estimated_size|`.
5. Sorts results: **scored (non-rejected) → UNSCORED → REJECTED**, with scored shoes ordered by descending score.
6. Returns the full ranked list with per-shoe fit details, zone breakdowns per dimension, flags, and recommended size.

---

## Output Object (per shoe)

The two boolean flags are **mutually exclusive in scoring**, though both can be `false`:

| `has_toebox_data` | `has_area_data` | Scoring path |
|---|---|---|
| `true` | `false` | 4-dimension scoring (length + width + tb_len + tb_width); area is not used |
| `false` | `true` | 3-dimension scoring (length + width + area ratio) |
| `false` | `false` | 2-dimension scoring (length + width only) |

When `has_toebox_data` is `true`, area is never scored — the `dimensions` object will contain `toebox_length` and `toebox_width` entries but no `overall_area` entry, and `has_area_data` will always be `false`.

**Example — full toebox data available:**

```json
{
  "status": "GOOD",
  "total_score": 83.5,
  "reject_reason": null,
  "profile_used": "ROAD_RUNNING",
  "sub_type": "half_marathon",
  "adjustments_applied": [],
  "has_toebox_data": true,
  "has_area_data": false,
  "estimated_us_size": 11.0,
  "flags": [],
  "dimensions": {
    "foot_length":   { "clearance": 0.52, "zone": "optimal", "points_earned": 20.0, "points_max": 20 },
    "foot_width":    { "clearance_per_side": 0.14, "zone": "optimal", "points_earned": 30.0, "points_max": 30 },
    "toebox_length": { "clearance": 0.50, "zone": "optimal", "points_earned": 20.0, "points_max": 20 },
    "toebox_width":  { "clearance_per_side": 0.10, "zone": "tight", "points_earned": 13.5, "points_max": 30 }
  }
}
```

**Example — no toebox, area available:**

```json
{
  "status": "ACCEPTABLE",
  "total_score": 68.0,
  "reject_reason": null,
  "profile_used": "CASUAL",
  "sub_type": null,
  "adjustments_applied": [],
  "has_toebox_data": false,
  "has_area_data": true,
  "estimated_us_size": 10.5,
  "flags": [],
  "dimensions": {
    "foot_length":  { "clearance": 0.41, "zone": "optimal", "points_earned": 35.0, "points_max": 35 },
    "foot_width":   { "clearance_per_side": 0.05, "zone": "tight", "points_earned": 21.0, "points_max": 40 },
    "overall_area": { "foot_area": 28.1, "shoe_area": 33.5, "ratio": 1.19, "zone": "optimal", "points_earned": 12.0, "points_max": 25 }
  }
}
```

---

## Known Limitations

- **Bias calibration** is based on 24 captures of a single foot. Generalisability across foot shapes and camera conditions is unproven at scale.
- **Width CV noise** is high (±0.77" residual StdDev after correction). The wide reject window and 0.70 score floor compensate, but marginal-width shoes may still be mis-ranked.
- **Toebox CV data** is less reliable than overall foot dimensions; the algorithm does not use toebox length as a hard reject for this reason.
- **No personalization beyond fit geometry** — user preferences (brand, cushioning, price) are not factored into the score.
- **All shoes scored on every request** — no caching. With a large catalogue this will become a performance concern.
