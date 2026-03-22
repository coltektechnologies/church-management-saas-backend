"""
List churches by notification access (email/SMS):
- Churches WITH email/SMS access (not on FREE plan) and their admins
- Churches on FREE plan and their admins
"""

from django.core.management.base import BaseCommand

from accounts.models import Church, User, UserRole


class Command(BaseCommand):
    help = (
        "List churches with email/SMS access (non-free plan), "
        "and churches on FREE plan, with their admins."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format: table (readable) or json",
        )

    def get_church_admins(self, church):
        """Return list of admin users for a church (role level 1 or 2; else any user)."""
        admin_roles = UserRole.objects.filter(
            church=church, role__level__in=[1, 2], is_active=True
        ).select_related("user", "role")
        if admin_roles:
            return [
                {
                    "email": ur.user.email,
                    "name": getattr(ur.user, "full_name", None)
                    or ur.user.get_full_name()
                    or ur.user.email,
                    "role": ur.role.name,
                }
                for ur in admin_roles
            ]
        # Fallback: any active user for this church
        users = User.objects.filter(church=church, is_active=True)[:5]
        return [
            {
                "email": u.email,
                "name": getattr(u, "full_name", None) or u.get_full_name() or u.email,
                "role": "User",
            }
            for u in users
        ]

    def get_church_data(self, church, has_sms_email_access):
        admins = self.get_church_admins(church)
        return {
            "id": str(church.id),
            "name": church.name,
            "email": church.email,
            "subdomain": church.subdomain,
            "subscription_plan": church.subscription_plan,
            "has_email_sms_access": has_sms_email_access,
            "admins": admins,
        }

    def handle(self, *args, **options):
        output_format = options["format"]

        # Churches WITH email/SMS access (not FREE)
        with_access = Church.objects.exclude(subscription_plan="FREE").order_by("name")
        # Churches on FREE plan
        free_plan = Church.objects.filter(subscription_plan="FREE").order_by("name")

        with_access_data = [
            self.get_church_data(c, has_sms_email_access=True) for c in with_access
        ]
        free_data = [
            self.get_church_data(c, has_sms_email_access=False) for c in free_plan
        ]

        if output_format == "json":
            import json

            self.stdout.write(
                json.dumps(
                    {
                        "with_email_sms_access": with_access_data,
                        "free_plan": free_data,
                    },
                    indent=2,
                )
            )
            return

        # Table format
        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(
            self.style.SUCCESS(
                f"CHURCHES WITH EMAIL/SMS ACCESS (not on FREE plan): {with_access.count()}"
            )
        )
        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        for d in with_access_data:
            self.stdout.write(f"  Church: {d['name']}")
            self.stdout.write(
                f"    Email: {d['email']}  |  Subdomain: {d['subdomain']}  |  Plan: {d['subscription_plan']}"
            )
            if d["admins"]:
                for a in d["admins"]:
                    self.stdout.write(f"    Admin: {a['email']}  ({a['role']})")
            else:
                self.stdout.write(
                    self.style.WARNING("    Admin: (no admin role found)")
                )
            self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(
            self.style.WARNING(
                f"CHURCHES ON FREE PLAN (no email/SMS access): {free_plan.count()}"
            )
        )
        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        for d in free_data:
            self.stdout.write(f"  Church: {d['name']}")
            self.stdout.write(
                f"    Email: {d['email']}  |  Subdomain: {d['subdomain']}  |  Plan: {d['subscription_plan']}"
            )
            if d["admins"]:
                for a in d["admins"]:
                    self.stdout.write(f"    Admin: {a['email']}  ({a['role']})")
            else:
                self.stdout.write(
                    self.style.WARNING("    Admin: (no admin role found)")
                )
            self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"Total with access: {len(with_access_data)}  |  Total on FREE: {len(free_data)}"
            )
        )
