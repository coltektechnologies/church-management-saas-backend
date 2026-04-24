from django.contrib import admin

from .models import AgentAlert, AgentLog


@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "agent_name",
        "action",
        "status",
        "duration_ms",
        "church",
    )
    list_filter = ("status", "agent_name", "triggered_by")
    search_fields = ("agent_name", "action", "error")
    readonly_fields = ("id", "created_at")


@admin.register(AgentAlert)
class AgentAlertAdmin(admin.ModelAdmin):
    list_display = ("created_at", "agent_name", "alert_type", "severity", "church")
    list_filter = ("severity", "alert_type", "agent_name")
    search_fields = ("message", "agent_name")
    readonly_fields = ("id", "created_at")
