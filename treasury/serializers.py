from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from accounts.models.base_models import AuditLog
from departments.models import Department
from departments.serializers import DepartmentListSerializer, ProgramListSerializer
from members.serializers import MemberListSerializer

from .expense_approval_access import (
    can_approve_expense_as_dept_head_or_elder,
    can_approve_expense_as_first_elder,
    can_approve_expense_as_treasurer,
)
from .models import (
    Asset,
    ExpenseCategory,
    ExpenseRequest,
    ExpenseTransaction,
    IncomeAllocation,
    IncomeCategory,
    IncomeTransaction,
    MemberPledge,
)

# ==========================================
# MEMBER PLEDGE SERIALIZERS
# ==========================================


class MemberPledgeSerializer(serializers.ModelSerializer):
    """Portal + treasury: pledge with computed paid progress."""

    amount_fulfilled = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()

    class Meta:
        model = MemberPledge
        fields = [
            "id",
            "pledge_year",
            "title",
            "target_amount",
            "amount_fulfilled",
            "amount_remaining",
            "status",
            "notes",
            "fulfilled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "amount_fulfilled",
            "amount_remaining",
            "fulfilled_at",
            "created_at",
            "updated_at",
        ]

    def get_amount_fulfilled(self, obj):
        return str(obj.fulfilled_amount())

    def get_amount_remaining(self, obj):
        rem = obj.target_amount - obj.fulfilled_amount()
        if rem < Decimal("0"):
            rem = Decimal("0")
        return str(rem.quantize(Decimal("0.01")))

    def validate_pledge_year(self, value):
        from datetime import datetime

        y = datetime.now().year
        if value < y - 1 or value > y + 5:
            raise serializers.ValidationError(
                "Pledge year must be within a reasonable range."
            )
        return value

    def validate_target_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        member = self.context.get("member")
        church = self.context.get("church")
        if member is None or church is None:
            raise serializers.ValidationError("Member context required")
        return MemberPledge.objects.create(
            church=church,
            member=member,
            **validated_data,
        )


class MemberPledgeTreasurySerializer(serializers.ModelSerializer):
    """Compact row for treasury dropdown when recording income."""

    amount_fulfilled = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()

    class Meta:
        model = MemberPledge
        fields = [
            "id",
            "pledge_year",
            "title",
            "target_amount",
            "amount_fulfilled",
            "status",
            "label",
        ]

    def get_amount_fulfilled(self, obj):
        return str(obj.fulfilled_amount())

    def get_label(self, obj):
        title = (obj.title or "Giving pledge").strip()
        return f"{title} ({obj.pledge_year}) — {obj.target_amount} GHS"


class MemberPledgeChurchListSerializer(serializers.ModelSerializer):
    """All pledges for a church (treasury overview)."""

    amount_fulfilled = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = MemberPledge
        fields = [
            "id",
            "member_id",
            "member_name",
            "pledge_year",
            "title",
            "target_amount",
            "amount_fulfilled",
            "amount_remaining",
            "status",
            "notes",
            "fulfilled_at",
            "created_at",
            "updated_at",
        ]

    def get_amount_fulfilled(self, obj):
        return str(obj.fulfilled_amount())

    def get_amount_remaining(self, obj):
        rem = obj.target_amount - obj.fulfilled_amount()
        if rem < Decimal("0"):
            rem = Decimal("0")
        return str(rem.quantize(Decimal("0.01")))

    def get_member_name(self, obj):
        m = obj.member
        if not m:
            return ""
        return m.get_full_name() or ""


def expense_review_permissions(request, obj):
    if not request or not getattr(request.user, "is_authenticated", False):
        return {"dept_head": False, "first_elder": False, "treasurer": False}
    return {
        "dept_head": can_approve_expense_as_dept_head_or_elder(request, obj),
        "first_elder": can_approve_expense_as_first_elder(request, obj),
        "treasurer": can_approve_expense_as_treasurer(request, obj),
    }


# ==========================================
# INCOME CATEGORY SERIALIZERS
# ==========================================


