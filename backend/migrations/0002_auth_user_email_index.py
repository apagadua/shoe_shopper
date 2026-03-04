from django.db import migrations


class Migration(migrations.Migration):
    """
    Add a database index on auth_user.email to speed up the get_or_create
    lookup performed on every Google login.
    """

    dependencies = [
        ("backend", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS idx_auth_user_email ON auth_user (email);",
            reverse_sql="DROP INDEX IF EXISTS idx_auth_user_email;",
        ),
    ]
