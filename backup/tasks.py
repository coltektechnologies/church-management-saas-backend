"""
Automated backup task (Celery Beat) + optional admin-triggered backup.
"""

from backup.services.backup_service import BackupService
from church_saas.celery import app


@app.task(bind=True)
def run_automated_backup(self):
    """Create a full database backup. Called by Celery Beat (e.g. weekly)."""
    record, err = BackupService.create(created_by_id=None, notes="Automated backup")
    if err:
        return {"status": "error", "error": err}
    return {
        "status": "created",
        "backup_id": str(record.id),
        "path": record.file_path,
    }


@app.task(bind=True)
def run_admin_backup_task(
    self,
    backup_type,
    notes,
    church_id,
    created_by_id,
):
    """
    Run backup from Django admin form (full / lightweight / tenant).
    Must run in a worker — not in the HTTP thread — so dumpdata can take 30+ minutes
    without blocking the browser.
    """
    record, err = BackupService.create(
        backup_type=backup_type,
        created_by_id=created_by_id,
        notes=(notes or "")[:255],
        church_id=church_id,
        lock_wait_seconds=7100,
    )
    if err:
        return {"status": "error", "error": err}
    return {
        "status": "created",
        "backup_id": str(record.id),
        "path": record.file_path,
    }
