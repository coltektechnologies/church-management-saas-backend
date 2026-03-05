from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from departments.serializers import (DepartmentListSerializer,
                                     ProgramListSerializer)
from members.serializers import MemberListSerializer

from .models import (Asset, ExpenseCategory, ExpenseRequest,
                     ExpenseTransaction, IncomeAllocation, IncomeCategory,
                     IncomeTransaction)

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
    department_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    recorded_by_name = serializers.SerializerMethodField()
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    def create(self, validated_data):
        from departments.models import Department

        # Extract and remove department_id from validated_data
        department_id = validated_data.pop("department_id", None)

        # Create the instance
        instance = super().create(validated_data)

        # Set department if provided
        if department_id:
            try:
                department = Department.objects.get(
                    id=department_id, church=instance.church
                )
                instance.department = department
                instance.save()
            except Department.DoesNotExist:
                pass

        return instance

    def update(self, instance, validated_data):
        from departments.models import Department

        # Extract and remove department_id from validated_data
        department_id = validated_data.pop("department_id", None)

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
            instance.save()

        return instance

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
            from departments.models import Department

            church = getattr(request, "current_church", None) or getattr(
                request.user, "church", None
            )
            if church:
                self.fields["department_id"].queryset = Department.objects.filter(
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

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

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

        return ExpenseTransaction.objects.create(
            church=church,
            voucher_number=voucher_number,
            recorded_by=request.user,
            **validated_data,
        )


# ==========================================
# EXPENSE REQUEST SERIALIZERS
# ==========================================


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
            "created_at",
        ]

    def get_requested_by_name(self, obj):
        if obj.requested_by:
            return obj.requested_by.get_full_name() or obj.requested_by.username
        return None


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

    def create(self, validated_data):
        from departments.models import Department

        # Extract and remove department_id from validated_data
        department_id = validated_data.pop("department_id", None)

        # Create the instance
        instance = super().create(validated_data)

        # Set department if provided
        if department_id:
            try:
                department = Department.objects.get(
                    id=department_id, church=instance.church
                )
                instance.department = department
                instance.save()
            except Department.DoesNotExist:
                pass

        return instance

    def update(self, instance, validated_data):
        from departments.models import Department

        # Extract and remove department_id from validated_data
        department_id = validated_data.pop("department_id", None)

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
            instance.save()

        return instance

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
            "treasurer": {
                "approved": obj.treasurer_approved_at is not None,
                "approved_by": (
                    obj.treasurer_approved_by.get_full_name()
                    if obj.treasurer_approved_by
                    else None
                ),
                "approved_at": obj.treasurer_approved_at,
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
        }

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
