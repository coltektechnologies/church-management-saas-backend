from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog, Church


class Command(BaseCommand):
    help = "Delete a church and its related audit logs"

    def add_arguments(self, parser):
        parser.add_argument("church_id", type=str, help="UUID of the church to delete")

    def handle(self, *args, **options):
        church_id = options["church_id"]

        try:
            with transaction.atomic():
                # Delete the audit logs first
                audit_logs_deleted, _ = AuditLog.objects.filter(
                    church_id=church_id
                ).delete()

                # Then delete the church
                church = Church.objects.get(id=church_id)
                church_name = church.name
                church.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted church "{church_name}" and {audit_logs_deleted} related audit logs'
                    )
                )

        except Church.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Church with ID {church_id} does not exist")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error deleting church: {str(e)}"))
