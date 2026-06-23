# Shoe Shopper — Database Reference

> **Audience:** engineers working on the schema, migrations, or queries.
> **Scope:** the relational schema — tables, columns, keys, constraints,
> indexes, cascade behavior, and migration history. How the data is *used* is in
> [`BACKEND.md`](./BACKEND.md) and [`END_TO_END_FLOW.md`](./END_TO_END_FLOW.md).
>
> Source of truth: `backend/models/__init__.py` (current schema) cross-checked
> against `backend/migrations/`. Where it contradicts older notes, the code
> wins (Appendix B).

---

## 1. Physical stores & access paths

- **Canonical schema:** PostgreSQL (Supabase in prod). All `db_table` names,
  constraints, and indexes target Postgres.
- **Dev fallback:** a local `db.sqlite3` (not committed; created on first
  `migrate`). Convenience only — per `CLAUDE.md`, **do not treat the local
  SQLite schema as authoritative** for production migrations. Postgres-specific
  features (array columns, GIN indexes) do not behave the same on SQLite.
- **Two access paths** (which may point at the *same* database in prod, but use
  different drivers and credentials):
  1. **Django ORM** — every view, model, and catalog command; configured via the
     Django database settings.
  2. **Supabase Python client** — used *only* by `feedback_service` and
     `tolerance_storage` for the `user_feedback` and `tolerances` tables,
     bypassing the ORM, via its own Supabase URL/key (see §7).

---

## 2. Entity-relationship map

```
auth_user (Django)
  │ 1:1   ── profile
  │ 1:*   ── measurement ──┐         (owner = user XOR guest_session)
  │ 1:*   ── user_collection ──*── shoe
  │ 1:*   ── recommendation ──*── shoe
  │ │                         └──*── measurement (SET NULL)
  │ 1:*   ── training_image
guest_session 1:* ── measurement ──┘

shoe 1:* ── shoe_size                 (per-size insole geometry → fit inputs)
shoe 1:* ── shoe_colorway 1:* ── shoe_colorway_size   (live price/availability)

user_feedback     (standalone; Supabase-accessed)
tolerances        (standalone; Supabase-accessed)
```

---

## 3. Conventions

- **Explicit `db_table`** on every model (e.g. `measurement`, `shoe_size`) —
  table names are snake_case and stable; don't rely on Django's default naming.
- **Primary keys:** `BigAutoField` (`id`) except `guest_session` and
  `user_feedback`, which use `UUIDField`.
- **Timestamps:** most tables carry `created_at` (`auto_now_add`); mutable rows
  also carry `updated_at` (`auto_now`).
- **Money/measurements:** `DecimalField` (never float) — e.g. dimensions
  `(6,3)`, areas `(10,3)`, `us_size (4,1)`, `price_usd (10,2)`,
  recommendation `score (10,6)`.
- **Free text:** `TextField` is preferred over `CharField` except where a short
  bounded value is meaningful (status/choice fields, `dominant_color_hex(7)`).

---

## 4. Table reference

Each block lists purpose, foreign keys (with `on_delete`), uniqueness, check
constraints, and indexes. Full column types are in the model file.

### 4.1 `profile`
1:1 extension of the Django user.
- **FK:** `user → auth_user` (CASCADE, unique via OneToOne).
- Columns: `display_name`, `avatar_url` (both nullable), timestamps.

### 4.2 `guest_session`
Anonymous owner for guest measurements.
- **PK:** UUID. Columns: `created_at`, `last_accessed`, `expires_at`.
- **Index:** `idx_guest_session_expires_at`.

### 4.3 `measurement`
One foot-scan result.
- **FKs:** `user → auth_user` (CASCADE, nullable); `guest_session` (CASCADE,
  nullable).
- **Check constraints:**
  - `chk_measurement_owner` — exactly one of `user` / `guest_session` is set
    (`user XOR guest_session`).
  - `chk_measurement_length_positive`, `..._width_positive`,
    `..._area_positive`, `..._perimeter_positive` — each dimension is null or
    `> 0`.
- **Columns:** `status` (uploaded/processing/complete/error), `image_url`,
  `image_width_px`/`height_px`, `length_in`/`width_in`/`toebox_length_in`/
  `toebox_width_in (6,3)`, `area_sq_in`/`perimeter_in (10,3)`,
  `paper_type` (letter/a4), `measurement_method` (paper/arcore),
  `confidence (4,3)`, `algorithm_version`, `error_message`, timestamps.
- **Indexes:** `idx_measurement_user_created (user, -created_at)`,
  `idx_measurement_guest_created`, `idx_measurement_status`.

