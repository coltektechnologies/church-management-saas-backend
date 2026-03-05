"""
Admin-only view: create a database backup (full, lightweight, or tenant); download backup file.
"""

import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Church
from backup.models import BackupRecord
from backup.services.backup_service import BackupService


@staff_member_required
def admin_create_backup(request):
    """Create a DB backup (type chosen by user) and redirect to backup list."""
    churches = list(
        Church.objects.filter(deleted_at__isnull=True)
        .order_by("name")
        .values("id", "name", "subdomain")
    )
    backup_types = BackupRecord.BACKUP_TYPE_CHOICES

    if request.method == "POST":
        backup_type = (
            request.POST.get("backup_type") or ""
        ).strip() or BackupRecord.BACKUP_TYPE_FULL
        notes = (request.POST.get("notes") or "").strip()[:255]
        church_id = (request.POST.get("church_id") or "").strip() or None
        created_by_id = str(request.user.id) if request.user else None

        if backup_type == BackupRecord.BACKUP_TYPE_TENANT and not church_id:
            messages.error(request, "Please select a church for tenant backup.")
            return render(
                request,
                "admin/backup/backuprecord/create_backup.html",
                {
                    "title": "Create backup",
                    "backup_types": backup_types,
                    "churches": churches,
                },
            )

        record, err = BackupService.create(
            backup_type=backup_type,
            created_by_id=created_by_id,
            notes=notes,
            church_id=church_id,
        )
        if err:
            messages.error(request, f"Backup failed: {err}")
        else:
            messages.success(
                request,
                f"Backup created: {record.get_backup_type_display()} — {record.file_path} ({record.file_size_bytes or 0:,} bytes)",
            )
        return redirect("admin:backup_backuprecord_changelist")

    return render(
        request,
        "admin/backup/backuprecord/create_backup.html",
        {"title": "Create backup", "backup_types": backup_types, "churches": churches},
    )


@staff_member_required
def admin_download_backup(request, object_id):
    """Serve the backup file for download (staff only)."""
    record = get_object_or_404(BackupRecord, id=object_id)
    if not record.file_path or not os.path.isfile(record.file_path):
        raise Http404("Backup file not found on disk.")
    filename = os.path.basename(record.file_path)
    return FileResponse(
        open(record.file_path, "rb"),
        as_attachment=True,
        filename=filename,
        content_type="application/json",
    )
