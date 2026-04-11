"""
Keep church `UserRole` rows in sync with department portal assignments.

Login / post-login redirect uses `UserSerializer.get_roles` (UserRole), while
`/departments/my-portal/` uses DepartmentHead + Member.system_user_id.
Without this sync, a user who is only assigned as head on a department still
looks like a generic user and gets routed to `/admin`.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from accounts.models import Role, UserRole
from departments.models import Department, DepartmentHead
from members.models import Member

User = get_user_model()

ROLE_DEPARTMENT_HEAD = "Department Head"
ROLE_ELDER_IN_CHARGE = "Elder in charge"


def _user_for_member(member: Member | None) -> Any:
    if not member or not member.system_user_id:
        return None
    return User.objects.filter(
        pk=member.system_user_id, church_id=member.church_id
    ).first()


def _member_is_primary_head_anywhere(member_id, church_id) -> bool:
    return DepartmentHead.objects.filter(
        member_id=member_id,
        head_role=DepartmentHead.HeadRole.HEAD,
        department__church_id=church_id,
        department__deleted_at__isnull=True,
    ).exists()


def _member_is_elder_in_charge_anywhere(member_id, church_id) -> bool:
    return Department.objects.filter(
        elder_in_charge_id=member_id,
        church_id=church_id,
        deleted_at__isnull=True,
    ).exists()


def reconcile_department_head_user_role(
    member_id,
    church_id,
    *,
    assigned_by=None,
) -> None:
    try:
        member = Member.objects.get(pk=member_id, church_id=church_id)
    except Member.DoesNotExist:
        return

    role = Role.objects.filter(name=ROLE_DEPARTMENT_HEAD).first()
    if not role:
        return

    user = _user_for_member(member)
    if not user:
        return

    if _member_is_primary_head_anywhere(member_id, church_id):
        UserRole.objects.update_or_create(
            user=user,
            role=role,
            church_id=church_id,
            defaults={"is_active": True, "assigned_by": assigned_by},
        )
    else:
        UserRole.objects.filter(
            user=user,
            role=role,
            church_id=church_id,
        ).update(is_active=False)


def reconcile_elder_in_charge_user_role(
    member_id,
    church_id,
    *,
    assigned_by=None,
) -> None:
    try:
        member = Member.objects.get(pk=member_id, church_id=church_id)
    except Member.DoesNotExist:
        return

    role = Role.objects.filter(name=ROLE_ELDER_IN_CHARGE).first()
    if not role:
        return

    user = _user_for_member(member)
    if not user:
        return

    if _member_is_elder_in_charge_anywhere(member_id, church_id):
        UserRole.objects.update_or_create(
            user=user,
            role=role,
            church_id=church_id,
            defaults={"is_active": True, "assigned_by": assigned_by},
        )
    else:
        UserRole.objects.filter(
            user=user,
            role=role,
            church_id=church_id,
        ).update(is_active=False)


def after_primary_department_head_change(
    department: Department,
    previous_head_member_id,
    new_head_member_id,
    *,
    assigned_by=None,
) -> None:
    """Call after primary head assignment changes for one department."""
    church_id = department.church_id
    if previous_head_member_id is not None and str(previous_head_member_id) == str(
        new_head_member_id
    ):
        reconcile_department_head_user_role(
            new_head_member_id, church_id, assigned_by=assigned_by
        )
        return
    if previous_head_member_id is not None:
        reconcile_department_head_user_role(
            previous_head_member_id, church_id, assigned_by=assigned_by
        )
    if new_head_member_id is not None:
        reconcile_department_head_user_role(
            new_head_member_id, church_id, assigned_by=assigned_by
        )