### 4.4 `shoe`
Catalog base model (one row per shoe model, not per size).
- **Uniqueness:** `sku` unique, `kicks_id` unique.
- **Columns:** `brand`, `model`, `gender` (women/men/unisex/kids/unknown),
  `function_tags[]`, `style_tags[]` (Postgres arrays), `attributes_json`,
  `toe_shape` (round/almond/chisel/pointed), `cap_type` (none/steel/composite),
  `arch_type`, `colorway`, image/product URLs, `price_usd (10,2)`,
  `is_active`, `last_synced_at`, timestamps.
- **Indexes:** `idx_shoe_brand_model`; **GIN** `idx_shoe_tags_gin_function`
  (`function_tags`) and `idx_shoe_tags_gin_style` (`style_tags`) for array
  containment queries.

### 4.5 `shoe_size`
Per-size **insole geometry** — the shoe-side inputs to the fit algorithm.
- **FK:** `shoe → shoe` (CASCADE).
- **Uniqueness:** `(shoe, us_size, width)` → `shoe_size_shoe_id_us_size_width_key`.
- **Columns:** `us_size (4,1)`, `width` (narrow/regular/wide/extra_wide),
  `is_available`, `insole_length_in`/`insole_width_in`/`insole_toebox_length_in`/
  `insole_toebox_width_in (6,3)`, `insole_area_sq_in`/`insole_perimeter_in (10,3)`.
- **Index:** `idx_shoe_size_lookup (shoe, us_size, width, is_available)`.

> **Schema history:** insole columns lived on `shoe` until migration **0007**
> moved them here. The fit algorithm reads insole dims from `shoe_size`.

### 4.6 `shoe_colorway`
Color variant of a base shoe.
- **FK:** `shoe → shoe` (CASCADE).
- **Uniqueness:** `goat_id` unique.
- **Columns:** `sku`, `name`, `image_url`, `product_url`, `last_synced_at`,
  `dominant_color_hex (7)`, `dominant_color_source_url`,
  `dominant_color_computed_at`, `color_palette_hex` (JSON list).
- **Index:** `idx_shoe_colorway_shoe_goat (shoe, goat_id)`.

### 4.7 `shoe_colorway_size`
Live price/availability per colorway per size.
- **FK:** `colorway → shoe_colorway` (CASCADE).
- **Uniqueness:** `(colorway, us_size)` → `shoe_colorway_size_colorway_us_size_key`.
- **Columns:** `us_size (4,1)`, `price_usd (10,2)`, `is_available`
  (default **False**).
- **Index:** `idx_shoe_colorway_size_lookup (colorway, us_size, is_available)`.

### 4.8 `user_collection`
Server-side wishlist/owned list. *(The live UI keeps its own copy in
AsyncStorage; this table is not the UI source of truth — see
`END_TO_END_FLOW.md` §8.)*
- **FKs:** `user → auth_user` (CASCADE); `shoe → shoe` (CASCADE).
- **Uniqueness:** `(user, shoe, type)`.
- **Columns:** `type` (wishlist/owned), `size`, `color`, `notes`, timestamps.
- **Index:** `idx_coll_user_type_created (user, type, -created_at)`.

### 4.9 `recommendation`
Persisted recommendation run rows. **Not written by the live endpoint** —
scoring is computed per request (see `BACKEND.md` §5).
- **FKs:** `user → auth_user` (CASCADE); `shoe → shoe` (CASCADE);
  `measurement → measurement` (**SET NULL**, nullable).
- **Check constraint:** `chk_recommendation_rank_positive` (`rank > 0`).
- **Uniqueness:** `(user, run_id, rank)`.
- **Columns:** `run_id` (UUID), `rank`, `score (10,6)`, `algorithm_version`,
  `created_at`.
- **Indexes:** `idx_reco_user_created`, `idx_reco_user_shoe`,
  `idx_reco_user_run_rank`.

### 4.10 `training_image`
Foot-photo metadata for ML training.
- **FK:** `user → auth_user` (**SET NULL**, nullable).
- **Columns:** `image_url`, `label_json` (Roboflow-format), `in_dataset`,
  `created_at`.
- **Indexes:** `idx_training_in_dataset`, `idx_training_user_created`.

### 4.11 `user_feedback` *(Supabase-accessed)*
Fit feedback that drives tolerance learning.
- **PK:** UUID. No foreign keys.
- **Columns:** `feedback_type` (too_narrow/too_wide/too_short/too_long/perfect),
  `shoe_profile` (the 14 fit profiles), `current_tolerances` (JSON),
  `fit_score (4,2)`, `measurements` (JSON), `severity_rating` (int),
  `created_at`.
- **Indexes:** `idx_feedback_shoe_profile`, `idx_feedback_created_at`,
  `idx_feedback_type`.

### 4.12 `tolerances` *(Supabase-accessed)*
Versioned learned tolerance sets (model `ToleranceHistory`).
- **Columns:** `tolerances` (JSON), `total_feedback_count`, `active` (bool),
  `created_at`, `last_feedback_timestamp`. By convention only one row is
  `active` — there is **no DB constraint** enforcing this; `tolerance_storage`
  self-heals by deactivating older rows when it loads.
