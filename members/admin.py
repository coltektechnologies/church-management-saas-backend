import secrets
import string

from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.hashers import make_password
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from notifications.services.email_service import EmailService
from notifications.services.mnotify_service import MNotifyService

from .models import Member, MemberLocation, Visitor
from .services.credential_service import (send_credentials_email,
                                          send_credentials_sms)


class MemberAdminForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make church field required when creating a new member
        if not self.instance.pk:  # Creating a new member
            self.fields["church"].required = True


class MemberLocationInline(admin.StackedInline):
    model = MemberLocation
    can_delete = False
    verbose_name_plural = "Contact & Location Information"
    extra = 1  # Shows one empty form
    max_num = 1  # Maximum of one location per member
    show_change_link = True

    # Define region choices
    GHANA_REGIONS = [
        ("", "-- Select Region --"),
        ("Greater Accra", "Greater Accra"),
        ("Ashanti", "Ashanti"),
        ("Western", "Western"),
        ("Central", "Central"),
        ("Eastern", "Eastern"),
        ("Volta", "Volta"),
        ("Northern", "Northern"),
        ("Upper East", "Upper East"),
        ("Upper West", "Upper West"),
        ("Bono", "Bono"),
        ("Bono East", "Bono East"),
        ("Ahafo", "Ahafo"),
        ("Western North", "Western North"),
        ("Oti", "Oti"),
        ("Savannah", "Savannah"),
        ("North East", "North East"),
    ]

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "region":
            return forms.ChoiceField(
                choices=self.GHANA_REGIONS,
                required=False,
                label="Region",
                widget=forms.Select(attrs={"style": "width: 100%"}),
            )
        return super().formfield_for_dbfield(db_field, **kwargs)

    fieldsets = (
        (
            "Contact Information",
            {"fields": ("phone_primary", "phone_secondary", "email")},
        ),
        ("Location", {"fields": ("address", "city", "region", "country")}),
    )

    # Make all fields readonly when viewing existing members
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return [f.name for f in self.model._meta.fields]
        return []

    def has_add_permission(self, request, obj=None):
        # Only allow adding location when creating a new member
        return obj is None


