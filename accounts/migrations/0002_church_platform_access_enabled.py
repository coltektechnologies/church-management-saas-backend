from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="church",
            name="platform_access_enabled",
            field=models.BooleanField(
                default=True,
                help_text="When False, church users cannot log in or use the API until re-enabled.",
            ),
        ),
    ]
