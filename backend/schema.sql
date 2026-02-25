-- Shoe Shopper schema (PostgreSQL)
-- Compatible with Django default auth tables.
-- Assumes Django has already created public.auth_user.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================
-- 1) Profile
-- =========================
CREATE TABLE IF NOT EXISTS profile (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT UNIQUE NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  display_name TEXT,
  avatar_url   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================
-- 2) Guest sessions (optional)
-- =========================
CREATE TABLE IF NOT EXISTS guest_session (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_accessed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guest_session_expires_at
  ON guest_session(expires_at);

-- =========================
-- 3) Measurements
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'measurement_status') THEN
    CREATE TYPE measurement_status AS ENUM ('uploaded', 'processing', 'complete', 'error');
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paper_size') THEN
    CREATE TYPE paper_size AS ENUM ('letter', 'a4');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS measurement (
  id                BIGSERIAL PRIMARY KEY,
  user_id           BIGINT REFERENCES auth_user(id) ON DELETE CASCADE,
  guest_session_id  UUID REFERENCES guest_session(id) ON DELETE CASCADE,
  status            measurement_status NOT NULL DEFAULT 'uploaded',
  image_url         TEXT NOT NULL,
  image_width_px    INTEGER,
  image_height_px   INTEGER,
  length_in         NUMERIC(6,3),
  width_in          NUMERIC(6,3),
  area_sq_in        NUMERIC(10,3),
  perimeter_in      NUMERIC(10,3),
  paper_type        paper_size,
  confidence        NUMERIC(4,3),
  algorithm_version TEXT,
  error_message     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_measurement_owner
    CHECK (
      (user_id IS NOT NULL AND guest_session_id IS NULL) OR
      (user_id IS NULL AND guest_session_id IS NOT NULL)
    ),
  CONSTRAINT chk_measurement_length_positive
    CHECK (length_in IS NULL OR length_in > 0),
  CONSTRAINT chk_measurement_width_positive
    CHECK (width_in IS NULL OR width_in > 0),
  CONSTRAINT chk_measurement_area_positive
    CHECK (area_sq_in IS NULL OR area_sq_in > 0),
  CONSTRAINT chk_measurement_perimeter_positive
    CHECK (perimeter_in IS NULL OR perimeter_in > 0)
);

CREATE INDEX IF NOT EXISTS idx_measurement_user_created
  ON measurement(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_measurement_guest_created
  ON measurement(guest_session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_measurement_status
  ON measurement(status);

-- =========================
-- 4) Shoe catalog
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shoe_gender') THEN
    CREATE TYPE shoe_gender AS ENUM ('women', 'men', 'unisex', 'kids', 'unknown');
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shoe_width') THEN
    CREATE TYPE shoe_width AS ENUM ('narrow', 'regular', 'wide', 'extra_wide');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS shoe (
  id                  BIGSERIAL PRIMARY KEY,
  brand               TEXT NOT NULL,
  model               TEXT NOT NULL,
  gender              shoe_gender NOT NULL DEFAULT 'unknown',
  function_tags       TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  style_tags          TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  attributes_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
  insole_length_in    NUMERIC(6,3),
  insole_width_in     NUMERIC(6,3),
  insole_area_sq_in   NUMERIC(10,3),
  insole_perimeter_in NUMERIC(10,3),
  shoe_image_url      TEXT,
  product_url         TEXT,
  price_usd           NUMERIC(10,2),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shoe_brand_model
  ON shoe(brand, model);

CREATE INDEX IF NOT EXISTS idx_shoe_tags_gin_function
  ON shoe USING GIN(function_tags);

CREATE INDEX IF NOT EXISTS idx_shoe_tags_gin_style
  ON shoe USING GIN(style_tags);

CREATE TABLE IF NOT EXISTS shoe_size (
  id           BIGSERIAL PRIMARY KEY,
  shoe_id      BIGINT NOT NULL REFERENCES shoe(id) ON DELETE CASCADE,
  us_size      NUMERIC(4,1) NOT NULL,
  width        shoe_width NOT NULL DEFAULT 'regular',
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (shoe_id, us_size, width)
);

CREATE INDEX IF NOT EXISTS idx_shoe_size_lookup
  ON shoe_size(shoe_id, us_size, width, is_available);

-- =========================
-- 5) User collection (wishlist + owned)
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'collection_type') THEN
    CREATE TYPE collection_type AS ENUM ('wishlist', 'owned');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS user_collection (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  shoe_id      BIGINT NOT NULL REFERENCES shoe(id) ON DELETE CASCADE,
  type         collection_type NOT NULL,
  size         TEXT,
  color        TEXT,
  notes        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, shoe_id, type)
);

CREATE INDEX IF NOT EXISTS idx_collection_user_type_created
  ON user_collection(user_id, type, created_at DESC);

-- =========================
-- 6) Recommendations
-- =========================
CREATE TABLE IF NOT EXISTS recommendation (
  id                BIGSERIAL PRIMARY KEY,
  user_id           BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  shoe_id           BIGINT NOT NULL REFERENCES shoe(id) ON DELETE CASCADE,
  measurement_id    BIGINT REFERENCES measurement(id) ON DELETE SET NULL,
  run_id            UUID NOT NULL,
  rank              INTEGER NOT NULL,
  score             NUMERIC(10,6),
  algorithm_version TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_recommendation_rank_positive
    CHECK (rank > 0),
  UNIQUE (user_id, run_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_reco_user_created
  ON recommendation(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reco_user_shoe
  ON recommendation(user_id, shoe_id);

CREATE INDEX IF NOT EXISTS idx_reco_user_run_rank
  ON recommendation(user_id, run_id, rank);

-- =========================
-- 7) Training images
-- =========================
CREATE TABLE IF NOT EXISTS training_image (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT REFERENCES auth_user(id) ON DELETE SET NULL,
  image_url   TEXT NOT NULL,
  label_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
  in_dataset  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_in_dataset
  ON training_image(in_dataset);

CREATE INDEX IF NOT EXISTS idx_training_user_created
  ON training_image(user_id, created_at DESC);

-- =========================
-- 8) updated_at trigger
-- =========================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profile_updated_at ON profile;
CREATE TRIGGER trg_profile_updated_at
BEFORE UPDATE ON profile
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_measurement_updated_at ON measurement;
CREATE TRIGGER trg_measurement_updated_at
BEFORE UPDATE ON measurement
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_shoe_updated_at ON shoe;
CREATE TRIGGER trg_shoe_updated_at
BEFORE UPDATE ON shoe
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_collection_updated_at ON user_collection;
CREATE TRIGGER trg_collection_updated_at
BEFORE UPDATE ON user_collection
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