class DeletedListFilter(admin.SimpleListFilter):
    title = "deleted status"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return (
            ("deleted", "Deleted"),
            ("active", "Active"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        if self.value() == "deleted":
            return queryset.filter(deleted_at__isnull=False)
        if self.value() == "active":
            return queryset.filter(deleted_at__isnull=True)
        if self.value() == "all":
            return queryset
        return queryset.filter(deleted_at__isnull=True)


class SystemAccessFilter(admin.SimpleListFilter):
    title = "system access"
    parameter_name = "has_system_access"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has System Access"),
            ("no", "No System Access"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(has_system_access=True)
        if self.value() == "no":
            return queryset.filter(has_system_access=False)
        return queryset


class ChurchFilter(admin.SimpleListFilter):
    title = "church"
    parameter_name = "church"

    def lookups(self, request, model_admin):
        from accounts.models import Church

        return Church.objects.values_list("id", "name")

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(church_id=self.value())
        return queryset


def generate_random_password():
    """Generate a random password with letters, digits, and special characters"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(12))


class MemberForm(forms.ModelForm):
    SEND_CREDENTIALS_CHOICES = [
        ("NONE", "Do not send credentials"),
        ("PREFERRED", "Use member's notification preference"),
        ("EMAIL", "Send via Email"),
        ("SMS", "Send via SMS"),
        ("BOTH", "Send via both Email and SMS"),
    ]

    send_credentials = forms.ChoiceField(
        choices=SEND_CREDENTIALS_CHOICES,
        initial="PREFERRED",
        label="Send Login Credentials",
        help_text="Choose how to send login credentials after saving",
        required=False,
    )

    generate_password = forms.BooleanField(
        required=False,
        initial=True,
        label="Generate Random Password",
        help_text="Uncheck to set a custom password",
    )

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Leave empty to generate a random password",
    )

    class Meta:
        model = Member
        fields = "__all__"
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "member_since": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order churches by name in the dropdown
        self.fields["church"].queryset = self.fields["church"].queryset.order_by("name")

        # Set up password field based on instance
        if self.instance and self.instance.pk:
            self.fields["password"].initial = ""  # Don't show hashed password
            self.fields["generate_password"].initial = False
        else:
            self.fields["password"].widget.attrs[
                "placeholder"
            ] = "Leave empty to generate a random password"

        # Make email required if notification preference includes email
        if "notification_preference" in self.fields:
            self.fields["notification_preference"].help_text = (
                "Preferred method for receiving notifications and credentials"
            )


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberForm
    # Removed autocomplete_fields to use standard dropdown

    def get_form(self, request, obj=None, **kwargs):
        # Only include actual model fields in the form
        if "fields" not in kwargs:
            kwargs["fields"] = [f.name for f in self.model._meta.fields]

        # Get the form from the parent class
        form = super().get_form(request, obj, **kwargs)

        # Make church field required when creating a new member
        if not obj:  # Creating a new member
            form.base_fields["church"].required = True

        return form

    list_display = (
        "id",
        "full_name",
        "gender",
        "membership_status",
        "church",
        "member_since",
        "has_system_access",
        "deleted_at",
    )
    list_filter = (
        "membership_status",
        "gender",
        ChurchFilter,
        SystemAccessFilter,
        DeletedListFilter,
    )
    search_fields = (
        "first_name",
        "last_name",
        "national_id",
        "location__email",
        "location__phone_primary",
    )

    # Fields to show in the member edit form
    fieldsets = (
        (
            "Personal Information",
            {
                "fields": (
                    "title",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "gender",
                    "date_of_birth",
                    "marital_status",
                    "national_id",
                )
            },
        ),
        (
            "Church Information",
            {
                "fields": ("church", "member_since", "membership_status"),
                "classes": ("collapse",),
            },
        ),
        (
            "Education & Employment",
            {
                "fields": ("education_level", "occupation", "employer"),
                "classes": ("collapse",),
            },
        ),
        (
            "Emergency Contact",
            {
                "fields": (
                    "emergency_contact_name",
                    "emergency_contact_phone",
                    "emergency_contact_relationship",
                )
            },
        ),
        (
            "System Access",
            {
                "fields": (
                    "has_system_access",
                    "system_user_id",
                    ("send_credentials", "generate_password", "password"),
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # Add the location fields as readonly inline
    inlines = [MemberLocationInline]

    readonly_fields = ("created_at", "updated_at", "deleted_at", "system_user_id")

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        return fieldsets

    def save_model(self, request, obj, form, change):
        send_option = form.cleaned_data.get("send_credentials", "NONE")
        generate_password = form.cleaned_data.get("generate_password", True)
        password = form.cleaned_data.get("password", "")

        # Handle password generation/update
        if not change or "password" in form.changed_data or generate_password:
            if generate_password or not password:
                password = generate_random_password()
            obj.password = make_password(password)

        # Handle username generation for new members or when system access is enabled
        if (
            not change or "has_system_access" in form.changed_data
        ) and obj.has_system_access:
            if not obj.username:
                # Generate a username based on name
                base_username = f"{obj.first_name[0].lower()}{obj.last_name.lower()}"
                username = base_username
                counter = 1

                # Ensure username is unique
                while (
                    Member.objects.filter(username=username).exclude(pk=obj.pk).exists()
                ):
                    username = f"{base_username}{counter}"
                    counter += 1

                obj.username = username

        # Save the member first
        super().save_model(request, obj, form, change)

        # Handle credential sending based on the selected option
        if send_option != "NONE" and obj.has_system_access:
            try:
                location = getattr(obj, "location", None)
                if not location:
                    messages.warning(
                        request, "No contact information found for sending credentials"
                    )
                    return

                email = getattr(location, "email", None)
                phone = getattr(location, "phone_primary", None)

                # Determine what to send based on the selected option
                send_email = False
                send_sms = False

                if send_option == "PREFERRED":
                    if obj.notification_preference == "EMAIL" and email:
                        send_email = True
                    elif obj.notification_preference == "SMS" and phone:
                        send_sms = True
                    elif obj.notification_preference == "BOTH":
                        send_email = bool(email)
                        send_sms = bool(phone)
                elif send_option == "EMAIL" and email:
                    send_email = True
                elif send_option == "SMS" and phone:
                    send_sms = True
                elif send_option == "BOTH":
                    send_email = bool(email)
                    send_sms = bool(phone)

                # Send the credentials
                if send_email:
                    try:
                        send_credentials_email(obj, email, password)
                        messages.success(request, f"Login credentials sent to {email}")

                        # Also include email in SMS if SMS is also being sent
                        if send_sms:
                            try:
                                send_credentials_sms(obj, phone, password, email)
                                messages.success(
                                    request, f"Login credentials sent to {phone}"
                                )
                            except Exception as e:
                                messages.error(
                                    request, f"Failed to send SMS with email: {str(e)}"
                                )
                    except Exception as e:
                        messages.error(request, f"Failed to send email: {str(e)}")
                elif send_sms:  # Only send SMS if email wasn't sent
                    try:
                        send_credentials_sms(obj, phone, password)
                        messages.success(request, f"Login credentials sent to {phone}")
                    except Exception as e:
                        messages.error(request, f"Failed to send SMS: {str(e)}")

                # Update the last login timestamp
                obj.last_login = timezone.now()
                obj.save(update_fields=["last_login"])

            except Exception as e:
                messages.error(request, f"Error sending credentials: {str(e)}")
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send credentials: {str(e)}")

        # Ensure the location has the same church as the member
        if (
            hasattr(obj, "location")
            and obj.location
            and obj.location.church_id != obj.church_id
        ):
            obj.location.church = obj.church
            obj.location.save()

    def get_queryset(self, request):
        # Show all members (including deleted) in the admin
        return Member.objects.all_objects()

    def delete_queryset(self, request, queryset):
        # Override to perform soft delete
        queryset.update(deleted_at=timezone.now())

    def delete_model(self, request, obj):
        # Override to perform soft delete for single object
        obj.deleted_at = timezone.now()
        obj.save()


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
        "deleted_at",
    )
    list_filter = ("converted_to_member", "church", DeletedListFilter)

    def get_queryset(self, request):
        # Show all visitors (including deleted) in the admin
        return Visitor.objects.all_objects()

    def delete_queryset(self, request, queryset):
        # Override to perform soft delete
        queryset.update(deleted_at=timezone.now())

    def delete_model(self, request, obj):
        # Override to perform soft delete for single object
        obj.deleted_at = timezone.now()
        obj.save()


search_fields = ("full_name", "phone")
