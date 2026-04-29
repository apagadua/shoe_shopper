from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add is_active flag to Shoe.
    Wrapped in SeparateDatabaseAndState — column already exists in Supabase.
    """

    dependencies = [
        ("backend", "0007_insole_to_shoesize"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # column already exists in Supabase
            state_operations=[
                migrations.AddField(
                    model_name="shoe",
                    name="is_active",
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
    ]
