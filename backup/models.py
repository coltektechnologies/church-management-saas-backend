"""
Backup metadata: track created backups for list/restore.
"""

import uuid

from django.conf import settings
from django.db import models


class BackupRecord(models.Model):
    """Metadata for a database backup (full, lightweight, or tenant export)."""

    BACKUP_TYPE_FULL = "full"
    BACKUP_TYPE_LIGHTWEIGHT = "lightweight"
    BACKUP_TYPE_TENANT = "tenant"

    BACKUP_TYPE_CHOICES = [
        (BACKUP_TYPE_FULL, "Full database"),
        (BACKUP_TYPE_LIGHTWEIGHT, "Lightweight (exclude logs/audit)"),
        (BACKUP_TYPE_TENANT, "Tenant (single church export)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_type = models.CharField(
        max_length=20, choices=BACKUP_TYPE_CHOICES, default=BACKUP_TYPE_FULL
    )
    file_path = models.CharField(max_length=500)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)
    church_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="For tenant backups: the church that was exported.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "backup_records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.backup_type} @ {self.created_at}"
