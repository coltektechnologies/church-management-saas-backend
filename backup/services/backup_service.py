"""
Full database backup (dumpdata) and restore (loaddata).
Backups stored under BACKUP_ROOT (default: media/backups/).
"""

import os
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.core.management import call_command

from backup.models import BackupRecord


def get_backup_root():
    return getattr(settings, "BACKUP_ROOT", None) or os.path.join(
        settings.MEDIA_ROOT, "backups"
    )


def ensure_backup_dir():
    root = get_backup_root()
    os.makedirs(root, exist_ok=True)
    return root


# Excludes for lightweight backup (smaller, no audit/logs)
LIGHTWEIGHT_EXCLUDE = [
    "sessions.Session",
    "contenttypes.ContentType",
    "admin.LogEntry",
    "core.AuditLog",
    "notifications.Notification",
    "notifications.NotificationBatch",
    "notifications.SMSLog",
    "notifications.EmailLog",
]


class BackupService:
    """Create DB backup (full, lightweight, or tenant), list backups, restore from backup."""

    @staticmethod
    def create(backup_type=None, created_by_id=None, notes="", church_id=None):
        """
        Create a backup. backup_type: full, lightweight, or tenant.
        For tenant, church_id is required.
        Returns (BackupRecord, error_message). error_message is None on success.
        """
        backup_type = backup_type or BackupRecord.BACKUP_TYPE_FULL
        if backup_type == BackupRecord.BACKUP_TYPE_TENANT and not church_id:
            return None, "Church is required for tenant backup."

        ensure_backup_dir()
        root = get_backup_root()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{backup_type}_{stamp}.json"
        file_path = os.path.join(root, filename)

        if backup_type == BackupRecord.BACKUP_TYPE_TENANT:
            from backup.services.tenant_export_import import \
                TenantExportImportService

            data, err = TenantExportImportService.export_tenant_data(str(church_id))
            if err:
                return None, err
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(data)
                size = os.path.getsize(file_path)
                record = BackupRecord.objects.create(
                    backup_type=backup_type,
                    file_path=file_path,
                    file_size_bytes=size,
                    created_by_id=created_by_id,
                    church_id=church_id,
                    notes=(notes or "")[:255],
                )
                return record, None
            except Exception as e:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                return None, str(e)

        # full or lightweight: dumpdata
        exclude = ["sessions.Session", "contenttypes.ContentType", "admin.LogEntry"]
        if backup_type == BackupRecord.BACKUP_TYPE_LIGHTWEIGHT:
            exclude = LIGHTWEIGHT_EXCLUDE

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                call_command(
                    "dumpdata",
                    "--natural-foreign",
                    "--natural-primary",
                    "--indent",
                    "2",
                    exclude=exclude,
                    stdout=f,
                )
            size = os.path.getsize(file_path)
            record = BackupRecord.objects.create(
                backup_type=backup_type,
                file_path=file_path,
                file_size_bytes=size,
                created_by_id=created_by_id,
                notes=(notes or "")[:255],
            )
            return record, None
        except Exception as e:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            return None, str(e)

    @staticmethod
    def list_backups(backup_type=None):
        """Return list of BackupRecord ordered by created_at desc. Optional filter by backup_type."""
        qs = BackupRecord.objects.all().order_by("-created_at")
        if backup_type:
            qs = qs.filter(backup_type=backup_type)
        return list(qs)

    @staticmethod
    def get_backup(backup_id):
        """Return BackupRecord by id or None."""
        try:
            return BackupRecord.objects.get(id=backup_id)
        except BackupRecord.DoesNotExist:
            return None

    @staticmethod
    def restore(backup_id):
        """
        Run loaddata from the backup file. Only full and lightweight backups can be restored this way.
        Tenant backups use the import/tenant-data API instead.
        Returns (success: bool, error_message: str).
        """
        record = BackupService.get_backup(backup_id)
        if not record or not os.path.isfile(record.file_path):
            return False, "Backup not found or file missing."
        if record.backup_type == BackupRecord.BACKUP_TYPE_TENANT:
            return (
                False,
                "Tenant backups cannot be restored here; use Import tenant data instead.",
            )
        try:
            call_command("loaddata", record.file_path, verbosity=1)
            return True, None
        except Exception as e:
            return False, str(e)
