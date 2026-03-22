"""
Send SMS/email notifications for department activities to:
- department_members: members in the activity's department
- all_church: all church members
- specific_members: list of member IDs
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.notification_utils import church_can_use_sms_email

logger = logging.getLogger(__name__)

NOTIFY_TO_DEPARTMENT = "department_members"
NOTIFY_TO_ALL_CHURCH = "all_church"
NOTIFY_TO_SPECIFIC = "specific_members"


def _format_datetime(activity):
    """Format activity start/end for display."""
    parts = [activity.start_date.strftime("%A, %b %d, %Y")]
    if activity.start_time:
        parts.append(activity.start_time.strftime("%I:%M %p"))
    if activity.end_date and activity.end_date != activity.start_date:
        parts.append(" – " + activity.end_date.strftime("%A, %b %d, %Y"))
    if activity.end_time:
        parts.append(activity.end_time.strftime("%I:%M %p"))
    return " ".join(parts)


def _get_member_contacts(members, church):
    """Yield (email, phone) for each member that has at least one contact."""
    for member in members:
        email = None
        phone = None
        try:
            loc = getattr(member, "location", None)
            if loc:
                email = getattr(loc, "email", None) or ""
                phone = getattr(loc, "phone_primary", None) or ""
        except Exception:
            pass
        if email or phone:
            yield (email.strip() or None, phone.strip() or None)


def _get_recipients(activity, notify_to, member_ids=None):
    """
    Get list of (email, phone) for notification.
    notify_to: department_members | all_church | specific_members
    member_ids: required when notify_to == specific_members
    """
    from members.models import Member

    from ..models import MemberDepartment

    church = activity.church
    members = []

    if notify_to == NOTIFY_TO_DEPARTMENT:
        member_departments = MemberDepartment.objects.filter(
            department=activity.department
        ).select_related("member")
        members = [md.member for md in member_departments]
    elif notify_to == NOTIFY_TO_ALL_CHURCH:
        members = list(Member.objects.filter(church=church, deleted_at__isnull=True))
    elif notify_to == NOTIFY_TO_SPECIFIC and member_ids:
        members = list(
            Member.objects.filter(
                id__in=member_ids, church=church, deleted_at__isnull=True
            )
        )
    else:
        return []

    seen = set()
    out = []
    for email, phone in _get_member_contacts(members, church):
        key = (email or "", phone or "")
        if key in seen or (not email and not phone):
            continue
        seen.add(key)
        out.append((email, phone))
    return out


def send_activity_notifications(
    activity,
    notify_to,
    member_ids=None,
    send_email=True,
    send_sms=True,
):
    """
    Send activity notification (email and/or SMS) to the chosen audience.
    activity: DepartmentActivity instance
    notify_to: "department_members" | "all_church" | "specific_members"
    member_ids: list of member UUIDs when notify_to == "specific_members"
    send_email, send_sms: whether to send each channel
    Returns: {"email_sent": int, "sms_sent": int, "errors": list}
    """
    church = activity.church
    if not church_can_use_sms_email(church, allow_initial_admin=False):
        return {
            "email_sent": 0,
            "sms_sent": 0,
            "errors": ["SMS/email not allowed for this church plan"],
        }

    recipients = _get_recipients(activity, notify_to, member_ids)
    if not recipients:
        return {
            "email_sent": 0,
            "sms_sent": 0,
            "errors": ["No recipients with email or phone"],
        }

    datetime_str = _format_datetime(activity)
    title = activity.title
    location = activity.location or "TBA"
    description = (activity.description or "")[:500]

    result = {"email_sent": 0, "sms_sent": 0, "errors": []}

    # Email
    if send_email:
        subject = f"Activity: {title} – {activity.department.name}"
        body = f"""
Activity: {title}
Department: {activity.department.name}
When: {datetime_str}
Where: {location}

{description}
"""
        for email, _ in recipients:
            if not email:
                continue
            try:
                send_mail(
                    subject=subject,
                    message=body.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
                result["email_sent"] += 1
            except Exception as e:
                logger.exception("Activity notification email failed to %s", email)
                result["errors"].append(f"Email to {email}: {str(e)}")

    # SMS
    if send_sms:
        try:
            from notifications.services.mnotify_service import MNotifyService
        except ImportError:
            result["errors"].append("SMS service not available")
        else:
            msg = (
                f"{title}. When: {datetime_str}. Where: {location}. {description[:100]}"
            )
            mnotify = MNotifyService()
            for _, phone in recipients:
                if not phone:
                    continue
                r = mnotify.send_sms(to_phone=phone, message=msg)
                if r.get("success"):
                    result["sms_sent"] += 1
                else:
                    result["errors"].append(r.get("error", "SMS failed"))

    return result
