"""
Test command for audit logging functionality
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from accounts.models import AuditLog

User = get_user_model()


class Command(BaseCommand):
    help = "Test audit logging functionality"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting audit logging test..."))

        # Test user creation
        self.stdout.write("\n=== Testing User Creation ===")
        try:
            user = User.objects.create_user(
                email="test@example.com",
                username="testuser",
                password="testpass123",
                first_name="Test",
                last_name="User",
            )
            self.stdout.write(self.style.SUCCESS(f"Created test user: {user.email}"))

            # Test user update
            self.stdout.write("\n=== Testing User Update ===")
            user.first_name = "Updated Name"
            user.save()
            self.stdout.write(self.style.SUCCESS("Updated test user"))

            # Test audit log retrieval
            self.stdout.write("\n=== Testing Audit Log Retrieval ===")
            logs = AuditLog.objects.filter(user=user).order_by("-created_at")
            self.stdout.write(f"Found {logs.count()} audit log entries for test user")

            for log in logs[:5]:  # Show first 5 logs
                self.stdout.write(
                    f"\n[{log.created_at}] {log.get_action_display()}: {log.description}"
                )
                if log.changes:
                    self.stdout.write("Changes:")
                    for field, values in log.changes.items():
                        self.stdout.write(
                            f'  {field}: {values.get("old", "")} → {values.get("new", "")}'
                        )

            # Cleanup
            self.stdout.write("\n=== Cleaning Up ===")
            user.delete()
            self.stdout.write(self.style.SUCCESS("Test user deleted"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during test: {str(e)}"))
            raise e

        self.stdout.write(
            self.style.SUCCESS("\nAudit logging test completed successfully!")
        )
