from django.db import migrations


def create_default_dashboard(apps, schema_editor):
    AnalyticsDashboardInfo = apps.get_model("analytics", "AnalyticsDashboardInfo")
    if not AnalyticsDashboardInfo.objects.exists():
        AnalyticsDashboardInfo.objects.create(
            name="Analytics & Dashboard",
            api_base_url="/api/analytics/",
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_dashboard, noop),
    ]
