# KicksDB Integration — V2 Plan

Supersedes `KICKSDB_INTEGRATION.md`.

This document captures the full design for the second-generation KicksDB integration before any code is written. Read it top to bottom before touching any files.

---

## Goals

1. **Multi-colorway support** — show every available colorway of a shoe in the user's specific measured size, each with its own image, price, and buy link.
2. **Per-size pricing accuracy** — prices are shown for the user's recommended size, not a floor price across all sizes.
3. **Availability accuracy** — a colorway only appears if the measured size is actually listed for sale.
4. **Stale/unavailable shoe hygiene** — shoes that GOAT can't match are hidden from users without losing their curated insole data.
5. **GOAT only** — StockX is dropped. GOAT provides per-variant pricing; StockX does not. Per-size price accuracy requires GOAT.

---

## Current State and Its Problems

### Data model (today)
```
Shoe (one row = one colorway)
  brand, model, colorway, sku, kicks_id
  shoe_image_url, product_url, price_usd   ← single values, colorway-level
  last_synced_at, is_active (not yet added)
  └── ShoeSize
        us_size, width, is_available        ← availability synced from KicksDB
        insole_length_in, insole_width_in, ... ← curated measurement data
```

### Problems
- One `Shoe` row = one colorway. A model like Air Max 1 requires dozens of rows to represent all colorways, making the catalog hard to manage and the recommendation list redundant (same shoe, 30 times).
- `price_usd` is a floor price across all sizes. A user who wears size 13 sees a $120 price that only applies to size 7.5.
- `ShoeSize.is_available` is synced from KicksDB for all returned variants regardless of whether we have insole data for that size. This creates `ShoeSize` rows with no insole data, which can surface as a `recommended_size` that the fit algorithm can't actually score.
- StockX provides no per-variant pricing, making per-size prices impossible on that source.
- No `is_active` flag. Shoes with no live marketplace listing are served identically to shoes with one.

---

## New Data Model

### Relationship overview
```
Shoe  (one row = one shoe MODEL, e.g. "Nike Air Max 1 Men's")
  brand, model, gender, function_tags, style_tags, attributes_json
  toe_shape, cap_type, arch_type
  is_active                               ← NEW: False if GOAT finds no colorways
  last_synced_at                          ← updated each sync run
  [colorway, sku, kicks_id, shoe_image_url, product_url, price_usd kept but no longer written by sync]
  └── ShoeSize  (one row per size we have insole measurements for)
        us_size, width
        insole_length_in, insole_width_in, insole_area_sq_in
        insole_toebox_length_in, insole_toebox_width_in
        is_available                      ← no longer KicksDB-driven; semantics change (see below)
  └── ShoeColorway  (NEW — one row per GOAT product/colorway)
        goat_id (unique)                  ← GOAT's product UUID, our sync key
        sku                               ← manufacturer SKU
        name                             ← colorway display name, e.g. "Bred Toe"
        image_url
        product_url
        last_synced_at
        └── ShoeColorwaySize  (NEW — one row per size within a colorway)
              us_size
              price_usd                   ← GOAT lowest_ask for this size
              is_available                ← True if lowest_ask is present
              unique on (colorway, us_size)
```

### What `ShoeSize.is_available` now means

The KicksDB sync **stops writing** to `ShoeSize.is_available`. Its meaning shifts:

- `True` = we have measured this size (insole data present and usable)
- `False` = size exists in our DB but is incomplete/disabled

In practice, any `ShoeSize` with `insole_length_in IS NOT NULL` is the meaningful filter. `ShoeSize.is_available` may be repurposed or removed in a future cleanup migration; for now it is left unchanged and not written by the new sync.

### What the old `Shoe` colorway fields become

`Shoe.colorway`, `Shoe.sku`, `Shoe.kicks_id`, `Shoe.shoe_image_url`, `Shoe.product_url`, `Shoe.price_usd` are **kept in the schema but are no longer written by the sync command**. They remain as curated fallback data from the V1 integration or manual entry. They are not surfaced to the frontend once the new serializer is in place.

---

## New Models — Full Field Spec

