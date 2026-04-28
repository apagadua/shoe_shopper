# KicksDB Integration Plan

Weekly sync of real prices, images, and buy links from KicksDB into the shoe catalog. One record per colorway, filtered to the user's size.

---

## What KicksDB Provides

- `images[]` — CDN image URLs per colorway
- `link` — buy link (StockX, GOAT, etc.)
- `variants[]` — per-size price and availability (US sizing)
- `sku` — retailer SKU, uniquely identifies a colorway
- `id` — KicksDB UUID (stable across syncs)

KicksDB does **not** provide width data. All imported sizes stored as `width="regular"` unless manually overridden.

---

## Schema Changes

Add three fields to the `Shoe` model (`backend/models/__init__.py`):

| Field | Type | Purpose |
|---|---|---|
| `colorway` | `TextField(null=True, blank=True)` | Human-readable name, e.g. "White/White/White" |
| `sku` | `TextField(null=True, blank=True, unique=True)` | Retailer SKU — deduplication key |
| `kicks_id` | `TextField(null=True, blank=True, unique=True)` | KicksDB product UUID |

One migration required. No changes to `ShoeSize`, views, or URLs.

---

## Data Model: One Row Per Colorway

Each colorway in KicksDB maps to its own `Shoe` row:

- Nike Dunk Low Panda → `Shoe(brand="Nike", model="Dunk Low", colorway="Panda", sku="DD1391-100", ...)`
- Nike Dunk Low University Red → separate `Shoe` row
- Nike Dunk Low Michigan → separate `Shoe` row

`ShoeSize` rows stay per-`Shoe`, so availability is naturally per-colorway. The recommendation engine scores each colorway independently — colorways where the user's size is unavailable rank lower or are filtered out.

---

## Seed Command

**File:** `backend/management/commands/seed_kicks.py`
**Also needed:** `backend/management/__init__.py`, `backend/management/commands/__init__.py` (empty files)

### Logic

```
For each target shoe model (e.g. "Nike Dunk Low"):
  GET /v3/stockx/products?query=Nike+Dunk+Low&per_page=50
  Authorization: Bearer <KICKS_API_KEY>

  For each result (colorway):
    Shoe.objects.update_or_create(
      kicks_id=result["id"],
      defaults={
        brand, model, colorway=result["title"], sku=result["sku"],
        shoe_image_url=result["images"][0],
        product_url=result["link"],
        price_usd=min(v["price"] for v in result["variants"]),
      }
    )
    For each variant in result["variants"]:
      ShoeSize.objects.update_or_create(
        shoe=shoe, us_size=variant["size"], width="regular",
        defaults={"is_available": True}
      )
    Mark absent sizes is_available=False
```

### CLI Usage

```bash
python manage.py seed_kicks                        # sync all target models
python manage.py seed_kicks --query "Nike Dunk Low"  # single model
python manage.py seed_kicks --dry-run               # preview without writing
```

### Rate Limiting

Sleep 0.1s between requests. Free tier cap is 640 req/min — this keeps well under it.

---

## Request Budget

| Catalog size | Requests per sync | Free tier (1k/mo) at weekly cadence |
|---|---|---|
| 20 models, ~5 colorways each | ~20 | Fine |
| 50 models | ~50–100 | 4 syncs/month = 200–400 req, fine |
| 200 models | ~200–400 | Approaches cap — consider Starter (€29/mo) |

Free tier is US market only. Starter (€29/mo, 50k req) is the realistic production entry point.

---

## Weekly Sync Schedule

**Option A — Server cron (MVP, zero dependencies):**
```bash
# crontab: every Sunday at 2am
0 2 * * 0 cd /path/to/app && python manage.py seed_kicks
```

**Option B — Celery Beat (if Celery is added later):**
```python
CELERY_BEAT_SCHEDULE = {
    'sync-kicks-weekly': {
        'task': 'backend.tasks.sync_kicks',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
    },
}
```

---

## Serializer Changes

Add `colorway` and `sku` to both `ShoeSerializer` and `RecommendationSerializer` in `backend/api/serializers.py` so the frontend can display the colorway name on each card.

---

## Frontend Changes

Add a colorway label below brand/model on recommendation cards in `RecommendationsScreen.js`. No structural changes needed — each card already renders independently.

---

## Environment Variable

```
KICKS_API_KEY=Bearer KICKS-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Add to `.env` at repo root. Register at kicks.dev to obtain a key.

---

## Implementation Order

1. Add `colorway`, `sku`, `kicks_id` to `Shoe` model + generate migration
2. Create `backend/management/commands/seed_kicks.py`
3. Add `colorway`, `sku` to `ShoeSerializer` + `RecommendationSerializer`
4. Add colorway label to recommendation card in frontend
5. Add `KICKS_API_KEY` to `.env` and server environment
6. Add cron job on server

---

## Known Limitations

- **No "updated since" filter** — full poll every sync, no delta support
- **No webhooks** — polling only
- **Images hosted on kicks.dev CDN** — will 404 if subscription lapses; consider re-hosting on Supabase Storage for durability
- **Width data absent** — all sizes imported as `width="regular"`
- **Colorway match quality** — search results may include irrelevant colorways; seed command should allow specifying `kicks_id` directly for precision
- **Stale detection** — add `last_synced_at` field to `Shoe` to identify records not updated in recent syncs
