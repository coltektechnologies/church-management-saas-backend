import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import escape

from accounts.models import User
from departments.models import MemberDepartment
from members.models import Member, MemberLocation
from notifications.dispatch import NotificationService
from notifications.models import NotificationBatch, SMSLog
from notifications.services.notification_manager import NotificationManager

logger = logging.getLogger(__name__)


def process_batch(batch_id):
    """Process a single notification batch"""
    try:
        batch = NotificationBatch.objects.get(id=batch_id)
        logger.info(f"Processing batch: {batch.name} (ID: {batch.id})")

        # Get recipients based on batch configuration
        recipients = _get_recipients(batch)
        batch.total_recipients = len(recipients)
        batch.save(update_fields=["total_recipients", "updated_at"])

        # Process notifications for each recipient
        successful = 0
        failed = 0
        notification_manager = NotificationManager()

        # For SMS with mNotify, we can send in bulk if it's a group message
        if (
            batch.send_sms
            and batch.target_members
            and isinstance(batch.target_members, dict)
            and "phone_numbers" in batch.target_members
        ):
            try:
                # Send batch SMS using mNotify
                phone_numbers = [
                    str(phone).strip()
                    for phone in batch.target_members["phone_numbers"]
                    if str(phone).strip()
                ]

                if phone_numbers:
                    # Create individual SMS log entries for tracking
                    for phone in phone_numbers:
                        try:
                            result = notification_manager._send_sms_notification(
                                church=batch.church,
                                recipient={"phone": phone},
                                message=batch.message,
                                group_ids=batch.target_members.get("group_ids"),
                            )
                            if result.get("success"):
                                successful += 1
                                logger.info(f"Sent SMS to {phone} via mNotify")
                            else:
                                failed += 1
                                logger.error(
                                    f'Failed to send SMS to {phone}: {result.get("error")}'
                                )
                        except Exception as e:
                            failed += 1
                            logger.exception(f"Error sending SMS to {phone}: {str(e)}")
            except Exception as e:
                failed = len(phone_numbers) if "phone_numbers" in locals() else 0
                logger.exception(f"Error sending batch SMS: {str(e)}")

        title = (batch.name or "").strip() or f"Message from {batch.church.name}"
        msg = batch.message or ""
        message_html = f"<p>{escape(msg)}</p>"

        # Process other notifications individually
        for recipient in recipients:
            try:
                # Skip SMS if already processed as batch
                skip_sms = (
                    batch.send_sms
                    and batch.target_members
                    and isinstance(batch.target_members, dict)
                    and "phone_numbers" in batch.target_members
                )

                recipient_ok = True

                if not skip_sms and batch.send_sms:
                    if recipient.get("phone"):
                        r = notification_manager.send_notification(
                            church=batch.church,
                            notification_type="SMS",
                            recipient=recipient,
                            message=msg,
                            context={},
                        )
                        recipient_ok = recipient_ok and bool(r.get("success"))
                    else:
                        recipient_ok = False

                if batch.send_email:
                    if recipient.get("email"):
                        r = notification_manager.send_notification(
                            church=batch.church,
                            notification_type="EMAIL",
                            recipient=recipient,
                            message=msg,
                            message_html=message_html,
                            subject=title[:200],
                            context={},
                        )
                        recipient_ok = recipient_ok and bool(r.get("success"))
                    else:
                        recipient_ok = False

                if batch.send_in_app:
                    if recipient.get("user"):
                        r = notification_manager.send_notification(
                            church=batch.church,
                            notification_type="IN_APP",
                            recipient=recipient,
                            title=title[:200],
                            message=msg,
                            context={},
                            created_by=batch.created_by,
                        )
                        recipient_ok = recipient_ok and bool(r.get("success"))
                    elif recipient.get("member"):
                        NotificationService.create_notification(
                            church=batch.church,
                            user=None,
                            member=recipient["member"],
                            title=title[:200],
                            message=msg,
                            priority="MEDIUM",
                            created_by=batch.created_by,
                        )
                    else:
                        recipient_ok = False

                if recipient_ok:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Error processing recipient {recipient}: {str(e)}")
                failed += 1

        # Update batch status (choices: PENDING, PROCESSING, COMPLETED, FAILED)
        batch.status = "COMPLETED"
        batch.successful_count = successful
        batch.failed_count = failed
        batch.completed_at = timezone.now()
        batch.save(
            update_fields=[
                "status",
                "successful_count",
                "failed_count",
                "completed_at",
                "updated_at",
            ]
        )

        logger.info(
            f"Completed batch {batch.name}: {successful} successful, {failed} failed"
        )

    except NotificationBatch.DoesNotExist:
        logger.error(f"Batch with ID {batch_id} does not exist")
    except Exception as e:
        logger.exception(f"Error processing batch {batch_id}: {str(e)}")
        try:
            batch = NotificationBatch.objects.get(id=batch_id)
            batch.status = "FAILED"
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "completed_at", "updated_at"])
        except Exception:
            pass