### `ShoeColorway`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | |
| `shoe` | FK → Shoe, CASCADE | |
| `goat_id` | TextField, unique | GOAT's product UUID — sync key |
| `sku` | TextField, null/blank | Manufacturer SKU |
| `name` | TextField | Colorway display name |
| `image_url` | TextField, null/blank | |
| `product_url` | TextField, null/blank | |
| `last_synced_at` | DateTimeField, null/blank | Set on every successful sync |
| `created_at` | DateTimeField, auto | |

`db_table = "shoe_colorway"`
Index on `shoe` + `goat_id`.

### `ShoeColorwaySize`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | |
| `colorway` | FK → ShoeColorway, CASCADE | |
| `us_size` | DecimalField(4,1) | |
| `price_usd` | DecimalField(10,2), null/blank | GOAT `lowest_ask` |
| `is_available` | BooleanField, default False | True if `lowest_ask` present |
| `created_at` | DateTimeField, auto | |

`db_table = "shoe_colorway_size"`
UniqueConstraint on `(colorway, us_size)`.
Index on `(colorway, us_size, is_available)`.

---

## Migration Plan

Two new migrations needed (after the existing `0005`):

**`0006_shoe_is_active.py`**
- Add `Shoe.is_active = BooleanField(default=True)` — existing shoes default to active until next sync.

**`0007_shoe_colorway_models.py`**
- Create `ShoeColorway` table.
- Create `ShoeColorwaySize` table with FK to `ShoeColorway`.

Order matters: `0006` before `0007` (though they could be one migration — keeping them separate for clarity).

No existing data is deleted or modified by either migration.

---

## Seed Command Redesign

**File:** `backend/management/commands/seed_kicks.py` (full rewrite)

### High-level flow

```
run_started = timezone.now()

For each Shoe in DB:
  1. Get insole-measured sizes for this shoe (ShoeSize rows with insole_length_in NOT NULL)
     If none → skip entirely (no point syncing a shoe we can't score)

  2. SEARCH: GET /v3/goat/products?query={brand}+{model}&limit=100
     - If RequestException → log, skip (do NOT touch is_active)
     - If empty data → mark Shoe.is_active=False, continue
     - Follow pagination: if meta.total > limit, fetch additional pages (cap at ~300
       results total = 3 pages — anything beyond is noise for our catalog)
     - Filter to brand-matching products: case-insensitive substring of `brand` field

  3. colorway_touched = 0
     For each search result:
       a. DETAIL: GET /v3/goat/products/{slug}
          - If RequestException → log, skip this colorway
          - time.sleep(0.1)

       b. update_or_create ShoeColorway on goat_id=str(product["id"])
          defaults: {
            shoe, sku, name, image_url, product_url,
            last_synced_at: timezone.now(),
          }
          - name = product["nickname"] or product["colorway"] or product["name"]

       c. For each variant in product["variants"]:
            - Skip if variant["market"] != "US" or variant["currency"] != "USD"
            - Parse us_size = float(variant["size"])  (skip if non-numeric, <1.0, >20.0)
            - Skip if us_size not in insole_measured_sizes
            - update_or_create ShoeColorwaySize on (colorway, us_size):
                price_usd    = variant["lowest_ask"] or None
                is_available = bool(variant["available"])

       d. For insole-measured sizes NOT in the variants list:
            ShoeColorwaySize.objects.update_or_create(
                colorway=this_colorway, us_size=missing_size,
                defaults={"is_available": False, "price_usd": None},
            )

       colorway_touched += 1

  4. STALE CLEANUP (Option A):
     Any ShoeColorway for this shoe with last_synced_at < run_started
     → mark all its ShoeColorwaySize rows is_available=False.
     (The ShoeColorway row itself stays; it can be revived by a later sync.)

  5. Shoe.is_active = (colorway_touched > 0)
     Shoe.last_synced_at = timezone.now()
     Shoe.save()

  6. time.sleep(0.1)   (between shoes)
```

### Key decisions

**Pagination** — `limit=100` (API max). If `meta.total > 100`, loop fetching `page=2, 3, ...`. Cap at 3 pages (300 products) per shoe to bound worst-case request volume. Broad queries can return `total=1000`, but beyond the first few hundred results is almost always noise/unrelated colorways.

**Two-step fetch** — search returns empty `variants`; per-colorway detail fetches are required. This is the dominant cost of the sync.

