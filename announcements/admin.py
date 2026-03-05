from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from announcements.filters import (DateRangeFilter, IsActiveFilter,
                                   PriorityFilter, StatusFilter)
# Local imports
from announcements.models import (Announcement, AnnouncementAttachment,
                                  AnnouncementCategory, AnnouncementTemplate)


class AnnouncementAttachmentInline(admin.TabularInline):
    model = AnnouncementAttachment
    extra = 1
    fields = ("file", "file_type", "display_name", "description")
    readonly_fields = ("file_preview",)

    def file_preview(self, obj):
        if obj.file:
            if obj.file_type in ["image", "pdf"]:
                return mark_safe(
                    f'<a href="{obj.file.url}" target="_blank">View {obj.get_file_type_display()}</a>'
                )
            return mark_safe(
                f'<a href="{obj.file.url}" target="_blank">Download {obj.get_file_type_display()}</a>'
            )
        return "No file"

    file_preview.short_description = "Preview"


@admin.register(AnnouncementCategory)
class AnnouncementCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "announcement_count", "is_active", "created_at")
    list_filter = (IsActiveFilter, ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "description")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("church", "name", "description", "is_active")}),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "church"):
            return qs.filter(church=request.user.church)
        return qs

    def announcement_count(self, obj):
        return obj.announcements.count()

    announcement_count.short_description = "Announcements"

    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, "church"):
            obj.church = request.user.church
        super().save_model(request, obj, form, change)


