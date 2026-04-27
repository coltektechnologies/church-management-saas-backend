"""Who may act on program workflow steps (Elder → Secretariat → Treasury)."""

from accounts.permissions import has_permission as has_custom_permission
from members.models import Member


def user_is_department_elder_in_charge(user, department) -> bool:
    """True if user is the department's elder in charge (linked system user or member row)."""
    eic = getattr(department, "elder_in_charge", None)
    if not eic:
        return False
    if getattr(eic, "system_user_id", None) and str(eic.system_user_id) == str(user.id):
        return True
    try:
        member = Member.objects.get(system_user_id=user.id)
    except Member.DoesNotExist:
        return False
    return member.id == eic.id


def user_can_review_program_as_elder(user, program) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    dept = getattr(program, "department", None)
    if not dept:
        return False
    if user_is_department_elder_in_charge(user, dept):
        return True
    if user.groups.filter(name__icontains="Elder").exists():
        return True
    church = getattr(program, "church", None)
    if church and has_custom_permission(user, "departments.approve_programs", church):
        return True
    return False


def user_can_review_program_as_secretariat(user, program) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_platform_admin", False
    ):
        return True
    if user.has_perm("departments.approve_secretariat"):
        return True
    if user.groups.filter(name="Secretariat").exists():
        return True
    return False


def user_can_review_program_as_treasury(user, program) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(
        user, "is_platform_admin", False
    ):
        return True
    if user.has_perm("departments.approve_treasury"):
        return True
    if user.groups.filter(name="Treasury").exists():
        return True
    return False
