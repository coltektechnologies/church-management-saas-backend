"""Who may approve or reject expense requests at each workflow stage."""

from accounts.models import Role, UserRole
from accounts.permissions import has_permission as has_custom_permission
from departments.models import DepartmentHead
from members.models import MemberLocation


def can_approve_expense_as_dept_head_or_elder(request, expense_request):
    """Department head or elder in charge of the expense's department."""
    dept = expense_request.department
    if not dept:
        return False
    member_location = MemberLocation.objects.filter(
        email__iexact=request.user.email, church=expense_request.church
    ).first()
    if (
        member_location
        and DepartmentHead.objects.filter(
            department=dept, member=member_location.member
        ).exists()
    ):
        return True
    elder = getattr(dept, "elder_in_charge", None)
    if (
        elder
        and elder.system_user_id
        and str(elder.system_user_id) == str(request.user.id)
    ):
        return True
    return False


def can_approve_expense_as_first_elder(request, expense_request):
    """First Elder role at church, or elder in charge of the department."""
    church = expense_request.church
    dept = expense_request.department
    user = request.user
    first_elder_role = Role.objects.filter(name="First Elder").first()
    if (
        first_elder_role
        and UserRole.objects.filter(
            user=user, role=first_elder_role, church=church, is_active=True
        ).exists()
    ):
        return True
    if dept:
        elder = getattr(dept, "elder_in_charge", None)
        if elder and elder.system_user_id and str(elder.system_user_id) == str(user.id):
            return True
    return False


def can_approve_expense_as_treasurer(request, expense_request):
    """Treasurer final approval: RBAC permission or superuser / platform admin (not generic staff)."""
    user = request.user
    church = expense_request.church
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_platform_admin", False
    ):
        return True
    return has_custom_permission(user, "treasury.approve_expense", church=church)


def user_can_reject_expense_at_current_stage(request, expense_request) -> bool:
    """Reject is only allowed for actors who could approve at the current status."""
    st = (expense_request.status or "").strip()
    if st == "DRAFT":
        return expense_request.requested_by_id == request.user.id
    if st == "SUBMITTED":
        return can_approve_expense_as_dept_head_or_elder(request, expense_request)
    if st == "DEPT_HEAD_APPROVED":
        return can_approve_expense_as_first_elder(request, expense_request)
    if st == "FIRST_ELDER_APPROVED":
        return can_approve_expense_as_treasurer(request, expense_request)
    return False
