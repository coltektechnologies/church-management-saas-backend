from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Church, Permission, Role, RolePermission, User, UserRole


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country", "status", "created_at")
    list_filter = ("status", "country")
    search_fields = ("name", "city")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Platform admins see all churches
        if request.user.is_platform_admin:
            return qs
        # Regular admins see only their church
        if request.user.church:
            return qs.filter(id=request.user.church.id)
        return qs.none()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "church",
        "is_platform_admin",
        "is_active",
        "is_staff",
    )
    list_filter = ("is_active", "is_staff", "is_platform_admin", "church")
    search_fields = ("username", "email", "phone")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Church Information",
            {"fields": ("church", "phone", "mfa_enabled", "is_platform_admin")},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Platform admins see all users
        if request.user.is_platform_admin:
            return qs
        # Church admins see only their church users
        if request.user.church:
            return qs.filter(church=request.user.church)
        return qs.none()


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "created_at")
    ordering = ("level", "name")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "module", "description")
    list_filter = ("module",)
    search_fields = ("code", "description")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "church")
    list_filter = ("role", "church")
