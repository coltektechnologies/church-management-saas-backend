from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Church, User
from accounts.models.base_models import AuditLog
from members.models import Member
from members.serializers import MemberSerializer

from .models import (
    Department,
    DepartmentActivity,
    DepartmentHead,
    MemberDepartment,
    Program,
    ProgramBudgetItem,
)

# ==========================================
# DEPARTMENT SERIALIZERS
# ==========================================


class DepartmentListSerializer(serializers.ModelSerializer):
    """Lightweight department list"""

    member_count = serializers.SerializerMethodField()
    head_name = serializers.SerializerMethodField()
    elder_in_charge_name = serializers.SerializerMethodField()
    upcoming_programs_count = serializers.SerializerMethodField()
    past_programs_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "icon",
            "color",
            "is_active",
            "member_count",
            "head_name",
            "elder_in_charge_name",
            "upcoming_programs_count",
            "past_programs_count",
        ]

    def get_member_count(self, obj):
        return MemberDepartment.objects.filter(department=obj).count()

    def get_upcoming_programs_count(self, obj):
        return (
            Program.objects.filter(
                department=obj,
                start_date__gt=timezone.now().date(),
            )
            .exclude(status="CANCELLED")
            .count()
        )

    def get_past_programs_count(self, obj):
        return (
            Program.objects.filter(
                department=obj,
                end_date__lt=timezone.now().date(),
            )
            .exclude(status="CANCELLED")
            .count()
        )

    def get_head_name(self, obj):
        head = DepartmentHead.objects.filter(
            department=obj, head_role=DepartmentHead.HeadRole.HEAD
        ).first()
        if head:
            return head.member.full_name
        return None

    def get_elder_in_charge_name(self, obj):
        if obj.elder_in_charge:
            return obj.elder_in_charge.full_name
        return None


