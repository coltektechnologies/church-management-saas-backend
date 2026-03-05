import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from django.conf import settings


def upload_announcement_media(file, church_name, folder_type="announcements"):
    """
    Upload media to Cloudinary with church-specific folder structure.

    Args:
        file: The file to upload (Django InMemoryUploadedFile or similar)
        church_name: Name of the church (will be used in folder path)
        folder_type: Type of media (e.g., 'announcements', 'profiles', etc.)

    Returns:
        dict: Cloudinary upload response containing URL and other metadata
    """
    # Configure Cloudinary
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

    # Create folder path: church_name/folder_type/
    folder_path = f"{church_name.lower().replace(' ', '_')}/{folder_type}"

    # Upload the file
    upload_result = cloudinary.uploader.upload(
        file,
        folder=folder_path,
        resource_type="auto",  # Automatically detect if it's an image, video, etc.
        use_filename=True,  # Use the original filename
        unique_filename=True,  # Add a unique suffix to prevent overwrites
        overwrite=False,  # Don't overwrite existing files with the same name
    )

    return upload_result


def get_optimized_url(public_id, **transformations):
    """
    Generate an optimized URL for a Cloudinary resource.

    Args:
        public_id: The public ID of the resource
        **transformations: Additional transformation parameters

    Returns:
        str: Optimized URL
    """
    # Default transformations
    default_transformations = {"fetch_format": "auto", "quality": "auto"}

    # Merge with any provided transformations
    default_transformations.update(transformations)

    # Generate URL
    url, _ = cloudinary_url(public_id, **default_transformations)
    return url
