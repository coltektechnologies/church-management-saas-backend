import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.tasks import send_sms_delivery_report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send scheduled SMS delivery reports"

    def add_arguments(self, parser):
        parser.add_argument(
            "--frequency",
            type=str,
            choices=["daily", "weekly"],
            default="daily",
            help="Report frequency: daily or weekly (default: daily)",
        )
        parser.add_argument(
            "--recipients",
            type=str,
            help="Comma-separated list of email addresses to receive the report",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of days to include in the report (default: 1 for daily, 7 for weekly)",
        )

    def handle(self, *args, **options):
        frequency = options["frequency"]
        recipients = options.get("recipients")
        days = options["days"]

        # Set default days based on frequency if not specified
        if frequency == "weekly" and days == 1:
            days = 7

        self.stdout.write(
            f"Sending {frequency} SMS delivery report for the last {days} days..."
        )

        try:
            result = send_sms_delivery_report.delay(
                days=days, frequency=frequency, recipient_emails=recipients
            )

            # Wait for the task to complete with a timeout
            try:
                report_result = result.get(timeout=30)  # 30 seconds timeout
                self.stdout.write(self.style.SUCCESS(report_result))
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"Task timed out or failed: {str(e)}")
                )
                logger.error(
                    f"Error sending SMS delivery report: {str(e)}", exc_info=True
                )

        except Exception as e:
            error_msg = f"Failed to send SMS delivery report: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
