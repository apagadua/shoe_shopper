from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add is_active flag to Shoe.

    Existing shoes default to True (active) until the next seed_kicks run
    evaluates their GOAT availability.
    """

    dependencies = [
        ("backend", "0005_insole_to_shoesize"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoe",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