**Brand matching** — same substring logic as V1, applied to the search response's `brand` field before queuing a detail fetch. Avoids wasting detail requests on obviously-wrong matches.

**Colorway display name preference** — `ShoeColorway.name = nickname or colorway or name`. Nickname ("Triple White") is shortest and most marketing-clean; `colorway` ("White/White/White") is the fallback; `name` ("Nike Air Force 1 'Triple White'") is the last resort.

**`variant["available"]` is authoritative** — do not infer from `lowest_ask`. GOAT can return `available=false` with `lowest_ask=0` when delisted.

**Market/currency filter** — only `market="US"` + `currency="USD"` variants are processed. A single product can return variants for multiple markets; we want one consistent US-dollar price.

**Always overwrite colorway fields** — `ShoeColorway.sku`, `name`, `image_url`, `product_url`, `last_synced_at` are always overwritten. These are live marketplace data.

**`ShoeColorwaySize` scope** — only sizes matching an insole-measured `ShoeSize` row are considered. Never create rows for sizes we cannot score.

**`is_active` semantics** — True iff the search returned at least one brand-matching product AND at least one detail fetch succeeded. An empty search result OR all-detail-fetch-failures both produce `is_active=False`. API error during search (`RequestException`) leaves `is_active` untouched (temporary outage should not hide shoes).

**`--dry-run` flag** — preserved from V1.

### GOAT API field mapping

| Our field | GOAT response field |
|---|---|
| `ShoeColorway.goat_id` | `str(product["id"])` |
| `ShoeColorway.sku` | `product["sku"]` (e.g. `"306353 462"`) |
| `ShoeColorway.name` | `product["nickname"] or product["colorway"] or product["name"]` |
| `ShoeColorway.image_url` | `product["image_url"]` |
| `ShoeColorway.product_url` | `product["link"]` |
| `ShoeColorwaySize.us_size` | `float(variant["size"])` |
| `ShoeColorwaySize.price_usd` | `variant["lowest_ask"]` (nullable if 0) |
| `ShoeColorwaySize.is_available` | `bool(variant["available"])` |

---

## Backend API Changes

### `GET /api/recommendations/` — `views.py`

**Shoe queryset** — add `is_active=True` filter:
```python
shoes = Shoe.objects.prefetch_related("sizes", "colorways__sizes").filter(is_active=True)
```

**`recommended_size` computation** — currently uses `ShoeSize.is_available`. Change to: a size is available for recommendation if at least one `ShoeColorwaySize` for that `us_size` has `is_available=True`:

```python
# Sizes available in at least one colorway
available_us_sizes = set(
    ShoeColorwaySize.objects.filter(
        colorway__shoe=shoe,
        is_available=True,
    ).values_list("us_size", flat=True)
)
available_sizes = [s for s in all_sizes if float(s.us_size) in available_us_sizes]
```

**`colorway_options` construction** — after `recommended_size` is resolved, build the list:
```python
colorway_options = list(
    ShoeColorwaySize.objects.filter(
        colorway__shoe=shoe,
        us_size=recommended_size,
        is_available=True,
    )
    .select_related("colorway")
    .order_by("price_usd")          # cheapest first
    .values(
        name=F("colorway__name"),
        image_url=F("colorway__image_url"),
        product_url=F("colorway__product_url"),
        price_usd=F("price_usd"),
    )
)
```

Pass `colorway_options` into the result dict alongside `shoe`, `fit`, `recommended_size`.

**`can_score` logic** — unchanged. Still gates on `scoring_size.insole_length_in` and `insole_width_in`. Scoring does not touch colorway data.

### `GET /api/shoes/` — `views.py`

Add `filter(is_active=True)`:
```python
shoes = Shoe.objects.prefetch_related("sizes").filter(is_active=True).order_by("brand", "model")
```

### `GET /api/health/` — `views.py`

`Shoe.objects.count()` unchanged — total catalog count, including inactive, is fine for diagnostics.

### `serializers.py` — `RecommendationSerializer`

**Remove** these fields (no longer sourced from `Shoe` directly):
- `shoe_image_url`
- `product_url`
- `colorway`
- `price_usd`

