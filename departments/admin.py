from django.contrib import admin

from .models import Department, DepartmentHead, MemberDepartment


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "church", "is_active")
    list_filter = ("is_active", "church")
    search_fields = ("name", "code")


@admin.register(MemberDepartment)
class MemberDepartmentAdmin(admin.ModelAdmin):
    list_display = ("member", "department", "role_in_department")
    list_filter = ("department",)


@admin.register(DepartmentHead)
class DepartmentHeadAdmin(admin.ModelAdmin):
    list_display = ("member", "department", "assigned_at")
    list_filter = ("department",)
