from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (NotFound, PermissionDenied,
                                       ValidationError)
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from members.models import Member
from notifications.models import Notification
from notifications.services.email_service import EmailService

from ..models import Program, ProgramBudgetItem
from ..serializers import (ProgramApproveRejectSerializer,
                           ProgramBudgetItemCreateSerializer,
                           ProgramBudgetItemSerializer,
                           ProgramDetailSerializer, ProgramListSerializer,
                           ProgramSubmitSerializer)
from ..views.program_step_views import ProgramStepViewSetMixin


class IsProgramCreatorOrReadOnly(BasePermission):
    """
    Custom permission to only allow creators of a program to edit it,
    and only if it's in draft or rejected state.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        # Only allow updates if program is in draft or rejected state
        if obj.status not in ["DRAFT", "REJECTED"]:
            return False

        # Only the creator or staff can edit
        return obj.created_by == request.user or request.user.is_staff


class HasApproveSecretariatPermission(BasePermission):
    """Custom permission to only allow users with approve_secretariat permission"""

    def has_permission(self, request, view):
        return request.user.has_perm("departments.approve_secretariat")


class HasApproveTreasuryPermission(BasePermission):
    """Custom permission to only allow users with approve_treasury permission"""

    def has_permission(self, request, view):
        return request.user.has_perm("departments.approve_treasury")


class ProgramViewSet(ProgramStepViewSetMixin, viewsets.ModelViewSet):
    """
    Program CRUD operations

    list: GET /api/programs/
    create: POST /api/programs/
    retrieve: GET /api/programs/{id}/
    update: PUT /api/programs/{id}/
    partial_update: PATCH /api/programs/{id}/
    destroy: DELETE /api/programs/{id}/
    """

    permission_classes = [IsAuthenticated, IsProgramCreatorOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "department"]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["start_date", "end_date", "created_at"]
    ordering = ["-start_date"]

    def get_queryset(self):
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return Program.objects.none()

        user = self.request.user
        queryset = Program.objects.all()

        # Filter by department from nested URL or query param
        department_id = self.kwargs.get(
            "department_pk"
        ) or self.request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        # Filter by status if specified
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status.upper())

        # Platform admins can see all programs or filter by church_id
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            church_id = self.request.query_params.get("church_id")
            if church_id:
                queryset = queryset.filter(church_id=church_id)
            return queryset

        # Regular users can only see programs from their church
        if hasattr(user, "church") and user.church:
            return queryset.filter(church=user.church)

        return Program.objects.none()

    def get_serializer_class(self):
        if self.action == "list":
            return ProgramListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return ProgramDetailSerializer
        return ProgramDetailSerializer

    def get_serializer(self, *args, **kwargs):
        """Inject department from URL when using nested route (create, update, partial_update)."""
        if self.action in ("create", "update", "partial_update") and self.kwargs.get(
            "department_pk"
        ):
            data = kwargs.get("data", self.request.data)
            if data is not None and "department" not in data:
                data = dict(data)
                data["department"] = self.kwargs["department_pk"]
                kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        # Set the church and created_by fields automatically
        serializer.save(church=self.request.user.church, created_by=self.request.user)

    @swagger_auto_schema(
        operation_description="Submit a program for approval",
        request_body=ProgramSubmitSerializer,
        responses={
            200: ProgramDetailSerializer(),
            400: "Invalid program state or missing permissions",
        },
        tags=["Programs"],
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit_program(self, request, pk=None, department_pk=None):
        """Submit a program for approval to selected departments"""
        program = self.get_object()

        # Handle case where request.user might be email string instead of User instance
        User = get_user_model()
        user = request.user
        if not isinstance(user, User):
            try:
                user = User.objects.get(email=str(user))
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED
                )

        # Get the member for the user (Member inherits from User, so get the Member instance)
        try:
            member = Member.objects.get(pk=user.pk)
        except Member.DoesNotExist:
            member = None

        # Check if user is the creator, department head, or admin
        is_creator = program.created_by == user
        is_department_head = program.department.heads.filter(member=member).exists()
        is_admin = user.is_staff

        if not (is_creator or is_department_head or is_admin):
            return Response(
                {"detail": "You don't have permission to submit this program"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ProgramSubmitSerializer(
            program, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        program = serializer.save()

        # Notify approval chain (Elder, Secretariat, Treasury) - in-app + SMS
        from ..approval_notifications import notify_approval_chain

        submitter_name = (
            program.created_by.get_full_name() if program.created_by else "Unknown"
        )
        notify_approval_chain(program, submitter_name=submitter_name)

        return Response(
            ProgramDetailSerializer(program, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="Approve or reject a program (Secretariat)",
        request_body=ProgramApproveRejectSerializer,
        responses={
            200: ProgramDetailSerializer(),
            400: "Invalid program state or missing permissions",
        },
        tags=["Programs"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="approve-secretariat",
        permission_classes=[IsAuthenticated, HasApproveSecretariatPermission],
    )
    def approve_secretariat(self, request, pk=None, department_pk=None):
        """Approve or reject a program (Secretariat)"""
        program = self.get_object()
        serializer = ProgramApproveRejectSerializer(
            program,
            data={
                **request.data,
                "department": "SECRETARIAT",
                "action": request.data.get("action", "APPROVE").upper(),
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        program = serializer.save()

        # TODO: Send notification to program creator and treasury if needed

        return Response(
            ProgramDetailSerializer(program, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="Approve or reject a program (Treasury)",
        request_body=ProgramApproveRejectSerializer,
        responses={
            200: ProgramDetailSerializer(),
            400: "Invalid program state or missing permissions",
        },
        tags=["Programs"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="approve-treasury",
        permission_classes=[IsAuthenticated, HasApproveTreasuryPermission],
    )
    def approve_treasury(self, request, pk=None, department_pk=None):
        """Approve or reject a program (Treasury)"""
        program = self.get_object()
        serializer = ProgramApproveRejectSerializer(
            program,
            data={
                **request.data,
                "department": "TREASURY",
                "action": request.data.get("action", "APPROVE").upper(),
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        program = serializer.save()

        # TODO: Send notification to program creator and secretariat if needed

        return Response(
            ProgramDetailSerializer(program, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="review")
    def review_program(self, request, pk=None, department_pk=None):
        """Review a program (Approve or Reject). Flow: Elder → Secretariat → Treasury."""
        program = self.get_object()
        department = request.data.get("department", "").upper()
        action = request.data.get("action", "APPROVE").upper()
        notes = request.data.get("notes", "")

        user = request.user

        # Permission checks
        if department == "ELDER":
            # Must be: staff, OR department's elder_in_charge, OR in Elder group
            is_dept_elder = False
            if (
                program.department.elder_in_charge_id
                and program.department.elder_in_charge.system_user_id
            ):
                is_dept_elder = str(
                    program.department.elder_in_charge.system_user_id
                ) == str(user.id)
            is_elder_group = user.groups.filter(name__icontains="Elder").exists()
            if not (user.is_staff or is_dept_elder or is_elder_group):
                return Response(
                    {
                        "detail": "You don't have permission to review as Department Elder. "
                        "You must be the elder in charge of this department, in the Elder group, or staff."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if program.status != "SUBMITTED":
                return Response(
                    {"detail": "Program is not awaiting Elder approval"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif department == "SECRETARIAT":
            if not (user.is_staff or user.groups.filter(name="Secretariat").exists()):
                return Response(
                    {"detail": "You don't have permission to review for Secretariat"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if program.status != "ELDER_APPROVED":
                return Response(
                    {"detail": "Program must be approved by Elder first"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif department == "TREASURY":
            if not (user.is_staff or user.groups.filter(name="Treasury").exists()):
                return Response(
                    {"detail": "You don't have permission to review for Treasury"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if program.status != "SECRETARIAT_APPROVED":
                return Response(
                    {"detail": "Program must be approved by Secretariat first"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"detail": "Invalid department. Use ELDER, SECRETARIAT, or TREASURY."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action not in ["APPROVE", "REJECT"]:
            return Response(
                {"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Reject (any approver can reject)
        if action == "REJECT":
            program.status = "REJECTED"
            program.rejected_at = timezone.now()
            program.rejected_by = user
            program.rejection_reason = notes
            if department == "ELDER":
                program.elder_rejected_at = timezone.now()
                program.elder_rejected_by = user
        else:
            # Approve
            if department == "ELDER":
                program.elder_approved = True
                program.elder_approved_at = timezone.now()
                program.elder_notes = notes
                program.status = "ELDER_APPROVED"
            elif department == "SECRETARIAT":
                program.secretariat_approved = True
                program.secretariat_approved_at = timezone.now()
                program.secretariat_notes = notes
                program.status = "SECRETARIAT_APPROVED"
            elif department == "TREASURY":
                program.treasury_approved = True
                program.treasury_approved_at = timezone.now()
                program.treasury_notes = notes
                program.status = "APPROVED"
                program.approved_at = timezone.now()

        program.save()

        # Send in-app notification to program creator
        if program.created_by:
            Notification.objects.create(
                church=program.church,
                user=program.created_by,
                title=f"Program {action.lower()}d",
                message=f"Your program '{program.title}' has been {action.lower()}d by the {department.lower()} department.{f' Notes: {notes}' if notes else ''}",
                priority="MEDIUM",
                category="PROGRAM",
                link=f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/admin/departments/program/{program.id}/change/",
            )

        return Response(
            ProgramDetailSerializer(program, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ProgramBudgetItemViewSet(viewsets.ModelViewSet):
    """
    Program Budget Item CRUD operations

    list: GET /api/programs/{program_id}/budget-items/
    create: POST /api/programs/{program_id}/budget-items/
    retrieve: GET /api/programs/{program_id}/budget-items/{id}/
    update: PUT /api/programs/{program_id}/budget-items/{id}/
    partial_update: PATCH /api/programs/{program_id}/budget-items/{id}/
    destroy: DELETE /api/programs/{program_id}/budget-items/{id}/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProgramBudgetItemSerializer

    def get_queryset(self):
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return ProgramBudgetItem.objects.none()

        program_pk = self.kwargs.get("program_pk")
        if not program_pk:
            return ProgramBudgetItem.objects.none()

        try:
            program = Program.objects.get(id=program_pk)

            # Check if user has permission to view this program's budget items
            user = self.request.user
            if not (
                user.is_staff
                or program.church == user.church
                or program.created_by == user
            ):
                return ProgramBudgetItem.objects.none()

            return program.budget_items.all()

        except Program.DoesNotExist:
            return ProgramBudgetItem.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return ProgramBudgetItemCreateSerializer
        return ProgramBudgetItemSerializer

    def perform_create(self, serializer):
        program_pk = self.kwargs.get("program_pk")
        try:
            program = Program.objects.get(id=program_pk)

            # Check if user has permission to add budget items
            user = self.request.user
            if not (
                user.is_staff
                or program.church == user.church
                or program.created_by == user
            ):
                raise PermissionDenied(
                    "You don't have permission to add budget items to this program."
                )

            # Check if program is in a state that allows modifications
            if program.status not in ["DRAFT", "REJECTED"]:
                raise ValidationError(
                    "Cannot add budget items to a program that is not in draft or rejected state."
                )

            # Create the budget item
            budget_item = serializer.save()

            # Add to program and save to trigger budget totals update
            program.budget_items.add(budget_item)
            program.save()

        except Program.DoesNotExist:
            raise NotFound("Program not found.")

    def perform_update(self, serializer):
        program_pk = self.kwargs.get("program_pk")
        try:
            program = Program.objects.get(id=program_pk)

            # Check if program is in a state that allows modifications
            if program.status not in ["DRAFT", "REJECTED"]:
                raise ValidationError(
                    "Cannot update budget items in a program that is not in draft or rejected state."
                )

            # Save the budget item
            budget_item = serializer.save()

            # Save program to trigger budget totals update
            program.save()

        except Program.DoesNotExist:
            raise NotFound("Program not found.")

    def perform_destroy(self, instance):
        program_pk = self.kwargs.get("program_pk")
        try:
            program = Program.objects.get(id=program_pk)

            # Check if program is in a state that allows modifications
            if program.status not in ["DRAFT", "REJECTED"]:
                raise ValidationError(
                    "Cannot delete budget items from a program that is not in draft or rejected state."
                )

            # Remove the budget item
            program.budget_items.remove(instance)
            program.save()

            # Delete the budget item
            instance.delete()

        except Program.DoesNotExist:
            raise NotFound("Program not found.")


# Add these imports to the main views/__init__.py file
__all__ = ["ProgramViewSet", "ProgramBudgetItemViewSet"]