- **Indexes:** `idx_tolerance_active_created (active, -created_at)`,
  `idx_tolerance_last_feedback`.

---

## 5. Integrity rules at a glance

**Cascade behavior on delete:**

| Parent deleted | Effect |
|---|---|
| `auth_user` | CASCADE → profile, measurements, collections, recommendations; **SET NULL** → training_image |
| `guest_session` | CASCADE → its measurements |
| `shoe` | CASCADE → sizes, colorways (→ colorway_sizes), collections, recommendations |
| `shoe_colorway` | CASCADE → colorway_sizes |
| `measurement` | **SET NULL** on `recommendation.measurement` |

**Check constraints:** `measurement` (owner XOR + 4 positivity checks) and
`recommendation` (`rank > 0`).

**Account deletion** (`DELETE /api/auth/delete/`) is a hard `user.delete()` —
the cascades above wipe all owned rows immediately.

---

## 6. Postgres-specific features & SQLite caveats

- **Array columns:** `shoe.function_tags`, `shoe.style_tags` use
  `ArrayField` — Postgres-native; queried with array containment.
- **GIN indexes:** the two `idx_shoe_tags_gin_*` indexes accelerate those array
  queries; they are Postgres-only.
- **JSON columns:** `shoe.attributes_json`, `shoe_colorway.color_palette_hex`,
  `training_image.label_json`, and the Supabase `user_feedback` /
  `tolerances` JSON fields.
- On SQLite these features degrade or are skipped; use a Postgres instance for
  any work touching tags, GIN indexes, or array/JSON queries.

---

## 7. The Supabase-accessed tables

`user_feedback` and `tolerances` are defined as Django models
(`UserFeedback`, `ToleranceHistory`) **and** read/written through the Supabase
client by `feedback_service.py` / `tolerance_storage.py`. When the ORM and the
Supabase client are configured against the same Supabase project (the expected
prod setup), the table definitions above are authoritative — but writes from the
learning services do **not** go through the ORM (no Django signals, validation,
or migrations awareness on that path). Both tables do have Django migrations
(`user_feedback` in 0005, `tolerances` in 0011), so `migrate` creates them; the
Supabase client simply reads/writes the same rows out-of-band. Keep new feedback/tolerance work on the
Supabase path it already uses. The learning loop is otherwise **not wired** to a
live endpoint (see `BACKEND.md` §6).

---

## 8. Migration history (`backend/migrations/`)

| Migration | Change |
|---|---|
| `0001_initial` | Base schema: profile, guest_session, measurement, shoe, shoe_size, user_collection, recommendation, training_image |
| `0002_auth_user_email_index` | Index on the Django `auth_user.email` (Google login looks up users by email) |
| `0003_toebox_fields` | Adds toebox dimension columns |
| `0004_repair_shoe_columns` | Column repair/cleanup on `shoe` |
| `0005_userfeedback` | Adds `user_feedback` |
| `0006_kicks_fields` | Adds kicks.dev integration fields (`kicks_id`, etc.) |
| `0007_insole_to_shoesize` | **Moves insole dimensions from `shoe` → `shoe_size`** |
| `0008_shoe_is_active` | Adds `shoe.is_active` |
| `0009_shoe_colorway_models` | Adds `shoe_colorway` + `shoe_colorway_size` |
| `0010_measurement_method` | Adds `measurement.measurement_method` (paper/arcore) |
| `0011_alter_shoecolorway_id` | Alters `shoe_colorway`/`shoe_colorway_size` id fields **and creates `ToleranceHistory` (`tolerances` table)** |
| `0012_shoecolorway_dominant_color` | Adds dominant-color columns |
| `0013_shoecolorway_color_palette` | Adds `color_palette_hex` |

> Always commit the migration alongside the model change. `ToleranceHistory`
> (`tolerances`) is created by migration 0011 **and** read/written by the
> Supabase client at runtime; keep both in mind when changing that table.

---

## Appendix A — Key files

| Area | File |
|---|---|
| Models (current schema) | `backend/models/__init__.py` |
| Migrations | `backend/migrations/0001`–`0013` |
| Supabase access | `backend/services/supabase_client.py`, `feedback_service.py`, `tolerance_storage.py` |
| DB settings | `shoeshopper/settings.py` (§2.2 of `BACKEND.md`) |

## Appendix B — Discrepancies with older notes

1. **Insole dimensions are on `shoe_size`, not `shoe`** (migration 0007).
2. **12 tables** now exist (colorway, feedback, and tolerance tables were
   added after the original docs).
3. **`recommendation` rows are never written** by the live endpoint.
4. **`user_feedback` / `tolerances` are reached via the Supabase client**,
   outside the ORM, and the learning loop is not wired to an endpoint.
