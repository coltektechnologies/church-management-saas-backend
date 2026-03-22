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

from ..models import (Department, DepartmentHead, Member, MemberDepartment,
                      Program, ProgramBudgetItem)
from ..serializers import (AssignDepartmentHeadSerializer,
                           AssignMemberToDepartmentSerializer,
                           DepartmentCreateSerializer,
                           DepartmentHeadSerializer, DepartmentListSerializer,
                           DepartmentSerializer,
                           DepartmentStatisticsSerializer,
                           DepartmentWithHeadCreateSerializer,
                           MemberDepartmentSerializer,
                           ProgramBudgetItemSerializer, ProgramListSerializer)


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

    @action(detail=True, methods=["put"], url_path="head")
    def set_head(self, request, pk=None):
        """
        Set or update the head of a department.

        Required data:
        - member_id: UUID of the member to set as head
        """
        department = self.get_object()
        serializer = AssignDepartmentHeadSerializer(
            data=request.data, context={"request": request, "department": department}
        )

        if serializer.is_valid():
            member_id = serializer.validated_data["member_id"]

            # Create or update department head
            department_head, created = DepartmentHead.objects.update_or_create(
                department=department, defaults={"member_id": member_id}
            )

            return Response(
                DepartmentHeadSerializer(department_head).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        """
        Get statistics for departments.
        """
        departments = Department.objects.all()
        if not request.user.is_superuser:
            departments = departments.filter(church=request.user.church)
        total_departments = departments.count()
        active_departments = departments.filter(is_active=True).count()
        inactive_departments = total_departments - active_departments

        # Filter programs by church for non-superusers
        program_qs = Program.objects.exclude(status="CANCELLED")
        if not request.user.is_superuser:
            program_qs = program_qs.filter(church=request.user.church)
        today = timezone.now().date()
        total_members_in_departments = MemberDepartment.objects.filter(
            department__in=departments
        ).count()
        departments_without_heads = departments.filter(heads__isnull=True).count()
        total_programs = program_qs.count()
        upcoming_programs = program_qs.filter(start_date__gt=today).count()
        past_programs = program_qs.filter(end_date__lt=today).count()
        ongoing_programs = program_qs.filter(
            start_date__lte=today,
            end_date__gte=today,
        ).count()

        return Response(
            {
                "total_departments": total_departments,
                "active_departments": active_departments,
                "inactive_departments": inactive_departments,
                "total_members_in_departments": total_members_in_departments,
                "departments_without_heads": departments_without_heads,
                "total_programs": total_programs,
                "upcoming_programs": upcoming_programs,
                "past_programs": past_programs,
                "ongoing_programs": ongoing_programs,
            }
        )

    def get_queryset(self):
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return Department.objects.none()

        queryset = Department.objects.all()

        # Filter by church if user is not superuser
        if not self.request.user.is_superuser:
            queryset = queryset.filter(church=self.request.user.church)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return DepartmentListSerializer
        return (
            DepartmentWithHeadCreateSerializer
            if self.action == "create"
            else DepartmentSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        department = serializer.instance
        output_serializer = DepartmentSerializer(
            department, context={"request": request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Allow partial updates for PUT when body doesn't include all required fields
        partial = kwargs.get("partial", False)
        if request.method == "PUT" and not partial:
            data_keys = set(request.data.keys()) if request.data else set()
            if "name" not in data_keys or "code" not in data_keys:
                kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Head assignment is fully handled inside DepartmentWithHeadCreateSerializer.create()
        # using get_or_create — no duplicate logic needed here.
        serializer.save()

    @action(detail=True, methods=["get"], url_path="program-stats")
    def program_stats(self, request, pk=None):
        """
        Get program counts for a department: upcoming, past, and ongoing.
        """
        department = self.get_object()
        today = timezone.now().date()
        upcoming = (
            Program.objects.filter(
                department=department,
                start_date__gt=today,
            )
            .exclude(status="CANCELLED")
            .count()
        )
        past = (
            Program.objects.filter(
                department=department,
                end_date__lt=today,
            )
            .exclude(status="CANCELLED")
            .count()
        )
        ongoing = (
            Program.objects.filter(
                department=department,
                start_date__lte=today,
                end_date__gte=today,
            )
            .exclude(status="CANCELLED")
            .count()
        )
        total = upcoming + past + ongoing
        return Response(
            {
                "department_id": str(department.id),
                "department_name": department.name,
                "upcoming_programs_count": upcoming,
                "past_programs_count": past,
                "ongoing_programs_count": ongoing,
                "total_programs_count": total,
            }
        )

    @action(detail=True, methods=["get"])
    def programs(self, request, pk=None):
        """
        Get all programs for a department
        """
        department = self.get_object()
        programs = Program.objects.filter(department=department)
        serializer = ProgramListSerializer(programs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def budget_items(self, request, pk=None):
        """
        Get all budget items for a department's programs
        """
        department = self.get_object()
        budget_items = ProgramBudgetItem.objects.filter(program__department=department)
        serializer = ProgramBudgetItemSerializer(budget_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """
        Get all members of a department
        """
        department = self.get_object()
        member_departments = MemberDepartment.objects.filter(department=department)
        members = [md.member for md in member_departments]
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)


class MemberDepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing member-department relationships
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MemberDepartmentSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MemberDepartment.objects.none()

        queryset = MemberDepartment.objects.all()

        # Filter by church if user is not superuser
        if not self.request.user.is_superuser:
            queryset = queryset.filter(department__church=self.request.user.church)

        return queryset


class DepartmentHeadViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing department heads
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DepartmentHeadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DepartmentHead.objects.none()

        queryset = DepartmentHead.objects.all()

        # Filter by church if user is not superuser
        if not self.request.user.is_superuser:
            queryset = queryset.filter(department__church=self.request.user.church)

        return queryset


class DepartmentStatisticsView(APIView):
    """
    API endpoint for department statistics
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        # Get statistics for all departments
        departments = Department.objects.all()

        # Filter by church if user is not superuser
        if not request.user.is_superuser:
            departments = departments.filter(church=request.user.church)

        # Get department statistics
        department_stats = []
        for dept in departments:
            stats = {
                "id": dept.id,
                "name": dept.name,
                "member_count": dept.members.count(),
                "program_count": dept.programs.count(),
                "total_budget": dept.programs.aggregate(total_budget=Sum("budget"))[
                    "total_budget"
                ]
                or 0,
                "total_spent": dept.programs.aggregate(
                    total_spent=Sum("budget_items__amount_spent")
                )["total_spent"]
                or 0,
            }
            department_stats.append(stats)

        serializer = DepartmentStatisticsSerializer(department_stats, many=True)
        return Response(serializer.data)
