from django.contrib import admin
from django.urls import path

from .admin_views import admin_upload_file
from .models import ChurchFile


@admin.register(ChurchFile)
class ChurchFileAdmin(admin.ModelAdmin):
    list_display = [
        "original_filename",
        "church",
        "uploaded_by_display",
        "subfolder",
        "content_type",
        "size_bytes",
        "is_image",
        "created_at",
        "deleted_at",
    ]
    list_filter = ["church", "is_image", "resource_type"]
    search_fields = ["original_filename", "public_id", "description"]
    readonly_fields = [
        "id",
        "uploaded_by",
        "public_id",
        "secure_url",
        "cloudinary_version",
        "folder",
        "created_at",
        "updated_at",
    ]
    change_list_template = "admin/files/churchfile/change_list.html"

    @admin.display(description="Uploaded by")
    def uploaded_by_display(self, obj):
        if not obj or not obj.uploaded_by_id:
            return "—"
        u = obj.uploaded_by
        return (
            getattr(u, "email", None)
            or getattr(u, "get_full_name", lambda: "")().strip()
            or str(u)
        )

    def has_add_permission(self, request):
        # Use "Upload file" instead of manual add (files come from Cloudinary)
        return False

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "upload/",
                admin.site.admin_view(admin_upload_file),
                name="files_churchfile_upload",
            ),
        ]
        return extra + urls