class IncomeCategorySerializer(serializers.ModelSerializer):
    """Income category serializer"""

    transaction_count = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = IncomeCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "transaction_count",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_transaction_count(self, obj):
        return obj.transactions.filter(deleted_at__isnull=True).count()

    def get_total_amount(self, obj):
        total = obj.transactions.filter(deleted_at__isnull=True).aggregate(
            total=Sum("amount")
        )["total"]
        return str(total or Decimal("0.00"))

    def validate_code(self, value):
        """Ensure code is uppercase"""
        return value.upper()

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        return IncomeCategory.objects.create(church=church, **validated_data)


# ==========================================
# INCOME TRANSACTION SERIALIZERS
# ==========================================


class IncomeAllocationSerializer(serializers.ModelSerializer):
    """Income allocation (Church/Conference split)."""

    destination_display = serializers.CharField(
        source="get_destination_display", read_only=True
    )

    class Meta:
        model = IncomeAllocation
        fields = ["id", "destination", "destination_display", "amount", "percentage"]


class IncomeTransactionListSerializer(serializers.ModelSerializer):
    """Lightweight income transaction list"""

    category_name = serializers.CharField(source="category.name", read_only=True)
    contributor_display = serializers.SerializerMethodField()
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    allocations = serializers.SerializerMethodField()

    class Meta:
        model = IncomeTransaction
        fields = [
            "id",
            "receipt_number",
            "transaction_date",
            "category_name",
            "amount",
            "payment_method_display",
            "contributor_display",
            "service_type",
            "allocations",
            "created_at",
        ]

    def get_allocations(self, obj):
        return IncomeAllocationSerializer(
            obj.allocations.all().order_by("destination"), many=True
        ).data

    def get_contributor_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.member:
            return obj.member.full_name
        return obj.contributor_name or "N/A"


