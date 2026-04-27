"""
In-app + SMS notifications for expense request workflow.

Program/budget submissions use ``departments.approval_notifications.notify_approval_chain``.
Expense request submit previously did not notify anyone — this module wires the approval chain.

Flow: SUBMITTED → DEPT_HEAD_APPROVED → FIRST_ELDER_APPROVED → APPROVED (treasurer)
"""

import logging

from django.db.models import Q
from django.utils import timezone

from departments.approval_notifications import _get_phone_for_user

logger = logging.getLogger(__name__)


def mark_expense_stage_notifications_read(expense_request, stage: str) -> int:
    """
    Mark in-app FINANCE notifications for this expense as read when a workflow step is done.

    ``stage``: ``department`` | ``first_elder`` | ``treasurer`` | ``all``
    (``all`` is used on rejection to clear every pending step for this request_number).
    """
    from notifications.models import Notification

    ref = (getattr(expense_request, "request_number", None) or "").strip()
    church_id = getattr(expense_request, "church_id", None)
    if not ref or not church_id:
        return 0

    prefix = f"Expense request {ref}"
    qs = Notification.objects.filter(
        church_id=church_id,
        category="FINANCE",
        is_read=False,
        title__startswith=prefix,
        status__in=["SENT", "PENDING"],
    )
    if stage == "department":
        qs = qs.filter(
            Q(title__icontains="needs department approval")
            | Q(title__icontains="no dept head found")
        )
    elif stage == "first_elder":
        qs = qs.filter(
            Q(title__icontains="needs First Elder")
            | Q(title__icontains="configure First Elder")
        )
    elif stage == "treasurer":
        qs = qs.filter(title__icontains="treasurer approval")
    elif stage == "all":
        pass
    else:
        return 0

    now = timezone.now()
    updated = qs.update(is_read=True, read_at=now, status="READ")
    if updated:
        logger.debug(
            "Marked %s expense FINANCE notifications read (stage=%s, ref=%s)",
            updated,
            stage,
            ref,
        )
    return updated


def _send_expense_notice(
    *,
    church,
    user,
    title,
    message,
    sms_body,
    notified_ids,
    can_sms,
):
    from accounts.models import User
    from notifications.services import NotificationService, SMSService

    if not user or not isinstance(user, User) or user.id in notified_ids:
        return

    try:
        NotificationService.create_notification(
            church=church,
            user=user,
            title=title,
            message=message,
            priority="HIGH",
            category="FINANCE",
            link=None,
        )
    except Exception as e:
        logger.warning(
            "Expense request in-app notify failed for user %s: %s", user.id, e
        )

    if can_sms:
        phone = _get_phone_for_user(user)
        if phone:
            try:
                SMSService.send_sms(
                    church=church,
                    phone_number=phone,
                    message=sms_body[:480],
                )
            except Exception as e:
                logger.warning("Expense request SMS failed for %s: %s", phone, e)

    notified_ids.add(user.id)


def _base_message_parts(expense_request):
    ref = expense_request.request_number or str(expense_request.pk)[:8]
    submitter_name = (
        expense_request.requested_by.get_full_name()
        if expense_request.requested_by
        else "Unknown"
    )
    purpose = (expense_request.purpose or "")[:120]
    base_msg = (
        f"Expense request {ref} ({purpose}). "
        f"Submitted by {submitter_name}. Amount: {expense_request.amount_requested}."
    )
    return ref, purpose, base_msg


