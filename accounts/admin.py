from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import (
    AuditLog,
    Church,
    ChurchGroup,
    ChurchGroupMember,
    Permission,
    RegistrationSession,
    Role,
    RolePermission,
    User,
    UserRole,
)


class UserChurchGroupMemberInline(admin.TabularInline):
    """Assign user to church groups when editing user"""

    model = ChurchGroupMember
    fk_name = "user"
    extra = 0
    autocomplete_fields = ["group", "added_by"]
    readonly_fields = ["added_at"]
    verbose_name = "Church group"
    verbose_name_plural = "Church groups (add user to groups for auto role)"


from .models.payment import Payment


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    """Church admin interface"""

    list_display = [
        "name",
        "subdomain",
        "city",
        "country",
        "status",
        "platform_access_enabled",
        "subscription_plan",
        "user_count",
        "created_at",
    ]
    list_filter = [
        "status",
        "subscription_plan",
        "country",
        "church_size",
        "created_at",
    ]
    search_fields = ["name", "email", "subdomain", "city", "country", "phone"]
    list_select_related = True
    list_per_page = 25
    show_full_result_count = True
    readonly_fields = [
        "id",
        "full_domain",
        "is_trial_active",
        "is_subscription_active",
        "days_until_expiry",
        "created_at",
        "updated_at",
    ]

    # Add this to enable autocomplete lookups
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        return queryset, use_distinct

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "name",
                    "email",
                    "subdomain",
                    "full_domain",
                    "denomination",
                )
            },
        ),
        ("Location", {"fields": ("country", "region", "city", "address", "phone")}),
        (
            "Configuration",
            {"fields": ("church_size", "logo", "timezone", "currency", "max_users")},
        ),
        (
            "Subscription",
            {
                "fields": (
                    "status",
                    "subscription_plan",
                    "billing_cycle",
                    "trial_ends_at",
                    "subscription_starts_at",
                    "subscription_ends_at",
                    "next_billing_date",
                    "is_trial_active",
                    "is_subscription_active",
                    "days_until_expiry",
                )
            },
        ),
        (
            "Payment Info",
            {
                "fields": (
                    "paystack_customer_code",
                    "paystack_subscription_code",
                    "last_payment_reference",
                    "last_payment_date",
                )
            },
        ),
        (
            "Features",
            {
                "fields": (
                    "platform_access_enabled",
                    "enable_online_giving",
                    "enable_sms_notifications",
                    "enable_email_notifications",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at", "deleted_at")}),
    )

    def user_count(self, obj):
        """Get active user count"""
        count = obj.users.filter(is_active=True).count()
        return format_html("<strong>{}</strong> / {}", count, obj.max_users)

    user_count.short_description = "Users"

    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).prefetch_related("users")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """User admin interface"""

    inlines = [UserChurchGroupMemberInline]

    list_display = [
        "email",
        "username",
        "full_name_display",
        "church",
        "is_active",
        "is_staff",
        "is_platform_admin",
        "last_login",
        "get_notification_preference_display",
    ]
    list_filter = [
        "is_active",
        "is_staff",
        "is_platform_admin",
        "mfa_enabled",
        "email_verified",
        "church__status",
        "notification_preference",
    ]
    search_fields = ["email", "username", "first_name", "last_name", "phone"]
    readonly_fields = [
        "id",
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
        "failed_login_attempts",
        "is_account_locked",
        "mfa_secret",
    ]

    fieldsets = (
        ("Account", {"fields": ("id", "username", "email", "password")}),
        (
            "Personal Info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "profile_image",
                    "date_of_birth",
                    "gender",
                    "address",
                )
            },
        ),
        (
            "Church & Permissions",
            {
                "fields": (
                    "church",
                    "is_platform_admin",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Security",
            {
                "classes": ("collapse",),
                "fields": (
                    "mfa_enabled",
                    "mfa_secret",
                    "email_verified",
                    "failed_login_attempts",
                    "account_locked_until",
                    "is_account_locked",
                    "notification_preference",
                ),
            },
        ),
        (
            "Important Dates",
            {
                "classes": ("collapse",),
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ),
            },
        ),
    )

    add_fieldsets = (
        (
            "Account",
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
        (
            "Personal Info",
            {
                "fields": ("first_name", "last_name", "phone"),
            },
        ),
        (
            "Church & Permissions",
            {
                "fields": ("church", "is_platform_admin", "is_active", "is_staff"),
            },
        ),
        (
            "Notification Settings",
            {
                "classes": ("collapse",),
                "fields": ("notification_preference", "email_verified"),
            },
        ),
    )

    def full_name_display(self, obj):
        """Display full name"""
        return f"{obj.first_name} {obj.last_name}".strip() or "—"

    full_name_display.short_description = "Full Name"
    full_name_display.admin_order_field = "last_name"

    def get_notification_preference_display(self, obj):
        return obj.get_notification_preference_display() or "—"

    get_notification_preference_display.short_description = "Notifications"

    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related("church")

    def save_model(self, request, obj, form, change):
        # Handle password hashing
        if "password" in form.changed_data and form.cleaned_data["password"]:
            obj.set_password(form.cleaned_data["password"])

        # Handle new user creation with credentials
        if not change and "send_credentials" in request.POST:
            send_credentials = request.POST.get("send_credentials") == "on"
            notification_preference = request.POST.get(
                "notification_preference", "email"
            )

            # Generate a password if not provided
            if not obj.password:
                obj.set_password(User.objects.make_random_password())

            # Save the user first
            super().save_model(request, obj, form, change)

            # Send credentials if requested
            if send_credentials and obj.email:
                try:
                    from members.services.credential_service import (
                        send_credentials_email,
                        send_credentials_sms,
                    )

                    if notification_preference in ["email", "both"] and obj.email:
                        send_credentials_email(
                            obj,
                            obj.email,
                            form.cleaned_data.get("password1")
                            or form.cleaned_data.get("password"),
                        )

                    if notification_preference in ["sms", "both"] and obj.phone:
                        send_credentials_sms(
                            obj,
                            obj.phone,
                            form.cleaned_data.get("password1")
                            or form.cleaned_data.get("password"),
                            obj.email,
                        )

                    self.message_user(
                        request,
                        f"User created and credentials sent via {notification_preference}",
                        messages.SUCCESS,
                    )

                except Exception as e:
                    logger.error(f"Failed to send credentials: {str(e)}")
                    self.message_user(
                        request,
                        f"User created but failed to send credentials: {str(e)}",
                        messages.ERROR,
                    )
            return

        super().save_model(request, obj, form, change)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Role admin interface"""

    list_display = [
        "name",
        "level",
        "permission_count_display",
        "is_system_role",
        "created_at",
    ]
    list_filter = ["level", "is_system_role"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "permission_count"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "name", "level", "description", "is_system_role")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def permission_count_display(self, obj):
        """Display permission count"""
        count = obj.permission_count
        return format_html("<strong>{}</strong> permissions", count)

    permission_count_display.short_description = "Permissions"

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system roles"""
        if obj and obj.is_system_role:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Permission admin interface"""

    list_display = [
        "code",
        "module",
        "description",
        "is_system_permission",
        "created_at",
    ]
    list_filter = ["module", "is_system_permission"]
    search_fields = ["code", "description"]
    readonly_fields = ["id", "created_at"]

    fieldsets = (
        (
            "Permission Details",
            {"fields": ("id", "code", "description", "module", "is_system_permission")},
        ),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system permissions"""
        if obj and obj.is_system_permission:
            return False
        return super().has_delete_permission(request, obj)


class RolePermissionInline(admin.TabularInline):
    """Inline for role permissions"""

    model = RolePermission
    extra = 1
    autocomplete_fields = ["permission"]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Role-Permission mapping admin"""

    list_display = ["role", "permission", "created_at"]
    list_filter = ["role__level", "permission__module"]
    search_fields = ["role__name", "permission__code"]
    autocomplete_fields = ["role", "permission"]
    readonly_fields = ["id", "created_at"]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """User-Role assignment admin"""

    list_display = ["user", "role", "church", "is_active", "assigned_by", "assigned_at"]
    list_filter = ["is_active", "role__level", "church__status"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "role__name",
        "church__name",
    ]
    autocomplete_fields = ["user", "role", "church", "assigned_by"]
    readonly_fields = ["id", "assigned_at"]

    fieldsets = (
        ("Assignment", {"fields": ("id", "user", "role", "church", "is_active")}),
        ("Metadata", {"fields": ("assigned_by", "assigned_at")}),
    )


class ChurchGroupMemberInline(admin.TabularInline):
    model = ChurchGroupMember
    extra = 0
    autocomplete_fields = ["user", "added_by"]
    readonly_fields = ["added_at"]


@admin.register(ChurchGroup)
class ChurchGroupAdmin(admin.ModelAdmin):
    """Church group admin - users in group auto-get the role"""

    list_display = ["name", "church", "role", "member_count", "created_at"]
    list_filter = ["church", "role__level"]
    search_fields = ["name", "church__name", "role__name"]
    autocomplete_fields = ["church", "role"]
    inlines = [ChurchGroupMemberInline]
    readonly_fields = ["created_at", "updated_at"]

    def member_count(self, obj):
        return obj.members.count()

    member_count.short_description = "Members"


@admin.register(ChurchGroupMember)
class ChurchGroupMemberAdmin(admin.ModelAdmin):
    """Church group member admin"""

    list_display = ["user", "group", "role_display", "added_by", "added_at"]
    list_filter = ["group__church", "group__role"]
    search_fields = ["user__email", "group__name"]
    autocomplete_fields = ["group", "user", "added_by"]
    readonly_fields = ["added_at"]

    def role_display(self, obj):
        return obj.group.role.name if obj.group else "—"

    role_display.short_description = "Role (from group)"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit log admin interface with enhanced features"""

    list_display = [
        "created_at",
        "action_icon",
        "user",
        "church",
        "model_name",
        "object_link",
        "short_description",
        "ip_address",
    ]
    list_filter = [
        "action",
        "model_name",
        "created_at",
        "church",
        ("content_type", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        "description",
        "user__email",
        "church__name",
        "object_id",
        "ip_address",
        "user_agent",
    ]
    readonly_fields = [
        "id",
        "user",
        "church",
        "action",
        "model_name",
        "content_type",
        "object_id",
        "description",
        "ip_address",
        "user_agent",
        "created_at",
        "changes_formatted",
        "content_object_link",
    ]
    fieldsets = (
        (
            "Action Details",
            {
                "fields": (
                    "id",
                    "user",
                    "church",
                    "action",
                    "model_name",
                    "content_type",
                    "object_id",
                    "content_object_link",
                )
            },
        ),
        ("Description", {"fields": ("description", "changes_formatted")}),
        (
            "Request Info",
            {"classes": ("collapse",), "fields": ("ip_address", "user_agent")},
        ),
        ("Metadata", {"classes": ("collapse",), "fields": ("metadata",)}),
        ("Timestamps", {"classes": ("collapse",), "fields": ("created_at",)}),
    )
    list_select_related = ["user", "church", "content_type"]
    date_hierarchy = "created_at"
    list_per_page = 25
    actions = None

    def action_icon(self, obj):
        """Display action with icon"""
        icons = {
            "CREATE": "🟢",
            "UPDATE": "🔵",
            "DELETE": "🔴",
            "LOGIN": "🔑",
            "LOGOUT": "🚪",
        }
        return f"{icons.get(obj.action, 'ℹ️')} {obj.get_action_display()}"

    action_icon.short_description = "Action"
    action_icon.admin_order_field = "action"

    def short_description(self, obj):
        """Truncate description for list view"""
        if not obj.description:
            return ""
        return (
            (obj.description[:97] + "...")
            if len(obj.description) > 100
            else obj.description
        )

    short_description.short_description = "Description"

    def changes_formatted(self, obj):
        """Format changes for display"""
        if not obj.changes:
            return "No changes recorded"

        output = []
        for field, values in obj.changes.items():
            old_val = values.get("old", "")
            new_val = values.get("new", "")
            output.append(f"<strong>{field}:</strong> {old_val} → {new_val}")

        return format_html("<br>".join(output))

    changes_formatted.short_description = "Changes"
    changes_formatted.allow_tags = True

    def object_link(self, obj):
        """Create a link to the changed object if possible"""
        if not obj.object_id or not obj.content_type:
            return obj.object_id

        model = obj.content_type.model_class()
        if not model:
            return obj.object_id

        try:
            # Try to get the admin URL for the object
            url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[obj.object_id],
            )
            return format_html('<a href="{}">{}</a>', url, obj.object_id)
        except:
            return obj.object_id

    object_link.short_description = "Object ID"
    object_link.admin_order_field = "object_id"
    object_link.allow_tags = True

    def content_object_link(self, obj):
        """Link to the actual object if it exists"""
        if not obj.content_object:
            return "-"
        return format_html(
            '<a href="{}">{}</a>',
            (
                obj.content_object.get_absolute_url()
                if hasattr(obj.content_object, "get_absolute_url")
                else "#"
            ),
            str(obj.content_object),
        )

    content_object_link.short_description = "Linked Object"
    content_object_link.allow_tags = True

    def has_add_permission(self, request):
        """Prevent manual creation of audit logs"""
        return False

    def has_change_permission(self, request, obj=None):
        """Make audit logs read-only"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs"""
        return request.user.is_superuser  # Only superusers can delete logs

    def get_queryset(self, request):
        """Optimize queries"""
        return (
            super()
            .get_queryset(request)
            .select_related("user", "church", "content_type")
        )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Payment admin interface"""

    list_display = [
        "church",
        "amount",
        "currency",
        "payment_method",
        "status",
        "subscription_plan",
        "billing_cycle",
        "payment_date",
        "next_billing_date",
    ]
    list_filter = ["status", "payment_method", "billing_cycle", "subscription_plan"]
    search_fields = ["church__name", "reference", "payment_details"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "payment_date"

    fieldsets = (
        (
            "Payment Information",
            {"fields": ("church", "amount", "currency", "reference", "status")},
        ),
        (
            "Subscription Details",
            {
                "fields": (
                    "subscription_plan",
                    "billing_cycle",
                    "payment_method",
                    "payment_date",
                    "next_billing_date",
                )
            },
        ),
        (
            "Additional Information",
            {
                "classes": ("collapse",),
                "fields": ("payment_details", "created_at", "updated_at"),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make all fields read-only if payment is successful
        if obj and obj.status == "SUCCESSFUL":
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields


@admin.register(RegistrationSession)
class RegistrationSessionAdmin(admin.ModelAdmin):
    """Registration Session admin interface"""

    list_display = [
        "id_short",
        "step",
        "is_expired_display",
        "created_at",
        "updated_at",
        "expires_at",
    ]
    list_filter = ["step", "created_at", "expires_at"]
    search_fields = ["id", "data"]
    readonly_fields = ["id", "created_at", "updated_at", "is_expired_display"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Session Information", {"fields": ("id", "step", "is_expired_display")}),
        ("Session Data", {"fields": ("data",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "expires_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def id_short(self, obj):
        """Display shortened ID"""
        return str(obj.id)[:8] + "..."

    id_short.short_description = "ID"

    def is_expired_display(self, obj):
        """Display expired status with color"""
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')

    is_expired_display.short_description = "Status"
    is_expired_display.admin_order_field = "expires_at"


# Customize admin site
admin.site.site_header = "OpenDoor Church Management"
admin.site.site_title = "OpenDoor Admin"
admin.site.index_title = "Administration Dashboard"


# Hide framework/internal models - show only setup and church management
def _unregister_unwanted_admin_models():
    from django.contrib.auth.models import Group
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.sessions.models import Session

    to_unregister = [Group, Session, ContentType]

    for model in to_unregister:
        try:
            admin.site.unregister(model)
        except admin.sites.NotRegistered:
            pass

    # Token blacklist (JWT internals)
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        for m in (OutstandingToken, BlacklistedToken):
            try:
                admin.site.unregister(m)
            except admin.sites.NotRegistered:
                pass
    except ImportError:
        pass

    # Django RQ (workers, jobs)
    try:
        from django_rq.models import Queue

        admin.site.unregister(Queue)
    except (ImportError, admin.sites.NotRegistered):
        pass

    # Guardian object permissions
    try:
        from guardian.models import GroupObjectPermission, UserObjectPermission

        for m in (UserObjectPermission, GroupObjectPermission):
            try:
                admin.site.unregister(m)
            except admin.sites.NotRegistered:
                pass
    except ImportError:
        pass

    # Celery beat / results (periodic tasks, task results)
    try:
        from django_celery_beat.models import (
            ClockedSchedule,
            CrontabSchedule,
            IntervalSchedule,
            PeriodicTask,
            SolarSchedule,
        )

        for m in (
            PeriodicTask,
            ClockedSchedule,
            IntervalSchedule,
            CrontabSchedule,
            SolarSchedule,
        ):
            try:
                admin.site.unregister(m)
            except admin.sites.NotRegistered:
                pass
    except ImportError:
        pass
    try:
        from django_celery_results.models import TaskResult

        admin.site.unregister(TaskResult)
    except (ImportError, admin.sites.NotRegistered):
        pass


_unregister_unwanted_admin_models()
