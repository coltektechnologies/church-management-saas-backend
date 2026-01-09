import uuid

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

        # Create Roles
        roles_data = [
            {
                "name": "Pastor",
                "level": 1,
                "description": "Church Pastor - Full Access",
            },
            {
                "name": "First Elder",
                "level": 1,
                "description": "First Elder - Full Access",
            },
            {"name": "Secretary", "level": 2, "description": "Church Secretary"},
            {"name": "Treasurer", "level": 2, "description": "Church Treasurer"},
            {
                "name": "Department Head",
                "level": 3,
                "description": "Department Head/Staff",
            },
            {"name": "Member", "level": 4, "description": "Regular Church Member"},
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data["name"], defaults=role_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role.name}"))

        # Create Permissions
        permissions_data = [
            # Members
            {
                "code": "members.view_all",
                "module": "MEMBERS",
                "description": "View all members",
            },
            {
                "code": "members.create",
                "module": "MEMBERS",
                "description": "Create new members",
            },
            {
                "code": "members.edit",
                "module": "MEMBERS",
                "description": "Edit member details",
            },
            {
                "code": "members.delete",
                "module": "MEMBERS",
                "description": "Delete members",
            },
            {
                "code": "members.view_financial",
                "module": "MEMBERS",
                "description": "View member financial data",
            },
            # Treasury
            {
                "code": "treasury.view",
                "module": "TREASURY",
                "description": "View financial data",
            },
            {
                "code": "treasury.record_income",
                "module": "TREASURY",
                "description": "Record income",
            },
            {
                "code": "treasury.record_expense",
                "module": "TREASURY",
                "description": "Record expenses",
            },
            {
                "code": "treasury.approve_expense",
                "module": "TREASURY",
                "description": "Approve expense requests",
            },
            {
                "code": "treasury.generate_reports",
                "module": "TREASURY",
                "description": "Generate financial reports",
            },
            # Secretariat
            {
                "code": "secretariat.view",
                "module": "SECRETARIAT",
                "description": "View secretariat module",
            },
            {
                "code": "secretariat.create_announcement",
                "module": "SECRETARIAT",
                "description": "Create announcements",
            },
            {
                "code": "secretariat.approve_announcement",
                "module": "SECRETARIAT",
                "description": "Approve announcements",
            },
            {
                "code": "secretariat.send_sms",
                "module": "SECRETARIAT",
                "description": "Send SMS notifications",
            },
            # Departments
            {
                "code": "departments.view",
                "module": "DEPARTMENTS",
                "description": "View departments",
            },
            {
                "code": "departments.manage",
                "module": "DEPARTMENTS",
                "description": "Manage departments",
            },
            {
                "code": "departments.request_funds",
                "module": "DEPARTMENTS",
                "description": "Request department funds",
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

        self.stdout.write(self.style.SUCCESS("Initial data setup complete!"))
