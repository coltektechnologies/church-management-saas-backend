from django.core.management.base import BaseCommand

from accounts.models import Church, Permission, Role, RolePermission
from accounts.seed import (
    CHURCH_GROUPS_SEED_DATA,
    PERMISSIONS_SEED_DATA,
    ROLE_PERMISSION_ASSIGNMENTS,
    ROLES_SEED_DATA,
)
from accounts.seed.tenant_church_groups import ensure_catalog_church_groups


class Command(BaseCommand):
    help = "Setup initial roles, permissions, default church, and role–permission links"

    def handle(self, *args, **options):
        church, created = Church.objects.get_or_create(
            name="Default Church",
            defaults={
                "country": "Ghana",
                "region": "Greater Accra",
                "city": "Accra",
                "timezone": "Africa/Accra",
                "currency": "GHS",
                "status": "ACTIVE",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created church: {church.name}"))

        for role_data in ROLES_SEED_DATA:
            role, was_created = Role.objects.get_or_create(
                name=role_data["name"], defaults=role_data
            )
            if was_created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role.name}"))

        role_names = [r["name"] for r in ROLES_SEED_DATA]
        Role.objects.filter(name__in=role_names).update(is_system_role=True)

        for perm_data in PERMISSIONS_SEED_DATA:
            perm, was_created = Permission.objects.get_or_create(
                code=perm_data["code"], defaults=perm_data
            )
            if was_created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created permission: {perm.code}")
                )

        perm_codes = [p["code"] for p in PERMISSIONS_SEED_DATA]
        Permission.objects.filter(code__in=perm_codes).update(is_system_permission=True)

        # Full matrix from accounts/seed/role_permissions_catalog.py
        linked = 0
        for role_name, codes in ROLE_PERMISSION_ASSIGNMENTS.items():
            role = Role.objects.filter(name=role_name).first()
            if not role:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip role–permission: unknown role {role_name!r}"
                    )
                )
                continue
            for code in codes:
                perm = Permission.objects.filter(code=code).first()
                if not perm:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skip role–permission: unknown permission {code!r}"
                        )
                    )
                    continue
                _, was_created = RolePermission.objects.get_or_create(
                    role=role, permission=perm
                )
                if was_created:
                    linked += 1

        if linked:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Linked {linked} new role–permission row(s) from ROLE_PERMISSION_ASSIGNMENTS."
                )
            )

        # Church groups for every church (same logic as accounts.signals seed_catalog_church_groups).
        groups_created = 0
        for ch in Church.objects.all().order_by("name"):
            for gname, rname in ensure_catalog_church_groups(ch):
                groups_created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created church group {gname!r} → role {rname!r} "
                        f"(church={ch.name!r})"
                    )
                )

        if groups_created == 0 and CHURCH_GROUPS_SEED_DATA:
            self.stdout.write(
                "Church groups: none new (already exist on all churches or roles missing)."
            )

        self.stdout.write(
            "Applied is_system_role / is_system_permission flags to seeded catalog."
        )
        self.stdout.write(self.style.SUCCESS("Initial data setup complete!"))
