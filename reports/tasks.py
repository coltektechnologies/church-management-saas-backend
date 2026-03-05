"""
Celery tasks for scheduled report generation.
"""

from datetime import timedelta

from django.utils import timezone

from church_saas.celery import app
from reports.models import ScheduledReport
from reports.services import ReportGenerationService
from reports.services.exporters import CSVExporter, ExcelExporter, PDFExporter


def compute_next_run(scheduled: ScheduledReport):
    """Set next_run_at from frequency and last_run_at (or now)."""
    now = timezone.now()
    base = scheduled.last_run_at or now
    if scheduled.frequency == "DAILY":
        scheduled.next_run_at = base + timedelta(days=1)
    elif scheduled.frequency == "WEEKLY":
        scheduled.next_run_at = base + timedelta(weeks=1)
    elif scheduled.frequency == "BIWEEKLY":
        scheduled.next_run_at = base + timedelta(weeks=2)
    elif scheduled.frequency == "MONTHLY":
        # Simple: +1 month (approx)
        next_month = base.month + 1
        year = base.year
        if next_month > 12:
            next_month -= 12
            year += 1
        try:
            scheduled.next_run_at = base.replace(year=year, month=next_month)
        except ValueError:
            scheduled.next_run_at = base + timedelta(days=30)
    elif scheduled.frequency == "QUARTERLY":
        scheduled.next_run_at = base + timedelta(days=90)
    else:
        scheduled.next_run_at = now + timedelta(days=1)


@app.task(bind=True)
def run_scheduled_reports(self):
    """
    Celery Beat task: find scheduled reports where next_run_at <= now, generate report,
    then update last_run_at and next_run_at. Optionally email recipients.
    """
    now = timezone.now()
    due = list(
        ScheduledReport.objects.filter(
            is_active=True,
            next_run_at__lte=now,
            next_run_at__isnull=False,
        ).select_related("church", "created_by")
    )
    for scheduled in due:
        try:
            run_single_scheduled_report(str(scheduled.id))
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "Scheduled report %s failed: %s", scheduled.id, e
            )
    return {"processed": len(due)}


def run_single_scheduled_report(scheduled_id: str):
    """
    Generate one scheduled report, update last/next run, optionally send email.
    Can be called from Celery or from code.
    """
    scheduled = ScheduledReport.objects.select_related("church").get(id=scheduled_id)
    church = scheduled.church
    # Default date range: previous period (e.g. last month for monthly)
    today = timezone.localdate()
    if scheduled.frequency == "MONTHLY":
        date_to = today.replace(day=1) - timedelta(days=1)
        date_from = date_to.replace(day=1)
    elif scheduled.frequency == "WEEKLY":
        date_to = today - timedelta(days=today.weekday() + 1)
        date_from = date_to - timedelta(days=6)
    elif scheduled.frequency == "DAILY":
        date_to = today - timedelta(days=1)
        date_from = date_to
    else:
        date_from = today - timedelta(days=30)
        date_to = today

    service = ReportGenerationService(church)
    result = service.get_report(
        report_type=scheduled.report_type,
        date_from=date_from,
        date_to=date_to,
        filters=scheduled.custom_config or {},
        use_cache=False,
    )

    # Export to buffer if format is file
    buffer = None
    filename = None
    content_type = None
    if scheduled.format in ("pdf", "xlsx", "csv"):
        if scheduled.format == "pdf":
            exporter = PDFExporter()
        elif scheduled.format == "xlsx":
            exporter = ExcelExporter()
        else:
            exporter = CSVExporter()
        buffer = exporter.export(result, title=scheduled.name)
        filename = f"{scheduled.name}_{date_from}_{date_to}.{exporter.file_extension}"
        content_type = exporter.content_type

    # Update last_run_at and next_run_at
    scheduled.last_run_at = timezone.now()
    compute_next_run(scheduled)
    scheduled.save(update_fields=["last_run_at", "next_run_at", "updated_at"])

    # Optional: send email to recipient_emails with attachment
    if scheduled.recipient_emails and buffer and filename:
        try:
            from django.core.mail import EmailMessage

            buffer.seek(0)
            email = EmailMessage(
                subject=f"Report: {scheduled.name}",
                body=f"Please find attached the report: {scheduled.name} for period {date_from} to {date_to}.",
                from_email=None,  # use DEFAULT_FROM_EMAIL
                to=scheduled.recipient_emails,
            )
            email.attach(filename, buffer.read(), content_type)
            email.send(fail_silently=True)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to email scheduled report %s: %s", scheduled.id, e
            )
