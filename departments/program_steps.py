"""
5-Step Program/Budget Submission Flow
Created by departmental heads. Approval: Department Elder → Secretariat → Treasury.
"""

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from members.models import Member, MemberLocation

from .models import (Department, DepartmentHead, Program, ProgramBudgetItem,
                     ProgramDocument)

# ============================================
# STEP 1: Basic Information
# ============================================


class ProgramStep1Serializer(serializers.Serializer):
    """Step 1: Department, fiscal year, budget title, overview. Auto-populate head info."""

    department_id = serializers.UUIDField(required=True)
    fiscal_year = serializers.IntegerField(
        min_value=2020, max_value=2100, required=True
    )
    budget_title = serializers.CharField(max_length=300, required=True)
    budget_overview = serializers.CharField(required=True, allow_blank=True)
    # Head contact (optional - auto-populated from department head, user can override)
    department_head_email = serializers.EmailField(required=False, allow_blank=True)
    department_head_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )

    def validate_department_id(self, value):
        request = self.context.get("request")
        church = getattr(request.user, "church", None)
        if not church:
            raise serializers.ValidationError("User must belong to a church")
        if not Department.objects.filter(id=value, church=church).exists():
            raise serializers.ValidationError("Invalid department")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        church = request.user.church
        department_id = attrs["department_id"]
        department = Department.objects.get(id=department_id)

        # Check if user is head of selected department
        head = (
            DepartmentHead.objects.filter(department=department, member__church=church)
            .select_related("member")
            .first()
        )

        is_head = False
        if head:
            member = head.member
            # User is head if they are the system user for this member
            if member.system_user_id and str(member.system_user_id) == str(
                request.user.id
            ):
                is_head = True
            # Staff/platform admin can submit on behalf of any department
            elif getattr(request.user, "is_staff", False):
                is_head = True

        attrs["_department"] = department
        attrs["_is_department_head"] = is_head
        attrs["_head"] = head
        return attrs


# ============================================
# STEP 2: Budget Items
# ============================================


class BudgetItemInputSerializer(serializers.Serializer):
    """Single budget item input"""

    category = serializers.ChoiceField(
        choices=ProgramBudgetItem.BUDGET_CATEGORIES + [("CUSTOM", "Custom")],
        required=True,
    )
    description = serializers.CharField(max_length=300, required=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)
    # For custom category, description acts as the item name


class ProgramStep2Serializer(serializers.Serializer):
    """Step 2: Budget items with categories, subtotals, grand total"""

    budget_items = BudgetItemInputSerializer(many=True, required=True)

    def validate_budget_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one budget item is required")
        return value


# ============================================
# STEP 3: Justification
# ============================================


class ProgramStep3Serializer(serializers.Serializer):
    """Step 3: Justification fields"""

    strategic_objectives = serializers.CharField(required=True, allow_blank=True)
    expected_impact = serializers.CharField(required=True, allow_blank=True)
    ministry_benefits = serializers.CharField(required=True, allow_blank=True)
    previous_year_comparison = serializers.CharField(required=False, allow_blank=True)
    number_of_beneficiaries = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    implementation_timeline = serializers.CharField(required=False, allow_blank=True)


# ============================================
# STEP 4: Documents
# ============================================


class ProgramDocumentSerializer(serializers.ModelSerializer):
    """Program document upload (max 10MB)"""

    class Meta:
        model = ProgramDocument
        fields = ["id", "file", "original_filename", "file_size", "uploaded_at"]
        read_only_fields = ["id", "original_filename", "file_size", "uploaded_at"]

    def validate_file(self, value):
        max_size = ProgramDocument.MAX_FILE_SIZE  # 10MB
        if value and value.size > max_size:
            raise serializers.ValidationError(
                f"File size must not exceed 10MB. Current: {value.size / (1024*1024):.2f}MB"
            )
        return value

    def create(self, validated_data):
        validated_data["original_filename"] = (
            validated_data.get("file").name if validated_data.get("file") else ""
        )
        return super().create(validated_data)


# ============================================
# STEP 5: Review & Submit
# ============================================


class ProgramReviewSerializer(serializers.ModelSerializer):
    """Step 5: Budget submission summary for review"""

    department_name = serializers.CharField(source="department.name", read_only=True)
    total_amount = serializers.DecimalField(
        source="total_expenses", max_digits=15, decimal_places=2, read_only=True
    )
    budget_breakdown = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            "id",
            "department",
            "department_name",
            "fiscal_year",
            "budget_title",
            "total_amount",
            "budget_breakdown",
            "grand_total",
            "department_head_name",
            "department_head_email",
            "department_head_phone",
            "submitted_by_department_head",
        ]

    def get_budget_breakdown(self, obj):
        from django.db.models import Sum

        items = obj.budget_items.filter(item_type="EXPENSE")
        by_category = {}
        for item in items:
            cat = item.category or "CUSTOM"
            cat_display = dict(ProgramBudgetItem.BUDGET_CATEGORIES).get(cat, "Custom")
            if cat_display not in by_category:
                by_category[cat_display] = {"items": [], "subtotal": 0}
            amt = float(item.amount)
            by_category[cat_display]["items"].append(
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "amount": amt,
                }
            )
            by_category[cat_display]["subtotal"] += amt
        return [
            {"category": k, "items": v["items"], "subtotal": v["subtotal"]}
            for k, v in by_category.items()
        ]

    def get_grand_total(self, obj):
        return float(obj.total_expenses or 0)