@admin.register(AnnouncementTemplate)
class AnnouncementTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "subject_preview", "is_active", "created_at")
    list_filter = (IsActiveFilter, ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "subject", "content")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("church", "name", "subject", "content", "is_active")}),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def subject_preview(self, obj):
        return obj.subject[:50] + ("..." if len(obj.subject) > 50 else "")

    subject_preview.short_description = "Subject"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "church"):
            return qs.filter(church=request.user.church)
        return qs

    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, "church"):
            obj.church = request.user.church
        super().save_model(request, obj, form, change)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status_badge",
        "priority_badge",
        "category",
        "is_featured",
        "is_pinned",
        "publish_at",
        "expires_at",
        "created_by",
    )
    list_filter = (
        StatusFilter,
        PriorityFilter,
        "is_featured",
        "is_pinned",
        "category",
        ("publish_at", admin.DateFieldListFilter),
        ("expires_at", admin.DateFieldListFilter),
        "created_at",
    )
    search_fields = ("title", "content", "created_by__email")
    list_editable = ("is_featured", "is_pinned")
    readonly_fields = (
        "created_at",
        "updated_at",
        "approved_at",
        "view_announcement_link",
    )
    fieldsets = (
        (
            "Content",
            {
                "fields": (
                    "church",
                    "title",
                    "content",
                    "category",
                    "template",
                    "status",
                    "priority",
                    "is_featured",
                    "is_pinned",
                    "allow_comments",
                    "allow_sharing",
                    "publish_at",
                    "expires_at",
                    "rejection_reason",
                )
            },
        ),
        (
            "Ownership",
            {
                "classes": ("collapse",),
                "fields": ("created_by", "approved_by", "approved_at"),
            },
        ),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "view_announcement_link"),
            },
        ),
    )
    inlines = [AnnouncementAttachmentInline]
    actions = [
        "publish_selected",
        "approve_selected",
        "reject_selected",
        "duplicate_selected",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, "church"):
                qs = qs.filter(church=request.user.church)
            else:
                qs = qs.none()
        return qs.prefetch_related("attachments", "category")

    def status_badge(self, obj):
        status_colors = {
            "DRAFT": "gray",
            "PENDING_REVIEW": "orange",
            "APPROVED": "blue",
            "PUBLISHED": "green",
            "REJECTED": "red",
        }
        return format_html(
            '<span class="status-badge" style="background: {}; color: white; '
            'padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            status_colors.get(obj.status, "gray"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def priority_badge(self, obj):
        priority_colors = {
            "LOW": "gray",
            "MEDIUM": "blue",
            "HIGH": "red",
        }
        return format_html(
            '<span class="priority-badge" style="background: {}; color: white; '
            'padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            priority_colors.get(obj.priority, "gray"),
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"
    priority_badge.admin_order_field = "priority"

    def view_announcement_link(self, obj):
        if obj.id:
            url = reverse("announcement-detail", kwargs={"pk": obj.id})
            return format_html('<a href="{}" target="_blank">View on Site</a>', url)
        return ""

    view_announcement_link.short_description = "Public View"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "church" in form.base_fields:
            if not request.user.is_superuser:
                # For non-superusers, set the church to their church if they have one
                if hasattr(request.user, "church"):
                    form.base_fields["church"].initial = request.user.church
                    form.base_fields["church"].disabled = True
                form.base_fields["church"].required = True
        return form

    def save_model(self, request, obj, form, change):
        # Set created_by for new announcements
        if not change:
            obj.created_by = request.user

        # Ensure church is set
        if not obj.church_id:
            if hasattr(request.user, "church"):
                obj.church = request.user.church
            else:
                # This will show as a form error instead of a 500
                from django import forms

                raise forms.ValidationError(
                    "You must be associated with a church to create announcements. "
                    "Please contact an administrator to assign you to a church."
                )

        # Handle approval
        if "status" in form.changed_data and obj.status == "APPROVED":
            obj.approved_by = request.user
            obj.approved_at = timezone.now()

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)

        # For existing objects, make church read-only for non-superusers
        if obj and "church" not in readonly_fields and not request.user.is_superuser:
            readonly_fields.append("church")

        # Make all fields read-only for non-superusers after publishing/rejection
        if (
            obj
            and obj.status in ["PUBLISHED", "REJECTED"]
            and not request.user.is_superuser
        ):
            return [f.name for f in self.model._meta.fields if f.name != "id"]

        return readonly_fields

    # Custom actions
    def publish_selected(self, request, queryset):
        updated = queryset.filter(status="APPROVED").update(
            status="PUBLISHED", publish_at=timezone.now()
        )
        self.message_user(request, f"Successfully published {updated} announcements.")

    publish_selected.short_description = "Publish selected approved announcements"

    def approve_selected(self, request, queryset):
        updated = queryset.filter(status="PENDING_REVIEW").update(
            status="APPROVED", approved_by=request.user, approved_at=timezone.now()
        )
        self.message_user(request, f"Approved {updated} announcements.")

    approve_selected.short_description = "Approve selected pending announcements"

    def reject_selected(self, request, queryset):
        updated = queryset.filter(status="PENDING_REVIEW").update(
            status="REJECTED", rejection_reason="Rejected in bulk by admin."
        )
        self.message_user(request, f"Rejected {updated} announcements.")

    reject_selected.short_description = "Reject selected pending announcements"

    def duplicate_selected(self, request, queryset):
        for announcement in queryset:
            announcement.id = None
            announcement.status = "DRAFT"
            announcement.title = f"{announcement.title} (Copy)"
            announcement.publish_at = None
            announcement.save()
        self.message_user(
            request, f"Duplicated {queryset.count()} announcements as drafts."
        )

    duplicate_selected.short_description = "Duplicate selected announcements as drafts"


@admin.register(AnnouncementAttachment)
class AnnouncementAttachmentAdmin(admin.ModelAdmin):
    list_display = ("display_name", "announcement_link", "file_type", "uploaded_at")
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("display_name", "announcement__title")
    readonly_fields = ("file_preview", "uploaded_at", "file_link")
    fields = (
        "announcement",
        "file",
        "file_type",
        "display_name",
        "description",
        "file_preview",
        "file_link",
        "uploaded_at",
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["file"] = forms.URLField(
            label="File URL",
            required=True,
            help_text="URL of the file (e.g., from Cloudinary or other storage)",
        )
        return form

    def announcement_link(self, obj):
        url = reverse(
            "admin:announcements_announcement_change", args=[obj.announcement.id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.announcement.title)

    announcement_link.short_description = "Announcement"
    announcement_link.admin_order_field = "announcement__title"

    def file_preview(self, obj):
        if obj.file:
            if obj.file_type in [
                AnnouncementAttachment.AttachmentType.IMAGE,
                AnnouncementAttachment.AttachmentType.PDF,
            ]:
                return format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-height: 200px; max-width: 100%;" />'
                    "</a>",
                    obj.file,
                    obj.file,
                )
        return "No preview available"

    file_preview.short_description = "Preview"

    def file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" class="button" target="_blank">View/Download {}</a>',
                obj.file,
                obj.get_file_type_display(),
            )
        return "No file"

    file_link.short_description = "File Link"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "church"):
            return qs.filter(announcement__church=request.user.church)
        return qs


# Add custom CSS and JS for admin
class AnnouncementAdminSite(admin.AdminSite):
    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        return urls

    class Media:
        css = {"all": ("css/admin/announcements.css",)}
        js = ("js/admin/announcements.js",)
