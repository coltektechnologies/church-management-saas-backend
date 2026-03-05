from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (Asset, ExpenseCategory, ExpenseRequest,
                     ExpenseTransaction, IncomeAllocation, IncomeCategory,
                     IncomeTransaction)

# ==========================================
# INCOME CATEGORY ADMIN
# ==========================================


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "church",
        "is_active",
        "transaction_count",
        "total_amount_display",
        "created_at",
    ]
    list_filter = ["is_active", "church", "created_at"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("church", "name", "code", "description", "is_active")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def transaction_count(self, obj):
        count = obj.transactions.filter(deleted_at__isnull=True).count()
        return format_html('<span style="color: #0066cc;">{}</span>', count)

    transaction_count.short_description = "Transactions"

    def total_amount_display(self, obj):
        total = (
            obj.transactions.filter(deleted_at__isnull=True).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        formatted_total = "${:,.2f}".format(float(total))
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">{}</span>',
            formatted_total,
        )

    total_amount_display.short_description = "Total Amount"


# ==========================================
# INCOME ALLOCATION INLINE (read-only)
# ==========================================


class IncomeAllocationInline(admin.TabularInline):
    model = IncomeAllocation
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ["destination_display", "amount", "percentage"]
    verbose_name = "Church/Conference split"
    verbose_name_plural = "Church/Conference allocation (auto: Tithe 100% Conference; General/Loose Offering 50/50)"

    def destination_display(self, obj):
        return obj.get_destination_display() if obj else ""

    destination_display.short_description = "Destination"

    def has_add_permission(self, request, obj=None):
        return False


# ==========================================
# INCOME TRANSACTION ADMIN
# ==========================================


@admin.register(IncomeTransaction)
class IncomeTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "receipt_number",
        "transaction_date",
        "church",
        "category",
        "amount_display",
        "payment_method",
        "contributor_display",
        "recorded_by",
    ]
    list_filter = [
        "transaction_date",
        "payment_method",
        "service_type",
        "category",
        "church",
        "is_anonymous",
    ]
    search_fields = [
        "receipt_number",
        "contributor_name",
        "member__first_name",
        "member__last_name",
    ]
    readonly_fields = ["receipt_number", "recorded_by", "created_at", "updated_at"]
    date_hierarchy = "transaction_date"
    inlines = [IncomeAllocationInline]

    fieldsets = (
        (
            "Transaction Details",
            {
                "fields": (
                    "church",
                    "receipt_number",
                    "transaction_date",
                    "category",
                    "service_type",
                )
            },
        ),
        ("Amount Information", {"fields": ("amount", "amount_in_words")}),
        (
            "Payment Details",
            {
                "fields": (
                    "payment_method",
                    "cheque_number",
                    "transaction_reference",
                    "bank_name",
                )
            },
        ),
        (
            "Contributor Information",
            {"fields": ("member", "contributor_name", "is_anonymous")},
        ),
        (
            "Project Allocation",
            {"fields": ("department", "project_name"), "classes": ("collapse",)},
        ),
        ("Recording Details", {"fields": ("recorded_by", "witnessed_by", "notes")}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def amount_display(self, obj):
        if obj.amount is not None:
            try:
                amount = float(obj.amount)
                formatted_amount = "${:,.2f}".format(amount)
                return mark_safe(
                    f'<span style="color: #28a745; font-weight: bold;">{formatted_amount}</span>'
                )
            except (ValueError, TypeError):
                return str(obj.amount) if obj.amount else ""
        return ""

    amount_display.short_description = "Amount"
    amount_display.admin_order_field = "amount"

    def contributor_display(self, obj):
        if obj.is_anonymous:
            return mark_safe('<span style="color: #6c757d;">Anonymous</span>')
        if (
            obj.member
            and hasattr(obj.member, "pk")
            and hasattr(obj.member, "full_name")
        ):
            try:
                url = reverse("admin:members_member_change", args=[obj.member.pk])
                return mark_safe(f'<a href="{url}">{obj.member.full_name}</a>')
            except Exception:
                return obj.member.full_name or str(obj.member)
        return obj.contributor_name or "N/A"

    contributor_display.short_description = "Contributor"

    def save_model(self, request, obj, form, change):
        if not change:  # New record
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# EXPENSE CATEGORY ADMIN
# ==========================================


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "church",
        "is_active",
        "transaction_count",
        "total_amount_display",
        "created_at",
    ]
    list_filter = ["is_active", "church", "created_at"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("church", "name", "code", "description", "is_active")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def transaction_count(self, obj):
        count = obj.transactions.filter(deleted_at__isnull=True).count()
        return format_html('<span style="color: #0066cc;">{}</span>', count)

    transaction_count.short_description = "Transactions"

    def total_amount_display(self, obj):
        total = (
            obj.transactions.filter(deleted_at__isnull=True).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        formatted_total = "${:,.2f}".format(total)
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">{}</span>',
            formatted_total,
        )

    total_amount_display.short_description = "Total Amount"


# ==========================================
# EXPENSE TRANSACTION ADMIN
# ==========================================


@admin.register(ExpenseTransaction)
class ExpenseTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "voucher_number",
        "transaction_date",
        "church",
        "category",
        "department",
        "amount_display",
        "paid_to",
        "payment_method",
        "approved_by",
    ]
    list_filter = [
        "transaction_date",
        "payment_method",
        "category",
        "department",
        "church",
    ]
    search_fields = ["voucher_number", "paid_to", "description"]
    readonly_fields = ["voucher_number", "recorded_by", "created_at", "updated_at"]
    date_hierarchy = "transaction_date"

    fieldsets = (
        (
            "Transaction Details",
            {
                "fields": (
                    "church",
                    "voucher_number",
                    "transaction_date",
                    "category",
                    "department",
                )
            },
        ),
        ("Amount Information", {"fields": ("amount", "amount_in_words")}),
        (
            "Payment Details",
            {
                "fields": (
                    "payment_method",
                    "cheque_number",
                    "transaction_reference",
                    "bank_name",
                )
            },
        ),
        (
            "Recipient Information",
            {"fields": ("paid_to", "recipient_phone", "recipient_id")},
        ),
        ("Description", {"fields": ("description",)}),
        (
            "Authorization",
            {
                "fields": (
                    "requested_by",
                    "approved_by",
                    "recorded_by",
                    "expense_request",
                )
            },
        ),
        ("Additional Notes", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def amount_display(self, obj):
        formatted_amount = "${:,.2f}".format(obj.amount) if obj.amount else "$0.00"
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">{}</span>',
            formatted_amount,
        )

    amount_display.short_description = "Amount"
    amount_display.admin_order_field = "amount"

    def save_model(self, request, obj, form, change):
        if not change:  # New record
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# EXPENSE REQUEST ADMIN
# ==========================================


@admin.register(ExpenseRequest)
class ExpenseRequestAdmin(admin.ModelAdmin):
    list_display = [
        "request_number",
        "church",
        "department",
        "amount_requested_display",
        "status_badge",
        "priority_badge",
        "approval_progress_bar",
        "requested_by",
        "required_by_date",
    ]
    list_filter = [
        "status",
        "priority",
        "department",
        "church",
        "required_by_date",
        "created_at",
    ]
    search_fields = ["request_number", "purpose", "justification"]
    readonly_fields = [
        "request_number",
        "requested_by",
        "requested_at",
        "dept_head_approved_by",
        "dept_head_approved_at",
        "treasurer_approved_by",
        "treasurer_approved_at",
        "first_elder_approved_by",
        "first_elder_approved_at",
        "approval_progress",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Request Details",
            {
                "fields": (
                    "church",
                    "request_number",
                    "department",
                    "category",
                    "required_by_date",
                )
            },
        ),
        (
            "Amount & Description",
            {
                "fields": (
                    "amount_requested",
                    "amount_approved",
                    "purpose",
                    "justification",
                )
            },
        ),
        ("Status & Priority", {"fields": ("status", "priority")}),
        ("Requester Information", {"fields": ("requested_by", "requested_at")}),
        (
            "Approval Chain - Department Head",
            {
                "fields": ("dept_head_approved_by", "dept_head_approved_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Approval Chain - First Elder",
            {
                "fields": ("first_elder_approved_by", "first_elder_approved_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Approval Chain - Treasurer",
            {
                "fields": ("treasurer_approved_by", "treasurer_approved_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Rejection/Comments",
            {
                "fields": ("rejection_reason", "approval_comments"),
                "classes": ("collapse",),
            },
        ),
        (
            "Disbursement",
            {"fields": ("disbursed_at", "disbursed_amount"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def amount_requested_display(self, obj):
        formatted_amount = "${:,.2f}".format(obj.amount_requested)
        return format_html(
            '<span style="font-weight: bold;">{}</span>', formatted_amount
        )

    amount_requested_display.short_description = "Amount"
    amount_requested_display.admin_order_field = "amount_requested"

    def status_badge(self, obj):
        colors = {
            "DRAFT": "#6c757d",
            "SUBMITTED": "#0066cc",
            "DEPT_HEAD_APPROVED": "#17a2b8",
            "ELDER_APPROVED": "#17a2b8",
            "FIRST_ELDER_APPROVED": "#17a2b8",
            "TREASURER_APPROVED": "#17a2b8",
            "APPROVED": "#28a745",
            "REJECTED": "#dc3545",
            "DISBURSED": "#28a745",
            "CANCELLED": "#6c757d",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def priority_badge(self, obj):
        colors = {
            "LOW": "#28a745",
            "MEDIUM": "#ffc107",
            "HIGH": "#fd7e14",
            "URGENT": "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.priority, "#6c757d"),
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"
    priority_badge.admin_order_field = "priority"

    def approval_progress_bar(self, obj):
        progress = obj.approval_progress
        color = "#28a745" if progress == 100 else "#0066cc"
        return format_html(
            """
            <div style="width: 100px; background-color: #e9ecef; border-radius: 3px; overflow: hidden;">
                <div style="width: {}%; background-color: {}; height: 20px; line-height: 20px; text-align: center; color: white; font-size: 11px;">
                    {}%
                </div>
            </div>
            """,
            progress,
            color,
            int(progress),
        )

    approval_progress_bar.short_description = "Progress"


# ==========================================
# ASSET ADMIN
# ==========================================


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "asset_tag",
        "name",
        "church",
        "category_badge",
        "purchase_cost_display",
        "current_value_display",
        "condition_badge",
        "department",
        "custodian",
    ]
    list_filter = ["category", "condition", "church", "department", "purchase_date"]
    search_fields = ["asset_tag", "name", "serial_number", "supplier"]
    readonly_fields = ["asset_tag", "created_at", "updated_at"]
    date_hierarchy = "purchase_date"

    fieldsets = (
        (
            "Asset Details",
            {"fields": ("church", "name", "asset_tag", "category", "serial_number")},
        ),
        (
            "Purchase Information",
            {"fields": ("purchase_date", "purchase_cost", "supplier")},
        ),
        ("Current Status", {"fields": ("current_value", "condition")}),
        ("Location & Custodian", {"fields": ("department", "custodian")}),
        (
            "Warranty & Insurance",
            {
                "fields": ("warranty_expiry", "insurance_policy"),
                "classes": ("collapse",),
            },
        ),
        ("Additional Notes", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "deleted_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def category_badge(self, obj):
        colors = {
            "LAND_BUILDING": "#6f42c1",
            "FURNITURE": "#fd7e14",
            "EQUIPMENT": "#0066cc",
            "VEHICLE": "#dc3545",
            "IT_EQUIPMENT": "#17a2b8",
            "MUSICAL_INSTRUMENTS": "#e83e8c",
            "BOOKS": "#28a745",
            "OTHER": "#6c757d",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.category, "#6c757d"),
            obj.get_category_display(),
        )

    category_badge.short_description = "Category"
    category_badge.admin_order_field = "category"

    def condition_badge(self, obj):
        colors = {
            "EXCELLENT": "#28a745",
            "GOOD": "#17a2b8",
            "FAIR": "#ffc107",
            "POOR": "#fd7e14",
            "DAMAGED": "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.condition, "#6c757d"),
            obj.get_condition_display(),
        )

    condition_badge.short_description = "Condition"
    condition_badge.admin_order_field = "condition"

    def purchase_cost_display(self, obj):
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>', obj.purchase_cost
        )

    purchase_cost_display.short_description = "Purchase Cost"
    purchase_cost_display.admin_order_field = "purchase_cost"

    def current_value_display(self, obj):
        if obj.current_value:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">${:,.2f}</span>',
                obj.current_value,
            )
        return format_html('<span style="color: #6c757d;">N/A</span>')

    current_value_display.short_description = "Current Value"
    current_value_display.admin_order_field = "current_value"


# ==========================================
# ADMIN SITE CUSTOMIZATION
# ==========================================