class DepartmentSerializer(serializers.ModelSerializer):
    """Full department details"""

    member_count = serializers.SerializerMethodField()
    heads = serializers.SerializerMethodField()
    elder_in_charge = serializers.PrimaryKeyRelatedField(
        queryset=Member.objects.all(), required=False, allow_null=True
    )
    elder_in_charge_name = serializers.SerializerMethodField()
    current_budget = serializers.SerializerMethodField()
    upcoming_programs_count = serializers.SerializerMethodField()
    past_programs_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "description",
            "icon",
            "color",
            "is_active",
            "member_count",
            "heads",
            "elder_in_charge",
            "elder_in_charge_name",
            "current_budget",
            "upcoming_programs_count",
            "past_programs_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "elder_in_charge_name"]

    def get_member_count(self, obj):
        return MemberDepartment.objects.filter(department=obj).count()

    def get_heads(self, obj):
        heads = (
            DepartmentHead.objects.filter(department=obj)
            .select_related("member")
            .annotate(
                _role_sort=Case(
                    When(head_role=DepartmentHead.HeadRole.HEAD, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("_role_sort", "id")
        )
        return [
            {
                "id": head.member.id,
                "name": head.member.full_name,
                "assigned_at": head.assigned_at,
                "head_role": head.head_role,
            }
            for head in heads
        ]

    def get_elder_in_charge_name(self, obj):
        if obj.elder_in_charge:
            return obj.elder_in_charge.full_name
        return None

    def get_upcoming_programs_count(self, obj):
        return (
            Program.objects.filter(
                department=obj,
                start_date__gt=timezone.now().date(),
            )
            .exclude(status="CANCELLED")
            .count()
        )

    def get_past_programs_count(self, obj):
        return (
            Program.objects.filter(
                department=obj,
                end_date__lt=timezone.now().date(),
            )
            .exclude(status="CANCELLED")
            .count()
        )

    def get_current_budget(self, obj):
        program = (
            Program.objects.filter(
                department=obj, status__in=["APPROVED", "IN_PROGRESS", "COMPLETED"]
            )
            .order_by("-start_date")
            .first()
        )

        if program:
            return {
                "allocated": str(program.total_income or 0),
                "spent": str(program.total_expenses or 0),
                "remaining": str(
                    (program.total_income or 0) - (program.total_expenses or 0)
                ),
                "utilization": (
                    f"{((program.total_expenses or 0) / (program.total_income or 1)) * 100:.2f}%"
                    if program.total_income
                    else "0.00%"
                ),
            }
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            raise serializers.ValidationError("Church context required")

        return Department.objects.create(church=church, **validated_data)


class DepartmentWithHeadCreateSerializer(serializers.ModelSerializer):
    """Create department with optional head assignment"""

    head_member_id = serializers.UUIDField(required=False, write_only=True)

    class Meta:
        model = Department
        fields = [
            "name",
            "code",
            "description",
            "icon",
            "color",
            "is_active",
            "head_member_id",
        ]

    def validate_code(self, value):
        """Ensure code is uppercase and unique per church"""
        value = value.upper()
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        # Check uniqueness within the church
        if church and Department.objects.filter(church=church, code=value).exists():
            raise serializers.ValidationError(
                "A department with this code already exists in your church."
            )
        return value

    def validate_head_member_id(self, value):
        """Validate that the member exists and belongs to the same church"""
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        try:
            member = Member.objects.get(id=value, church=church)
            # Return the member object directly so create() can use it without a second DB hit
            return member
        except Member.DoesNotExist:
            raise serializers.ValidationError(
                "Member not found or doesn't belong to this church."
            )

    @transaction.atomic
    def create(self, validated_data):
        head_member = validated_data.pop("head_member_id", None)
        request = self.context.get("request")

        # Resolve church from request — this was missing and caused the NULL constraint error
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            raise serializers.ValidationError(
                "Church context is required to create a department."
            )

        department = Department.objects.create(church=church, **validated_data)

        # Assign head if provided.
        # Use get_or_create to prevent the duplicate key IntegrityError if the
        # same member+department combo already exists (e.g. retried requests).
        if head_member:
            DepartmentHead.objects.filter(
                department=department, head_role=DepartmentHead.HeadRole.HEAD
            ).exclude(member=head_member).delete()

            DepartmentHead.objects.get_or_create(
                department=department,
                head_role=DepartmentHead.HeadRole.HEAD,
                member=head_member,
                defaults={"church": church},
            )

        return department


class DepartmentCreateSerializer(serializers.ModelSerializer):
    """Create department with validation"""

    class Meta:
        model = Department
        fields = ["name", "code", "description", "icon", "color", "is_active"]
        read_only_fields = ["church"]

    def validate_code(self, value):
        """Ensure code is uppercase and unique per church"""
        value = value.upper()
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        if Department.objects.filter(church=church, code=value).exists():
            raise serializers.ValidationError(
                "Department with this code already exists in your church"
            )
        return value


# ==========================================
# MEMBER DEPARTMENT SERIALIZERS
# ==========================================


class MemberDepartmentSerializer(serializers.ModelSerializer):
    """Member-Department assignment"""

    member_name = serializers.CharField(source="member.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = MemberDepartment
        fields = [
            "id",
            "member",
            "member_name",
            "department",
            "department_name",
            "role_in_department",
            "assigned_at",
        ]
        read_only_fields = ["id", "assigned_at"]

    def validate(self, attrs):
        """Ensure member and department belong to same church"""
        member = attrs.get("member")
        department = attrs.get("department")
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        if member.church != church:
            raise serializers.ValidationError("Member does not belong to your church")

        if department.church != church:
            raise serializers.ValidationError(
                "Department does not belong to your church"
            )

        if MemberDepartment.objects.filter(
            member=member, department=department
        ).exists():
            raise serializers.ValidationError(
                {
                    "detail": "This member is already assigned to this department.",
                    "code": "member_already_assigned",
                    "member_id": str(member.id),
                    "department_id": str(department.id),
                }
            )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        return MemberDepartment.objects.create(church=church, **validated_data)


class AssignMemberToDepartmentSerializer(serializers.Serializer):
    """Assign member to department"""

    member_id = serializers.UUIDField()
    role_in_department = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )

    def validate_member_id(self, value):
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        try:
            Member.objects.get(id=value, church=church)
        except Member.DoesNotExist:
            raise serializers.ValidationError("Member not found in your church")

        return value


# ==========================================
# DEPARTMENT HEAD SERIALIZERS
# ==========================================


class DepartmentHeadSerializer(serializers.ModelSerializer):
    """Department head assignment"""

    member_name = serializers.CharField(source="member.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = DepartmentHead
        fields = [
            "id",
            "member",
            "member_name",
            "department",
            "department_name",
            "head_role",
            "assigned_at",
        ]
        read_only_fields = ["id", "assigned_at"]

    def validate(self, attrs):
        """Validate head assignment"""
        member = attrs.get("member")
        department = attrs.get("department")
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        if member.church != church or department.church != church:
            raise serializers.ValidationError(
                "Member and department must belong to your church"
            )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        return DepartmentHead.objects.create(church=church, **validated_data)


class AssignDepartmentHeadSerializer(serializers.Serializer):
    """Assign department head"""

    member_id = serializers.UUIDField()

    def validate_member_id(self, value):
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        try:
            Member.objects.get(id=value, church=church)
        except Member.DoesNotExist:
            raise serializers.ValidationError("Member not found in your church")

        return value


class AssignAssistantHeadSerializer(serializers.Serializer):
    """Assign or clear assistant department head (member_id null removes)."""

    member_id = serializers.UUIDField(required=True, allow_null=True)

    def validate_member_id(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        church = getattr(request, "current_church", None) or request.user.church

        try:
            Member.objects.get(id=value, church=church)
        except Member.DoesNotExist:
            raise serializers.ValidationError("Member not found in your church")

        return value


# ==========================================
# PROGRAM BUDGET ITEM SERIALIZERS
# ==========================================


class ProgramBudgetItemSerializer(serializers.ModelSerializer):
    """Program Budget Item Serializer"""

    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = ProgramBudgetItem
        fields = [
            "id",
            "item_type",
            "income_source",
            "description",
            "amount",
            "amount_display",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "amount_display"]

    def get_amount_display(self, obj):
        return f"₦{obj.amount:,.2f}" if obj.amount else "₦0.00"

    def validate(self, attrs):
        item_type = attrs.get("item_type")
        income_source = attrs.get("income_source")

        if item_type == "INCOME" and not income_source:
            raise serializers.ValidationError(
                {"income_source": "Income source is required for income items."}
            )

        if item_type == "EXPENSE" and income_source:
            attrs["income_source"] = None

        return attrs


class ProgramBudgetItemCreateSerializer(ProgramBudgetItemSerializer):
    """Serializer for creating budget items with program context"""

    class Meta(ProgramBudgetItemSerializer.Meta):
        fields = ProgramBudgetItemSerializer.Meta.fields

    def create(self, validated_data):
        return ProgramBudgetItem.objects.create(**validated_data)


# ==========================================
# PROGRAM SERIALIZERS
# ==========================================


class ProgramListSerializer(serializers.ModelSerializer):
    """Lightweight program list"""

    department_name = serializers.CharField(source="department.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    budget_summary = serializers.SerializerMethodField()
    requires_approval = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            "id",
            "title",
            "department",
            "department_name",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "location",
            "total_income",
            "total_expenses",
            "net_budget",
            "budget_summary",
            "submission_type",
            "requires_approval",
            "submitted_at",
            "approved_at",
        ]

    def get_budget_summary(self, obj):
        return f"Income: {obj.total_income}, Expenses: {obj.total_expenses}, Net: {obj.net_budget}"

    def get_requires_approval(self, obj):
        needs = []
        if obj.submitted_to_secretariat and not obj.secretariat_approved:
            needs.append("SECRETARIAT")
        if obj.submitted_to_treasury and not obj.treasury_approved:
            needs.append("TREASURY")
        return needs


class ProgramDetailSerializer(serializers.ModelSerializer):
    """Detailed program view with budget items"""

    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    budget_items = ProgramBudgetItemSerializer(many=True, read_only=True)

    can_edit = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            "id",
            "title",
            "description",
            "department",
            "department_name",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "location",
            "total_income",
            "total_expenses",
            "net_budget",
            "budget_items",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "submitted_at",
            "approved_at",
            "can_edit",
            "can_submit",
            "can_approve",
            "submission_type",
            "submitted_to_secretariat",
            "submitted_to_treasury",
            "secretariat_approved",
            "treasury_approved",
            "approval_status",
            "secretariat_notes",
            "treasury_notes",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "total_income",
            "total_expenses",
            "net_budget",
            "submitted_at",
            "approved_at",
            "submitted_to_secretariat",
            "submitted_to_treasury",
            "secretariat_approved",
            "treasury_approved",
            "secretariat_notes",
            "treasury_notes",
            "secretariat_approved_at",
            "treasury_approved_at",
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None

    def get_approval_status(self, obj):
        return {
            "needs_secretariat": obj.submitted_to_secretariat
            and not obj.secretariat_approved,
            "needs_treasury": obj.submitted_to_treasury and not obj.treasury_approved,
            "secretariat_approved": obj.secretariat_approved,
            "treasury_approved": obj.treasury_approved,
            "secretariat_approved_at": obj.secretariat_approved_at,
            "treasury_approved_at": obj.treasury_approved_at,
            "is_fully_approved": obj.is_fully_approved,
        }

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        if obj.status not in ["DRAFT", "REJECTED"]:
            return False
        return obj.created_by == request.user or request.user.is_staff

    def get_can_submit(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        if obj.status not in ["DRAFT", "REJECTED"]:
            return False
        if obj.created_by == request.user or request.user.is_staff:
            return True
        return DepartmentHead.objects.filter(
            department=obj.department, member__user=request.user
        ).exists()

    def get_can_approve(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if obj.status != "SUBMITTED":
            return False
        can_approve_secretariat = False
        can_approve_treasury = False
        if obj.submitted_to_secretariat and not obj.secretariat_approved:
            can_approve_secretariat = request.user.has_perm(
                "departments.approve_secretariat"
            )
        if obj.submitted_to_treasury and not obj.treasury_approved:
            can_approve_treasury = request.user.has_perm("departments.approve_treasury")
        return can_approve_secretariat or can_approve_treasury

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["created_by"] = request.user
        return Program.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if instance.status not in ["DRAFT", "REJECTED"]:
            raise serializers.ValidationError(
                {
                    "status": "Cannot update a program that is not in draft or rejected state."
                }
            )
        return super().update(instance, validated_data)


class ProgramSubmitSerializer(serializers.ModelSerializer):
    """Serializer for submitting a program for approval"""

    submit_to_secretariat = serializers.BooleanField(default=True)
    submit_to_treasury = serializers.BooleanField(default=True)

    class Meta:
        model = Program
        fields = ["submit_to_secretariat", "submit_to_treasury"]

    def validate(self, attrs):
        program = self.instance

        if program.status not in ["DRAFT", "REJECTED"]:
            raise serializers.ValidationError(
                "Only programs in DRAFT or REJECTED state can be submitted"
            )
        if not attrs.get("submit_to_secretariat") and not attrs.get(
            "submit_to_treasury"
        ):
            raise serializers.ValidationError(
                "You must select at least one department to submit to"
            )
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")
        if not (
            program.created_by == request.user
            or request.user.is_staff
            or program.department.heads.filter(member__user=request.user).exists()
        ):
            raise serializers.ValidationError(
                "You don't have permission to submit this program"
            )
        return attrs

    def update(self, instance, validated_data):
        instance.submit_for_approval(
            submit_to_secretariat=validated_data.get("submit_to_secretariat", True),
            submit_to_treasury=validated_data.get("submit_to_treasury", True),
        )
        request = self.context.get("request")
        if request and request.user:
            AuditLog.log(
                request.user,
                "STATUS_CHANGE",
                instance,
                request=request,
                description=f"Program '{instance.title}' submitted for approval",
            )
        return instance


class ProgramApproveRejectSerializer(serializers.ModelSerializer):
    """Serializer for approving or rejecting a program"""

    department = serializers.ChoiceField(
        choices=["SECRETARIAT", "TREASURY"],
        help_text="Which department is approving/rejecting?",
    )
    action = serializers.ChoiceField(
        choices=[("APPROVE", "Approve"), ("REJECT", "Reject")]
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Program
        fields = ["department", "action", "notes"]

    def validate(self, attrs):
        program = self.instance
        request = self.context.get("request")
        department = attrs.get("department")
        action = attrs.get("action")

        if program.status != "SUBMITTED":
            raise serializers.ValidationError(
                "Only submitted programs can be approved or rejected"
            )
        if department == "SECRETARIAT" and not program.submitted_to_secretariat:
            raise serializers.ValidationError(
                "This program is not submitted for secretariat approval"
            )
        if department == "TREASURY" and not program.submitted_to_treasury:
            raise serializers.ValidationError(
                "This program is not submitted for treasury approval"
            )
        if department == "SECRETARIAT" and program.secretariat_approved:
            raise serializers.ValidationError("Already approved by secretariat")
        if department == "TREASURY" and program.treasury_approved:
            raise serializers.ValidationError("Already approved by treasury")
        if department == "SECRETARIAT" and not request.user.has_perm(
            "departments.approve_secretariat"
        ):
            raise serializers.ValidationError(
                "You don't have permission to approve for secretariat"
            )
        if department == "TREASURY" and not request.user.has_perm(
            "departments.approve_treasury"
        ):
            raise serializers.ValidationError(
                "You don't have permission to approve for treasury"
            )
        if action == "REJECT" and not attrs.get("notes"):
            raise serializers.ValidationError("Please provide a reason for rejection")
        return attrs

    def update(self, instance, validated_data):
        department = validated_data.get("department")
        action = validated_data.get("action")
        notes = validated_data.get("notes", "")
        user = self.context.get("request").user

        request = self.context.get("request")
        if action == "APPROVE":
            instance.approve(user, department, notes)
            if request and request.user:
                AuditLog.log(
                    request.user,
                    "STATUS_CHANGE",
                    instance,
                    request=request,
                    description=f"Program '{instance.title}' approved by {department}",
                )
        else:
            instance.reject(user, f"Rejected by {department}: {notes}")
            if request and request.user:
                AuditLog.log(
                    request.user,
                    "STATUS_CHANGE",
                    instance,
                    request=request,
                    description=f"Program '{instance.title}' rejected by {department}",
                )
        return instance


# ==========================================
# STATISTICS SERIALIZERS
# ==========================================


class DepartmentStatisticsSerializer(serializers.Serializer):
    """Department statistics"""

    total_departments = serializers.IntegerField(default=0)
    active_departments = serializers.IntegerField(default=0)
    total_members_in_departments = serializers.IntegerField(default=0)
    departments_without_heads = serializers.IntegerField(default=0)
    total_programs = serializers.IntegerField(default=0)
    upcoming_programs = serializers.IntegerField(default=0)
    # Per-department stats fields (used by department_statistics action)
    total_members = serializers.IntegerField(default=0, required=False)
    current_program = serializers.DictField(required=False, allow_null=True)


# ==========================================
# DEPARTMENT ACTIVITY (EVENT) SERIALIZERS
# ==========================================


class DepartmentActivitySerializer(serializers.ModelSerializer):
    """Department activity/event with optional time and is_upcoming flag."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    is_upcoming = serializers.SerializerMethodField()

    class Meta:
        model = DepartmentActivity
        fields = [
            "id",
            "department",
            "department_name",
            "church",
            "title",
            "description",
            "status",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "location",
            "expected_attendance",
            "actual_attendance",
            "budget_allocated",
            "budget_spent",
            "notes",
            "is_upcoming",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "church", "created_by", "created_at", "updated_at"]

    def get_is_upcoming(self, obj):
        now = timezone.now()
        if obj.end_date < now.date():
            return False
        if obj.start_date > now.date():
            return True
        if obj.end_time and now.time() > obj.end_time:
            return False
        return True

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("Request context required")
        validated_data["church"] = request.user.church
        validated_data["created_by"] = request.user
        return super().create(validated_data)
