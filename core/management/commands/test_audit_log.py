from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from accounts.models import AuditLog, Church

User = get_user_model()


class Command(BaseCommand):
    help = "Test audit logging functionality"

    def handle(self, *args, **options):
        # Create a test church if not exists
        church, _ = Church.objects.get_or_create(
            name="Test Church",
            email="test@example.com",
            subdomain="test",
            country="Ghana",
            region="Greater Accra",
            city="Accra",
        )

        # Create a test user if not exists
        user, created = User.objects.get_or_create(
            username="testuser",
            defaults={"email": "test@example.com", "is_active": True, "church": church},
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created test user"))

        # Create a mock request
        factory = RequestFactory()
        request = factory.get("/")
        request.user = user

        # Update the user to trigger audit log
        user.first_name = "Test"
        user.last_name = "User"
        user.save()

        # Manually log an action to test the AuditLog.log method
        AuditLog.log(
            user=user,
            action="UPDATE",
            instance=user,
            request=request,
            changes={"first_name": {"old": None, "new": "Test"}},
            description="Test audit log entry",
        )

        # Check if audit logs were created
        logs = AuditLog.objects.filter(
            model_name="User",  # Note: Model names are capitalized in the audit log
            object_id=str(user.id),
        ).order_by("-created_at")

        if logs.exists():
            self.stdout.write(self.style.SUCCESS("Audit logs found:"))
            for log in logs[:5]:  # Show last 5 logs
                self.stdout.write(
                    f"- {log.created_at}: {log.action} - {log.description}"
                )
        else:
            self.stdout.write(self.style.ERROR("No audit logs found for the test user"))

        # Check if the audit signals are connected to the User model
        from django.apps import apps
        from django.db.models.signals import post_save

        user_model = apps.get_model("accounts", "User")
        has_audit_handlers = False

        for receiver in post_save._live_receivers(user_model):
            if "audit_model_changes" in str(receiver):
                has_audit_handlers = True
                break

        if has_audit_handlers:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ Audit signal handlers are properly connected to User model"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "\n❌ Audit signal handlers are NOT connected to User model"
                )
            )

        # Check if we have any audit logs
        if logs.exists():
            self.stdout.write(self.style.SUCCESS("✅ Audit logging is working!"))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {logs.count()} audit log entries for the test user"
                )
            )

            # Show the most recent log entry
            latest_log = logs.first()
            self.stdout.write("\nMost recent log entry:")
            self.stdout.write(f"- Action: {latest_log.action}")
            self.stdout.write(f"- Model: {latest_log.model_name}")
            self.stdout.write(f"- Description: {latest_log.description}")
            self.stdout.write(f"- Timestamp: {latest_log.created_at}")

            if latest_log.changes:
                self.stdout.write("\nChanges:")
                try:
                    # Try to parse changes as JSON if it's a string
                    changes = latest_log.changes
                    if isinstance(changes, str):
                        import json

                        changes = json.loads(changes)

                    if isinstance(changes, dict):
                        for field, change in changes.items():
                            if isinstance(change, dict):
                                self.stdout.write(
                                    f"  - {field}: {change.get('old', 'None')} → {change.get('new', 'None')}"
                                )
                            else:
                                self.stdout.write(f"  - {field}: {change}")
                    else:
                        self.stdout.write(f"  {changes}")
                except Exception as e:
                    self.stdout.write(f"  Could not parse changes: {e}")
                    self.stdout.write(f"  Raw changes: {latest_log.changes}")
        else:
            self.stdout.write(
                self.style.ERROR("\n❌ No audit logs were created during this test")
            )
