from django.db import migrations, models


def seed_subscription_plan_settings(apps, schema_editor):
    SubscriptionPlanSetting = apps.get_model("accounts", "SubscriptionPlanSetting")
    rows = [
        {
            "plan_code": "TRIAL",
            "label": "Free Trial (30 Days)",
            "sort_order": 0,
            "max_users_default": 50,
            "sms_monthly_quota": 200,
            "enforce_sms_quota": False,
            "notes": "Seeded default; edit in Subscription plan defaults.",
        },
        {
            "plan_code": "FREE",
            "label": "Free Forever (1 Admin)",
            "sort_order": 1,
            "max_users_default": 1,
            "sms_monthly_quota": 50,
            "enforce_sms_quota": False,
            "notes": "",
        },
        {
            "plan_code": "BASIC",
            "label": "Basic",
            "sort_order": 2,
            "max_users_default": 5,
            "sms_monthly_quota": 1000,
            "enforce_sms_quota": False,
            "notes": "",
        },
        {
            "plan_code": "PREMIUM",
            "label": "Premium",
            "sort_order": 3,
            "max_users_default": 500,
            "sms_monthly_quota": None,
            "enforce_sms_quota": False,
            "notes": "No SMS cap by default; set quota if you need to cap usage.",
        },
        {
            "plan_code": "ENTERPRISE",
            "label": "Enterprise",
            "sort_order": 4,
            "max_users_default": 9999,
            "sms_monthly_quota": None,
            "enforce_sms_quota": False,
            "notes": "",
        },
    ]
    for row in rows:
        code = row.pop("plan_code")
        SubscriptionPlanSetting.objects.update_or_create(plan_code=code, defaults=row)


def unseed_subscription_plan_settings(apps, schema_editor):
    SubscriptionPlanSetting = apps.get_model("accounts", "SubscriptionPlanSetting")
    SubscriptionPlanSetting.objects.filter(
        plan_code__in=["TRIAL", "FREE", "BASIC", "PREMIUM", "ENTERPRISE"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_church_platform_access_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlanSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "plan_code",
                    models.CharField(
                        choices=[
                            ("FREE", "FREE"),
                            ("TRIAL", "TRIAL"),
                            ("BASIC", "BASIC"),
                            ("PREMIUM", "PREMIUM"),
                            ("ENTERPRISE", "ENTERPRISE"),
                        ],
                        db_index=True,
                        max_length=20,
                        unique=True,
                        verbose_name="Plan code",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        help_text="Optional friendly name shown in admin.",
                        max_length=120,
                        verbose_name="Display label",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "max_users_default",
                    models.PositiveIntegerField(
                        default=50,
                        help_text="Default seat limit for new or upgraded churches on this plan.",
                    ),
                ),
                (
                    "sms_monthly_quota",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Optional monthly SMS segments cap per church (blank = no platform cap).",
                        null=True,
                    ),
                ),
                (
                    "enforce_sms_quota",
                    models.BooleanField(
                        default=False,
                        help_text="When True, operational code may enforce sms_monthly_quota (if implemented).",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Subscription plan default",
                "verbose_name_plural": "Subscription plan defaults",
                "db_table": "subscription_plan_settings",
                "ordering": ["sort_order", "plan_code"],
            },
        ),
        migrations.RunPython(
            seed_subscription_plan_settings, unseed_subscription_plan_settings
        ),
    ]
