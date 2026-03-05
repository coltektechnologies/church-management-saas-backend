"""
Automated backup task (Celery Beat). Run daily to create full DB backup.
"""

from backup.services.backup_service import BackupService
from church_saas.celery import app


@app.task(bind=True)
def run_automated_backup(self):
    """Create a full database backup. Called by Celery Beat (e.g. daily)."""
    record, err = BackupService.create(created_by_id=None, notes="Automated backup")
    if err:
        return {"status": "error", "error": err}
    return {"status": "created", "backup_id": str(record.id), "path": record.file_path}
