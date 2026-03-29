from django import forms
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import Church
from members.models import Member, MemberLocation

from .models import (
    Department,
    DepartmentActivity,
    DepartmentHead,
    MemberDepartment,
    Program,
    ProgramBudgetItem,
    ProgramDocument,
)

# ==========================================
# INLINE ADMINS
# ==========================================


class MemberDepartmentInline(admin.TabularInline):
    """Inline for members in department"""

    model = MemberDepartment
    extra = 0
    raw_id_fields = ["member"]
    fields = ["member", "role_in_department", "assigned_at"]
    readonly_fields = ["assigned_at"]


class DepartmentHeadInline(admin.TabularInline):
    """Inline for department head and assistant head"""

    model = DepartmentHead
    extra = 0
    max_num = 2
    raw_id_fields = ["member"]
    fields = ["head_role", "member", "assigned_at"]
    readonly_fields = ["assigned_at"]


class DepartmentActivityInline(admin.TabularInline):
    """Inline for department activities (events)"""

    model = DepartmentActivity
    extra = 0
    max_num = 10
    fields = [
        "title",
        "status",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "location",
    ]
    readonly_fields = []
    show_change_link = True


class ProgramBudgetItemInline(admin.TabularInline):
    """Inline for program budget items (Step 2 of 5-step flow)"""

    model = ProgramBudgetItem
    extra = 1
    verbose_name = "Budget item"
    verbose_name_plural = "Step 2: Budget Items"
    fields = [
        "item_type",
        "category",
        "description",
        "quantity",
        "amount",
        "income_source",
        "notes",
    ]
    readonly_fields = ["created_at"]

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if "income_source" in formset.form.base_fields:
            formset.form.base_fields["income_source"].required = False
        if "category" in formset.form.base_fields:
            formset.form.base_fields["category"].required = False
        return formset


# ==========================================
# DEPARTMENT HEAD FORM
# ==========================================


