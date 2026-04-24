"""
Fix Member rows where has_system_access=True but system_user_id is NULL (invalid state).

Tries to attach User by MemberLocation email (same church as sync_department_portal_access).
Then runs reconcile_department_head_user_role / reconcile_elder_in_charge_user_role.

If no matching User exists, clears has_system_access=False so UI filters stay truthful.

Usage:
  python manage.py repair_member_user_links --dry-run
  python manage.py repair_member_user_links
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

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
    help = "Link Member.system_user_id from User by email, or clear orphan has_system_access flags."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change; do not write.",
        )

    def handle(self, *args, **options):
        dry: bool = options["dry_run"]
        fixed_link = 0
        cleared = 0

        orphans = Member.objects.filter(
            has_system_access=True,
            system_user_id__isnull=True,
            deleted_at__isnull=True,
        ).select_related("church")

        for m in orphans:
            church_id = m.church_id
            email = _member_contact_email(m)
            linked_this = False
            if email:
                user = User.objects.filter(
                    email__iexact=email, church_id=church_id
                ).first()
                if user:
                    linked_this = True
                    if dry:
                        self.stdout.write(
                            f"[dry-run] Would link {m.full_name} -> User {user.email}"
                        )
                    else:
                        m.system_user_id = user.id
                        m.save(update_fields=["system_user_id"])
                        reconcile_department_head_user_role(m.id, church_id)
                        reconcile_elder_in_charge_user_role(m.id, church_id)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Linked {m.full_name} -> User {user.email}; reconciled portal roles."
                            )
                        )
                    fixed_link += 1

            if linked_this:
                continue

            msg = f"{m.full_name}: has_system_access=True but no system_user_id; " + (
                f"no User with email {email!r} in church."
                if email
                else "no email on MemberLocation."
            )
            if dry:
                self.stdout.write(f"[dry-run] Would clear has_system_access — {msg}")
            else:
                m.has_system_access = False
                m.save(update_fields=["has_system_access"])
                self.stdout.write(
                    self.style.WARNING(f"Cleared has_system_access — {msg}")
                )
            cleared += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. linked={fixed_link}, cleared_bad_flag={cleared}, dry_run={dry}"
            )
        )