**Add:**
```python
colorway_options     = serializers.SerializerMethodField()
recommended_size     = serializers.SerializerMethodField()  # already exists

def get_colorway_options(self, obj):  return obj.get("colorway_options", [])
```

Each item in `colorway_options` is a dict: `{ name, image_url, product_url, price_usd }`.

`recommended_size` and `estimated_us_size` remain unchanged.

**`ShoeSerializer`** (used by `GET /api/shoes/`) — leave as-is for now. The shoe list endpoint is a utility/debug endpoint, not user-facing in the app.

---

## Frontend Changes

### Overview

The card currently renders a single image, a single colorway label, a single price, and a single "View details" button — all driven by flat fields on the recommendation item. With the new response shape, these come from `colorway_options[selectedIndex]`.

### `ShoeCard` component (extracted from `RecommendationsScreen.js`)

Extract the card JSX into a standalone `ShoeCard` component. This is required because each card needs its own `selectedIndex` state — keeping that in the parent would require a `{ [id]: index }` map that complicates the parent.

**Props:** `item`, `isSaved`, `toggleSaved`, `onToast`, `path`

**Internal state:**
```javascript
const [selectedIndex, setSelectedIndex] = useState(0); // 0 = cheapest (backend-sorted)

const options = item.colorway_options ?? [];
const selected = options[selectedIndex] ?? null;
```

**Derived display values:**
```javascript
const mainImage  = selected?.image_url   ?? null;
const buyUrl     = selected?.product_url ?? null;
const price      = selected?.price_usd   ?? null;
const colorName  = selected?.name        ?? null;
```

### Card layout (updated)

```
┌─────────────────────────────────────┐
│ BRAND NAME                    ♡     │  ← unchanged
│ Model Name                          │  ← unchanged
│ [Fit badge]  Profile label          │  ← unchanged
│                                     │
│ ┌─────────────────────────────────┐ │
│ │         Main image              │ │  ← driven by selected colorway
│ └─────────────────────────────────┘ │
│                                     │
│ ── Colorway strip ──────────────── │
│ [chip][chip][chip][chip] →          │  ← horizontal ScrollView
│                                     │
│ Size 10  ·  $165                    │  ← recommended_size + selected price
│                                     │
│ [     View on GOAT     ]            │  ← selected product_url
│                                     │
│ [tag][tag][tag]                     │  ← attribute tags, unchanged
└─────────────────────────────────────┘
```

### Colorway chip design

Each chip in the horizontal strip:

```
┌──────────────────┐
│  [48×48 thumb]   │
│  Bred Toe        │  ← truncated to 1 line, fontSize 11
│  $165            │  ← bold, fontSize 12
└──────────────────┘
```

- Width: ~72px, so 5–6 chips visible before scrolling
- Active chip: 2px border `#C28A5B`
- Inactive chip: 1px border `#E2D4C0`
- If `image_url` is null: show a `#F0E2D0` block in place of thumbnail

### Graceful degradation

| `colorway_options` state | Card behavior |
|---|---|
| Non-empty array | Full strip + image + price + buy button |
| Empty array `[]` | Placeholder image, no strip, no buy button, no price |
| Single item | Strip renders with one chip (no scroll); functionally equivalent |
| Selected item has no `image_url` | Placeholder image block |
| Selected item has no `product_url` | Buy button hidden |

### `RecommendationsScreen.js` changes

- Import and render `ShoeCard` instead of inline card JSX
- Remove references to `item.shoe_image_url`, `item.product_url`, `item.colorway`, `item.price_usd`
- No changes to filtering logic, drawer, toast, or loading/error states

---

## What Is NOT Changing

- Fit algorithm (`backend/services/fit_algorithm.py`) — untouched
- `ShoeSize` insole fields — untouched; these are the curated measurement data
- `Measurement` model and `FootMeasureView` — untouched
- Auth flow — untouched
- `UserCollection` — untouched
- Filtering logic in `RecommendationsScreen` (function/silhouette/attribute filters) — untouched
- `SavedShoesContext` — currently saves the shoe object; may need updating if it references removed fields, but deferred

---

## Implementation Order

Do not begin any step until the previous step is complete and verified.

