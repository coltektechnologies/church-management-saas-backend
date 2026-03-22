from django.db import migrations, models


class Migration(migrations.Migration):
    """
    State-only migration: notification_preference was already added by
    0004_add_notification_preference. This migration exists for the merge
    (0007) dependency chain. No database operations needed.
    """

    dependencies = [
        ("accounts", "0005_merge_20260218_1141"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
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
            ],
            database_operations=[],  # Column already exists from 0004_add_notification_preference
        ),
    ]
