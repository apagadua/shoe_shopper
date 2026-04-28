from django.db import migrations, models


class Migration(migrations.Migration):
    """Add KicksDB integration fields to Shoe model."""

    dependencies = [
        ("backend", "0005_userfeedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoe",
            name="colorway",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shoe",
            name="sku",
            field=models.TextField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="shoe",
            name="kicks_id",
            field=models.TextField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="shoe",
            name="last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
