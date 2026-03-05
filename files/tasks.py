"""
File cleanup: purge soft-deleted files from Cloudinary and delete DB records.
"""

import logging

from django.conf import settings
from django.utils import timezone

from church_saas.celery import app
from files.models import ChurchFile
from files.services import CloudinaryFileService

logger = logging.getLogger(__name__)


@app.task(bind=True)
def cleanup_deleted_files(self):
    """
    Find ChurchFiles with deleted_at set, destroy on Cloudinary, then delete from DB.
    Run periodically (e.g. daily) via Celery Beat.
    """
    # Only consider records soft-deleted at least 1 hour ago (allow undo window)
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=1)
    qs = ChurchFile.objects.filter(deleted_at__isnull=False, deleted_at__lte=cutoff)
    count = 0
    for church_file in qs:
        try:
            service = CloudinaryFileService(church_file.church)
            if service.destroy_remote(
                church_file.public_id, church_file.resource_type or "image"
            ):
                church_file.delete()
                count += 1
            else:
                logger.warning(
                    "Could not destroy Cloudinary asset %s", church_file.public_id
                )
        except Exception as e:
            logger.exception("Cleanup failed for file %s: %s", church_file.id, e)
    return {"purged": count}
