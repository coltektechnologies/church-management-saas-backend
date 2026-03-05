"""
Report models: cache and scheduled reports.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User


class ReportCache(models.Model):
    """
    Cached report result to avoid recomputing heavy reports.
    Key is built from report_type + church_id + date_range + filter_hash.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="report_caches",
        db_column="church_id",
    )

    report_type = models.CharField(max_length=80, db_index=True)
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)

    # Serialized result (JSON)
    result_data = models.JSONField(default=dict)

    # Optional file storage for exported formats (path or null)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    format = models.CharField(max_length=20, blank=True, null=True)  # pdf, xlsx, csv

    # Date range this cache is valid for (for invalidation)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "report_caches"
        verbose_name = _("Report Cache")
        verbose_name_plural = _("Report Caches")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "report_type"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.report_type} ({self.church.name})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class ScheduledReport(models.Model):
    """
    User-defined scheduled report (e.g. weekly member summary, monthly finance).
    """

    FREQUENCY_CHOICES = [
        ("DAILY", _("Daily")),
        ("WEEKLY", _("Weekly")),
        ("BIWEEKLY", _("Bi-weekly")),
        ("MONTHLY", _("Monthly")),
        ("QUARTERLY", _("Quarterly")),
    ]

    REPORT_TYPE_CHOICES = [
        ("members", _("Members Report")),
        ("members_growth", _("Members Growth")),
        ("members_demographics", _("Members Demographics")),
        ("departments", _("Departments Report")),
        ("finance_income", _("Finance - Income")),
        ("finance_expenses", _("Finance - Expenses")),
        ("finance_balance_sheet", _("Finance - Balance Sheet")),
        ("finance_cash_flow", _("Finance - Cash Flow")),
        ("announcements", _("Announcements Report")),
        ("audit_trail", _("Audit Trail")),
        ("custom", _("Custom Report")),
    ]

    FORMAT_CHOICES = [
        ("json", "JSON"),
        ("pdf", "PDF"),
        ("xlsx", "Excel"),
        ("csv", "CSV"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="scheduled_reports",
        db_column="church_id",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_reports",
    )

    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="pdf")

    # Optional: custom report config (for report_type=custom)
    custom_config = models.JSONField(default=dict, blank=True)

    # Recipients (emails for delivery)
    recipient_emails = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of email addresses to receive the report"),
    )

    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduled_reports"
        verbose_name = _("Scheduled Report")
        verbose_name_plural = _("Scheduled Reports")
        ordering = ["next_run_at", "name"]
        indexes = [
            models.Index(fields=["church", "is_active"]),
            models.Index(fields=["next_run_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"
