from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_subscription_plan_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="church",
            name="last_subscription_reminder_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last time platform staff sent a subscription/trial reminder email from admin.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplansetting",
            name="email_monthly_quota",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Optional monthly outbound email cap per church (blank = no platform cap).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplansetting",
            name="enforce_email_quota",
            field=models.BooleanField(
                default=False,
                help_text="When True, operational code may enforce email_monthly_quota (if implemented).",
            ),
        ),
    ]
