from django.db import migrations, models


class Migration(migrations.Migration):
    """Add measurement_method field to Measurement to track paper vs ARCore."""

    dependencies = [
        ("backend", "0009_shoe_colorway_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="measurement",
            name="measurement_method",
            field=models.CharField(
                choices=[("paper", "Paper"), ("arcore", "ARCore")],
                default="paper",
                max_length=10,
            ),
        ),
    ]
