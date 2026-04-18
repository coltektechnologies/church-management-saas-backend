"""
Link department heads / elders in charge to login users and sync UserRole rows.

Login redirect and JWT roles use UserRole; my-portal uses Member.system_user_id.
If a head's member has no system_user_id, they get sent to /admin after login.

Usage:
  python manage.py sync_department_portal_access
  python manage.py sync_department_portal_access --dry-run

Auto-link rule: if member.system_user_id is empty, match User by
member.location.email (same church, case-insensitive). Then grant
"Department Head" or "Elder in charge" UserRole via reconcile_* helpers.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from departments.models import Department, DepartmentHead
from departments.services.portal_user_roles import (
    reconcile_department_head_user_role,
    reconcile_elder_in_charge_user_role,
)
from members.models import Member

User = get_user_model()


def _member_contact_email(member: Member) -> str:
    try:
        loc = member.location
        if loc and loc.email:
            return str(loc.email).strip()
    except Exception:
        pass
    return ""


class Command(BaseCommand):
    help = (
        "Link primary department heads and elders in charge to Users by email, "
        "then sync Department Head / Elder in charge UserRole rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions only; do not write to the database.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        linked_heads = 0
        reconciled_heads = 0
        linked_elders = 0
        reconciled_elders = 0
        skipped: list[str] = []

        # --- Primary department heads ---
        heads = DepartmentHead.objects.filter(
            head_role=DepartmentHead.HeadRole.HEAD
        ).select_related("member", "department")
        for dh in heads:
            dept = dh.department
            if dept.deleted_at is not None:
                continue
            m = dh.member
            if m.deleted_at is not None:
                continue

            church_id = m.church_id
            email = _member_contact_email(m)

            if not m.system_user_id and email:
                user = User.objects.filter(
                    email__iexact=email, church_id=church_id
                ).first()
                if user:
                    msg = (
                        f"Head {m.full_name} ({dept.name}): link member -> "
                        f"User {user.email}"
                    )
                    if dry_run:
                        self.stdout.write(f"[dry-run] Would {msg.lower()}")
                    else:
                        m.system_user_id = user.id
                        m.has_system_access = True
                        m.save(update_fields=["system_user_id", "has_system_access"])
                        self.stdout.write(self.style.SUCCESS(msg))
                    linked_heads += 1
                else:
                    skipped.append(
                        f"Head {m.full_name} ({dept.code}): no User with email "
                        f"{email!r} in this church — create/link manually."
                    )
            elif not m.system_user_id and not email:
                skipped.append(
                    f"Head {m.full_name} ({dept.code}): no system_user_id and "
                    f"no location email — add email or link member to a User."
                )

            if dry_run:
                if m.system_user_id or (
                    email
                    and User.objects.filter(
                        email__iexact=email, church_id=church_id
                    ).exists()
                ):
                    self.stdout.write(
                        f"[dry-run] Would reconcile Department Head role for "
                        f"{m.full_name} ({dept.code})"
                    )
                    reconciled_heads += 1
            else:
                m.refresh_from_db()
                if m.system_user_id:
                    reconcile_department_head_user_role(
                        m.id, church_id, assigned_by=None
                    )
                    reconciled_heads += 1

        # --- Elder in charge ---
        for dept in Department.objects.filter(
            deleted_at__isnull=True, elder_in_charge__isnull=False
        ).select_related("elder_in_charge"):
            m = dept.elder_in_charge
            if m.deleted_at is not None:
                continue
            church_id = dept.church_id
            email = _member_contact_email(m)

            if not m.system_user_id and email:
                user = User.objects.filter(
                    email__iexact=email, church_id=church_id
                ).first()
                if user:
                    msg = (
                        f"Elder in charge {m.full_name} ({dept.name}): link -> "
                        f"User {user.email}"
                    )
                    if dry_run:
                        self.stdout.write(f"[dry-run] Would {msg.lower()}")
                    else:
                        m.system_user_id = user.id
                        m.has_system_access = True
                        m.save(update_fields=["system_user_id", "has_system_access"])
                        self.stdout.write(self.style.SUCCESS(msg))
                    linked_elders += 1
                else:
                    skipped.append(
                        f"Elder {m.full_name} ({dept.code}): no User with email "
                        f"{email!r} — fix manually."
                    )
            elif not m.system_user_id and not email:
                skipped.append(
                    f"Elder {m.full_name} ({dept.code}): no system_user_id / no email."
                )

            if dry_run:
                if m.system_user_id or (
                    email
                    and User.objects.filter(
                        email__iexact=email, church_id=church_id
                    ).exists()
                ):
                    self.stdout.write(
                        f"[dry-run] Would reconcile Elder in charge role for "
                        f"{m.full_name} ({dept.code})"
                    )
                    reconciled_elders += 1
            else:
                m.refresh_from_db()
                if m.system_user_id:
                    reconcile_elder_in_charge_user_role(
                        m.id, church_id, assigned_by=None
                    )
                    reconciled_elders += 1

        for line in skipped:
            self.stdout.write(self.style.WARNING(line))

        self.stdout.write(
            f"\nSummary: heads linked={linked_heads}, heads reconciled={reconciled_heads}, "
            f"elders linked={linked_elders}, elders reconciled={reconciled_elders}, "
            f"dry_run={dry_run}"
        )
