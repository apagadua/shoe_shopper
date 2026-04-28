from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Align Django models with actual Supabase schema.

    In Supabase the insole measurement columns were always on shoe_size (per-size),
    not on shoe (per-model). Django's model incorrectly had them on Shoe.

    Changes to Django state:
      - Remove 6 insole fields from Shoe
      - Add those 6 insole fields to ShoeSize
      - Add arch_type to Shoe (exists in Supabase but was missing from the model)

    Changes to the database:
      - Only one real operation: rename the typo'd column
        shoe_size.inole_toebox_width_in → shoe_size.insole_toebox_width_in
      - Everything else is already correct in Supabase, so SeparateDatabaseAndState
        is used to update Django's understanding without issuing redundant DDL.
    """

    dependencies = [
        ("backend", "0006_kicks_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # --- Remove insole fields from Shoe ---
                # (These columns don't exist in Supabase's shoe table)
                migrations.RemoveField(model_name="shoe", name="insole_length_in"),
                migrations.RemoveField(model_name="shoe", name="insole_width_in"),
                migrations.RemoveField(model_name="shoe", name="insole_area_sq_in"),
                migrations.RemoveField(model_name="shoe", name="insole_perimeter_in"),
                migrations.RemoveField(model_name="shoe", name="insole_toebox_length_in"),
                migrations.RemoveField(model_name="shoe", name="insole_toebox_width_in"),
                # --- Add arch_type to Shoe ---
                # (Already exists in Supabase's shoe table)
                migrations.AddField(
                    model_name="shoe",
                    name="arch_type",
                    field=models.TextField(blank=True, null=True),
                ),
                # --- Add insole fields to ShoeSize ---
                # (Already exist in Supabase's shoe_size table)
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_length_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
                ),
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_width_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
                ),
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_area_sq_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
                ),
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_perimeter_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
                ),
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_toebox_length_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
                ),
                migrations.AddField(
                    model_name="shoesize",
                    name="insole_toebox_width_in",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
                ),
            ],
            database_operations=[
                # Fix the column name typo in shoe_size (missing 's' in 'insole')
                migrations.RunSQL(
                    sql="ALTER TABLE shoe_size RENAME COLUMN inole_toebox_width_in TO insole_toebox_width_in",
                    reverse_sql="ALTER TABLE shoe_size RENAME COLUMN insole_toebox_width_in TO inole_toebox_width_in",
                ),
            ],
        ),
    ]
