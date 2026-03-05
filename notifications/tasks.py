import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, ExpressionWrapper, F, Q, fields
from django.db.models.functions import TruncDay, TruncHour
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_notification_batch(self, batch_id):
    """Process notification batch in background"""
    from members.models import Member, MemberDepartment

    from .models import Notification, NotificationBatch
    from .services import EmailService, NotificationService, SMSService

    try:
        batch = NotificationBatch.objects.get(id=batch_id)

        # Update status
        batch.status = "PROCESSING"
        batch.started_at = timezone.now()
        batch.save()

        # Get target members
        members = []

        if batch.target_all_members:
            members = Member.objects.filter(
                church=batch.church, deleted_at__isnull=True
            )
        elif batch.target_departments:
            members = Member.objects.filter(
                memberdepartment__department_id__in=batch.target_departments,
                church=batch.church,
                deleted_at__isnull=True,
            ).distinct()
        elif batch.target_members:
            members = Member.objects.filter(
                id__in=batch.target_members,
                church=batch.church,
                deleted_at__isnull=True,
            )

        batch.total_recipients = members.count()
        batch.save()

        # Send notifications
        for member in members:
            try:
                # In-app notification
                if batch.send_in_app and hasattr(member, "user"):
                    NotificationService.create_notification(
                        church=batch.church,
                        user=member.user,
                        title=f"Message from {batch.church.name}",
                        message=batch.message,
                        priority="MEDIUM",
                    )

                # SMS
                if batch.send_sms and hasattr(member, "location"):
                    SMSService.send_sms(
                        church=batch.church,
                        phone_number=member.location.phone_primary,
                        message=batch.message,
                        member=member,
                    )

                # Email
                if (
                    batch.send_email
                    and hasattr(member, "location")
                    and member.location.email
                ):
                    EmailService.send_email(
                        church=batch.church,
                        email_address=member.location.email,
                        subject=f"Message from {batch.church.name}",
                        message_html=f"<p>{batch.message}</p>",
                        member=member,
                    )

                batch.successful_count += 1

            except Exception as e:
                logger.error(f"Failed to send to member {member.id}: {e}")
                batch.failed_count += 1

            batch.save()

        # Mark as completed
        batch.status = "COMPLETED"
        batch.completed_at = timezone.now()
        batch.save()

        return f"Batch {batch_id} processed: {batch.successful_count} successful, {batch.failed_count} failed"

    except Exception as exc:
        logger.error(f"Batch processing failed: {exc}")

        try:
            batch = NotificationBatch.objects.get(id=batch_id)
            batch.status = "FAILED"
            batch.save()
        except:
            pass

        # Retry
        raise self.retry(exc=exc, countdown=60)


@shared_task
def process_scheduled_notifications():
    """Process all notifications scheduled for now"""
    from .models import EmailLog, Notification, SMSLog
    from .services import EmailService, SMSService

    now = timezone.now()

    # Process in-app notifications
    pending_notifications = Notification.objects.filter(
        status="PENDING", scheduled_for__lte=now
    )

    for notification in pending_notifications:
        notification.status = "SENT"
        notification.sent_at = now
        notification.save()

    # Process SMS
    pending_sms = SMSLog.objects.filter(status="PENDING", scheduled_for__lte=now)

    for sms in pending_sms:
        SMSService._send_via_gateway(sms)

    # Process emails
    pending_emails = EmailLog.objects.filter(status="PENDING", scheduled_for__lte=now)

    for email in pending_emails:
        EmailService._send_via_gateway(email)

    logger.info(
        f"Processed {pending_notifications.count()} notifications, "
        f"{pending_sms.count()} SMS, {pending_emails.count()} emails"
    )


@shared_task
def send_service_reminders():
    """Send service reminders to all churches"""
    from accounts.models import Church
    from members.models import Member

    from .services import SMSService

    churches = Church.objects.filter(deleted_at__isnull=True)

    for church in churches:
        members = Member.objects.filter(
            church=church, membership_status="ACTIVE", deleted_at__isnull=True
        ).select_related("location")

        message = f"Hello, worship with us tomorrow at {church.name}. See you there!"

        for member in members:
            if hasattr(member, "location") and member.location.phone_primary:
                SMSService.send_sms(
                    church=church,
                    phone_number=member.location.phone_primary,
                    message=message,
                    member=member,
                )

    logger.info(f"Service reminders sent for {churches.count()} churches")


@shared_task
def send_birthday_greetings():
    """Send birthday greetings to members"""
    from members.models import Member

    from .services import SMSService

    today = datetime.now().date()

    # Find members with birthdays today
    members = Member.objects.filter(
        date_of_birth__month=today.month,
        date_of_birth__day=today.day,
        deleted_at__isnull=True,
    ).select_related("church", "location")

    for member in members:
        if hasattr(member, "location") and member.location.phone_primary:
            message = (
                f"Happy Birthday {member.first_name}! "
                f"May God bless you abundantly. - {member.church.name} Family"
            )

            SMSService.send_sms(
                church=member.church,
                phone_number=member.location.phone_primary,
                message=message,
                member=member,
            )

    logger.info(f"Birthday greetings sent to {members.count()} members")