1. **`0006_shoe_is_active.py`** — add `Shoe.is_active` field + migrate
2. **`0007_shoe_colorway_models.py`** — create `ShoeColorway` and `ShoeColorwaySize` + migrate
3. **`backend/models/__init__.py`** — define both new models, add `is_active` to `Shoe`
4. **`backend/management/commands/seed_kicks.py`** — full rewrite (GOAT-only, all colorways, insole-gated size sync, `is_active` logic)
5. **`backend/api/views.py`** — `is_active` filter, `available_us_sizes` from `ShoeColorwaySize`, `colorway_options` construction
6. **`backend/api/serializers.py`** — add `colorway_options`, remove old single-colorway fields
7. **`frontend/screens/RecommendationsScreen.js`** — extract `ShoeCard`, add colorway strip

Run `seed_kicks --dry-run` after step 4 to verify the command before writing to DB.
Verify API response shape manually (curl or Postman) after step 6 before touching frontend.

---

## Research Findings (Verified Against Live API)

All findings below were verified by direct test calls to `https://api.kicks.dev/v3/goat/*` on 2026-04-15.

### Pagination — resolved

- **Parameter is `limit`, not `per_page`**. Passing `per_page` silently returns the default 20 items.
- **Max `limit` is `100`**. `limit=200` returns HTTP 422.
- **Page parameter is `page`** (1-indexed).
- **Response meta shape**: `{ "current_page": N, "per_page": N, "total": N }` — no `has_more` field; compute from `(current_page * per_page) < total`.
- **`total` appears capped at 1000** for broad queries (e.g. `query="Nike Air Force 1"` returned `total: 1000`). Narrow queries return exact counts. This is fine for our usage since we query by specific model names.

### Two-step API flow — critical finding

The search endpoint **does not populate the `variants` array**. Search returns lightweight product metadata only.

To get per-size pricing/availability, we must fetch each product individually:

```
Step 1: GET /v3/goat/products?query={brand} {model}&limit=100   → list of colorways, variants=[]
Step 2: For each product, GET /v3/goat/products/{slug}          → single product with variants populated
```

This means the request volume per shoe is `1 + N` where N is the colorway count, not just `1`. A 50-shoe catalog with ~15 colorways/shoe = ~800 requests per sync.

Rate limit is 640 req/min. With `time.sleep(0.1)` between calls, a 800-request sync takes ~80 seconds. KicksDB Starter tier (€29/mo, 50k req) comfortably supports weekly syncs at this scale. Free tier (1k/mo) is insufficient.

### Product fields — verified

Returned by both search and detail endpoints:

| Field | Example | Our use |
|---|---|---|
| `id` | `19206` (int) | `ShoeColorway.goat_id` (store as TextField for safety) |
| `slug` | `"air-force-1-306353-462"` | Detail-fetch key — use this over `id` |
| `sku` | `"306353 462"` (note space) | `ShoeColorway.sku` |
| `name` | `"Nike Air Force 1"` | Model-level — not useful for colorway display |
| `nickname` | `"Triple White"` | **Preferred for `ShoeColorway.name`** (short, marketing-clean) |
| `colorway` | `"White/White/White"` | Fallback for `ShoeColorway.name` if `nickname` is null |
| `brand` | `"Nike"` | Brand-match check |
| `model` | `"Air Force 1"` | Model-match check |
| `image_url` | CDN URL | `ShoeColorway.image_url` |
| `images` | array | Not used (we take primary only) |
| `link` | goat.sjv.io affiliate URL | `ShoeColorway.product_url` |

### Variant fields — verified

Per variant (populated only on detail fetch):

```json
{
  "product_id": 19206,
  "size": "10",
  "lowest_ask": 165,
  "currency": "USD",
  "market": "US",
  "available": true,
  "updated_at": "2026-04-16T00:02:03Z"
}
```

- **Use `variant["available"]` directly** — do not infer from `lowest_ask`. GOAT can show `lowest_ask=0` with `available=false` when delisted.
- **Filter to `market == "US"` and `currency == "USD"`** before processing. Avoids mixing foreign-market prices into the recommendation.
- **`size` is a string** (e.g. `"10"`, `"10.5"`) — parse to float before comparing with `ShoeSize.us_size`.
- **Half sizes present**: `"10.5"`, `"11.5"`, etc. Our insole-measured `ShoeSize` rows must match exactly for the sync to write a `ShoeColorwaySize` row.