def _build_recipient_dict(member, loc):
    """Build recipient dict using Member + optional MemberLocation (phone/email) and system_user_id."""
    phone = (loc.phone_primary or "").strip() if loc else ""
    email = (loc.email or "").strip() if loc else ""
    user = None
    if member.system_user_id:
        user = User.objects.filter(id=member.system_user_id).first()
    return {
        "member": member,
        "name": member.get_full_name(),
        "phone": phone or None,
        "email": email or None,
        "user": user,
    }


def _get_recipients(batch):
    """Resolve members for a batch using MemberLocation and MemberDepartment (real schema)."""
    recipients = []

    # Handle direct phone numbers in target_members
    if (
        isinstance(batch.target_members, dict)
        and "phone_numbers" in batch.target_members
    ):
        for phone in batch.target_members["phone_numbers"]:
            if phone:
                recipients.append({"phone": str(phone).strip()})
        return recipients

    members_qs = None

    if batch.target_all_members:
        members_qs = Member.objects.filter(
            church=batch.church, deleted_at__isnull=True, is_active=True
        )
    elif batch.target_departments and isinstance(batch.target_departments, list):
        member_ids = (
            MemberDepartment.objects.filter(
                department_id__in=batch.target_departments,
                member__church=batch.church,
                member__deleted_at__isnull=True,
                member__is_active=True,
                deleted_at__isnull=True,
            )
            .values_list("member_id", flat=True)
            .distinct()
        )
        members_qs = Member.objects.filter(
            id__in=member_ids,
            church=batch.church,
            deleted_at__isnull=True,
            is_active=True,
        )
    elif isinstance(batch.target_members, list) and batch.target_members:
        members_qs = Member.objects.filter(
            id__in=batch.target_members,
            church=batch.church,
            deleted_at__isnull=True,
            is_active=True,
        )

    if not members_qs:
        return recipients

    members = list(members_qs)
    if not members:
        return recipients

    loc_map = {
        loc.member_id: loc
        for loc in MemberLocation.objects.filter(
            member_id__in=[m.id for m in members], deleted_at__isnull=True
        )
    }

    seen = set()
    for member in members:
        if member.id in seen:
            continue
        seen.add(member.id)
        loc = loc_map.get(member.id)
        recipients.append(_build_recipient_dict(member, loc))

    return recipients


class Command(BaseCommand):
    help = "Process pending notification batches"

    def handle(self, *args, **options):
        # Get batches that are PENDING and scheduled for now or in the past
        now = timezone.now()
        pending_batches = NotificationBatch.objects.filter(
            status="PENDING", scheduled_for__lte=now
        )

        if not pending_batches.exists():
            self.stdout.write(
                self.style.SUCCESS("No pending notification batches to process")
            )
            return

        for batch in pending_batches:
            self.stdout.write(f"Processing batch: {batch.name} (ID: {batch.id})")

            try:
                # Update status to PROCESSING
                batch.status = "PROCESSING"
                batch.started_at = now
                batch.save(update_fields=["status", "started_at", "updated_at"])

                # Process the batch using the process_batch function
                process_batch(batch.id)

            except Exception as e:
                self._handle_batch_error(batch, e)

    def _handle_batch_error(self, batch, exception):
        self.stderr.write(f"Error processing batch {batch.id}: {str(exception)}")
        batch.status = "FAILED"
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at", "updated_at"])