class DepartmentHeadForm(forms.ModelForm):
    """
    Custom form for DepartmentHead admin.

    THE FIX: Django validates submitted values against the field's queryset.
    The JS dynamically filters dropdowns by church — but if the queryset is
    also filtered (or empty), Django rejects the submitted ID with:
    "Select a valid choice. That choice is not one of the available choices."

    Solution:
    - Allow ALL members and departments in the queryset so Django accepts any valid ID.
    - Enforce church consistency manually in clean() instead.
    - On edit, pre-filter to the existing church for cleaner UX.
    """

    class Meta:
        model = DepartmentHead
        fields = ["church", "department", "head_role", "member"]
        widgets = {
            "church": forms.Select(attrs={"id": "id_church"}),
            "department": forms.Select(attrs={"id": "id_department"}),
            "head_role": forms.Select(attrs={"id": "id_head_role"}),
            "member": forms.Select(attrs={"id": "id_member"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["church"].widget.attrs.update(
            {"onchange": "updateMemberAndDepartmentDropdowns(this)"}
        )

        self.fields["member"].queryset = Member.objects.all().order_by(
            "first_name", "last_name"
        )
        self.fields["department"].queryset = Department.objects.filter(
            deleted_at__isnull=True, is_active=True
        ).order_by("name")

        if self.instance and self.instance.pk and self.instance.church_id:
            self.fields["member"].queryset = Member.objects.filter(
                church=self.instance.church
            ).order_by("first_name", "last_name")
            self.fields["department"].queryset = Department.objects.filter(
                church=self.instance.church, deleted_at__isnull=True, is_active=True
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        church = cleaned_data.get("church")
        member = cleaned_data.get("member")
        department = cleaned_data.get("department")

        if church and member and member.church != church:
            self.add_error(
                "member",
                f"This member does not belong to '{church.name}'. "
                f"Please select a member from the correct church.",
            )

        if church and department and department.church != church:
            self.add_error(
                "department",
                f"This department does not belong to '{church.name}'. "
                f"Please select a department from the correct church.",
            )

        return cleaned_data


# ==========================================
# MAIN ADMINS
# ==========================================


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Department administration"""

    list_display = [
        "name",
        "code",
        "church",
        "is_active_badge",
        "member_count",
        "head_name",
        "elder_in_charge_display",
        "created_at",
    ]
    raw_id_fields = ["elder_in_charge"]
    list_filter = ["is_active", "church", "created_at"]
    search_fields = ["name", "code", "description", "church__name"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("church", "name", "code", "description")}),
        (
            "Oversight",
            {
                "fields": ("elder_in_charge",),
                "description": "Elder in charge approves department programs first (Elder → Secretariat → Treasury).",
            },
        ),
        ("Visual Settings", {"fields": ("icon", "color")}),
        ("Status", {"fields": ("is_active", "deleted_at")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = [
        DepartmentHeadInline,
        MemberDepartmentInline,
        DepartmentActivityInline,
    ]

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color:#28a745;color:white;'
                'padding:3px 10px;border-radius:3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color:#dc3545;color:white;'
            'padding:3px 10px;border-radius:3px;">Inactive</span>'
        )

    is_active_badge.short_description = "Status"
    is_active_badge.admin_order_field = "is_active"

    def member_count(self, obj):
        return obj.memberdepartment_set.count()

    member_count.short_description = "Members"

    def head_name(self, obj):
        head = (
            obj.heads.filter(head_role=DepartmentHead.HeadRole.HEAD)
            .select_related("member")
            .first()
        )
        if head and hasattr(head, "member") and head.member:
            return head.member.full_name
        return "No head assigned"

    head_name.short_description = "Head"

    def elder_in_charge_display(self, obj):
        if obj.elder_in_charge:
            return obj.elder_in_charge.full_name
        return "—"

    elder_in_charge_display.short_description = "Elder in charge"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(church=request.user.church)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "elder_in_charge":
            obj = getattr(request, "_current_department_obj", None)
            church_id = getattr(obj, "church_id", None) if obj else None
            if (
                not church_id
                and hasattr(request.user, "church")
                and request.user.church
            ):
                church_id = request.user.church_id
            if church_id:
                kwargs["queryset"] = Member.objects.filter(
                    church_id=church_id, deleted_at__isnull=True
                ).order_by("first_name", "last_name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        request._current_department_obj = None
        if object_id:
            try:
                request._current_department_obj = self.get_object(request, object_id)
            except Department.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)


# Notification choices for activity form (must match activity_notifications)
_NOTIFY_CHOICES = [
    ("department_members", "Department members only"),
    ("all_church", "All church members"),
    ("specific_members", "Specific members (enter IDs below)"),
]


class DepartmentActivityForm(forms.ModelForm):
    """Activity form with HTML5 date/time (no repeated Today/Now) and notification options."""

    send_notification = forms.BooleanField(
        required=False,
        initial=False,
        label="Send notification when saving",
    )
    notify_to = forms.ChoiceField(
        choices=_NOTIFY_CHOICES,
        required=False,
        initial="department_members",
        label="Send to",
    )
    member_ids_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Member IDs (one per line, for Specific members only)",
    )
    send_email = forms.BooleanField(required=False, initial=True, label="Send email")
    send_sms = forms.BooleanField(required=False, initial=False, label="Send SMS")

    class Meta:
        model = DepartmentActivity
        fields = [
            "title",
            "description",
            "status",
            "location",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "department",
            "church",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }


@admin.register(DepartmentActivity)
class DepartmentActivityAdmin(admin.ModelAdmin):
    """Department activities (events): title, date, time, location, description."""

    form = DepartmentActivityForm
    list_display = [
        "title",
        "department",
        "church",
        "status",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "location",
        "is_upcoming_display",
        "created_at",
    ]
    list_filter = ["status", "church", "department", "start_date"]
    search_fields = ["title", "description", "location", "department__name"]
    raw_id_fields = ["department", "church", "created_by"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]
    date_hierarchy = "start_date"
    change_form_template = "admin/departments/departmentactivity/change_form.html"

    fieldsets = (
        (
            "Activity",
            {
                "fields": (
                    "title",
                    "description",
                    "status",
                    "location",
                ),
            },
        ),
        (
            "Date & time",
            {"fields": ("start_date", "end_date", "start_time", "end_time")},
        ),
        (
            "Notification",
            {
                "fields": (
                    "send_notification",
                    "notify_to",
                    "member_ids_raw",
                    "send_email",
                    "send_sms",
                ),
                "description": "Optionally send email and/or SMS when you save. Choose who receives it.",
            },
        ),
        (
            "Organization",
            {
                "fields": ("department", "church"),
                "classes": ("collapse",),
                "description": "Required for saving. Usually set from your church.",
            },
        ),
    )

    def is_upcoming_display(self, obj):
        from django.utils import timezone

        now = timezone.now()
        if obj.end_date < now.date():
            return format_html('<span style="color:#6c757d;">Past</span>')
        if obj.start_date > now.date():
            return format_html('<span style="color:#28a745;">Upcoming</span>')
        return format_html('<span style="color:#ffc107;">Ongoing</span>')

    is_upcoming_display.short_description = "Time"

    def save_model(self, request, obj, form, change):
        if not change:
            if obj.department and not obj.church_id:
                obj.church = obj.department.church
            elif (
                not obj.church_id
                and hasattr(request.user, "church")
                and request.user.church
            ):
                obj.church = request.user.church
            if not obj.created_by_id:
                obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # Send notification if requested from the form
        if form.cleaned_data.get("send_notification"):
            from departments.services.activity_notifications import (
                send_activity_notifications,
            )

            notify_to = form.cleaned_data.get("notify_to") or "department_members"
            member_ids = None
            if notify_to == "specific_members":
                raw = form.cleaned_data.get("member_ids_raw") or ""
                member_ids = [x.strip() for x in raw.splitlines() if x.strip()]
            result = send_activity_notifications(
                obj,
                notify_to=notify_to,
                member_ids=member_ids,
                send_email=form.cleaned_data.get("send_email", True),
                send_sms=form.cleaned_data.get("send_sms", False),
            )
            msg = "Notification sent: {email_sent} email(s), {sms_sent} SMS.".format(
                email_sent=result.get("email_sent", 0),
                sms_sent=result.get("sms_sent", 0),
            )
            if result.get("errors"):
                msg += " Errors: " + "; ".join(result["errors"][:3])
            messages.success(request, msg)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(deleted_at__isnull=True)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, "church") and request.user.church:
            return qs.filter(church=request.user.church)
        return qs

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:object_id>/send-notification/",
                self.admin_site.admin_view(self.send_notification_view),
                name="departments_departmentactivity_send_notification",
            ),
        ]
        return custom + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context["send_notification_url"] = reverse(
                "admin:departments_departmentactivity_send_notification",
                args=[object_id],
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def send_notification_view(self, request, object_id):
        """Send SMS/email notification for this activity to chosen audience."""
        from django import forms as django_forms
        from django.template.response import TemplateResponse

        from departments.services.activity_notifications import (
            NOTIFY_TO_ALL_CHURCH,
            NOTIFY_TO_DEPARTMENT,
            NOTIFY_TO_SPECIFIC,
            send_activity_notifications,
        )

        activity = get_object_or_404(DepartmentActivity, pk=object_id)
        if not request.user.is_staff:
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect(
                reverse("admin:departments_departmentactivity_change", args=[object_id])
            )

        class SendNotificationForm(django_forms.Form):
            notify_to = django_forms.ChoiceField(
                choices=[
                    (NOTIFY_TO_DEPARTMENT, "Department members only"),
                    (NOTIFY_TO_ALL_CHURCH, "All church members"),
                    (NOTIFY_TO_SPECIFIC, "Specific members (enter IDs below)"),
                ],
                label="Send to",
            )
            member_ids_raw = django_forms.CharField(
                required=False,
                widget=django_forms.Textarea(attrs={"rows": 3}),
                label="Member IDs (one per line, only for Specific members)",
            )
            send_email = django_forms.BooleanField(initial=True, label="Send email")
            send_sms = django_forms.BooleanField(initial=False, label="Send SMS")

        if request.method == "POST":
            form = SendNotificationForm(request.POST)
            if form.is_valid():
                notify_to = form.cleaned_data["notify_to"]
                member_ids = None
                if notify_to == NOTIFY_TO_SPECIFIC:
                    raw = form.cleaned_data.get("member_ids_raw") or ""
                    member_ids = [x.strip() for x in raw.splitlines() if x.strip()]
                result = send_activity_notifications(
                    activity,
                    notify_to=notify_to,
                    member_ids=member_ids,
                    send_email=form.cleaned_data["send_email"],
                    send_sms=form.cleaned_data["send_sms"],
                )
                msg = (
                    "Notification sent: {email_sent} email(s), {sms_sent} SMS.".format(
                        email_sent=result.get("email_sent", 0),
                        sms_sent=result.get("sms_sent", 0),
                    )
                )
                if result.get("errors"):
                    msg += " Errors: " + "; ".join(result["errors"][:3])
                    if len(result["errors"]) > 3:
                        msg += " (+%s more)" % (len(result["errors"]) - 3)
                    messages.warning(request, msg)
                else:
                    messages.success(request, msg)
                return HttpResponseRedirect(
                    reverse(
                        "admin:departments_departmentactivity_change", args=[object_id]
                    )
                )
        else:
            form = SendNotificationForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Send activity notification",
            "activity": activity,
            "form": form,
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/departments/departmentactivity/send_notification.html",
            context,
        )


@admin.register(MemberDepartment)
class MemberDepartmentAdmin(admin.ModelAdmin):
    """Member-Department assignment administration"""

    list_display = [
        "member_name",
        "department",
        "role_in_department",
        "church",
        "assigned_at",
    ]
    list_filter = ["department", "church", "assigned_at"]
    search_fields = [
        "member__first_name",
        "member__last_name",
        "department__name",
        "role_in_department",
    ]
    raw_id_fields = ["member", "department", "church"]
    readonly_fields = ["assigned_at"]

    fieldsets = (
        ("Assignment Details", {"fields": ("member", "department", "church")}),
        ("Role Information", {"fields": ("role_in_department",)}),
        ("Timestamps", {"fields": ("assigned_at",), "classes": ("collapse",)}),
    )

    def member_name(self, obj):
        return obj.member.full_name

    member_name.short_description = "Member"
    member_name.admin_order_field = "member__last_name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(church=request.user.church)


@admin.register(DepartmentHead)
class DepartmentHeadAdmin(admin.ModelAdmin):
    """Department head administration"""

    form = DepartmentHeadForm

    list_display = ["department", "head_role", "member_name", "church", "assigned_at"]
    list_filter = ["head_role", "department", "church", "assigned_at"]
    search_fields = ["member__first_name", "member__last_name", "department__name"]

    fieldsets = (
        ("Assignment", {"fields": ("church", "department", "head_role", "member")}),
    )

    class Media:
        css = {"all": ("departments/admin.css",)}

    def member_name(self, obj):
        return obj.member.full_name if obj.member else "No member assigned"

    member_name.short_description = "Head"
    member_name.admin_order_field = "member__last_name"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            form.base_fields["member"].widget.attrs["data-selected-value"] = (
                str(obj.member_id) if obj.member_id else ""
            )
            form.base_fields["department"].widget.attrs["data-selected-value"] = (
                str(obj.department_id) if obj.department_id else ""
            )
        if not request.user.is_superuser:
            form.base_fields["church"].queryset = Church.objects.filter(
                id=request.user.church_id
            )
        return form

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return super().get_readonly_fields(request, obj) + ("assigned_at",)
        return super().get_readonly_fields(request, obj)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("member", "church", "department")
        )
        if request.user.is_superuser:
            return qs
        return qs.filter(church=request.user.church)

    def save_model(self, request, obj, form, change):
        if not obj.church_id and obj.department_id:
            obj.church = obj.department.church
        super().save_model(request, obj, form, change)


# ==========================================
# PROGRAM BUDGET ITEM ADMIN
# ==========================================


@admin.register(ProgramBudgetItem)
class ProgramBudgetItemAdmin(admin.ModelAdmin):
    """Program Budget Item Administration"""

    list_display = [
        "description",
        "item_type",
        "income_source",
        "amount_display",
        "created_at",
    ]
    list_filter = ["item_type", "income_source", "created_at"]
    search_fields = ["description", "notes"]
    readonly_fields = ["created_at", "updated_at"]

    def amount_display(self, obj):
        color = "#28a745" if obj.item_type == "INCOME" else "#dc3545"
        try:
            amount_value = float(obj.amount or 0)
        except (TypeError, ValueError):
            amount_value = 0.0
        amount_str = f"{amount_value:,.2f}"
        return format_html('<span style="color:{};">GHS {}</span>', color, amount_str)

    amount_display.short_description = "Amount"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(program__church=request.user.church)


class ProgramDocumentInline(admin.TabularInline):
    model = ProgramDocument
    extra = 0
    verbose_name = "Document"
    verbose_name_plural = "Step 4: Documents"
    readonly_fields = ["original_filename", "file_size", "uploaded_at"]


# ==========================================
# PROGRAM ADMIN
# ==========================================


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """Program Administration"""

    change_form_template = "admin/departments/program/change_form.html"
    list_display = [
        "id",
        "title",
        "department",
        "status_badge",
        "date_range",
        "budget_summary",
        "approval_status",
        "created_by",
    ]
    list_filter = ["status", "department", "start_date"]
    search_fields = ["title", "description", "department__name"]
    raw_id_fields = ["created_by", "rejected_by"]
    readonly_fields = [
        "total_income",
        "total_expenses",
        "net_budget",
        "created_at",
        "updated_at",
        "submitted_at",
        "approved_at",
        "rejected_at",
        "submission_status",
        "budget_summary_display",
        "created_by",
        "rejected_by",
        "department_elder_display",
        "elder_approved",
        "elder_approved_at",
        "secretariat_approved_at",
        "treasury_approved_at",
        "submitted_to_secretariat",
        "secretariat_approved",
        "submitted_to_treasury",
        "treasury_approved",
    ]
    date_hierarchy = "start_date"
    inlines = [ProgramBudgetItemInline, ProgramDocumentInline]

    # Fieldsets in 5-step order
    fieldsets = (
        (
            "Step 1: Basic Information",
            {
                "fields": (
                    "department",
                    "church",
                    "fiscal_year",
                    "budget_title",
                    "budget_overview",
                    "department_head_name",
                    "department_head_email",
                    "department_head_phone",
                    "submitted_by_department_head",
                    "status",
                )
            },
        ),
        (
            "Step 2: Budget Items",
            {
                "description": 'Add budget items in the "Step 2: Budget Items" section below.',
                "fields": (),
            },
        ),
        (
            "Step 3: Justification",
            {
                "fields": (
                    "strategic_objectives",
                    "expected_impact",
                    "ministry_benefits",
                    "previous_year_comparison",
                    "number_of_beneficiaries",
                    "implementation_timeline",
                )
            },
        ),
        (
            "Step 4: Documents",
            {
                "description": 'Upload supporting documents in the "Step 4: Documents" section below.',
                "fields": (),
            },
        ),
        (
            "Schedule & Location",
            {"fields": ("title", "description", "start_date", "end_date", "location")},
        ),
        (
            "Step 5: Budget Summary (Review)",
            {
                "fields": (
                    "total_income",
                    "total_expenses",
                    "net_budget",
                    "budget_summary_display",
                )
            },
        ),
        (
            "Approval Workflow (Elder → Secretariat → Treasury)",
            {
                "fields": (
                    "department_elder_display",
                    ("elder_approved", "elder_approved_at", "elder_notes"),
                    (
                        "submitted_to_secretariat",
                        "secretariat_approved",
                        "secretariat_approved_at",
                    ),
                    "secretariat_notes",
                    (
                        "submitted_to_treasury",
                        "treasury_approved",
                        "treasury_approved_at",
                    ),
                    "treasury_notes",
                )
            },
        ),
        (
            "Rejection Information",
            {"fields": ("rejection_reason", "rejected_by"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {
                "fields": (
                    ("created_at", "updated_at"),
                    ("submitted_at", "approved_at", "rejected_at"),
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def department_elder_display(self, obj):
        """Show who the department elder is (first approver)."""
        if not obj or not obj.department_id:
            return "— Select a department first —"
        elder = getattr(obj.department, "elder_in_charge", None)
        if elder:
            return format_html("<strong>Department Elder:</strong> {}", elder.full_name)
        return format_html(
            '<span style="color:#856404;">No elder assigned to this department. '
            'Assign one in <a href="{}">Department settings</a>.</span>',
            reverse("admin:departments_department_change", args=[obj.department_id]),
        )

    department_elder_display.short_description = "Department Elder (First Approver)"

    def status_badge(self, obj):
        status_map = {
            "DRAFT": ("#6c757d", "Draft"),
            "SUBMITTED": ("#17a2b8", "Submitted"),
            "ELDER_APPROVED": ("#20c997", "Elder Approved"),
            "SECRETARIAT_APPROVED": ("#007bff", "Secretariat Approved"),
            "TREASURY_APPROVED": ("#28a745", "Treasury Approved"),
            "APPROVED": ("#28a745", "Approved"),
            "REJECTED": ("#dc3545", "Rejected"),
            "CANCELLED": ("#343a40", "Cancelled"),
        }
        color, text = status_map.get(obj.status, ("#6c757d", obj.get_status_display()))
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:3px;font-size:11px;">{}</span>',
            color,
            text,
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def date_range(self, obj):
        if not obj.start_date or not obj.end_date:
            return obj.fiscal_year or "—"
        return f"{obj.start_date.strftime('%b %d, %Y')} - {obj.end_date.strftime('%b %d, %Y')}"

    date_range.short_description = "Date Range"

    def budget_summary(self, obj):
        try:
            income = float(obj.total_income or 0)
        except (TypeError, ValueError):
            income = 0.0
        try:
            expenses = float(obj.total_expenses or 0)
        except (TypeError, ValueError):
            expenses = 0.0
        try:
            net = float(obj.net_budget or 0)
        except (TypeError, ValueError):
            net = 0.0

        net_color = "#28a745" if net >= 0 else "#dc3545"
        html = (
            '<div style="font-size:12px;">'
            'In: <span style="color:#28a745">GHS {:,.0f}</span> &nbsp;'
            'Ex: <span style="color:#dc3545">GHS {:,.0f}</span> &nbsp;'
            'Net: <strong style="color:{:s}">GHS {:,.0f}</strong>'
            "</div>"
        ).format(income, expenses, net_color, net)
        return mark_safe(html)

    budget_summary.short_description = "Budget"

    def approval_status(self, obj):
        parts = []
        if obj.submitted_to_secretariat:
            if obj.secretariat_approved:
                parts.append(
                    '<span style="background:#28a745;color:white;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;margin-right:12px;">Sec: Approved</span>'
                )
            else:
                parts.append(
                    '<span style="background:#17a2b8;color:white;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;margin-right:12px;">Sec: Pending</span>'
                )
        if obj.submitted_to_treasury:
            if obj.treasury_approved:
                parts.append(
                    '<span style="background:#28a745;color:white;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;margin-right:12px;">Treas: Approved</span>'
                )
            else:
                parts.append(
                    '<span style="background:#ffc107;color:#212529;padding:2px 6px;'
                    'border-radius:3px;font-size:11px;">Treas: Pending</span>'
                )
        if not parts:
            return format_html('<span style="color:#6c757d;">Not submitted</span>')
        return mark_safe(
            '<span style="white-space:nowrap;">' + " &nbsp; ".join(parts) + "</span>"
        )

    approval_status.short_description = "Approval Status"

    class Media:
        css = {"all": ("departments/admin.css",)}
        js = ("departments/js/program_form.js",)

    def budget_summary_display(self, obj):
        return self.budget_summary(obj)

    budget_summary_display.short_description = "Budget Summary"

    def submission_status(self, obj):
        if obj.status == "APPROVED" and obj.approved_at:
            return f"Approved on {obj.approved_at.strftime('%b %d, %Y')}"
        elif obj.status == "SUBMITTED" and obj.submitted_at:
            return f"Submitted on {obj.submitted_at.strftime('%b %d, %Y')}"
        return "Not Submitted"

    submission_status.short_description = "Submission Status"

    def save_model(self, request, obj, form, change):
        if not change:
            if obj.department and not obj.church_id:
                obj.church = obj.department.church
            elif (
                not obj.church_id
                and hasattr(request.user, "church")
                and request.user.church
            ):
                obj.church = request.user.church
            if not obj.created_by_id:
                obj.created_by = request.user
        # Sync title from budget_title when budget_title is set (5-step flow)
        if obj.budget_title and not obj.title:
            obj.title = obj.budget_title
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.save()
        formset.save_m2m()
        program = form.instance
        program._calculate_budget_totals()
        program.save()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "church":
            if request.user.is_superuser or getattr(
                request.user, "is_platform_admin", False
            ):
                pass
            elif hasattr(request.user, "church") and request.user.church:
                kwargs["queryset"] = Church.objects.filter(id=request.user.church.id)
            else:
                kwargs["queryset"] = Church.objects.none()
        elif db_field.name == "department":
            church_id = getattr(request, "_program_church_id", None)
            if church_id:
                kwargs["queryset"] = Department.objects.filter(
                    church_id=church_id, is_active=True, deleted_at__isnull=True
                ).order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _get_department_head_info(self, head):
        """Return (name, email, phone) for a DepartmentHead."""
        if not head or not head.member:
            return None, None, None
        m = head.member
        name = getattr(m, "full_name", None) or f"{m.first_name} {m.last_name}".strip()
        email, phone = None, None
        try:
            loc = m.location
            email = getattr(loc, "email", None) or None
            phone = getattr(loc, "phone_primary", None) or None
        except (AttributeError, MemberLocation.DoesNotExist):
            pass
        return name, email, phone

    def department_head_info_view(self, request, dept_id):
        """Return department head name, email, phone as JSON for admin auto-populate."""
        dept = get_object_or_404(Department, pk=dept_id)
        head = (
            DepartmentHead.objects.filter(
                department=dept, head_role=DepartmentHead.HeadRole.HEAD
            )
            .select_related("member")
            .first()
        )
        name, email, phone = self._get_department_head_info(head)
        return JsonResponse(
            {
                "head_name": name or "",
                "head_email": email or "",
                "head_phone": phone or "",
            }
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "department-head-info/<uuid:dept_id>/",
                self.admin_site.admin_view(self.department_head_info_view),
                name="departments_program_dept_head_info",
            ),
            path(
                "<uuid:object_id>/approve-elder/",
                self.admin_site.admin_view(self.approve_elder_view),
                name="departments_program_approve_elder",
            ),
            path(
                "<uuid:object_id>/approve-secretariat/",
                self.admin_site.admin_view(self.approve_secretariat_view),
                name="departments_program_approve_secretariat",
            ),
            path(
                "<uuid:object_id>/approve-treasury/",
                self.admin_site.admin_view(self.approve_treasury_view),
                name="departments_program_approve_treasury",
            ),
            path(
                "<uuid:object_id>/reject/",
                self.admin_site.admin_view(self.reject_view),
                name="departments_program_reject",
            ),
        ]
        return custom_urls + urls

    def _can_approve_elder(self, request, program):
        if request.user.is_staff:
            return True
        if request.user.groups.filter(name__icontains="Elder").exists():
            return True
        elder = getattr(program.department, "elder_in_charge", None)
        if (
            elder
            and elder.system_user_id
            and str(elder.system_user_id) == str(request.user.id)
        ):
            return True
        return False

    def _can_approve_secretariat(self, request):
        return (
            request.user.is_staff
            or request.user.groups.filter(name="Secretariat").exists()
            or request.user.has_perm("departments.approve_secretariat")
        )

    def _can_approve_treasury(self, request):
        return (
            request.user.is_staff
            or request.user.groups.filter(name="Treasury").exists()
            or request.user.has_perm("departments.approve_treasury")
        )

    def approve_elder_view(self, request, object_id):
        program = get_object_or_404(Program, pk=object_id)
        if not self._can_approve_elder(request, program):
            messages.error(
                request, "You don't have permission to approve as Department Elder."
            )
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.status != "SUBMITTED":
            messages.warning(request, "This program is not awaiting Elder approval.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.elder_approved:
            messages.info(request, "Elder has already approved this program.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        program.elder_approved = True
        program.elder_approved_at = timezone.now()
        program.elder_notes = (
            request.POST.get("notes") or request.GET.get("notes") or ""
        )
        program.status = "ELDER_APPROVED"
        program.save()
        messages.success(request, "Program approved by Department Elder.")
        return HttpResponseRedirect(
            reverse("admin:departments_program_change", args=[object_id])
        )

    def approve_secretariat_view(self, request, object_id):
        program = get_object_or_404(Program, pk=object_id)
        if not self._can_approve_secretariat(request):
            messages.error(
                request, "You don't have permission to approve for Secretariat."
            )
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if not program.submitted_to_secretariat:
            messages.warning(
                request, "This program was not submitted for Secretariat approval."
            )
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.status != "ELDER_APPROVED":
            messages.warning(request, "Program must be approved by Elder first.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.secretariat_approved:
            messages.info(request, "Secretariat has already approved this program.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        program.approve(request.user, "SECRETARIAT")
        messages.success(request, "Program approved by Secretariat.")
        return HttpResponseRedirect(
            reverse("admin:departments_program_change", args=[object_id])
        )

    def approve_treasury_view(self, request, object_id):
        program = get_object_or_404(Program, pk=object_id)
        if not self._can_approve_treasury(request):
            messages.error(
                request, "You don't have permission to approve for Treasury."
            )
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if not program.submitted_to_treasury:
            messages.warning(
                request, "This program was not submitted for Treasury approval."
            )
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.status != "SECRETARIAT_APPROVED":
            messages.warning(request, "Program must be approved by Secretariat first.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        if program.treasury_approved:
            messages.info(request, "Treasury has already approved this program.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        program.approve(request.user, "TREASURY")
        messages.success(request, "Program approved by Treasury.")
        return HttpResponseRedirect(
            reverse("admin:departments_program_change", args=[object_id])
        )

    def reject_view(self, request, object_id):
        program = get_object_or_404(Program, pk=object_id)
        can_reject = (
            self._can_approve_elder(request, program)
            or self._can_approve_secretariat(request)
            or self._can_approve_treasury(request)
        )
        if not can_reject:
            messages.error(request, "You don't have permission to reject this program.")
            return HttpResponseRedirect(
                reverse("admin:departments_program_change", args=[object_id])
            )
        reason = (
            request.POST.get("reason")
            or request.GET.get("reason")
            or "Rejected from admin."
        )
        program.reject(request.user, reason)
        messages.success(request, "Program rejected.")
        return HttpResponseRedirect(
            reverse("admin:departments_program_change", args=[object_id])
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        request._program_church_id = None
        extra_context = extra_context or {}
        if object_id:
            try:
                program = self.get_object(request, object_id)
                if program and program.church_id:
                    request._program_church_id = program.church_id
                extra_context["show_approval_actions"] = program.status in (
                    "SUBMITTED",
                    "ELDER_APPROVED",
                    "SECRETARIAT_APPROVED",
                )
                extra_context["can_approve_elder"] = (
                    self._can_approve_elder(request, program)
                    and program.status == "SUBMITTED"
                    and not program.elder_approved
                )
                extra_context["can_approve_secretariat"] = (
                    self._can_approve_secretariat(request)
                    and program.status == "ELDER_APPROVED"
                    and program.submitted_to_secretariat
                    and not program.secretariat_approved
                )
                extra_context["can_approve_treasury"] = (
                    self._can_approve_treasury(request)
                    and program.status == "SECRETARIAT_APPROVED"
                    and program.submitted_to_treasury
                    and not program.treasury_approved
                )
                extra_context["can_reject"] = (
                    self._can_approve_elder(request, program)
                    or self._can_approve_secretariat(request)
                    or self._can_approve_treasury(request)
                )
                extra_context["approve_elder_url"] = reverse(
                    "admin:departments_program_approve_elder", args=[object_id]
                )
                extra_context["approve_secretariat_url"] = reverse(
                    "admin:departments_program_approve_secretariat", args=[object_id]
                )
                extra_context["approve_treasury_url"] = reverse(
                    "admin:departments_program_approve_treasury", args=[object_id]
                )
                extra_context["reject_url"] = reverse(
                    "admin:departments_program_reject", args=[object_id]
                )
            except Program.DoesNotExist:
                pass
        if not request._program_church_id and getattr(request.user, "church_id", None):
            request._program_church_id = request.user.church_id
        base = reverse("admin:departments_program_changelist")
        extra_context["dept_head_info_base"] = (
            base.rstrip("/") + "/department-head-info/"
        )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related(
                "department",
                "church",
                "created_by",
                "department__church",
                "department__elder_in_charge",
            )
        )
        if request.user.is_superuser or getattr(
            request.user, "is_platform_admin", False
        ):
            return qs
        if hasattr(request.user, "church") and request.user.church:
            return qs.filter(church=request.user.church)
        return qs.none()