def _notify_department_stage(expense_request, notified_ids, can_sms):
    """SUBMITTED — department heads + elder in charge."""
    from accounts.models import User
    from departments.models import DepartmentHead

    church = expense_request.church
    dept = expense_request.department
    ref, purpose, base_msg = _base_message_parts(expense_request)

    title = f"Expense request {ref} — needs department approval"
    msg = base_msg + " Please review as department head or elder in charge."
    sms = f"{ref}: expense needs your approval. {purpose[:60]}."

    if not dept:
        return

    heads = DepartmentHead.objects.filter(
        department=dept,
        head_role=DepartmentHead.HeadRole.HEAD,
        church=church,
    ).select_related("member")
    for h in heads:
        uid = getattr(h.member, "system_user_id", None)
        if uid:
            try:
                u = User.objects.get(pk=uid, is_active=True)
                _send_expense_notice(
                    church=church,
                    user=u,
                    title=title,
                    message=msg,
                    sms_body=sms,
                    notified_ids=notified_ids,
                    can_sms=can_sms,
                )
            except User.DoesNotExist:
                pass

    elder = getattr(dept, "elder_in_charge", None)
    if elder and elder.system_user_id:
        try:
            u = User.objects.get(pk=elder.system_user_id, is_active=True)
            _send_expense_notice(
                church=church,
                user=u,
                title=title,
                message=msg,
                sms_body=sms,
                notified_ids=notified_ids,
                can_sms=can_sms,
            )
        except User.DoesNotExist:
            pass

    if not notified_ids:
        for user in User.objects.filter(
            church=church,
            is_active=True,
        ).filter(Q(is_staff=True) | Q(is_superuser=True)):
            _send_expense_notice(
                church=church,
                user=user,
                title=f"Expense request {ref} — no dept head found",
                message=msg + " (Fallback: assign department heads for notifications.)",
                sms_body=sms,
                notified_ids=notified_ids,
                can_sms=can_sms,
            )


def _notify_first_elder_stage(expense_request, notified_ids, can_sms):
    """DEPT_HEAD_APPROVED — First Elder role + elder in charge."""
    from accounts.models import Role, User, UserRole

    church = expense_request.church
    dept = expense_request.department
    ref, purpose, base_msg = _base_message_parts(expense_request)

    title = f"Expense request {ref} — needs First Elder approval"
    msg = base_msg + " Department step satisfied; please review as First Elder."
    sms = f"{ref}: needs First Elder approval. {purpose[:50]}."

    first_elder_role = Role.objects.filter(name="First Elder").first()
    if first_elder_role:
        for uid in (
            UserRole.objects.filter(
                role=first_elder_role, church=church, is_active=True
            )
            .values_list("user_id", flat=True)
            .distinct()
        ):
            try:
                u = User.objects.get(pk=uid, is_active=True)
                _send_expense_notice(
                    church=church,
                    user=u,
                    title=title,
                    message=msg,
                    sms_body=sms,
                    notified_ids=notified_ids,
                    can_sms=can_sms,
                )
            except User.DoesNotExist:
                pass

    if dept:
        elder = getattr(dept, "elder_in_charge", None)
        if elder and elder.system_user_id:
            try:
                u = User.objects.get(pk=elder.system_user_id, is_active=True)
                _send_expense_notice(
                    church=church,
                    user=u,
                    title=title,
                    message=msg,
                    sms_body=sms,
                    notified_ids=notified_ids,
                    can_sms=can_sms,
                )
            except User.DoesNotExist:
                pass

    if not notified_ids:
        for user in User.objects.filter(
            church=church,
            is_active=True,
        ).filter(Q(is_staff=True) | Q(is_superuser=True)):
            _send_expense_notice(
                church=church,
                user=user,
                title=f"Expense request {ref} — configure First Elder role",
                message=msg + " (Fallback: no First Elder UserRole assigned.)",
                sms_body=sms,
                notified_ids=notified_ids,
                can_sms=can_sms,
            )


