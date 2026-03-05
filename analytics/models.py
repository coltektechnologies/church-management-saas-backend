"""
Minimal model so the Analytics app appears in Django admin.
Analytics data is served via the API (/api/analytics/); this model is for visibility and optional config.
"""

import uuid

from django.db import models


class AnalyticsDashboardInfo(models.Model):
    """Placeholder for admin visibility; optional cache TTL override (future use)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="Analytics & Dashboard")
    api_base_url = models.CharField(max_length=200, default="/api/analytics/")
    cache_ttl_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional: override default dashboard cache TTL (seconds). Leave blank for default (300).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_dashboard_info"
        verbose_name = "Analytics dashboard"
        verbose_name_plural = "Analytics dashboards"

    def __str__(self):
        return self.name
