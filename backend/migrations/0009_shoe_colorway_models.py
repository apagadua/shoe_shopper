from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Create ShoeColorway and ShoeColorwaySize tables.
    Wrapped in SeparateDatabaseAndState — tables already exist in Supabase.
    """

    dependencies = [
        ("backend", "0008_shoe_is_active"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # tables already exist in Supabase
            state_operations=[
                migrations.CreateModel(
                    name="ShoeColorway",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                        ("shoe", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="colorways",
                            to="backend.shoe",
                        )),
                        ("goat_id", models.TextField(unique=True)),
                        ("sku", models.TextField(blank=True, null=True)),
                        ("name", models.TextField()),
                        ("image_url", models.TextField(blank=True, null=True)),
                        ("product_url", models.TextField(blank=True, null=True)),
                        ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={"db_table": "shoe_colorway"},
                ),
                migrations.AddIndex(
                    model_name="shoecolorway",
                    index=models.Index(fields=["shoe", "goat_id"], name="idx_shoe_colorway_shoe_goat"),
                ),
                migrations.CreateModel(
                    name="ShoeColorwaySize",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                        ("colorway", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="sizes",
                            to="backend.shoecolorway",
                        )),
                        ("us_size", models.DecimalField(decimal_places=1, max_digits=4)),
                        ("price_usd", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                        ("is_available", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={"db_table": "shoe_colorway_size"},
                ),
                migrations.AddConstraint(
                    model_name="shoecolorwaysize",
                    constraint=models.UniqueConstraint(
                        fields=["colorway", "us_size"],
                        name="shoe_colorway_size_colorway_us_size_key",
                    ),
                ),
                migrations.AddIndex(
                    model_name="shoecolorwaysize",
                    index=models.Index(
                        fields=["colorway", "us_size", "is_available"],
                        name="idx_shoe_colorway_size_lookup",
                    ),
                ),
            ],
        ),
    ]
