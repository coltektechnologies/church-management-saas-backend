"""
Notify members when a treasury income row is created for them.

The record-income UI encodes channel choice in ``notes`` as
``Notifications: sms, email, both`` (see frontend ``recordIncomeSubmit.ts``).
In-app notification is always created for linked members; SMS/email run only when
parsed from that line and the church may use outbound messaging.
"""

from __future__ import annotations

import logging
import re
from html import escape

from departments.approval_notifications import _get_phone_for_user

logger = logging.getLogger(__name__)

_NOTES_NOTIFICATIONS = re.compile(r"Notifications:\s*([^|]+)", re.IGNORECASE)


def parse_income_notification_channels(notes: str | None) -> tuple[bool, bool]:
    """
    Return (want_sms, want_email) from income ``notes`` text.
    ``both`` enables SMS and email.
    """
    if not notes or not str(notes).strip():
        return False, False
    m = _NOTES_NOTIFICATIONS.search(notes)
    if not m:
        return False, False
    part = m.group(1).strip().lower()
    tokens = {t.strip() for t in part.split(",") if t.strip()}
    want_sms = "sms" in tokens or "both" in tokens
    want_email = "email" in tokens or "both" in tokens
    return want_sms, want_email


def _user_for_member(member):
    from accounts.models import User

    uid = getattr(member, "system_user_id", None)
    if not uid:
        return None
    return User.objects.filter(pk=uid, is_active=True).first()


def _phone_for_member(member, user):
    if user:
        phone = _get_phone_for_user(user)
        if phone:
            return phone
    loc = getattr(member, "location", None)
    if loc and getattr(loc, "phone_primary", None):
        p = str(loc.phone_primary).strip()
        if p:
            return p
    return None


def _email_for_member(member):
    loc = getattr(member, "location", None)
    if not loc:
        return None
    e = getattr(loc, "email", None)
    if e and str(e).strip():
        return str(e).strip()
    return None


def notify_member_income_recorded(transaction, *, created: bool) -> None:
    """Create in-app notification; optional SMS/email from ``notes`` channels."""
    from accounts.notification_utils import church_can_use_sms_email
    from members.models import Member
    from notifications.services import EmailService, NotificationService, SMSService

    if not created or not transaction.member_id or transaction.deleted_at:
        return
    church = transaction.church
    if not church or not getattr(church, "pk", None):
        return

    member = (
        Member.objects.filter(pk=transaction.member_id)
        .select_related("location", "church")
        .first()
    )
    if not member:
        return

    try:
        category_name = (
            transaction.category.name if transaction.category_id else "Contribution"
        )
    except Exception:
        category_name = "Contribution"

    receipt = (transaction.receipt_number or str(transaction.pk)[:8]).strip()
    amount = transaction.amount
    tdate = transaction.transaction_date

    title = f"Contribution recorded — {receipt}"
    message = (
        f"Your {category_name} contribution of {amount} was recorded on {tdate}. "
        f"Receipt number: {receipt}. Thank you."
    )
    sms_body = f"{receipt}: {category_name} {amount} recorded {tdate}. Thank you."

    user = _user_for_member(member)

    try:
        NotificationService.create_notification(
            church=church,
            user=user,
            member=member,
            title=title,
            message=message,
            priority="MEDIUM",
            category="FINANCE",
            link=None,
            created_by=transaction.recorded_by,
        )
    except Exception as e:
        logger.warning(
            "Income in-app notify failed for member %s: %s", member.pk, e, exc_info=True
        )

    want_sms, want_email = parse_income_notification_channels(transaction.notes)
    can_outbound = church_can_use_sms_email(church, allow_initial_admin=False)

    if want_sms and can_outbound:
        phone = _phone_for_member(member, user)
        if phone:
            try:
                SMSService.send_sms(
                    church=church,
                    phone_number=phone,
                    message=sms_body[:480],
                    member=member,
                )
            except PermissionError:
                logger.debug("Income SMS skipped (plan) for member %s", member.pk)
            except Exception as e:
                logger.warning("Income SMS failed for %s: %s", phone, e)

    if want_email and can_outbound:
        email_addr = _email_for_member(member)
        if email_addr:
            try:
                subject = f"Contribution recorded — {receipt}"
                html = f"<p>{escape(message)}</p>"
                EmailService.send_email(
                    church=church,
                    email_address=email_addr,
                    subject=subject,
                    message_html=html,
                    message_plain=message,
                    member=member,
                )
            except PermissionError:
                logger.debug("Income email skipped (plan) for member %s", member.pk)
            except Exception as e:
                logger.warning("Income email failed for %s: %s", email_addr, e)
