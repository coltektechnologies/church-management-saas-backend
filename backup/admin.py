import os

from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

from .admin_views import admin_create_backup, admin_download_backup
from .models import BackupRecord


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "backup_type",
        "church_id",
        "file_path_short",
        "file_size_bytes",
        "download_link",
        "created_by_id",
        "created_at",
        "notes",
    ]
    list_filter = ["backup_type"]
    search_fields = ["notes", "file_path"]
    readonly_fields = [
        "id",
        "backup_type",
        "church_id",
        "file_path",
        "file_size_bytes",
        "created_by_id",
        "created_at",
        "notes",
    ]
    change_list_template = "admin/backup/backuprecord/change_list.html"
    change_form_template = "admin/backup/backuprecord/change_form.html"

    def file_path_short(self, obj):
        return (
            obj.file_path[:60] + "…"
            if obj.file_path and len(obj.file_path) > 60
            else (obj.file_path or "—")
        )

    file_path_short.short_description = "File path"

    def download_link(self, obj):
        if not obj.file_path or not os.path.isfile(obj.file_path):
            return "—"
        url = reverse("admin:backup_backuprecord_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)

    download_link.short_description = ""

    def has_add_permission(self, request):
        # Use "Create backup" action instead of manual add
        return False

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "create/",
                admin.site.admin_view(admin_create_backup),
                name="backup_backuprecord_create",
            ),
            path(
                "<uuid:object_id>/download/",
                admin.site.admin_view(admin_download_backup),
                name="backup_backuprecord_download",
            ),
        ]
        return extra + urls
