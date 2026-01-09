from django.contrib import admin

from .models import Member, MemberLocation, Visitor


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "gender",
        "membership_status",
        "church",
        "member_since",
    )
    list_filter = ("membership_status", "gender", "church")
    search_fields = ("first_name", "last_name", "national_id")


@admin.register(MemberLocation)
class MemberLocationAdmin(admin.ModelAdmin):
    list_display = ("member", "phone_primary", "city", "country")
    search_fields = ("member__first_name", "member__last_name", "phone_primary")


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "first_visit_date",
        "converted_to_member",
        "church",
    )
    list_filter = ("converted_to_member", "church")


search_fields = ("full_name", "phone")