### Stale colorway cleanup — decided

**Option A confirmed**: after each shoe's sync, mark `ShoeColorway` rows whose `last_synced_at` is stale (older than the current run's start timestamp) as having all their `ShoeColorwaySize.is_available = False`. This handles colorways that disappeared from GOAT entirely.

Implementation detail:
```python
run_started = timezone.now()
# ... sync loop runs, each touched ShoeColorway gets last_synced_at = now ...
# After processing shoe's colorways:
ShoeColorwaySize.objects.filter(
    colorway__shoe=shoe,
    colorway__last_synced_at__lt=run_started,
).update(is_available=False)
```

We do **not** delete stale `ShoeColorway` rows — they stay in the DB with all sizes flagged unavailable. If they reappear on GOAT later, the next sync revives them via `update_or_create` on `goat_id`.

### Audit of references to soon-to-be-stale fields

Grepped `shoe_image_url`, `product_url`, `price_usd`, `colorway`, `kicks_id` across both frontend and backend:

**Frontend** — only `RecommendationsScreen.js` references these fields (lines 299, 300, 314, 315, 333, 334). No other screen reads them.

- **`SavedShoesContext.js`** — stores the entire shoe object verbatim; agnostic to field shape. No changes needed.
- **`SavedShoesScreen.js`** — reads `shoe.name`, `shoe.typicalSize`, `shoe.lengthCm`, `shoe.widthCm`, `shoe.functionPath`, `shoe.attributes`. These field names do **not** match what `RecommendationsScreen` actually saves (it saves the recommendation item, which has `model`, `brand`, `fit_*`, etc.). **This screen is already broken** — it was built against mock data. Pre-existing bug, not introduced by this change, not our problem to fix here. The context also exports `savedMap` but `SavedShoesScreen` destructures `savedShoes` — that's a second pre-existing bug. Flag and move on.

**Backend** — references are in:
- `backend/models/__init__.py` (field definitions — kept, no longer written by new sync)
- `backend/api/serializers.py` — **both** `ShoeSerializer` and `RecommendationSerializer` reference the old fields
- `backend/api/views.py` — no direct field references beyond what the serializer pulls
- `backend/management/commands/seed_kicks.py` — entirely replaced
- `backend/management/commands/seed_demo_data.py` — writes `price_usd` directly for demo shoes; **leave as-is** (fallback data)
- `backend/schema.sql` — legacy DDL snapshot for reference; not executed by Django, ignore
- `backend/migrations/0001_initial.py`, `0004_kicks_fields.py` — historical migrations; untouched

### `ShoeSerializer` decision

`ShoeSerializer` (used only by `GET /api/shoes/` → a debug/utility endpoint called from `ProfileScreen` smoke test) is **left as-is**. It continues to return `colorway`, `sku`, `price_usd`, `shoe_image_url`, `product_url` from the legacy `Shoe` fields. After the new sync runs, these will become stale on any previously-synced shoes, but the endpoint is not user-facing and the test in `ProfileScreen` only checks for a successful response, not field values.

Only `RecommendationSerializer` is updated to use the new `colorway_options` shape.

---

## Known Limitations

- **3-page cap per shoe** — we stop after 300 search results even if `meta.total` is higher. Popular shoes (Air Force 1 hits 1000) have a very long tail of obscure colorways we intentionally skip.
- **Width data absent from GOAT** — all `ShoeColorwaySize` rows are implicitly regular-width.
- **Images hosted on GOAT CDN** — will 404 if GOAT removes the product. Re-hosting to Supabase Storage is a future hardening step.
- **No delta sync** — full re-query every run. Request budget per sync ≈ (# shoes × (1 + avg colorways)). At 50 shoes × 15 colorways = ~800 requests. Weekly = ~3,200/mo. Starter tier (50k/mo) has ample headroom.
- **GOAT listing only** — no StockX or other retailer fallback. Buy links are always GOAT.
- **SavedShoesScreen pre-existing bug** — unrelated to this change, but flagged: it reads field names (`shoe.name`, `shoe.typicalSize`) that don't match what `RecommendationsScreen` saves, and destructures `savedShoes` from a context that exports `savedMap`. Fixing this is out of scope for V2.
