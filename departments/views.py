from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from members.models import Member
from members.serializers import MemberSerializer

from .models import Department, DepartmentHead, MemberDepartment, Program
from .serializers import (AssignDepartmentHeadSerializer,
                          AssignMemberToDepartmentSerializer,
                          DepartmentCreateSerializer, DepartmentHeadSerializer,
                          DepartmentListSerializer, DepartmentSerializer,
                          DepartmentStatisticsSerializer,
                          DepartmentWithHeadCreateSerializer,
                          MemberDepartmentSerializer, ProgramListSerializer)
from .views import ProgramViewSet


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Department CRUD operations

    list: GET /api/departments/
    create: POST /api/departments/
    retrieve: GET /api/departments/{id}/
    update: PUT /api/departments/{id}/
    partial_update: PATCH /api/departments/{id}/
    destroy: DELETE /api/departments/{id}/
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code", "description"]
    ordering = ["name"]

    def get_queryset(self):
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return Department.objects.none()

        user = self.request.user

        # Handle unauthenticated users
        if not user.is_authenticated:
            return Department.objects.none()

        # Platform admins can see all departments or filter by church_id
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            church_id = self.request.query_params.get("church_id")
            if church_id:
                return Department.objects.filter(
                    church_id=church_id, deleted_at__isnull=True
                )
            return Department.objects.filter(deleted_at__isnull=True)

        # Regular users can only see departments from their church
        if hasattr(user, "church") and user.church:
            return Department.objects.filter(
                church=user.church, deleted_at__isnull=True
            )

        return Department.objects.none()

    def get_serializer_class(self):
        if self.action == "list":
            return DepartmentListSerializer
        return DepartmentSerializer

    @swagger_auto_schema(
        operation_description="Get list of all departments",
        responses={200: DepartmentListSerializer(many=True)},
        tags=["Departments"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Create a new department with an optional department head",
        request_body=DepartmentWithHeadCreateSerializer,
        responses={201: DepartmentSerializer(), 400: "Invalid input data"},
        tags=["Departments"],
    )
    def create(self, request, *args, **kwargs):
        # Use the new serializer that supports head assignment
        serializer = DepartmentWithHeadCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        department = serializer.save()

        output_serializer = DepartmentSerializer(
            department, context={"request": request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="Delete department (soft delete)",
        responses={204: "Department deleted"},
        tags=["Departments"],
    )
    def destroy(self, request, *args, **kwargs):
        department = self.get_object()
        department.deleted_at = timezone.now()
        department.is_active = False
        department.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ==========================================
    # MEMBER MANAGEMENT
    # ==========================================

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        operation_description="Get all members in a department",
        responses={200: MemberSerializer(many=True)},
        tags=["Departments"],
    )
    def members(self, request, pk=None):
        """Get all members in this department"""
        department = self.get_object()
        assignments = MemberDepartment.objects.filter(
            department=department
        ).select_related("member")

        members = [assignment.member for assignment in assignments]
        serializer = MemberSerializer(members, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @swagger_auto_schema(
        operation_description="Assign a member to this department",
        request_body=AssignMemberToDepartmentSerializer,
        responses={201: MemberDepartmentSerializer()},
        tags=["Departments"],
    )
    def assign_member(self, request, pk=None):
        """Assign member to department"""
        department = self.get_object()

        input_serializer = AssignMemberToDepartmentSerializer(
            data=request.data, context={"request": request}
        )
        input_serializer.is_valid(raise_exception=True)

        member = Member.objects.get(id=input_serializer.validated_data["member_id"])

        assignment = MemberDepartment.objects.create(
            member=member,
            department=department,
            church=department.church,
            role_in_department=input_serializer.validated_data.get(
                "role_in_department", ""
            ),
        )

        serializer = MemberDepartmentSerializer(
            assignment, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="members/(?P<member_id>[^/.]+)")
    @swagger_auto_schema(
        operation_description="Remove a member from this department",
        responses={204: "Member removed from department"},
        tags=["Departments"],
    )
    def remove_member(self, request, pk=None, member_id=None):
        """Remove member from department"""
        department = self.get_object()

        try:
            assignment = MemberDepartment.objects.get(
                department=department, member_id=member_id
            )
            assignment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except MemberDepartment.DoesNotExist:
            return Response(
                {"error": "Member not found in this department"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # ==========================================
    # DEPARTMENT HEAD MANAGEMENT
    # ==========================================

    @action(detail=True, methods=["put"])
    @swagger_auto_schema(
        operation_description="Assign department head",
        request_body=AssignDepartmentHeadSerializer,
        responses={200: DepartmentHeadSerializer()},
        tags=["Departments"],
    )
    def head(self, request, pk=None):
        """Assign or update department head"""
        department = self.get_object()

        input_serializer = AssignDepartmentHeadSerializer(
            data=request.data, context={"request": request}
        )
        input_serializer.is_valid(raise_exception=True)

        member = Member.objects.get(id=input_serializer.validated_data["member_id"])

        # Remove existing head
        DepartmentHead.objects.filter(department=department).delete()

        # Assign new head
        head = DepartmentHead.objects.create(
            department=department, member=member, church=department.church
        )

        serializer = DepartmentHeadSerializer(head, context={"request": request})
        return Response(serializer.data)

    # ==========================================
    # PROGRAM MANAGEMENT
    # ==========================================

    @action(detail=True, methods=["get"], url_path="programs")
    def department_programs(self, request, pk=None):
        """
        Get all programs for a specific department
        """
        department = self.get_object()
        programs = Program.objects.filter(department=department)
        serializer = ProgramListSerializer(
            programs, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="statistics")
    def department_statistics(self, request, pk=None):
        """
        Get statistics for a specific department
        """
        department = self.get_object()

        # Get total members in department
        total_members = MemberDepartment.objects.filter(department=department).count()

        # Get current active program (if any)
        current_program = Program.objects.filter(
            department=department,
            status__in=["APPROVED", "IN_PROGRESS"],
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now(),
        ).first()

        # Get upcoming programs (next 30 days)
        upcoming_programs = Program.objects.filter(
            department=department,
            start_date__gte=timezone.now(),
            start_date__lte=timezone.now() + timezone.timedelta(days=30),
        ).count()

        # Calculate statistics
        statistics = {
            "total_members": total_members,
            "current_program": {
                "title": current_program.title if current_program else None,
                "start_date": current_program.start_date if current_program else None,
                "end_date": current_program.end_date if current_program else None,
                "total_income": (
                    float(current_program.total_income) if current_program else 0
                ),
                "total_expenses": (
                    float(current_program.total_expenses) if current_program else 0
                ),
                "net_budget": (
                    float(current_program.net_budget) if current_program else 0
                ),
            },
            "upcoming_programs": upcoming_programs,
        }

        serializer = DepartmentStatisticsSerializer(statistics)
        return Response(serializer.data)

    # ==========================================
    # STATISTICS
    # ==========================================

    @action(detail=False, methods=["get"])
    @swagger_auto_schema(
        operation_description="Get department statistics",
        responses={200: DepartmentStatisticsSerializer()},
        tags=["Departments"],
    )
    def statistics(self, request):
        """Get department statistics"""
        queryset = self.get_queryset()

        stats = {
            "total_departments": queryset.count(),
            "active_departments": queryset.filter(is_active=True).count(),
            "total_members_in_departments": MemberDepartment.objects.filter(
                department__in=queryset
            ).count(),
            "departments_without_heads": queryset.filter(heads__isnull=True).count(),
            "total_programs": Program.objects.filter(department__in=queryset).count(),
            "upcoming_programs": Program.objects.filter(
                department__in=queryset,
                start_date__gte=timezone.now().date(),
                status="PLANNED",
            ).count(),
        }

        serializer = DepartmentStatisticsSerializer(stats)
        return Response(serializer.data)
