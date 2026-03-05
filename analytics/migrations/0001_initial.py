# Generated migration for analytics app

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AnalyticsDashboardInfo",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.CharField(default="Analytics & Dashboard", max_length=100),
                ),
                (
                    "api_base_url",
                    models.CharField(default="/api/analytics/", max_length=200),
                ),
                (
                    "cache_ttl_seconds",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Optional: override default dashboard cache TTL (seconds). Leave blank for default (300).",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Analytics dashboard",
                "verbose_name_plural": "Analytics dashboards",
                "db_table": "analytics_dashboard_info",
            },
        ),
    ]