@shared_task
def send_sms_async(church_id, phone_number, message, member_id=None):
    """Send SMS asynchronously"""
    from accounts.models import Church
    from members.models import Member

    from .services import SMSService

    church = Church.objects.get(id=church_id)
    member = Member.objects.get(id=member_id) if member_id else None

    return SMSService.send_sms(church, phone_number, message, member)


@shared_task
def send_email_async(church_id, email_address, subject, message_html, member_id=None):
    """Send email asynchronously"""
    from .services import EmailService

    EmailService.send_email(
        church_id=church_id,
        email_address=email_address,
        subject=subject,
        message_html=message_html,
        member_id=member_id,
    )


@shared_task
def check_sms_delivery_status(hours=24, message_ids=None, retry_failed=False):
    """
    Check and update delivery status of sent SMS messages

    Args:
        hours: Check messages from the last N hours
        message_ids: Comma-separated list of message IDs to check (overrides hours)
        retry_failed: Whether to retry failed messages
    """
    from .management.commands.check_sms_delivery_status import Command
    from .models import SMSDeliveryReport, SMSLog
    from .services import SMSService

    # Call the management command
    cmd = Command()
    options = {"hours": hours, "retry_failed": retry_failed, "message_ids": message_ids}
    cmd.handle(**options)


@shared_task
def retry_failed_sms(report_id):
    """
    Retry sending a failed SMS message

    Args:
        report_id: ID of the SMSDeliveryReport to retry
    """
    from .models import SMSDeliveryReport, SMSLog
    from .services import SMSService

    try:
        report = SMSDeliveryReport.objects.select_related("sms_log").get(id=report_id)

        # Only retry if status is failed and retry count is less than max
        if report.status != "failed" or report.retry_count >= 3:
            return

        # Update status to pending
        report.status = "pending"
        report.save(update_fields=["status", "updated_at"])

        # Resend the SMS
        sms_log = report.sms_log
        result = SMSService.send_sms(
            church_id=sms_log.church_id,
            phone_number=sms_log.phone_number,
            message=sms_log.message,
            member_id=sms_log.member_id if sms_log.member_id else None,
        )

        # Update the report with the result
        if result.get("success"):
            report.status = "pending"  # Will be updated on next status check
            report.status_message = "Retry initiated"
        else:
            report.status = "failed"
            report.status_message = (
                f"Retry failed: {result.get('message', 'Unknown error')}"
            )

        report.retry_count = F("retry_count") + 1
        report.last_retry = timezone.now()
        report.save(
            update_fields=[
                "status",
                "status_message",
                "retry_count",
                "last_retry",
                "updated_at",
            ]
        )

    except SMSDeliveryReport.DoesNotExist:
        logger.error(f"SMSDeliveryReport {report_id} not found")
    except Exception as e:
        logger.error(f"Error retrying SMS {report_id}: {str(e)}", exc_info=True)


@shared_task
def send_sms_delivery_report(days=1, frequency="daily", recipient_emails=None):
    """
    Generate and send SMS delivery report

    Args:
        days: Number of days to include in the report
        frequency: 'daily' or 'weekly'
        recipient_emails: Comma-separated list of email addresses to send the report to
    """
    from django.contrib.sites.models import Site

    from .models import SMSDeliveryReport, SMSLog

    # Get date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    # Get report data
    reports = SMSDeliveryReport.objects.filter(
        created_at__gte=start_date, created_at__lte=end_date
    ).select_related("sms_log")

    # Aggregate data
    total_messages = reports.count()
    status_counts = reports.values("status").annotate(count=Count("id"))

    # Daily message counts
    daily_counts = (
        reports.annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(
            count=Count("id"),
            delivered=Count("id", filter=Q(status="delivered")),
            failed=Count("id", filter=Q(status="failed")),
            pending=Count("id", filter=Q(status="pending")),
        )
        .order_by("day")
    )

    # Format data for template
    report_data = {
        "start_date": start_date,
        "end_date": end_date,
        "total_messages": total_messages,
        "status_counts": status_counts,
        "daily_counts": daily_counts,
        "site_name": Site.objects.get_current().name,
        "frequency": frequency.capitalize(),
    }

    # Render email content
    subject = (
        f"{report_data['site_name']} - {frequency.capitalize()} SMS Delivery Report"
    )
    html_message = render_to_string(
        "notifications/emails/sms_delivery_report.html", report_data
    )
    plain_message = strip_tags(html_message)

    # Get recipient emails
    if not recipient_emails:
        recipient_emails = [admin[1] for admin in settings.ADMINS]
    elif isinstance(recipient_emails, str):
        recipient_emails = [email.strip() for email in recipient_emails.split(",")]

    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        html_message=html_message,
        fail_silently=False,
    )

    return f"Sent {frequency} SMS delivery report to {', '.join(recipient_emails)}"


@shared_task
def cleanup_old_sms_reports(days_to_keep=90):
    """
    Clean up old SMS delivery reports

    Args:
        days_to_keep: Number of days to keep reports (default: 90)
    """
    from .models import SMSDeliveryReport

    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    deleted_count, _ = SMSDeliveryReport.objects.filter(
        created_at__lt=cutoff_date
    ).delete()

    return f"Deleted {deleted_count} old SMS delivery reports"
