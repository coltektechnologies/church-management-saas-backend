"""
Cloudinary file service: upload, validation, image compression, church folder structure.
Credentials from Django settings (env vars); never hardcode secrets.
"""

import logging
import re
from typing import Optional, Tuple

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from accounts.models import Church
from files.models import ChurchFile

logger = logging.getLogger(__name__)


def _config_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def _church_folder(church: Church) -> str:
    """Base folder for church: safe name or id."""
    if church.name:
        base = re.sub(r"[^\w\-]", "_", church.name.strip()).strip("_") or str(church.id)
    else:
        base = str(church.id)
    return base.lower()[:64]


def _full_folder(church: Church, subfolder: str = "") -> str:
    """Full path: {church_folder}/files/{subfolder}"""
    base = f"{_church_folder(church)}/files"
    if subfolder and subfolder.strip():
        sub = re.sub(r"[^\w\-/]", "_", subfolder.strip()).strip("/")[:100]
        return f"{base}/{sub}" if sub else base
    return base


# Validation
def validate_file(
    file: UploadedFile,
    max_size_mb: Optional[int] = None,
    allowed_types: Optional[list] = None,
) -> Tuple[bool, str]:
    """
    Validate type and size. Returns (ok, error_message).
    """
    max_size_mb = max_size_mb or getattr(settings, "FILE_MAX_SIZE_MB", 20)
    allowed = allowed_types or getattr(settings, "FILE_ALLOWED_TYPES", [])
    max_bytes = max_size_mb * 1024 * 1024

    if file.size is not None and file.size > max_bytes:
        return False, f"File size exceeds {max_size_mb} MB limit."

    content_type = getattr(file, "content_type", "") or ""
    if content_type and allowed and content_type not in allowed:
        return False, f"File type not allowed: {content_type}"

    # Fallback: check extension for common types
    name = getattr(file, "name", "") or ""
    if not content_type and name:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        allowed_ext = {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "webp",
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "txt",
            "csv",
            "mp4",
            "webm",
            "mov",
        }
        if ext not in allowed_ext:
            return False, f"File extension .{ext} not allowed."

    return True, ""


def _is_image(content_type: str, resource_type: str) -> bool:
    return resource_type == "image" or (content_type or "").startswith("image/")


class CloudinaryFileService:
    """
    Upload to Cloudinary with church folder and optional image compression.
    """

    def __init__(self, church: Church):
        self.church = church
        _config_cloudinary()

    def upload(
        self,
        file: UploadedFile,
        uploaded_by_id=None,
        subfolder: str = "",
        description: str = "",
        tags: Optional[list] = None,
        use_compression: bool = True,
    ) -> ChurchFile:
        """
        Validate, upload to Cloudinary (with image compression if image), create ChurchFile.
        Folder: {church_name}/files/{subfolder}/
        """
        ok, err = validate_file(file)
        if not ok:
            raise ValueError(err)

        folder_path = _full_folder(self.church, subfolder)
        content_type = getattr(file, "content_type", "") or ""

        # Image: apply quality and format for compression
        extra = {}
        if use_compression and _is_image(content_type, "image"):
            extra["quality"] = "auto:good"
            extra["fetch_format"] = "auto"

        upload_result = cloudinary.uploader.upload(
            file,
            folder=folder_path,
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            **extra,
        )

        public_id = upload_result.get("public_id", "")
        secure_url = upload_result.get("secure_url", "")
        resource_type = upload_result.get("resource_type", "image")
        version = upload_result.get("version")
        bytes_val = upload_result.get("bytes", 0) or getattr(file, "size", 0) or 0

        church_file = ChurchFile.objects.create(
            church=self.church,
            uploaded_by_id=uploaded_by_id,
            public_id=public_id,
            secure_url=secure_url,
            resource_type=resource_type,
            cloudinary_version=str(version) if version else None,
            folder=folder_path,
            subfolder=(subfolder or "").strip(),
            original_filename=getattr(file, "name", "") or "upload",
            content_type=content_type,
            size_bytes=bytes_val,
            is_image=_is_image(content_type, resource_type),
            description=(description or "").strip()[:500],
            tags=tags or [],
        )
        return church_file

    def get_optimized_url(self, church_file: ChurchFile, **transformations) -> str:
        """URL with optional transformations (e.g. width, height, crop)."""
        _config_cloudinary()
        opts = {"quality": "auto", "fetch_format": "auto"}
        opts.update(transformations)
        url, _ = cloudinary_url(church_file.public_id, **opts)
        return url

    def destroy_remote(self, public_id: str, resource_type: str = "image") -> bool:
        """Remove file from Cloudinary. Returns True if destroyed or not found."""
        _config_cloudinary()
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result.get("result") in ("ok", "not found")
        except Exception as e:
            logger.warning("Cloudinary destroy failed for %s: %s", public_id, e)
            return False
