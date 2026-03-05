from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_church_subscription_plan"),
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
                help_text="Preferred method for receiving notifications",
            ),
        ),
    ]
