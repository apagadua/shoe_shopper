# Computer Vision & Fit Algorithm — Shoe Shopper

How the app measures a foot from a photo and scores shoes against those measurements.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Measurement Pipeline (Roboflow)](#2-measurement-pipeline-roboflow)
3. [Fit Algorithm](#3-fit-algorithm)
4. [Tolerance Profiles](#4-tolerance-profiles)
5. [Scoring Math](#5-scoring-math)
6. [Size Estimation (Brannock)](#6-size-estimation-brannock)
7. [Algorithm Output Reference](#7-algorithm-output-reference)
8. [Debugging the Pipeline](#8-debugging-the-pipeline)

---

## 1. Overview

```
Photo
  │
  ▼
Roboflow inference API
  │  detects: paper bounding box, foot polygon, (optional) toe box polygon
  ▼
Django view (FootMeasureView)
  │  computes PPI from paper → converts pixels → inches
  │  extracts: length, width, area, toebox dimensions
  ▼
Measurement record (DB)
  │
  ▼
Fit algorithm (fit_algorithm.py)
  │  applies CV bias corrections
  │  selects tolerance profile from shoe's function_tags
  │  scores 0–100 across 2–4 dimensions
  │  checks hard-reject conditions
  ▼
Recommendation results
```

---

## 2. Measurement Pipeline (Roboflow)

**File:** `backend/api/views.py` → `FootMeasureView`

### Setup

The `foot-measuring` workflow lives in the `armaanai` Roboflow workspace. It must be published before inference calls will succeed. Check the workspace dashboard if you get unexpected 400 errors from the backend.

### Request to Roboflow

The view encodes the uploaded image as base64 and POSTs it to the Roboflow Workflows API:

```
POST https://detect.roboflow.com/{workspace}/workflows/{project}
Body: { "api_key": "<ROBOFLOW_API_KEY>", "inputs": { "image": { "type": "base64", "value": "<encoded>" } } }
Headers: { "Content-Type": "application/json" }
```

### Parsing the Response

Roboflow returns a JSON object with an `outputs` array. The view iterates through outputs looking for predictions that include the following `class` values:

| Class | What it represents |
|---|---|
| `paper` | The reference sheet of paper — provides the pixel scale |
| `foot` or `insole` | The outline of the foot |
| `toe box` | The front section of the foot (optional, improves toebox scoring) |

### Computing Pixels-Per-Inch (PPI)

The paper bounding box is the scale reference. Known paper dimensions:

| Paper size | Width × Height |
|---|---|
| Letter | 8.5" × 11.0" |
| A4 | 8.27" × 11.69" |

The view checks the aspect ratio of the bounding box to determine orientation (portrait vs. landscape), then computes PPI from whichever side is more reliably measured.

### Extracting Foot Dimensions

The foot prediction is a **polygon** (list of `(x, y)` points). The view derives:

| Dimension | Method |
|---|---|
| **Length** | Maximum Euclidean distance between any two polygon vertices, divided by PPI |
| **Width** | 95th-percentile perpendicular span (perpendicular to the length axis), divided by PPI |
| **Area** | Shoelace formula applied to the polygon points, divided by PPI² |
| **Perimeter** | Field exists in the `Measurement` model but is not currently computed or saved |

If a `toe box` polygon is also detected, `toebox_length_in` and `toebox_width_in` are extracted the same way.

### Saved to Database

A `Measurement` record is created with `status=complete` and all computed dimensions. The image itself is not stored (see `SECURITY_REVIEW.md` M5).

### Training the Model

The model was trained to recognize foot, toebox, paper, wall base, and insole. 

Annotation was done manually using bounded boxes to highlight the objects mentioned above. The model was then trained using Roboflow's RF-DETR. In general, larger model sizes yielded better metrics.

---

## 3. Fit Algorithm

**File:** `backend/services/fit_algorithm.py` — Version 1.5

### Core Concept

A shoe starts at **100 points**. Points are deducted when foot-to-shoe clearances fall outside optimal ranges. Three hard-reject conditions can override scoring entirely and mark a shoe as `REJECTED`.

### CV Bias Corrections

Raw Roboflow measurements have systematic errors (the model tends to underestimate length and overestimate width). These corrections are applied before scoring:

```
corrected_length = raw_length + 0.508"   (model underestimates foot length)
corrected_width  = raw_width  − 0.371"   (model overestimates foot width)
```

These constants are calibrated from ground-truth measurements and may be updated as the training dataset grows.

### Hard-Reject Conditions

Before scoring, three conditions can immediately reject a shoe (checked in this order):

1. **`TOEBOX_WIDTH_COMPRESSION`** — The toebox would compress the foot.
   - Triggered if per-side toebox compression > `FOOT_WIDTH_LO / 2` (i.e., > 0.55")

2. **`LENGTH_OUT_OF_RANGE`** — The foot length range and shoe length range do not overlap.
   - Foot range: `[corrected_length − 0.55", corrected_length + 0.55"]`
   - Shoe range: `[insole_length − 0.79", insole_length]`

3. **`WIDTH_OUT_OF_RANGE`** — The foot width range and shoe width range do not overlap.
   - Foot range: `[corrected_width − 1.10", corrected_width + 1.10"]`
   - Shoe range: `[insole_width − 0.92", insole_width + 1.25"]`

If any of these fire, the shoe gets `status=REJECTED` with a `reject_reason` string and a score of 0.

### Pre-Scoring Adjustments

Before computing clearances, the algorithm applies modifiers to account for shoe design:

| Adjustment | Trigger | Effect |
|---|---|---|
| **Fashion allowance** | DRESS profile | Reduces tolerable length/width clearance based on toe shape (pointed shoes sacrifice more fit) |
| **Cap wall deduction** | WORK profile + `safety_toe` attribute | Subtracts internal cap wall from usable toebox width |
| **Silhouette modifiers** | e.g. combat boots | Raises minimum length clearance |
| **Sub-type modifiers** | e.g. `marathon`, `clay_court` | Shifts optimal clearance ranges for the activity |

### Clearances

After adjustments, the algorithm computes clearance for each dimension:

```
length_clearance    = insole_length − corrected_length
width_clearance     = (insole_width − corrected_width) / 2     (per side)
toebox_len_clearance = toebox_length − corrected_toebox_length
toebox_wid_clearance = (toebox_width − corrected_toebox_width) / 2
```

Positive clearance = room to spare. Negative clearance = compression.

---

## 4. Tolerance Profiles

Each shoe is assigned a tolerance profile based on its `function_tags`. The profile defines the optimal clearance ranges for each dimension.

| Profile | Required `function_tags` (all must be present, case-insensitive) | Notes |
|---|---|---|
| `ROAD_RUNNING` | `Athletic` + `Running` + `Road` (or just `Athletic` + `Running` as fallback) | Moderate length, snug width |
| `TRAIL_RUNNING` | `Athletic` + `Running` + `Trail` | More width tolerance |
| `INDOOR_TRACK` | `Athletic` + `Running` + `Indoor` | Very snug all around |
| `TRAINING` | `Athletic` + `Training` | Balanced |
| `BASKETBALL` | `Athletic` + `Basketball` | Extra length clearance |
| `CLEATED_SPORT` | `Athletic` + one of: `Field Sports`, `Soccer`, `Football`, `Lacrosse` | Sport-specific snug fit |
| `TENNIS` | `Athletic` + `Tennis` | Lateral stability focus |
| `SKATE` | `Athletic` + `Skate` | Wide toebox preferred |
| `HIKING` | `Athletic` + `Hiking` | Extra length and width |
| `CASUAL` | `Casual` (without `Slip-ons`) | Most forgiving |
| `CASUAL_SLIPON` | `Casual` + `Slip-ons` | Width-dominant |
| `WORK_INDOOR` | `Work` + `Indoor` | Comfort-focused |
| `WORK_OUTDOOR` | `Work` + `Outdoor` | Similar to hiking |
| `DRESS` | `Formal` | Fashion allowance applied |

Routes are checked most-specific-first in `_TAG_ROUTES` (e.g. `Athletic + Running + Road` is checked before `Athletic + Running`). If none of the shoe's tags match any route, `CASUAL` is used as the fallback.

---

## 5. Scoring Math

### Point Budgets

The budget varies based on which dimensions are available:

| Available data | Length | Width | Toebox length | Toebox width | Area | Total |
|---|---|---|---|---|---|---|
| Full toebox data | 20 | 30 | 20 | 30 | — | 100 |
| No toebox, with area | 35 | 40 | — | — | 25 | 100 |
| Length + width only | 50 | 50 | — | — | — | 100 |

SKATE and CASUAL_SLIPON have slightly different distributions that weight width more heavily.

### Dimension Scoring

Each dimension is scored independently using `_score_dimension(clearance, tolerance_band, max_points)`:

The clearance range is divided into zones:

```
      compression   tight    │   optimal   │   loose         excessive
      ─────────────────────────────────────────────────────────────────►
                      lo   target  hi             loose_hi
```

| Zone | Points earned | Notes |
|---|---|---|
| Optimal (lo → hi) | Full `max_points` | Perfect clearance |
| Tight (below lo) | Linear decrease toward 0 | Foot feeling snug |
| Compression (negative) | 0 | Foot is compressed |
| Loose (hi → loose_hi) | `0.70–1.0 × max_points` (linear) | Floor at 0.70 × max at the boundary; extra room |
| Excessive (above loose_hi) | Decays from `0.70 × max_points` toward 0 | Starts at 0.70 × max, linearly decays to 0 over 4× the loose band width |

### Status Thresholds

| Score | Status |
|---|---|
| ≥ 90 | `PERFECT` |
| ≥ 75 | `GOOD` |
| ≥ 60 | `ACCEPTABLE` |
| ≥ 40 | `MARGINAL` |
| < 40 | `POOR` |
| N/A | `REJECTED` (hard reject) |
| N/A | `UNSCORED` (shoe missing insole data) |

---

## 6. Size Estimation (Brannock)

The algorithm estimates US shoe size using the standard Brannock formula:

```
Men / unisex:   size = (3 × foot_length_in) − 22.0
Women:          size = (3 × foot_length_in) − 20.5
```

The result is rounded to the nearest 0.5.

The same formula is implemented in the frontend (`frontend/utils/shoeSize.js`) for display on the MeasurementsScreen, and in the backend fit algorithm for matching to available `ShoeSize` records.

After estimating the ideal size, `RecommendationsView` finds the closest **available** `ShoeSize` (where `is_available=True`) and returns it as `recommended_size`.

---

## 7. Algorithm Output Reference

`score_shoe()` returns a dict:

```python
{
    "status": "PERFECT",              # or GOOD, ACCEPTABLE, MARGINAL, POOR, REJECTED, UNSCORED
    "total_score": 87.4,              # 0–100
    "reject_reason": None,            # "LENGTH_OUT_OF_RANGE" etc. if REJECTED
    "profile_used": "ROAD_RUNNING",   # tolerance profile that was applied
    "sub_type": "marathon",           # if sub_type param was passed
    "adjustments_applied": [          # list of modifier strings
        "fashion_deduction: pointed 0.99"
    ],
    "has_toebox_data": True,
    "has_area_data": False,
    "estimated_us_size": 10.5,
    "dimensions": {
        "foot_length": {
            "clearance": 0.32,        # inches: insole − foot
            "zone": "optimal",
            "points_earned": 20.0,
            "points_max": 20
        },
        "foot_width": { ... },
        "toebox_length": { ... },
        "toebox_width": { ... }
    },
    "flags": [                        # descriptive flags for UI display
        "SPORT_TIGHT_FIT",
        "TOEBOX_DATA_USED"
    ]
}
```

The `RecommendationSerializer` in `backend/api/serializers.py` flattens this into the API response.

---

## 8. Debugging the Pipeline

### Roboflow doesn't detect the paper

**Symptom:** `POST /api/foot/measure/` returns 400 with a message about missing paper detection.

**Check:**
- Is the `foot-measuring` workflow published in the `armaanai` Roboflow workspace?
- Is the paper fully in frame and well-lit?
- Is the phone held level (tilt sensor shows ≤10°)?
- Is the ambient light sufficient (light sensor shows ≥50 lux)?

**Debugging:** Add temporary logging in `FootMeasureView` immediately after `rf_resp.json()` to print the raw Roboflow response:

```python
rf_data = rf_resp.json()
print("Roboflow raw response:", rf_data)   # remove before committing
```

### Measurements seem too large or too small

The CV bias corrections (`+0.508"` length, `−0.371"` width) may need recalibration if you switch to a different Roboflow model version. To recalibrate:
1. Measure several feet with a physical tape measure
2. Capture photos through the app for the same feet
3. Compare raw Roboflow output to ground truth
4. Update the constants at the top of `fit_algorithm.py`

### All shoes are REJECTED

If every shoe comes back as REJECTED, the foot measurements are probably outside the expected range (very large or very small values). Possible causes:
- PPI computation failed (paper wasn't detected correctly, so the scale is wrong)
- A measurement unit mismatch (e.g., values in cm instead of inches)
- CV bias corrections producing negative corrected_width

Log the `foot_data` dict inside `RecommendationsView` to inspect what the algorithm receives.

### `UNSCORED` shoes

Shoes are `UNSCORED` when they lack `insole_length` or `insole_width` in the database. This is a data quality issue — populate those fields for any shoe that should participate in fit scoring.
