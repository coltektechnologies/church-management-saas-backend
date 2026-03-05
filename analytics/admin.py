from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AnalyticsDashboardInfo


@admin.register(AnalyticsDashboardInfo)
class AnalyticsDashboardInfoAdmin(admin.ModelAdmin):
    list_display = ["name", "api_link", "cache_ttl_seconds", "updated_at"]
    readonly_fields = [
        "id",
        "api_base_url",
        "endpoints_help",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": ("name", "api_base_url", "cache_ttl_seconds"),
            },
        ),
        (
            "API endpoints",
            {
                "fields": ("endpoints_help",),
                "description": "Use these endpoints with your JWT token (Authorization: Bearer <token>).",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "updated_at"),
            },
        ),
    )

    def api_link(self, obj):
        url = obj.api_base_url or "/api/analytics/"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{} (open API base)</a>',
            url,
            url,
        )

    api_link.short_description = "API base"

    def endpoints_help(self, obj):
        return mark_safe(
            "<ul>"
            "<li><b>Dashboard:</b> /api/analytics/dashboard/secretariat/ , "
            "/api/analytics/dashboard/treasury/ , "
            "/api/analytics/dashboard/department/&lt;uuid&gt;/ , "
            "/api/analytics/dashboard/admin/</li>"
            "<li><b>Analytics:</b> /api/analytics/members/stats/ , "
            "/api/analytics/finance/trends/ , /api/analytics/finance/kpis/ , "
            "/api/analytics/announcements/stats/ , "
            "/api/analytics/departments/performance/</li>"
            "<li>Full API docs: <a href='/api/docs/' target='_blank'>/api/docs/</a> (Swagger)</li>"
            "</ul>"
        )

    endpoints_help.short_description = "Available endpoints"
