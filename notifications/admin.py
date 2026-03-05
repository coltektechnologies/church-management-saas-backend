from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User
from members.models import Member
from notifications.services.mnotify_service import MNotifyService

from .models import (EmailLog, Notification, NotificationBatch,
                     NotificationPreference, NotificationTemplate,
                     SMSDeliveryReport, SMSLog)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    change_form_template = "admin/notifications/notification/change_form.html"
    list_display = (
        "title",
        "get_recipient",
        "church",
        "is_read",
        "priority",
        "status",
        "created_at",
    )
    list_filter = ("church", "is_read", "category", "priority", "status", "created_at")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        from .models import Notification

        try:
            notification = Notification.objects.get(pk=object_id)
            extra_context["has_program_link"] = (
                notification.category == "PROGRAM" and notification.link
            )
            extra_context["program_link"] = notification.link or ""
        except Notification.DoesNotExist:
            extra_context["has_program_link"] = False
            extra_context["program_link"] = ""
        return super().change_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if (
            not request.user.is_superuser
            and hasattr(request.user, "church")
            and request.user.church
        ):
            qs = qs.filter(church=request.user.church)
        return qs

    search_fields = (
        "title",
        "message",
        "user__email",
        "member__first_name",
        "member__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "read_at", "sent_at")
    date_hierarchy = "created_at"
    list_select_related = ("user", "member")
    raw_id_fields = ("user", "member")
    fieldsets = (
        (None, {"fields": ("church", "title", "message", "is_read", "read_at")}),
        ("Recipient", {"fields": ("user", "member")}),
        (
            "Metadata",
            {
                "fields": ("category", "priority", "status", "link", "icon"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timing",
            {
                "fields": ("scheduled_for", "sent_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_recipient(self, obj):
        if obj.user:
            return f"User: {obj.user.email}"
        elif obj.member:
            return f"Member: {obj.member.full_name}"
        return "No recipient"

    get_recipient.short_description = "Recipient"


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "template_type",
        "category",
        "is_active",
        "is_system_template",
    )
    list_filter = (
        "template_type",
        "category",
        "is_active",
        "is_system_template",
        "created_at",
    )
    search_fields = ("name", "subject", "message")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at", "get_variables_help_text")
    fieldsets = (
        (None, {"fields": ("name", "church", "is_active", "is_system_template")}),
        ("Content", {"fields": ("template_type", "category", "subject", "message")}),
        (
            "Advanced",
            {
                "fields": ("get_variables_help_text", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_variables_help_text(self, obj):
        return """
        <p>Available variables:</p>
        <ul>
            <li><code>{name}</code> - Recipient's name</li>
            <li><code>{date}</code> - Current date</li>
            <li><code>{time}</code> - Current time</li>
            <li><code>{church}</code> - Church name</li>
        </ul>
        """

    get_variables_help_text.short_description = "Template Variables"
    get_variables_help_text.allow_tags = True


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "enable_email",
        "enable_sms",
        "enable_in_app",
        "digest_mode",
    )
    search_fields = ("user__email", "user__username")
    list_filter = ("enable_email", "enable_sms", "enable_in_app", "digest_mode")
    fieldsets = (
        (None, {"fields": ("user",)}),
        (
            "Notification Channels",
            {"fields": ("enable_email", "enable_sms", "enable_in_app")},
        ),
        (
            "Notification Types",
            {
                "fields": (
                    "announcements",
                    "reminders",
                    "birthdays",
                    "events",
                    "finance",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Digest Settings",
            {"fields": ("digest_mode", "digest_frequency"), "classes": ("collapse",)},
        ),
        (
            "Quiet Hours",
            {
                "fields": (
                    "quiet_hours_enabled",
                    "quiet_hours_start",
                    "quiet_hours_end",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "get_recipient_name",
        "status",
        "delivery_status",
        "get_gateway_display",
        "created_at",
        "sent_at",
        "get_cost_display",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sms-balance/",
                self.admin_site.admin_view(self.sms_balance_view),
                name="sms-balance",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_sms_balance"] = True
        return super().changelist_view(request, extra_context=extra_context)

    def sms_balance_view(self, request):
        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "SMS Balance",
                "opts": self.model._meta,
                "has_view_permission": self.has_view_permission(request),
            }
        )

        mnotify = MNotifyService()
        balance = mnotify.check_balance()

        if balance["success"]:
            context["balance"] = balance
            context["has_balance"] = True
        else:
            messages.error(
                request,
                f"Failed to check SMS balance: {balance.get('error', 'Unknown error')}",
            )
            context["has_balance"] = False

        return TemplateResponse(
            request,
            "admin/notifications/sms_balance.html",
            context,
        )

    # Change the displayed name in admin
    class Meta:
        app_label = "Quick Messages"

    # Override the app label
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model._meta.verbose_name = "Quick Message"
        self.model._meta.verbose_name_plural = "Quick Messages"

    list_filter = ("status", "delivery_status", "gateway", "created_at", "church")
    search_fields = (
        "phone_number",
        "message",
        "error_message",
        "gateway_message_id",
        "member__first_name",
        "member__last_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "sent_at",
        "delivered_at",
        "error_message",
        "gateway_message_id",
        "sms_count",
        "get_cost",
        "get_recipient_info",
        "get_message_preview",
        "get_delivery_status",
        "message_length",
    )
    date_hierarchy = "created_at"
    list_select_related = ("member", "church")
    raw_id_fields = ("member",)
    actions = ["send_selected_messages", "resend_failed_messages"]
    list_per_page = 25

    fieldsets = (
        (
            "Recipient Information",
            {
                "fields": (
                    "church",
                    "phone_number",
                    "member",
                    "status",
                    "delivery_status",
                )
            },
        ),
        (
            "Message Content",
            {
                "fields": (
                    "message",
                    "get_message_preview",
                    "message_length",
                    "sms_count",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Gateway & Delivery",
            {
                "fields": (
                    "gateway",
                    "gateway_message_id",
                    "get_delivery_status",
                    "error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Financials", {"fields": ("get_cost",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": (
                    "scheduled_for",
                    "sent_at",
                    "delivered_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Filter by user's church if not superuser
        if not request.user.is_superuser and hasattr(request.user, "church"):
            qs = qs.filter(church=request.user.church)
        return qs

    def get_cost(self, obj):
        return f"${obj.cost:.4f}" if obj.cost else "Not available"

    get_cost.short_description = "Cost (USD)"

    def get_cost_display(self, obj):
        return f"${obj.cost:.4f}" if obj.cost else "-"

    get_cost_display.short_description = "Cost"

    def get_recipient_name(self, obj):
        if obj.member:
            return f"{obj.member.get_full_name() or 'Unnamed Member'}"
        return "-"

    get_recipient_name.short_description = "Recipient"
    get_recipient_name.admin_order_field = "member__first_name"

    def get_recipient_info(self, obj):
        info = f"<strong>Phone:</strong> {obj.phone_number}<br>"
        if obj.member:
            info += f"<strong>Member:</strong> {obj.member.get_full_name() or 'Unnamed Member'}<br>"
            if obj.member.email:
                info += f"<strong>Email:</strong> {obj.member.email}<br>"
        return format_html(info)

    get_recipient_info.short_description = "Recipient Information"
    get_recipient_info.allow_tags = True

    def get_message_preview(self, obj):
        preview = obj.message[:200] + ("..." if len(obj.message) > 200 else "")
        return format_html(
            f'<div style="max-height: 150px; overflow-y: auto; padding: 5px; border: 1px solid #ddd;">{preview}</div>'
        )

    get_message_preview.short_description = "Message Preview"

    def get_delivery_status(self, obj):
        status_icons = {
            "SENT": "icon-yes",
            "DELIVERED": "icon-yes",
            "FAILED": "icon-no",
            "REJECTED": "icon-no",
            "PENDING": "icon-clock",
            "QUEUED": "icon-clock",
        }

        icon = status_icons.get(obj.status, "icon-help")
        status_html = f'<span class="{icon}" style="margin-right: 5px;"></span> {obj.get_status_display()}'

        if obj.error_message:
            status_html += (
                f'<br><span style="color: #a00;">{obj.error_message[:100]}</span>'
            )

        if obj.delivery_status:
            status_html += f"<br><small>Delivery: {obj.delivery_status}</small>"

        return format_html(status_html)

    get_delivery_status.short_description = "Status"

    @admin.action(description="Send selected messages now")
    def send_selected_messages(self, request, queryset):
        success = 0
        failed = 0

        for sms in queryset.filter(status__in=["DRAFT", "PENDING", "FAILED"]):
            if sms.send():
                success += 1
            else:
                failed += 1

        self.message_user(
            request,
            f"Successfully sent {success} message(s). {failed} message(s) failed to send.",
        )

    @admin.action(description="Resend failed messages")
    def resend_failed_messages(self, request, queryset):
        failed_messages = queryset.filter(status="FAILED")
        return self.send_selected_messages(request, failed_messages)

    def save_model(self, request, obj, form, change):
        # Set the church if not set and user has a church
        if not obj.church_id and hasattr(request.user, "church"):
            obj.church = request.user.church

        # If message is being created or updated, update the status
        if "message" in form.changed_data:
            obj.status = "PENDING"

        # Set default direction for new SMS logs
        if not change and not hasattr(obj, "direction"):
            obj.direction = "OUTBOUND"  # or whatever default direction makes sense

        super().save_model(request, obj, form, change)

        # If this is a new message and not scheduled, send it immediately
        if not change and not obj.scheduled_for:
            obj.send()

    class Media:
        css = {"all": ("admin/css/sms-log.css",)}
        js = ("admin/js/sms-log.js",)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "email_address",
        "get_subject",
        "status",
        "opened_count",
        "created_at",
        "send_now_button",
    )
    list_filter = ("status", "gateway", "has_attachments", "created_at")
    search_fields = ("email_address", "subject", "gateway_message_id")
    readonly_fields = (
        "created_at",
        "updated_at",
        "sent_at",
        "delivered_at",
        "first_opened_at",
        "last_opened_at",
        "opened_count",
        "clicked_count",
        "error_message",
        "gateway_message_id",
        "send_now_button",
    )

    def save_model(self, request, obj, form, change):
        # First save the object to get an ID
        super().save_model(request, obj, form, change)

        # Only send if this is a new email or if we're explicitly saving and sending
        send_email = "_save" in request.POST and not change  # Only on initial save

        if send_email and obj.status not in ["SENT", "DELIVERED"]:
            from notifications.services.email_service import EmailService

            try:
                email_service = EmailService()
                result = email_service.send_email(
                    to_email=obj.email_address,
                    subject=obj.subject,
                    plain_message=obj.message_plain or "",
                    html_message=obj.message_html or "",
                )

                if result.get("success"):
                    obj.status = "SENT"
                    obj.sent_at = timezone.now()
                    obj.gateway_message_id = result.get("message_id", "")
                else:
                    obj.status = "FAILED"
                    obj.error_message = result.get("error", "Unknown error")

                # Save again to update status
                obj.save()

            except Exception as e:
                obj.status = "FAILED"
                obj.error_message = str(e)
                obj.save()

    date_hierarchy = "created_at"
    list_select_related = ("member", "church")
    raw_id_fields = ("member",)
    actions = ["send_selected_emails"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "church",
                    "email_address",
                    "member",
                    "status",
                    "send_now_button",
                )
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "subject",
                    "message_html",
                    "message_plain",
                    "has_attachments",
                    "attachment_urls",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Tracking",
            {
                "fields": (
                    "opened_count",
                    "clicked_count",
                    "first_opened_at",
                    "last_opened_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Gateway",
            {
                "fields": ("gateway", "gateway_message_id", "error_message"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "scheduled_for",
                    "sent_at",
                    "delivered_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_subject(self, obj):
        return obj.subject or "No subject"

    get_subject.short_description = "Subject"

    def send_now_button(self, obj):
        if obj.status not in ["SENT", "DELIVERED"]:
            return format_html(
                '<a class="button" href="{}">Send Now</a>',
                reverse("admin:send_email_now", args=[obj.pk]),
            )
        return "Already sent"

    send_now_button.short_description = "Actions"
    send_now_button.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:email_id>/send-now/",
                self.admin_site.admin_view(self.send_email_now),
                name="send_email_now",
            ),
        ]
        return custom_urls + urls

    def send_email_now(self, request, email_id, *args, **kwargs):
        from django.contrib import messages

        from notifications.services.email_service import EmailService

        try:
            email_log = EmailLog.objects.get(pk=email_id)
            email_service = EmailService()

            result = email_service.send_email(
                to_email=email_log.email_address,
                subject=email_log.subject,
                plain_message=email_log.message_plain,
                html_message=email_log.message_html,
            )

            if result.get("success"):
                email_log.status = "SENT"
                email_log.sent_at = timezone.now()
                email_log.gateway_message_id = result.get("message_id", "")
                email_log.save()
                messages.success(request, "Email sent successfully!")
            else:
                email_log.status = "FAILED"
                email_log.error_message = result.get("error", "Unknown error")
                email_log.save()
                messages.error(
                    request, f"Failed to send email: {email_log.error_message}"
                )

        except Exception as e:
            messages.error(request, f"Error sending email: {str(e)}")

        return redirect("admin:notifications_emaillog_changelist")

    def send_selected_emails(self, request, queryset):
        from django.contrib import messages

        from notifications.services.email_service import EmailService

        success_count = 0
        fail_count = 0

        for email_log in queryset:
            try:
                if email_log.status in ["SENT", "DELIVERED"]:
                    continue

                email_service = EmailService()
                result = email_service.send_email(
                    to_email=email_log.email_address,
                    subject=email_log.subject,
                    plain_message=email_log.message_plain,
                    html_message=email_log.message_html,
                )

                if result.get("success"):
                    email_log.status = "SENT"
                    email_log.sent_at = timezone.now()
                    email_log.gateway_message_id = result.get("message_id", "")
                    email_log.save()
                    success_count += 1
                else:
                    email_log.status = "FAILED"
                    email_log.error_message = result.get("error", "Unknown error")
                    email_log.save()
                    fail_count += 1

            except Exception as e:
                email_log.status = "FAILED"
                email_log.error_message = str(e)
                email_log.save()
                fail_count += 1

        if success_count:
            self.message_user(
                request, f"Successfully sent {success_count} emails.", messages.SUCCESS
            )
        if fail_count:
            self.message_user(
                request, f"Failed to send {fail_count} emails.", messages.ERROR
            )

    send_selected_emails.short_description = "Send selected emails"


# Custom admin site with SMS balance link
class CustomAdminSite(admin.AdminSite):
    site_header = "Church Management Admin"
    site_title = "Church Management Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sms-balance/",
                self.admin_view(self.sms_balance_view),
                name="sms-balance",
            ),
        ]
        return custom_urls + urls

    def sms_balance_view(self, request):
        context = self.each_context(request)
        context.update(
            {
                "title": "SMS Balance",
                "opts": self._registry[NotificationBatch].model._meta,
                "has_view_permission": self.has_permission(request),
            }
        )

        mnotify = MNotifyService()
        balance = mnotify.check_balance()

        if balance["success"]:
            context["balance"] = balance
            context["has_balance"] = True
        else:
            messages.error(
                request,
                f"Failed to check SMS balance: {balance.get('error', 'Unknown error')}",
            )
            context["has_balance"] = False

        return TemplateResponse(
            request,
            "admin/notifications/sms_balance.html",
            context,
        )


# Register NotificationBatch with the default admin site
@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "get_channels",
        "total_recipients",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "send_sms", "send_email", "send_in_app", "created_at")
    search_fields = ("name", "description", "message")
    readonly_fields = (
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "successful_count",
        "failed_count",
        "total_recipients",
        "get_processing_time",
    )
    date_hierarchy = "created_at"
    raw_id_fields = ("created_by", "template")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sms-balance/",
                self.admin_site.admin_view(self.sms_balance_view),
                name="sms-balance",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_sms_balance"] = True
        return super().changelist_view(request, extra_context=extra_context)

    def sms_balance_view(self, request):
        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "SMS Balance",
                "opts": self.model._meta,
                "has_view_permission": self.has_view_permission(request),
            }
        )

        mnotify = MNotifyService()
        balance = mnotify.check_balance()

        if balance["success"]:
            context["balance"] = balance
            context["has_balance"] = True
        else:
            messages.error(
                request,
                f"Failed to check SMS balance: {balance.get('error', 'Unknown error')}",
            )
            context["has_balance"] = False

        return TemplateResponse(
            request,
            "admin/notifications/sms_balance.html",
            context,
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_sms_balance"] = True
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "church"):
            qs = qs.filter(church=request.user.church)
        return qs

    def get_channels(self, obj):
        channels = []
        if obj.send_sms:
            channels.append("SMS")
        if obj.send_email:
            channels.append("Email")
        if obj.send_in_app:
            channels.append("In-App")
        return ", ".join(channels) if channels else "None"

    get_channels.short_description = "Channels"

    def get_processing_time(self, obj):
        if obj.started_at and obj.completed_at:
            return obj.completed_at - obj.started_at
        return "N/A"

    get_processing_time.short_description = "Processing Time"

    fieldsets = (
        (None, {"fields": ("church", "name", "description", "status", "created_by")}),
        ("Content", {"fields": ("template", "message")}),
        (
            "Recipients",
            {
                "fields": (
                    "target_all_members",
                    "target_departments",
                    "target_members",
                    "total_recipients",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Channels",
            {
                "fields": ("send_sms", "send_email", "send_in_app"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": ("successful_count", "failed_count", "get_processing_time"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timing",
            {
                "fields": (
                    "scheduled_for",
                    "started_at",
                    "completed_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_channels(self, obj):
        channels = []
        if obj.send_sms:
            channels.append("SMS")
        if obj.send_email:
            channels.append("Email")
        if obj.send_in_app:
            channels.append("In-App")
        return ", ".join(channels) if channels else "None"

    get_channels.short_description = "Channels"

    def get_processing_time(self, obj):
        if obj.started_at and obj.completed_at:
            return obj.completed_at - obj.started_at
        return "N/A"

    get_processing_time.short_description = "Processing Time"


@admin.register(SMSDeliveryReport)
class SMSDeliveryReportAdmin(admin.ModelAdmin):
    """Admin interface for SMS delivery reports"""

    list_display = (
        "get_message_id",
        "get_recipient",
        "status",
        "status_code",
        "delivery_timestamp",
        "retry_count",
        "created_at",
    )
    list_filter = ("status", "delivery_timestamp", "created_at")
    search_fields = (
        "sms_log__gateway_message_id",
        "sms_log__recipient",
        "status_message",
        "status_code",
    )
    readonly_fields = (
        "sms_log",
        "status",
        "status_code",
        "status_message",
        "delivery_timestamp",
        "created_at",
        "updated_at",
        "gateway_response",
        "get_recipient_info",
        "get_message_preview",
    )
    date_hierarchy = "created_at"
    list_select_related = ("sms_log",)
    actions = ["retry_failed_reports"]

    fieldsets = (
        (
            "Delivery Status",
            {
                "fields": (
                    "status",
                    "status_code",
                    "status_message",
                    "delivery_timestamp",
                    "retry_count",
                    "last_retry",
                )
            },
        ),
        (
            "Message Details",
            {
                "fields": ("get_recipient_info", "get_message_preview"),
                "classes": ("collapse",),
            },
        ),
        (
            "Gateway Response",
            {"fields": ("gateway_response",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("sms_log")

    def get_message_id(self, obj):
        return obj.sms_log.gateway_message_id if obj.sms_log else "N/A"

    get_message_id.short_description = "Message ID"
    get_message_id.admin_order_field = "sms_log__gateway_message_id"

    def get_recipient(self, obj):
        return obj.sms_log.phone_number if obj.sms_log else "N/A"

    get_recipient.short_description = "Recipient"
    get_recipient.admin_order_field = "sms_log__phone_number"

    def get_recipient_info(self, obj):
        if not obj.sms_log:
            return "N/A"

        info = f"""
        <div style="margin-left: 10px;">
            <p><strong>Recipient:</strong> {obj.sms_log.phone_number}</p>
            <p><strong>Message ID:</strong> {obj.sms_log.gateway_message_id}</p>
            <p><strong>Status:</strong> {obj.sms_log.get_status_display()}</p>
            <p><strong>Sent at:</strong> {obj.sms_log.sent_at or 'N/A'}</p>
        </div>
        """
        return format_html(info)

    get_recipient_info.short_description = "Recipient Information"
    get_recipient_info.allow_tags = True

    def get_message_preview(self, obj):
        if not obj.sms_log or not obj.sms_log.message:
            return "N/A"

        preview = obj.sms_log.message[:200]
        if len(obj.sms_log.message) > 200:
            preview += "..."
        return format_html(f'<div style="white-space: pre-wrap;">{preview}</div>')

    get_message_preview.short_description = "Message Preview"

    def retry_failed_reports(self, request, queryset):
        """Action to retry failed delivery reports"""
        from ..tasks import retry_failed_sms

        failed_reports = queryset.filter(status="failed")
        count = failed_reports.count()

        for report in failed_reports:
            retry_failed_sms.delay(report.id)

        self.message_user(
            request, f"Scheduled {count} failed reports for retry", messages.SUCCESS
        )

    retry_failed_reports.short_description = "Retry selected failed reports"
