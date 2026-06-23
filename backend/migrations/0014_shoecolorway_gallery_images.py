from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0013_shoecolorway_color_palette"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoecolorway",
            name="gallery_image_urls",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