class IncomeTransactionDetailSerializer(serializers.ModelSerializer):
    """Full income transaction details"""

    category = IncomeCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=IncomeCategory.objects.all(), source="category", write_only=True
    )
    member_details = MemberListSerializer(source="member", read_only=True)
    department_details = DepartmentListSerializer(source="department", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    service_type_display = serializers.CharField(
        source="get_service_type_display", read_only=True
    )
    allocations = serializers.SerializerMethodField()
    pledge = serializers.PrimaryKeyRelatedField(
        queryset=MemberPledge.objects.all(),
        required=False,
        allow_null=True,
    )
    pledge_detail = serializers.SerializerMethodField()

    class Meta:
        model = IncomeTransaction
        fields = [
            "id",
            "receipt_number",
            "transaction_date",
            "category",
            "category_id",
            "service_type",
            "service_type_display",
            "amount",
            "amount_in_words",
            "payment_method",
            "payment_method_display",
            "cheque_number",
            "transaction_reference",
            "bank_name",
            "member",
            "member_details",
            "contributor_name",
            "is_anonymous",
            "department",
            "department_details",
            "project_name",
            "pledge",
            "pledge_detail",
            "allocations",
            "recorded_by",
            "recorded_by_name",
            "witnessed_by",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "receipt_number",
            "recorded_by",
            "created_at",
            "updated_at",
        ]

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None

    def get_allocations(self, obj):
        return IncomeAllocationSerializer(
            obj.allocations.all().order_by("destination"), many=True
        ).data

    def get_pledge_detail(self, obj):
        if not obj.pledge_id:
            return None
        p = obj.pledge
        return {
            "id": str(p.id),
            "pledge_year": p.pledge_year,
            "title": p.title,
            "target_amount": str(p.target_amount),
            "amount_fulfilled": str(p.fulfilled_amount()),
            "status": p.status,
        }

    def validate(self, attrs):
        """Validate payment method specific fields"""
        payment_method = attrs.get("payment_method")

        if payment_method == "CHEQUE" and not attrs.get("cheque_number"):
            raise serializers.ValidationError(
                {"cheque_number": "Cheque number is required for cheque payments"}
            )

        if payment_method in ["MOBILE_MONEY", "BANK_TRANSFER"] and not attrs.get(
            "transaction_reference"
        ):
            raise serializers.ValidationError(
                {"transaction_reference": "Transaction reference is required"}
            )

        if "pledge" in attrs:
            pledge = attrs["pledge"]
        elif self.instance:
            pledge = self.instance.pledge
        else:
            pledge = None

        if "member" in attrs:
            member = attrs["member"]
        elif self.instance:
            member = self.instance.member
        else:
            member = None

        if pledge:
            if not member:
                raise serializers.ValidationError(
                    {"pledge": "Select a member before linking a pledge."}
                )
            if pledge.member_id != member.pk:
                raise serializers.ValidationError(
                    {"pledge": "This pledge does not match the selected member."}
                )
            request = self.context.get("request")
            church = None
            if request:
                church = getattr(request, "current_church", None) or getattr(
                    getattr(request, "user", None), "church", None
                )
            if church and pledge.church_id != church.pk:
                raise serializers.ValidationError(
                    {"pledge": "Pledge is not in your church."}
                )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        # Generate receipt number
        from datetime import datetime

        year = datetime.now().year
        last_receipt = (
            IncomeTransaction.objects.filter(
                church=church, receipt_number__startswith=f"REC-{year}-"
            )
            .order_by("-created_at")
            .first()
        )

        if last_receipt:
            last_num = int(last_receipt.receipt_number.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        receipt_number = f"REC-{year}-{new_num:06d}"

        return IncomeTransaction.objects.create(
            church=church,
            receipt_number=receipt_number,
            recorded_by=request.user,
            **validated_data,
        )


# ==========================================
# EXPENSE CATEGORY SERIALIZERS
# ==========================================


class ExpenseCategorySerializer(serializers.ModelSerializer):
    """Expense category serializer"""

    transaction_count = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "transaction_count",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_transaction_count(self, obj):
        return obj.transactions.filter(deleted_at__isnull=True).count()

    def get_total_amount(self, obj):
        total = obj.transactions.filter(deleted_at__isnull=True).aggregate(
            total=Sum("amount")
        )["total"]
        return str(total or Decimal("0.00"))

    def validate_code(self, value):
        """Ensure code is uppercase"""
        return value.upper()

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        return ExpenseCategory.objects.create(church=church, **validated_data)


# ==========================================
# EXPENSE TRANSACTION SERIALIZERS
# ==========================================


class ExpenseTransactionListSerializer(serializers.ModelSerializer):
    """Lightweight expense transaction list"""

    category_name = serializers.CharField(source="category.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = ExpenseTransaction
        fields = [
            "id",
            "voucher_number",
            "transaction_date",
            "category_name",
            "department_name",
            "amount",
            "paid_to",
            "payment_method_display",
            "created_at",
        ]


class ExpenseTransactionDetailSerializer(serializers.ModelSerializer):
    """Full expense transaction details"""

    category = ExpenseCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ExpenseCategory.objects.all(), source="category", write_only=True
    )
    department = DepartmentListSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.none(),
        source="department",
        write_only=True,
    )
    recorded_by_name = serializers.SerializerMethodField()
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = ExpenseTransaction
        fields = [
            "id",
            "voucher_number",
            "transaction_date",
            "category",
            "category_id",
            "department",
            "department_id",
            "amount",
            "amount_in_words",
            "payment_method",
            "payment_method_display",
            "cheque_number",
            "transaction_reference",
            "bank_name",
            "paid_to",
            "recipient_phone",
            "recipient_id",
            "description",
            "requested_by",
            "approved_by",
            "recorded_by",
            "recorded_by_name",
            "expense_request",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "voucher_number",
            "recorded_by",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            church = getattr(request, "current_church", None) or getattr(
                request.user, "church", None
            )
            if church:
                self.fields["department_id"].queryset = Department.objects.filter(
                    church=church
                )
                self.fields["category_id"].queryset = ExpenseCategory.objects.filter(
                    church=church
                )

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None

    def validate(self, attrs):
        """Validate payment method specific fields"""
        payment_method = attrs.get("payment_method")

        if payment_method == "CHEQUE" and not attrs.get("cheque_number"):
            raise serializers.ValidationError(
                {"cheque_number": "Cheque number is required for cheque payments"}
            )

        if payment_method in ["MOBILE_MONEY", "BANK_TRANSFER"] and not attrs.get(
            "transaction_reference"
        ):
            raise serializers.ValidationError(
                {"transaction_reference": "Transaction reference is required"}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        expense_req = validated_data.get("expense_request")
        if expense_req:
            if (
                validated_data.get("requested_by") is None
                and expense_req.requested_by_id
            ):
                validated_data["requested_by"] = expense_req.requested_by
            if (
                validated_data.get("approved_by") is None
                and expense_req.treasurer_approved_by_id
            ):
                validated_data["approved_by"] = expense_req.treasurer_approved_by

        # Generate voucher number
        from datetime import datetime

        year = datetime.now().year
        last_voucher = (
            ExpenseTransaction.objects.filter(
                church=church, voucher_number__startswith=f"VCH-{year}-"
            )
            .order_by("-created_at")
            .first()
        )

        if last_voucher:
            last_num = int(last_voucher.voucher_number.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        voucher_number = f"VCH-{year}-{new_num:06d}"

        instance = ExpenseTransaction.objects.create(
            church=church,
            voucher_number=voucher_number,
            recorded_by=request.user,
            **validated_data,
        )

        if expense_req and expense_req.status == "APPROVED":
            expense_req.status = "DISBURSED"
            expense_req.disbursed_at = timezone.now()
            expense_req.disbursed_amount = instance.amount
            expense_req.save()
            try:
                AuditLog.log(
                    request.user,
                    "STATUS_CHANGE",
                    expense_req,
                    request=request,
                    description=(
                        f"Expense request {expense_req.request_number} marked disbursed "
                        f"from expense transaction {instance.voucher_number}"
                    ),
                )
            except Exception:
                pass

        return instance


# ==========================================
# EXPENSE REQUEST SERIALIZERS
# ==========================================


def expense_request_pending_step(obj) -> dict:
    """
    Who must act next on this expense request (for list API, admin, and UI).
    Returns {"code": str, "label": str}.
    """
    s = (getattr(obj, "status", None) or "").strip()
    if s == "DRAFT":
        return {
            "code": "DRAFT",
            "label": "Submitter: complete draft and submit",
        }
    if s == "SUBMITTED":
        return {
            "code": "DEPT_HEAD",
            "label": "Department head or elder in charge",
        }
    if s == "DEPT_HEAD_APPROVED":
        return {
            "code": "FIRST_ELDER",
            "label": "First Elder or elder in charge",
        }
    if s == "FIRST_ELDER_APPROVED":
        return {
            "code": "TREASURER",
            "label": "Treasurer (final approval)",
        }
    if s == "TREASURER_APPROVED":
        return {
            "code": "TREASURER",
            "label": "Treasurer (complete workflow)",
        }
    if s == "APPROVED":
        return {
            "code": "DISBURSE",
            "label": "Treasurer: record disbursement when paid",
        }
    if s == "DISBURSED":
        return {"code": "DONE", "label": "Completed (disbursed)"}
    if s == "REJECTED":
        return {"code": "REJECTED", "label": "Rejected — no further approvals"}
    if s == "CANCELLED":
        return {"code": "CANCELLED", "label": "Cancelled"}
    label = obj.get_status_display() if hasattr(obj, "get_status_display") else s
    return {"code": s or "UNKNOWN", "label": label}


def expense_request_approval_chain(obj) -> dict:
    """
    Approval stages for list/detail API and admin UI.
    Keys: dept_head, first_elder, treasurer — each has approved, approved_by, approved_at.
    """
    return {
        "dept_head": {
            "approved": obj.dept_head_approved_at is not None,
            "approved_by": (
                obj.dept_head_approved_by.get_full_name()
                if obj.dept_head_approved_by
                else None
            ),
            "approved_at": obj.dept_head_approved_at,
        },
        "first_elder": {
            "approved": obj.first_elder_approved_at is not None,
            "approved_by": (
                obj.first_elder_approved_by.get_full_name()
                if obj.first_elder_approved_by
                else None
            ),
            "approved_at": obj.first_elder_approved_at,
        },
        "treasurer": {
            "approved": obj.treasurer_approved_at is not None,
            "approved_by": (
                obj.treasurer_approved_by.get_full_name()
                if obj.treasurer_approved_by
                else None
            ),
            "approved_at": obj.treasurer_approved_at,
        },
    }


class ExpenseRequestListSerializer(serializers.ModelSerializer):
    """Lightweight expense request list"""

    department_name = serializers.CharField(source="department.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    approval_progress = serializers.FloatField(read_only=True)
    pending_step = serializers.SerializerMethodField()
    approval_chain = serializers.SerializerMethodField()
    review_permissions = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseRequest
        fields = [
            "id",
            "request_number",
            "department_name",
            "category_name",
            "amount_requested",
            "amount_approved",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "required_by_date",
            "requested_by_name",
            "approval_progress",
            "approval_chain",
            "pending_step",
            "review_permissions",
            "created_at",
        ]

    def get_requested_by_name(self, obj):
        if obj.requested_by:
            return obj.requested_by.get_full_name() or obj.requested_by.username
        return None

    def get_pending_step(self, obj):
        return expense_request_pending_step(obj)

    def get_approval_chain(self, obj):
        return expense_request_approval_chain(obj)

    def get_review_permissions(self, obj):
        return expense_review_permissions(self.context.get("request"), obj)


class ExpenseRequestDetailSerializer(serializers.ModelSerializer):
    """Full expense request details"""

    department = DepartmentListSerializer(read_only=True)
    department_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    category = ExpenseCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ExpenseCategory.objects.all(), source="category", write_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    approval_progress = serializers.FloatField(read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    approval_chain = serializers.SerializerMethodField()
    pending_step = serializers.SerializerMethodField()
    review_permissions = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseRequest
        fields = [
            "id",
            "request_number",
            "department",
            "department_id",
            "category",
            "category_id",
            "amount_requested",
            "amount_approved",
            "purpose",
            "justification",
            "required_by_date",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "requested_by",
            "requested_by_name",
            "requested_at",
            "approval_chain",
            "pending_step",
            "review_permissions",
            "approval_progress",
            "rejection_reason",
            "approval_comments",
            "disbursed_at",
            "disbursed_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "request_number",
            "requested_by",
            "requested_at",
            "approval_chain",
            "pending_step",
            "review_permissions",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            from departments.models import Department

            church = getattr(request, "current_church", None) or getattr(
                request.user, "church", None
            )
            if church:
                self.fields["department_id"].queryset = Department.objects.filter(
                    church=church
                )

    def get_requested_by_name(self, obj):
        if obj.requested_by:
            return obj.requested_by.get_full_name() or obj.requested_by.username
        return None

    def get_approval_chain(self, obj):
        """Get approval chain status"""
        return expense_request_approval_chain(obj)

    def get_pending_step(self, obj):
        return expense_request_pending_step(obj)

    def get_review_permissions(self, obj):
        return expense_review_permissions(self.context.get("request"), obj)

    def update(self, instance, validated_data):
        from departments.models import Department

        department_id = validated_data.pop("department_id", None)
        instance = super().update(instance, validated_data)
        if department_id is not None:
            if department_id:
                try:
                    department = Department.objects.get(
                        id=department_id, church=instance.church
                    )
                    instance.department = department
                except Department.DoesNotExist:
                    pass
            else:
                instance.department = None
            instance.save()
        return instance

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        # Generate request number
        from datetime import datetime

        year = datetime.now().year
        last_request = (
            ExpenseRequest.objects.filter(
                church=church, request_number__startswith=f"EXP-{year}-"
            )
            .order_by("-created_at")
            .first()
        )

        if last_request:
            last_num = int(last_request.request_number.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        request_number = f"EXP-{year}-{new_num:06d}"

        return ExpenseRequest.objects.create(
            church=church,
            request_number=request_number,
            requested_by=request.user,
            **validated_data,
        )


class ApproveExpenseRequestSerializer(serializers.Serializer):
    """Approve expense request"""

    amount_approved = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True
    )
    comments = serializers.CharField(required=False, allow_blank=True)


class RejectExpenseRequestSerializer(serializers.Serializer):
    """Reject expense request"""

    rejection_reason = serializers.CharField(required=True)


class DisburseExpenseRequestSerializer(serializers.Serializer):
    """Disburse expense request"""

    disbursed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True
    )
    payment_method = serializers.ChoiceField(
        choices=ExpenseTransaction.PAYMENT_METHOD_CHOICES, required=True
    )
    transaction_reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


# ==========================================
# ASSET SERIALIZERS
# ==========================================


class AssetListSerializer(serializers.ModelSerializer):
    """Lightweight asset list"""

    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_tag",
            "name",
            "category",
            "category_display",
            "purchase_date",
            "purchase_cost",
            "current_value",
            "condition",
            "condition_display",
            "department_name",
        ]


class AssetDetailSerializer(serializers.ModelSerializer):
    """Full asset details"""

    department = DepartmentListSerializer(read_only=True)
    department_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    custodian = MemberListSerializer(read_only=True)
    custodian_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )

    def create(self, validated_data):
        from departments.models import Department
        from members.models import Member

        # Extract and remove department_id and custodian_id from validated_data
        department_id = validated_data.pop("department_id", None)
        custodian_id = validated_data.pop("custodian_id", None)

        # Create the instance
        instance = super().create(validated_data)

        # Set department if provided
        if department_id:
            try:
                department = Department.objects.get(
                    id=department_id, church=instance.church
                )
                instance.department = department
            except Department.DoesNotExist:
                pass

        # Set custodian if provided
        if custodian_id:
            try:
                custodian = Member.objects.get(id=custodian_id, church=instance.church)
                instance.custodian = custodian
            except Member.DoesNotExist:
                pass

        if department_id is not None or custodian_id is not None:
            instance.save()

        return instance

    def update(self, instance, validated_data):
        from departments.models import Department
        from members.models import Member

        # Extract and remove department_id and custodian_id from validated_data
        department_id = validated_data.pop("department_id", None)
        custodian_id = validated_data.pop("custodian_id", None)

        # Update the instance
        instance = super().update(instance, validated_data)

        # Update department if provided
        if department_id is not None:  # Could be None to clear the department
            if department_id:
                try:
                    department = Department.objects.get(
                        id=department_id, church=instance.church
                    )
                    instance.department = department
                except Department.DoesNotExist:
                    pass
            else:
                instance.department = None

        # Update custodian if provided
        if custodian_id is not None:  # Could be None to clear the custodian
            if custodian_id:
                try:
                    custodian = Member.objects.get(
                        id=custodian_id, church=instance.church
                    )
                    instance.custodian = custodian
                except Member.DoesNotExist:
                    pass
            else:
                instance.custodian = None

        if department_id is not None or custodian_id is not None:
            instance.save()

        return instance

    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "asset_tag",
            "category",
            "category_display",
            "serial_number",
            "purchase_date",
            "purchase_cost",
            "supplier",
            "current_value",
            "condition",
            "condition_display",
            "department",
            "department_id",
            "custodian",
            "custodian_id",
            "warranty_expiry",
            "insurance_policy",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "asset_tag", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            from departments.models import Department
            from members.models import Member

            church = getattr(request, "current_church", None) or getattr(
                request.user, "church", None
            )
            if church:
                self.fields["department_id"].queryset = Department.objects.filter(
                    church=church
                )
                self.fields["custodian_id"].queryset = Member.objects.filter(
                    church=church
                )

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        # Generate asset tag
        from datetime import datetime

        year = datetime.now().year
        category_code = validated_data.get("category", "OTH")[:3].upper()

        last_asset = (
            Asset.objects.filter(
                church=church, asset_tag__startswith=f"AST-{category_code}-{year}-"
            )
            .order_by("-created_at")
            .first()
        )

        if last_asset:
            last_num = int(last_asset.asset_tag.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        asset_tag = f"AST-{category_code}-{year}-{new_num:04d}"

        return Asset.objects.create(
            church=church, asset_tag=asset_tag, **validated_data
        )


# ==========================================
# STATISTICS SERIALIZERS
# ==========================================


class TreasuryStatisticsSerializer(serializers.Serializer):
    """Treasury statistics"""

    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    income_by_category = serializers.ListField()
    expenses_by_category = serializers.ListField()
    expenses_by_department = serializers.ListField()
    pending_expense_requests = serializers.IntegerField()
    total_assets_value = serializers.DecimalField(max_digits=15, decimal_places=2)