def _notify_treasury_stage(expense_request, notified_ids, can_sms):
    """FIRST_ELDER_APPROVED — treasury final approval."""
    from accounts.models import ChurchGroupMember, User, UserRole
    from accounts.permissions import has_permission

    church = expense_request.church
    ref, purpose, base_msg = _base_message_parts(expense_request)
    submitter_name = (
        expense_request.requested_by.get_full_name()
        if expense_request.requested_by
        else "Unknown"
    )

    title = f"Expense request {ref} — treasurer approval"
    msg = (
        f"Expense request {ref}. First Elder approved. "
        f"Purpose: {purpose}. Submitter: {submitter_name}. "
        f"Please complete treasurer approval."
    )
    sms = f"{ref}: treasurer approval needed. {purpose[:50]}."

    # Users tied to this church via roles (includes treasurers with UserRole only).
    candidate_ids = set(
        UserRole.objects.filter(church=church, is_active=True).values_list(
            "user_id", flat=True
        )
    )
    candidate_ids.update(
        ChurchGroupMember.objects.filter(group__church=church).values_list(
            "user_id", flat=True
        )
    )

    for uid in candidate_ids:
        try:
            user = User.objects.get(pk=uid, is_active=True)
        except User.DoesNotExist:
            continue
        if not has_permission(user, "treasury.approve_expense", church=church):
            continue
        _send_expense_notice(
            church=church,
            user=user,
            title=title,
            message=msg,
            sms_body=sms,
            notified_ids=notified_ids,
            can_sms=can_sms,
        )

    # Legacy: Django auth group "Treasury" on this church (may not use RolePermission).
    for user in User.objects.filter(
        groups__name="Treasury", church=church, is_active=True
    ).distinct():
        _send_expense_notice(
            church=church,
            user=user,
            title=title,
            message=msg,
            sms_body=sms,
            notified_ids=notified_ids,
            can_sms=can_sms,
        )

    # Church-scoped superusers only (avoid notifying every staff user on the church).
    for user in User.objects.filter(
        is_superuser=True, church=church, is_active=True
    ).distinct():
        _send_expense_notice(
            church=church,
            user=user,
            title=title,
            message=msg,
            sms_body=sms,
            notified_ids=notified_ids,
            can_sms=can_sms,
        )

    if not notified_ids:
        logger.warning(
            "No treasury recipients for expense request %s after first elder approval",
            ref,
        )


def notify_expense_request_submit(expense_request):
    """
    After POST .../expense-requests/{id}/submit/.

    Routes by status:
    - SUBMITTED → department heads + elder in charge
    - DEPT_HEAD_APPROVED (auto) → First Elder chain
    """
    from accounts.notification_utils import church_can_use_sms_email

    if not expense_request or not expense_request.church_id:
        return

    notified_ids = set()
    can_sms = church_can_use_sms_email(
        expense_request.church, allow_initial_admin=False
    )
    status = expense_request.status

    if status == "SUBMITTED":
        _notify_department_stage(expense_request, notified_ids, can_sms)
    elif status == "DEPT_HEAD_APPROVED":
        mark_expense_stage_notifications_read(expense_request, "department")
        _notify_first_elder_stage(expense_request, notified_ids, can_sms)


def notify_expense_request_after_dept_head(expense_request):
    """After POST .../approve-dept-head/ — next is First Elder."""
    from accounts.notification_utils import church_can_use_sms_email

    expense_request.refresh_from_db()
    if expense_request.status != "DEPT_HEAD_APPROVED":
        return
    notified_ids = set()
    can_sms = church_can_use_sms_email(
        expense_request.church, allow_initial_admin=False
    )
    mark_expense_stage_notifications_read(expense_request, "department")
    _notify_first_elder_stage(expense_request, notified_ids, can_sms)


def notify_expense_request_after_first_elder(expense_request):
    """After POST .../approve-first-elder/ — next is treasurer."""
    from accounts.notification_utils import church_can_use_sms_email

    expense_request.refresh_from_db()
    if expense_request.status != "FIRST_ELDER_APPROVED":
        return
    notified_ids = set()
    can_sms = church_can_use_sms_email(
        expense_request.church, allow_initial_admin=False
    )
    mark_expense_stage_notifications_read(expense_request, "first_elder")
    _notify_treasury_stage(expense_request, notified_ids, can_sms)


def notify_expense_request_after_treasurer(expense_request):
    """After final treasurer approval — clear stale 'treasurer approval' in-app notices."""
    expense_request.refresh_from_db()
    if expense_request.status != "APPROVED":
        return
    mark_expense_stage_notifications_read(expense_request, "treasurer")


def clear_expense_request_workflow_notifications(expense_request):
    """On rejection (any stage): mark all pending FINANCE inbox rows for this request as read."""
    mark_expense_stage_notifications_read(expense_request, "all")
