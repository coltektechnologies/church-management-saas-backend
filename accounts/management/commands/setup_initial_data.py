from django.core.management.base import BaseCommand

from accounts.models import Church, Permission, Role, RolePermission


class Command(BaseCommand):
    help = "Setup initial roles, permissions, and default church"

    def handle(self, *args, **options):
        # Create default church for development
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

        # Create Roles (core catalog — protected from delete in Django admin)
        roles_data = [
            {
                "name": "Pastor",
                "level": 1,
                "description": "Church Pastor - Full Access",
                "is_system_role": True,
            },
            {
                "name": "First Elder",
                "level": 1,
                "description": "First Elder - Full Access",
                "is_system_role": True,
            },
            {
                "name": "Secretary",
                "level": 2,
                "description": "Church Secretary",
                "is_system_role": True,
            },
            {
                "name": "Treasurer",
                "level": 2,
                "description": "Church Treasurer",
                "is_system_role": True,
            },
            {
                "name": "Department Head",
                "level": 3,
                "description": "Department Head/Staff",
                "is_system_role": True,
            },
            {
                "name": "Elder in charge",
                "level": 3,
                "description": "Oversight elder for a department (e.g. program approval)",
                "is_system_role": True,
            },
            {
                "name": "Member",
                "level": 4,
                "description": "Regular Church Member",
                "is_system_role": True,
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data["name"], defaults=role_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role.name}"))

        role_names = [r["name"] for r in roles_data]
        Role.objects.filter(name__in=role_names).update(is_system_role=True)

        # Create Permissions (core catalog — protected from delete in Django admin)
        permissions_data = [
            # Members
            {
                "code": "members.view_all",
                "module": "MEMBERS",
                "description": "View all members",
                "is_system_permission": True,
            },
            {
                "code": "members.create",
                "module": "MEMBERS",
                "description": "Create new members",
                "is_system_permission": True,
            },
            {
                "code": "members.edit",
                "module": "MEMBERS",
                "description": "Edit member details",
                "is_system_permission": True,
            },
            {
                "code": "members.delete",
                "module": "MEMBERS",
                "description": "Delete members",
                "is_system_permission": True,
            },
            {
                "code": "members.view_financial",
                "module": "MEMBERS",
                "description": "View member financial data",
                "is_system_permission": True,
            },
            # Treasury
            {
                "code": "treasury.view",
                "module": "TREASURY",
                "description": "View financial data",
                "is_system_permission": True,
            },
            {
                "code": "treasury.record_income",
                "module": "TREASURY",
                "description": "Record income",
                "is_system_permission": True,
            },
            {
                "code": "treasury.record_expense",
                "module": "TREASURY",
                "description": "Record expenses",
                "is_system_permission": True,
            },
            {
                "code": "treasury.approve_expense",
                "module": "TREASURY",
                "description": "Approve expense requests",
                "is_system_permission": True,
            },
            {
                "code": "treasury.generate_reports",
                "module": "TREASURY",
                "description": "Generate financial reports",
                "is_system_permission": True,
            },
            # Secretariat
            {
                "code": "secretariat.view",
                "module": "SECRETARIAT",
                "description": "View secretariat module",
                "is_system_permission": True,
            },
            {
                "code": "secretariat.create_announcement",
                "module": "SECRETARIAT",
                "description": "Create announcements",
                "is_system_permission": True,
            },
            {
                "code": "secretariat.approve_announcement",
                "module": "SECRETARIAT",
                "description": "Approve announcements",
                "is_system_permission": True,
            },
            {
                "code": "secretariat.send_sms",
                "module": "SECRETARIAT",
                "description": "Send SMS notifications",
                "is_system_permission": True,
            },
            # Departments
            {
                "code": "departments.view",
                "module": "DEPARTMENTS",
                "description": "View departments",
                "is_system_permission": True,
            },
            {
                "code": "departments.manage",
                "module": "DEPARTMENTS",
                "description": "Manage departments",
                "is_system_permission": True,
            },
            {
                "code": "departments.request_funds",
                "module": "DEPARTMENTS",
                "description": "Request department funds",
                "is_system_permission": True,
            },
            {
                "code": "departments.assign_head",
                "module": "DEPARTMENTS",
                "description": "Assign or change official department head (API)",
                "is_system_permission": True,
            },
            {
                "code": "departments.assign_elder_in_charge",
                "module": "DEPARTMENTS",
                "description": "Assign or change elder in charge for a department",
                "is_system_permission": True,
            },
        ]

        for perm_data in permissions_data:
            perm, created = Permission.objects.get_or_create(
                code=perm_data["code"], defaults=perm_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created permission: {perm.code}")
                )

        perm_codes = [p["code"] for p in permissions_data]
        Permission.objects.filter(code__in=perm_codes).update(is_system_permission=True)

        # Link leadership permissions to roles (get_or_create — safe to re-run)
        leadership_links = [
            (
                "Pastor",
                ["departments.assign_head", "departments.assign_elder_in_charge"],
            ),
            (
                "First Elder",
                ["departments.assign_head", "departments.assign_elder_in_charge"],
            ),
            (
                "Secretary",
                ["departments.assign_head", "departments.assign_elder_in_charge"],
            ),
            ("Department Head", ["departments.assign_head"]),
            (
                "Elder in charge",
                ["departments.assign_elder_in_charge"],
            ),
        ]
        linked = 0
        for role_name, codes in leadership_links:
            role = Role.objects.filter(name=role_name).first()
            if not role:
                continue
            for code in codes:
                perm = Permission.objects.filter(code=code).first()
                if not perm:
                    continue
                _, created = RolePermission.objects.get_or_create(
                    role=role, permission=perm
                )
                if created:
                    linked += 1
        if linked:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Linked {linked} new role–permission row(s) for leadership."
                )
            )

        self.stdout.write(
            "Applied is_system_role / is_system_permission flags to seeded catalog."
        )
        self.stdout.write(self.style.SUCCESS("Initial data setup complete!"))
