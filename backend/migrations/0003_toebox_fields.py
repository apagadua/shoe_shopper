from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add toebox dimension fields to Measurement and Shoe models,
    and add toe_shape / cap_type to Shoe for algorithm pre-processing.
    """

    dependencies = [
        ("backend", "0002_auth_user_email_index"),
    ]

    operations = [
        # Measurement: toebox dimensions from Roboflow Toe Box polygon
        migrations.AddField(
            model_name="measurement",
            name="toebox_length_in",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="measurement",
            name="toebox_width_in",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        # Shoe: toebox insole dimensions
        migrations.AddField(
            model_name="shoe",
            name="insole_toebox_length_in",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="shoe",
            name="insole_toebox_width_in",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
        # Shoe: algorithm pre-processing fields
        migrations.AddField(
            model_name="shoe",
            name="toe_shape",
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
        migrations.AddField(
            model_name="shoe",
            name="cap_type",
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
    ]
