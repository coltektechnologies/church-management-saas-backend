from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_subscription_plan_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptionplansetting",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="If checked, this plan is returned by the public registration/plans API and can be chosen at signup (when validation allows it).",
                verbose_name="Visible on site",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplansetting",
            name="plan_code",
            field=models.CharField(
                db_index=True,
                help_text="Unique ID stored on churches (e.g. FREE, BASIC, TECH). Must match Church.subscription_plan when assigning tenants.",
                max_length=20,
                unique=True,
                verbose_name="Plan code",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplansetting",
            name="label",
            field=models.CharField(
                blank=True,
                help_text="Name shown on pricing pages and admin.",
                max_length=120,
                verbose_name="Display label",
            ),
        ),
    ]
