"""
5-Step Program Submission Views
Endpoints: step1 (create) -> step2 -> step3 -> step4 -> step5 (review) -> submit
"""

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from members.models import MemberLocation

from ..models import (
    Department,
    DepartmentHead,
    Program,
    ProgramBudgetItem,
    ProgramDocument,
)
from ..program_steps import (
    ProgramDocumentSerializer,
    ProgramReviewSerializer,
    ProgramStep1Serializer,
    ProgramStep2Serializer,
    ProgramStep3Serializer,
)


def _get_department_head_info(head):
    """Get department head name, email, phone from DepartmentHead."""
    if not head:
        return None, None, None
    member = head.member
    name = (
        member.get_full_name()
        if hasattr(member, "get_full_name")
        else f"{member.first_name} {member.last_name}"
    )
    email, phone = None, None
    try:
        loc = member.location
        email = loc.email or None
        phone = loc.phone_primary or None
    except (AttributeError, MemberLocation.DoesNotExist):
        pass
    return name, email, phone


class ProgramStepViewSetMixin:
    """Mixin adding 5-step actions to ProgramViewSet."""

    @action(detail=False, methods=["post"], url_path="step1")
    def step1_create(self, request):
        """
        Step 1: Create program with basic info.
        Department dropdown, fiscal year, budget title, overview.
        Auto-populates department head; flags if submitter is not the head.
        """
        serializer = ProgramStep1Serializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        department = data["_department"]
        head = data["_head"]
        is_head = data["_is_department_head"]

        head_name, head_email, head_phone = _get_department_head_info(head)
        # Override with user input if provided
        head_email = data.get("department_head_email") or head_email
        head_phone = data.get("department_head_phone") or head_phone

        with transaction.atomic():
            program = Program.objects.create(
                church=request.user.church,
                department=department,
                title=data["budget_title"],
                fiscal_year=data["fiscal_year"],
                budget_title=data["budget_title"],
                budget_overview=data.get("budget_overview", ""),
                submitted_by_department_head=is_head,
                department_head_name=head_name,
                department_head_email=head_email,
                department_head_phone=head_phone,
                status="DRAFT",
                created_by=request.user,
                # Placeholder dates for budget-only flow
                start_date=timezone.now().date(),
                end_date=timezone.now().date(),
            )

        return Response(
            {
                "program_id": str(program.id),
                "message": "Step 1 completed. Proceed to Step 2.",
                "submitted_by_department_head": is_head,
                "department_name": department.name,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["put", "patch"], url_path="step2")
    def step2_budget_items(self, request, pk=None, department_pk=None):
        """
        Step 2: Add budget items by category.
        Categories: Personnel & Staff, Program & Activity, Equipment & Supplies, Custom.
        """
        program = self.get_object()
        if program.status not in ("DRAFT", "REJECTED"):
            return Response(
                {"detail": "Can only edit budget items for draft or rejected programs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProgramStep2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            program.budget_items.filter(item_type="EXPENSE").delete()
            for item_data in serializer.validated_data["budget_items"]:
                ProgramBudgetItem.objects.create(
                    program=program,
                    item_type="EXPENSE",
                    category=item_data["category"],
                    description=item_data["description"],
                    quantity=item_data.get("quantity", 1),
                    amount=item_data["amount"],
                )
            program.save()  # Recalculate totals

        from django.db.models import Sum

        total = (
            program.budget_items.filter(item_type="EXPENSE").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        return Response(
            {
                "program_id": str(program.id),
                "message": "Step 2 completed. Proceed to Step 3.",
                "total_amount": float(total),
            }
        )

    @action(detail=True, methods=["put", "patch"], url_path="step3")
    def step3_justification(self, request, pk=None, department_pk=None):
        """Step 3: Add justification fields."""
        program = self.get_object()
        if program.status not in ("DRAFT", "REJECTED"):
            return Response(
                {
                    "detail": "Can only edit justification for draft or rejected programs"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProgramStep3Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        for field, value in serializer.validated_data.items():
            setattr(program, field, value)
        program.save()

        return Response(
            {
                "program_id": str(program.id),
                "message": "Step 3 completed. Proceed to Step 4.",
            }
        )

    @action(detail=True, methods=["post"], url_path="step4/documents")
    def step4_upload_document(self, request, pk=None, department_pk=None):
        """Step 4: Upload supporting document (max 10MB)."""
        program = self.get_object()
        if program.status not in ("DRAFT", "REJECTED"):
            return Response(
                {"detail": "Can only upload documents for draft or rejected programs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProgramDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        doc = serializer.save(program=program)
        return Response(
            ProgramDocumentSerializer(doc).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"], url_path="step5/review")
    def step5_review(self, request, pk=None, department_pk=None):
        """Step 5: Get budget submission summary for review."""
        program = self.get_object()
        serializer = ProgramReviewSerializer(program)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="step5/submit")
    def step5_submit(self, request, pk=None, department_pk=None):
        """Final submit: Send for Elder → Secretariat → Treasury approval."""
        program = self.get_object()
        if program.status not in ("DRAFT", "REJECTED"):
            return Response(
                {
                    "detail": "Program has already been submitted or is not in draft/rejected state"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate minimum required data
        if not program.budget_items.exists():
            return Response(
                {"detail": "Add at least one budget item before submitting"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        program.status = "SUBMITTED"
        program.submitted_at = timezone.now()
        program.submitted_to_secretariat = True
        program.submitted_to_treasury = True
        program.save()

        # Notify approval chain (Elder, Secretariat, Treasury) - in-app + SMS
        from ..approval_notifications import notify_approval_chain

        submitter_name = (
            program.created_by.get_full_name() if program.created_by else "Unknown"
        )
        notify_approval_chain(program, submitter_name=submitter_name)

        return Response(
            {
                "program_id": str(program.id),
                "message": "Budget submitted successfully. Awaiting approval: Department Elder → Secretariat → Treasury.",
                "status": program.status,
            }
        )


class DepartmentListForProgramAPIView(APIView):
    """
    GET /api/departments/for-program/
    Returns departments with head info for Step 1 dropdown.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        church = getattr(request.user, "church", None)
        if not church:
            return Response(
                {"detail": "Church required"}, status=status.HTTP_403_FORBIDDEN
            )

        departments = Department.objects.filter(church=church, is_active=True)
        user_id = str(request.user.id)

        result = []
        for dept in departments:
            primary = (
                DepartmentHead.objects.filter(
                    department=dept,
                    member__church=church,
                    head_role=DepartmentHead.HeadRole.HEAD,
                )
                .select_related("member")
                .first()
            )

            head_name, head_email, head_phone = _get_department_head_info(primary)
            is_current_user_head = DepartmentHead.objects.filter(
                department=dept,
                member__church=church,
                member__system_user_id=request.user.id,
            ).exists()

            elder_name = None
            if dept.elder_in_charge:
                elder_name = dept.elder_in_charge.full_name
            result.append(
                {
                    "id": str(dept.id),
                    "name": dept.name,
                    "code": dept.code,
                    "head_name": head_name,
                    "head_email": head_email,
                    "head_phone": head_phone,
                    "elder_in_charge_name": elder_name,
                    "is_current_user_head": is_current_user_head,
                }
            )

        return Response(result)
