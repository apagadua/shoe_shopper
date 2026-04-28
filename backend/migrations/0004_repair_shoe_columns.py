"""
Repair drifted PostgreSQL `shoe` tables where migrations are marked applied
but columns from 0001_initial / 0003_toebox_fields were never created (e.g.
restored DB or manual schema). Uses ADD COLUMN IF NOT EXISTS so it is safe
to run on an already-correct database.
"""

from django.db import migrations


def repair_shoe_columns(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # Types match backend.models.Shoe and Django's PostgreSQL schema.
    statements = [
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS gender varchar(10) NOT NULL DEFAULT 'unknown'",
        (
            "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS function_tags text[] "
            "NOT NULL DEFAULT ARRAY[]::text[]"
        ),
        (
            "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS style_tags text[] "
            "NOT NULL DEFAULT ARRAY[]::text[]"
        ),
        (
            "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS attributes_json jsonb "
            "NOT NULL DEFAULT '{}'::jsonb"
        ),
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_length_in numeric(6,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_width_in numeric(6,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_area_sq_in numeric(10,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_perimeter_in numeric(10,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS shoe_image_url text NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS product_url text NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS price_usd numeric(10,2) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now()",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_toebox_length_in numeric(6,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS insole_toebox_width_in numeric(6,3) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS toe_shape varchar(12) NULL",
        "ALTER TABLE shoe ADD COLUMN IF NOT EXISTS cap_type varchar(12) NULL",
    ]
    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0003_toebox_fields"),
    ]

    operations = [
        migrations.RunPython(repair_shoe_columns, noop_reverse),
    ]
