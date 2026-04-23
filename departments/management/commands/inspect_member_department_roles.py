"""
Print department membership, head/assistant, elder-in-charge, and UserRole for members.

Usage:
  python manage.py inspect_member_department_roles <member_uuid> [<member_uuid> ...]
  python manage.py inspect_member_department_roles --all-church "Adenta Central SDA"
"""

from __future__ import annotations

import json
import sys
import uuid

from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserRole
from departments.models import Department, DepartmentHead, MemberDepartment
from members.models import Member


def _as_uuid(s: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(s).strip())
    except ValueError as e:
        raise CommandError(f"Not a valid UUID: {s!r}") from e


class Command(BaseCommand):
    help = "Show MemberDepartment, DepartmentHead, elder-in-charge, and UserRole for member(s)."

    def add_arguments(self, parser):
        parser.add_argument(
            "member_ids",
            nargs="*",
            help="Member UUID(s)",
        )
        parser.add_argument(
            "--all-church",
            dest="church_name",
            metavar="NAME",
            help='Inspect all active members whose church name contains this string (e.g. "Adenta Central SDA").',
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Machine-readable JSON lines",
        )

    def handle(self, *args, **options):
        ids: list[uuid.UUID] = []
        for raw in options.get("member_ids") or []:
            ids.append(_as_uuid(raw))

        church_filter = options.get("church_name")
        if church_filter:
            qs = Member.objects.filter(
                deleted_at__isnull=True,
                church__name__icontains=church_filter.strip(),
            ).order_by("last_name", "first_name")
            count = qs.count()
            if count == 0:
                raise CommandError(
                    f"No members found for church containing {church_filter!r}"
                )
            ids = list(qs.values_list("id", flat=True))
            self.stdout.write(
                f"Found {count} member(s) in church matching {church_filter!r}\n"
            )

        if not ids:
            self.stderr.write(
                "Provide at least one member UUID, or use --all-church NAME.\n"
                "Example:\n"
                "  python manage.py inspect_member_department_roles bd2c8c69-dad5-4d2f-84b9-cbd0eada2f72\n"
            )
            sys.exit(1)

        out_rows = []
        for mid in ids:
            row = self._inspect_one(mid)
            out_rows.append(row)
            if options.get("json"):
                self.stdout.write(json.dumps(row, default=str))
            else:
                self._print_human(row)

    def _inspect_one(self, member_id: uuid.UUID) -> dict:
        try:
            m = Member.objects.select_related("church").get(pk=member_id)
        except Member.DoesNotExist:
            return {
                "member_id": str(member_id),
                "error": "Member not found",
            }

        church_name = getattr(m.church, "name", "") if m.church_id else ""

        assignments = []
        for md in MemberDepartment.objects.filter(
            member_id=m.id,
            deleted_at__isnull=True,
        ).select_related("department"):
            assignments.append(
                {
                    "department_id": str(md.department_id),
                    "department_name": md.department.name,
                    "role_in_department": md.role_in_department or "",
                }
            )

        heads = []
        for dh in DepartmentHead.objects.filter(member_id=m.id).select_related(
            "department"
        ):
            heads.append(
                {
                    "department_id": str(dh.department_id),
                    "department_name": dh.department.name,
                    "head_role": dh.head_role,
                }
            )

        elder_for = []
        for d in Department.objects.filter(
            elder_in_charge_id=m.id,
            deleted_at__isnull=True,
        ):
            elder_for.append({"department_id": str(d.id), "department_name": d.name})

        roles = []
        if m.system_user_id:
            for ur in UserRole.objects.filter(
                user_id=m.system_user_id, is_active=True
            ).select_related("role"):
                roles.append(
                    {
                        "role_name": ur.role.name,
                        "level": ur.role.level,
                    }
                )

        return {
            "member_id": str(m.id),
            "full_name": m.full_name,
            "church": church_name,
            "has_system_access": m.has_system_access,
            "system_user_id": str(m.system_user_id) if m.system_user_id else None,
            "member_department_assignments": assignments,
            "department_head_or_assistant": heads,
            "elder_in_charge_for": elder_for,
            "user_roles_when_linked": roles,
            "summary": self._summary(assignments, heads, elder_for, roles),
        }

    def _summary(self, assignments, heads, elder_for, roles):
        parts = []
        if assignments:
            parts.append(f"{len(assignments)} dept membership(s)")
        else:
            parts.append("no MemberDepartment rows")
        if heads:
            parts.append(f"{len(heads)} head/assistant row(s)")
        if elder_for:
            parts.append(f"elder for {len(elder_for)} dept(s)")
        if roles:
            parts.append("UserRoles: " + ", ".join(r["role_name"] for r in roles))
        elif not heads and not elder_for:
            parts.append("no UserRoles (or not linked to user)")
        return "; ".join(parts)

    def _print_human(self, row: dict) -> None:
        self.stdout.write("=" * 72)
        if row.get("error"):
            self.stdout.write(self.style.ERROR(f"{row['member_id']}: {row['error']}"))
            return
        self.stdout.write(f"Member: {row['full_name']} ({row['member_id']})")
        self.stdout.write(f"Church: {row['church']}")
        self.stdout.write(
            f"System access: {row['has_system_access']} | system_user_id: {row['system_user_id']}"
        )
        self.stdout.write(self.style.WARNING(f"Summary: {row['summary']}"))

        if row["member_department_assignments"]:
            self.stdout.write("  MemberDepartment (membership):")
            for a in row["member_department_assignments"]:
                role = a["role_in_department"] or "(no role_in_department set)"
                self.stdout.write(f"    - {a['department_name']}: {role}")
        else:
            self.stdout.write("  MemberDepartment: (none)")

        if row["department_head_or_assistant"]:
            self.stdout.write("  DepartmentHead:")
            for h in row["department_head_or_assistant"]:
                self.stdout.write(f"    - {h['department_name']} [{h['head_role']}]")
        else:
            self.stdout.write("  DepartmentHead: (none)")

        if row["elder_in_charge_for"]:
            self.stdout.write("  Elder in charge:")
            for e in row["elder_in_charge_for"]:
                self.stdout.write(f"    - {e['department_name']}")
        else:
            self.stdout.write("  Elder in charge: (none)")

        if row["user_roles_when_linked"]:
            self.stdout.write("  Active UserRole (login/JWT):")
            for r in row["user_roles_when_linked"]:
                self.stdout.write(f"    - {r['role_name']} (level {r['level']})")
        else:
            self.stdout.write(
                "  UserRole: (none — no system_user_id or no UserRole rows)"
            )
        self.stdout.write("")
