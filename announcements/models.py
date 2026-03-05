import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User


class AnnouncementCategory(models.Model):
    """Categories for organizing announcements"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="announcement_categories",
        db_column="church_id",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcement_categories"
        verbose_name = _("Announcement Category")
        verbose_name_plural = _("Announcement Categories")
        unique_together = ("church", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.church.name})"


class AnnouncementTemplate(models.Model):
    """Templates for announcements"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="announcement_templates",
        db_column="church_id",
    )
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcement_templates"
        verbose_name = _("Announcement Template")
        verbose_name_plural = _("Announcement Templates")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.church.name})"


class Announcement(models.Model):
    """Announcement model for church communications"""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        PENDING_REVIEW = "PENDING_REVIEW", _("Pending Review")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        PUBLISHED = "PUBLISHED", _("Published")
        ARCHIVED = "ARCHIVED", _("Archived")

    class Priority(models.TextChoices):
        LOW = "LOW", _("Low")
        MEDIUM = "MEDIUM", _("Medium")
        HIGH = "HIGH", _("High")
        URGENT = "URGENT", _("Urgent")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
        db_column="church_id",
    )
    category = models.ForeignKey(
        AnnouncementCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    template = models.ForeignKey(
        AnnouncementTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    is_featured = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    allow_sharing = models.BooleanField(default=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_announcements",
        db_column="created_by_id",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_announcements",
        db_column="approved_by_id",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcements"
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")
        ordering = ["-publish_at", "-created_at"]
        indexes = [
            models.Index(fields=["church", "status"]),
            models.Index(fields=["publish_at", "expires_at"]),
            models.Index(fields=["is_featured"]),
            models.Index(fields=["is_pinned"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_published(self):
        """Check if the announcement is currently published"""
        now = timezone.now()
        return (
            self.status == self.Status.PUBLISHED
            and (self.publish_at is None or self.publish_at <= now)
            and (self.expires_at is None or self.expires_at > now)
        )


class AnnouncementAttachment(models.Model):
    """Attachments for announcements (images, documents, etc.)"""

    class AttachmentType(models.TextChoices):
        IMAGE = "IMAGE", _("Image")
        DOCUMENT = "DOCUMENT", _("Document")
        PDF = "PDF", _("PDF")
        AUDIO = "AUDIO", _("Audio")
        VIDEO = "VIDEO", _("Video")
        OTHER = "OTHER", _("Other")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.URLField(max_length=1000)  # Store Cloudinary URL
    file_public_id = models.CharField(
        max_length=500, blank=True
    )  # Store Cloudinary public ID
    file_type = models.CharField(
        max_length=20, choices=AttachmentType.choices, default=AttachmentType.OTHER
    )
    display_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_file_type_display()}: {self.display_name or 'Unnamed'}"

    def save(self, *args, **kwargs):
        from django.core.files.uploadedfile import InMemoryUploadedFile

        from .cloudinary_utils import upload_announcement_media

        # Handle file upload to Cloudinary if it's a new file
        if hasattr(self, "file_data") and isinstance(
            self.file_data, InMemoryUploadedFile
        ):
            try:
                # Upload to Cloudinary
                church_name = self.announcement.church.name
                result = upload_announcement_media(
                    self.file_data, church_name=church_name, folder_type="announcements"
                )

                # Store Cloudinary URL and public ID
                self.file = result.get("secure_url")
                self.file_public_id = result.get("public_id")

                # Set display name if not provided
                if not self.display_name:
                    self.display_name = self.file_data.name

                # Set file type based on Cloudinary resource type
                resource_type = result.get("resource_type", "").upper()
                if resource_type == "IMAGE":
                    self.file_type = self.AttachmentType.IMAGE
                elif resource_type == "VIDEO":
                    self.file_type = self.AttachmentType.VIDEO
                elif resource_type == "RAW" and self.file_data.name.lower().endswith(
                    ".pdf"
                ):
                    self.file_type = self.AttachmentType.PDF

            except Exception as e:
                # Log the error and re-raise
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error uploading to Cloudinary: {str(e)}")
                raise

        # Set file_type based on file extension if not provided
        if not self.file_type or self.file_type == self.AttachmentType.OTHER:
            if hasattr(self, "file_data") and hasattr(self.file_data, "name"):
                ext = self.file_data.name.split(".")[-1].lower()
                if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                    self.file_type = self.AttachmentType.IMAGE
                elif ext == "pdf":
                    self.file_type = self.AttachmentType.PDF
                elif ext in ["doc", "docx", "txt", "rtf"]:
                    self.file_type = self.AttachmentType.DOCUMENT
                elif ext in ["mp3", "wav", "ogg"]:
                    self.file_type = self.AttachmentType.AUDIO
                elif ext in ["mp4", "mov", "avi", "wmv"]:
                    self.file_type = self.AttachmentType.VIDEO

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to also remove the file from Cloudinary"""
        import cloudinary.uploader
        from django.conf import settings

        try:
            if self.file_public_id:
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET,
                    secure=True,
                )
                cloudinary.uploader.destroy(self.file_public_id)
        except Exception as e:
            # Log the error but don't prevent deletion
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting file from Cloudinary: {str(e)}")

        super().delete(*args, **kwargs)
