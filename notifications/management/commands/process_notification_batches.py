import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from members.models import Member
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

                if not skip_sms and batch.send_sms and recipient.get("phone"):
                    notification_manager.send_notification(
                        church=batch.church,
                        notification_type="SMS",
                        recipient=recipient,
                        message=batch.message,
                        context={},
                    )

                if batch.send_email and recipient.get("email"):
                    notification_manager.send_notification(
                        church=batch.church,
                        notification_type="EMAIL",
                        recipient=recipient,
                        message=batch.message,
                        context={},
                    )

                if batch.send_in_app and recipient.get("user"):
                    notification_manager.send_notification(
                        church=batch.church,
                        notification_type="IN_APP",
                        recipient=recipient,
                        message=batch.message,
                        context={},
                    )

                successful += 1

            except Exception as e:
                logger.error(f"Error processing recipient {recipient}: {str(e)}")
                failed += 1

        # Update batch status
        batch.status = "COMPLETED" if failed == 0 else "PARTIALLY_COMPLETED"
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


def _get_recipients(batch):
    """Get recipients based on batch configuration"""
    recipients = []

    # Handle direct phone numbers in target_members
    if (
        isinstance(batch.target_members, dict)
        and "phone_numbers" in batch.target_members
    ):
        for phone in batch.target_members["phone_numbers"]:
            if phone:
                recipients.append({"phone": str(phone).strip()})

    # Handle member IDs
    elif isinstance(batch.target_members, list) and batch.target_members:
        members = Member.objects.filter(
            id__in=batch.target_members, church=batch.church, is_active=True
        ).select_related("user")

        for member in members:
            recipient = {
                "member": member,
                "name": member.full_name or str(member),
                "phone": member.phone_number,
                "email": member.email,
            }
            if member.user:
                recipient["user"] = member.user
                recipient["email"] = member.user.email
            recipients.append(recipient)

    # Handle target all members
    elif batch.target_all_members:
        members = Member.objects.filter(
            church=batch.church, is_active=True
        ).select_related("user")

        for member in members:
            recipient = {
                "member": member,
                "name": member.full_name or str(member),
                "phone": member.phone_number,
                "email": member.email,
            }
            if member.user:
                recipient["user"] = member.user
                recipient["email"] = member.user.email
            recipients.append(recipient)

    # Handle target departments
    elif batch.target_departments and isinstance(batch.target_departments, list):
        from departments.models import DepartmentMember

        department_members = DepartmentMember.objects.filter(
            department_id__in=batch.target_departments,
            member__church=batch.church,
            member__is_active=True,
        ).select_related("member", "member__user")

        for dm in department_members:
            member = dm.member
            recipient = {
                "member": member,
                "name": member.full_name or str(member),
                "phone": member.phone_number,
                "email": member.email,
            }
            if member.user:
                recipient["user"] = member.user
                recipient["email"] = member.user.email

            # Avoid duplicates
            if not any(r.get("member") == member for r in recipients):
                recipients.append(recipient)

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

    def _get_recipients(self, batch):
        """Get recipients based on batch configuration"""
        from accounts.models import User
        from members.models import Member, MemberLocation

        recipients = []

        # Handle direct phone numbers in target_members
        if (
            isinstance(batch.target_members, dict)
            and "phone_numbers" in batch.target_members
        ):
            for phone in batch.target_members["phone_numbers"]:
                recipients.append(
                    {
                        "id": f"phone_{phone}",
                        "name": f"Phone: {phone}",
                        "phone": str(phone).strip(),
                    }
                )
            return recipients

        # Get members based on batch configuration
        members = Member.objects.filter(church=batch.church)

        if not batch.target_all_members:
            if batch.target_departments:
                members = members.filter(departments__in=batch.target_departments)
            if batch.target_members and isinstance(batch.target_members, list):
                members = members.filter(id__in=batch.target_members)

        # Get member locations in a single query
        member_ids = list(members.values_list("id", flat=True))
        member_locations = {
            loc.member_id: loc
            for loc in MemberLocation.objects.filter(member_id__in=member_ids)
        }

        # Convert members to recipient format
        for member in members:
            location = member_locations.get(member.id)

            # Skip if no contact method is available for the selected channels
            if batch.send_sms and (not location or not location.phone_primary):
                continue

            if batch.send_email and not location.email:
                continue

            recipient = {
                "id": str(
                    member.id
                ),  # Ensure ID is string to avoid UUID serialization issues
                "name": member.get_full_name(),
                "email": location.email if location else None,
                "phone": (
                    str(location.phone_primary)
                    if location and location.phone_primary
                    else None
                ),
                "member": member,
            }

            # Get user if exists
            if location and location.email:
                try:
                    user = User.objects.get(email=location.email)
                    recipient["user"] = user
                except User.DoesNotExist:
                    pass

            recipients.append(recipient)

        return recipients
