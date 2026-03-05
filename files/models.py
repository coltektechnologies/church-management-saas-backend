"""
Church file model: metadata for files stored in Cloudinary.
Folder structure: {church_folder}/files/{subfolder}/ (e.g. church_name/files/documents/)
"""

import re
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User


def _church_folder_name(church: Church) -> str:
    """Safe folder name from church: name or id, no spaces/special chars."""
    if church.name:
        base = re.sub(r"[^\w\-]", "_", church.name.strip()).strip("_") or str(church.id)
    else:
        base = str(church.id)
    return base.lower()[:64]


class ChurchFile(models.Model):
    """
    File metadata for uploads stored in Cloudinary.
    Church-scoped; optional subfolder within church's file root.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="church_files",
        db_column="church_id",
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_files",
    )

    # Cloudinary
    public_id = models.CharField(max_length=500, db_index=True)
    secure_url = models.URLField(max_length=1000)
    resource_type = models.CharField(
        max_length=20, default="image"
    )  # image, video, raw, auto
    cloudinary_version = models.CharField(max_length=50, blank=True, null=True)

    # Our folder (for display/organization): church_folder/files/subfolder
    folder = models.CharField(max_length=300)
    subfolder = models.CharField(max_length=100, blank=True, default="")

    # File info
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    is_image = models.BooleanField(default=False)

    # Optional description / tags
    description = models.CharField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True)  # list of strings

    # Soft delete for garbage collection
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "church_files"
        verbose_name = _("Church file")
        verbose_name_plural = _("Church files")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "deleted_at"]),
            models.Index(fields=["church", "subfolder"]),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.church.name})"

    @classmethod
    def church_folder(cls, church: Church) -> str:
        return _church_folder_name(church)
