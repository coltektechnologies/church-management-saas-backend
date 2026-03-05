from django.contrib import admin

from .models import ReportCache, ScheduledReport


@admin.register(ReportCache)
class ReportCacheAdmin(admin.ModelAdmin):
    list_display = ["cache_key", "church", "report_type", "expires_at", "created_at"]
    list_filter = ["report_type", "church"]
    search_fields = ["cache_key", "report_type"]
    readonly_fields = ["id", "cache_key", "result_data", "created_at", "expires_at"]


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "church",
        "report_type",
        "frequency",
        "format",
        "is_active",
        "next_run_at",
        "last_run_at",
    ]
    list_filter = ["report_type", "frequency", "is_active", "church"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at", "last_run_at", "next_run_at"]
