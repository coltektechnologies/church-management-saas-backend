import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...models import SMSDeliveryReport, SMSLog
from ...services.mnotify_service import MNotifyService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check and update delivery status of sent SMS messages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Check messages from the last N hours (default: 24)",
        )
        parser.add_argument(
            "--retry-failed", action="store_true", help="Retry sending failed messages"
        )
        parser.add_argument(
            "--message-ids",
            type=str,
            help="Comma-separated list of message IDs to check (overrides --hours)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        retry_failed = options["retry_failed"]
        message_ids = options.get("message_ids")

        if message_ids:
            # Get specific messages by ID
            message_id_list = [mid.strip() for mid in message_ids.split(",")]
            sms_logs = SMSLog.objects.filter(
                message_id__in=message_id_list
            ).select_related("delivery_report")
        else:
            # Get pending or failed messages within the time threshold
            time_threshold = timezone.now() - timezone.timedelta(hours=hours)
            sms_logs = SMSLog.objects.filter(
                created_at__gte=time_threshold,
                direction="OUTBOUND",  # Only check outbound messages
            ).select_related("delivery_report")

            if not retry_failed:
                sms_logs = sms_logs.filter(delivery_report__isnull=True)

        self.stdout.write(f"Checking status for {sms_logs.count()} SMS messages...")

        mnotify = MNotifyService()
        updated_count = 0
        failed_count = 0

        for sms_log in sms_logs:
            try:
                with transaction.atomic():
                    # Get or create delivery report
                    report, created = SMSDeliveryReport.objects.get_or_create(
                        sms_log=sms_log, defaults={"status": "pending"}
                    )

                    # Skip if already delivered and not retrying
                    if (
                        not created
                        and report.status == "delivered"
                        and not retry_failed
                    ):
                        continue

                    # Skip if no gateway message ID is available
                    if not sms_log.gateway_message_id:
                        logger.warning(
                            f"Skipping SMS log {sms_log.id}: No gateway message ID"
                        )
                        failed_count += 1
                        continue

                    # Get status from provider
                    status = mnotify.check_delivery_status(sms_log.gateway_message_id)

                    if status and status.get("success", False):
                        # Update SMS log with delivery status
                        if status["status"] == "delivered" and not sms_log.delivered_at:
                            sms_log.delivered_at = timezone.now()
                            sms_log.status = "DELIVERED"
                            sms_log.save(
                                update_fields=["delivered_at", "status", "updated_at"]
                            )

                        # Update delivery report
                        report.status = status["status"]
                        report.status_code = status.get("status_code")
                        report.status_message = status.get("message")

                        if status["status"] == "delivered":
                            report.delivery_timestamp = timezone.now()

                        report.save()
                        updated_count += 1

                        # Log the update
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated SMS {sms_log.id}: {report.get_status_display()}"
                            )
                        )
                    else:
                        error_msg = (
                            status.get("message", "Unknown error")
                            if status
                            else "No status returned"
                        )
                        self.stdout.write(
                            self.style.WARNING(
                                f"Failed to check status for SMS {sms_log.id}: {error_msg}"
                            )
                        )
                        failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Error checking status for SMS {getattr(sms_log, 'id', 'unknown')}: {str(e)}",
                    exc_info=True,
                )
                self.stdout.write(
                    self.style.ERROR(
                        f"Error checking status for SMS {getattr(sms_log, 'id', 'unknown')}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Updated: {updated_count}, Failed: {failed_count}"
            )
        )

    def _map_status(self, provider_status):
        """Map provider status to our status"""
        provider_status = (provider_status or "").lower()
        if "delivered" in provider_status:
            return "delivered"
        elif "failed" in provider_status or "rejected" in provider_status:
            return "failed"
        elif "pending" in provider_status:
            return "pending"
        return "undelivered"
