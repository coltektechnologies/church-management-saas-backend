"""
Send SMS and in-app notifications to the approval chain when a program is submitted.
Elder → Secretariat → Treasury
"""

import logging

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)


def _get_phone_for_user(user):
    """Get phone number for a User (from user.phone or linked Member's location)."""
    if getattr(user, "phone", None) and str(user.phone).strip():
        return str(user.phone).strip()
    try:
        from members.models import Member

        member = (
            Member.objects.filter(system_user_id=user.id)
            .select_related("location")
            .first()
        )
        if member and hasattr(member, "location") and member.location:
            phone = getattr(member.location, "phone_primary", None)
            if phone and str(phone).strip():
                return str(phone).strip()
    except Exception as e:
        logger.debug(f"Could not get phone for user {user.id}: {e}")
    return None


def notify_approval_chain(program, submitter_name=None):
    """
    Send in-app notifications and SMS to all approvers in the chain when a program
    is submitted for approval.

    Notifies: Department Elder, Secretariat users, Treasury users.
    """
    from accounts.models import User
    from accounts.notification_utils import church_can_use_sms_email
    from notifications.models import Notification
    from notifications.services import NotificationService, SMSService

    if not program or not program.church:
        return

    submitter_name = submitter_name or (
        program.created_by.get_full_name() if program.created_by else "Unknown"
    )
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    link = f"{site_url}/admin/departments/program/{program.id}/change/"
    program_title = program.title or "Untitled Program"

    # Short SMS message (max ~160 chars per SMS)
    sms_msg = f"Program '{program_title}' needs your approval. Submitted by {submitter_name}. Review: {link}"
    if len(sms_msg) > 160:
        sms_msg = f"Program '{program_title}' needs your approval. Review: {link}"

    notified_ids = set()
    can_sms = church_can_use_sms_email(program.church, allow_initial_admin=False)

    def send_to_user(user, title, message=None):
        if not user or user.id in notified_ids:
            return
        msg = (
            message
            or f"Program '{program_title}' has been submitted for your approval. Submitted by {submitter_name}."
        )
        # In-app notification (always)
        try:
            NotificationService.create_notification(
                church=program.church,
                user=user,
                title=title,
                message=msg,
                priority="HIGH",
                category="PROGRAM",
                link=link,
            )
        except Exception as e:
            logger.warning(
                f"Failed to create in-app notification for user {user.id}: {e}"
            )

        # SMS (if church allows and user has phone)
        if can_sms:
            phone = _get_phone_for_user(user)
            if phone:
                try:
                    SMSService.send_sms(
                        church=program.church,
                        phone_number=phone,
                        message=sms_msg,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to send SMS to {phone} for program approval: {e}"
                    )

        notified_ids.add(user.id)

    # 1. Department Elder (first approver)
    elder = getattr(program.department, "elder_in_charge", None)
    if elder and elder.system_user_id:
        try:
            elder_user = User.objects.get(id=elder.system_user_id)
            send_to_user(elder_user, "Program Submitted for Elder Approval")
        except User.DoesNotExist:
            pass

    # 2. Secretariat users
    if program.submitted_to_secretariat:
        for user in User.objects.filter(
            Q(groups__name="Secretariat") | Q(is_staff=True) | Q(is_superuser=True),
            church=program.church,
            is_active=True,
        ).distinct():
            send_to_user(user, "Program Submitted for Secretariat Approval")

    # 3. Treasury users
    if program.submitted_to_treasury:
        for user in User.objects.filter(
            Q(groups__name="Treasury") | Q(is_staff=True) | Q(is_superuser=True),
            church=program.church,
            is_active=True,
        ).distinct():
            send_to_user(user, "Program Submitted for Treasury Approval")

    # Fallback: staff if no one was notified
    if not notified_ids:
        for user in (
            User.objects.filter(church=program.church, is_active=True)
            .filter(Q(is_staff=True) | Q(is_superuser=True))
            .distinct()
        ):
            send_to_user(
                user, "Program Submitted for Approval (Elder → Secretariat → Treasury)"
            )
