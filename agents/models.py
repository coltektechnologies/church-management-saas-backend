import uuid

from django.db import models

from accounts.models import Church


class AgentLog(models.Model):
    """Append-only log row from churchagents / MCP automation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=255)
    status = models.CharField(max_length=64, db_index=True)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    church = models.ForeignKey(
        Church,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_logs",
    )
    triggered_by = models.CharField(max_length=64, default="SCHEDULED")
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "agent_logs"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.agent_name} {self.action} {self.status}"


class AgentAlert(models.Model):
    """Alert raised by agents for dashboard / ops review."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=255, db_index=True)
    alert_type = models.CharField(max_length=128, db_index=True)
    message = models.TextField()
    severity = models.CharField(max_length=32, default="WARNING", db_index=True)
    church = models.ForeignKey(
        Church,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "agent_alerts"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.severity} {self.alert_type}: {self.message[:80]}"
