from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_merge_20260218_1141"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="notification_preference",
            field=models.CharField(
                choices=[
                    ("email", "Email Only"),
                    ("sms", "SMS Only"),
                    ("both", "Both Email and SMS"),
                    ("none", "No Notifications"),
                ],
                default="email",
                max_length=10,
                help_text="Preferred notification method",
            ),
        ),
    ]
