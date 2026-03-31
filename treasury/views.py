from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models.base_models import AuditLog
from accounts.permissions import has_permission as has_custom_permission

from .models import (
    Asset,
    ExpenseCategory,
    ExpenseRequest,
    ExpenseTransaction,
    IncomeCategory,
    IncomeTransaction,
)
from .serializers import (
    ApproveExpenseRequestSerializer,
    AssetDetailSerializer,
    AssetListSerializer,
    DisburseExpenseRequestSerializer,
    ExpenseCategorySerializer,
    ExpenseRequestDetailSerializer,
    ExpenseRequestListSerializer,
    ExpenseTransactionDetailSerializer,
    ExpenseTransactionListSerializer,
    IncomeCategorySerializer,
    IncomeTransactionDetailSerializer,
    IncomeTransactionListSerializer,
    RejectExpenseRequestSerializer,
    TreasuryStatisticsSerializer,
)

# ==========================================
# INCOME CATEGORY VIEWS
# ==========================================


class IncomeCategoryView(APIView):
    """List all income categories or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all income categories",
        manual_parameters=[
            openapi.Parameter(
                "is_active",
                openapi.IN_QUERY,
                description="Filter by active status",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            )
        ],
        responses={200: IncomeCategorySerializer(many=True)},
        tags=["Treasury - Income Categories"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        categories = IncomeCategory.objects.filter(church=church)

        # Filter by active status
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            categories = categories.filter(is_active=is_active.lower() == "true")

        serializer = IncomeCategorySerializer(
            categories, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new income category",
        request_body=IncomeCategorySerializer,
        responses={201: IncomeCategorySerializer(), 400: "Bad Request"},
        tags=["Treasury - Income Categories"],
    )
    def post(self, request):
        serializer = IncomeCategorySerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IncomeCategoryDetailView(APIView):
    """Retrieve, update or delete an income category"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(IncomeCategory, pk=pk, church=church)

    @swagger_auto_schema(
        operation_description="Get income category details",
        responses={200: IncomeCategorySerializer()},
        tags=["Treasury - Income Categories"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)
        serializer = IncomeCategorySerializer(category, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update income category",
        request_body=IncomeCategorySerializer,
        responses={200: IncomeCategorySerializer()},
        tags=["Treasury - Income Categories"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)

        serializer = IncomeCategorySerializer(
            category, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete income category",
        responses={204: "Category deleted"},
        tags=["Treasury - Income Categories"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)

        # Check if category has transactions
        if category.transactions.filter(deleted_at__isnull=True).exists():
            return Response(
                {"error": "Cannot delete category with existing transactions"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# INCOME TRANSACTION VIEWS
# ==========================================


class IncomeTransactionView(APIView):
    """List all income transactions or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of income transactions",
        manual_parameters=[
            openapi.Parameter(
                "start_date",
                openapi.IN_QUERY,
                description="Filter from date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "end_date",
                openapi.IN_QUERY,
                description="Filter to date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "category_id",
                openapi.IN_QUERY,
                description="Filter by category ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "payment_method",
                openapi.IN_QUERY,
                description="Filter by payment method",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={200: IncomeTransactionListSerializer(many=True)},
        tags=["Treasury - Income"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        transactions = (
            IncomeTransaction.objects.filter(church=church, deleted_at__isnull=True)
            .select_related("category", "member", "department")
            .prefetch_related("allocations")
        )

        # Apply filters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        category_id = request.query_params.get("category_id")
        payment_method = request.query_params.get("payment_method")

        if start_date:
            transactions = transactions.filter(transaction_date__gte=start_date)
        if end_date:
            transactions = transactions.filter(transaction_date__lte=end_date)
        if category_id:
            transactions = transactions.filter(category_id=category_id)
        if payment_method:
            transactions = transactions.filter(payment_method=payment_method)

        serializer = IncomeTransactionListSerializer(
            transactions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new income transaction",
        request_body=IncomeTransactionDetailSerializer,
        responses={201: IncomeTransactionDetailSerializer(), 400: "Bad Request"},
        tags=["Treasury - Income"],
    )
    def post(self, request):
        serializer = IncomeTransactionDetailSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IncomeTransactionDetailView(APIView):
    """Retrieve, update or delete an income transaction"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(
            IncomeTransaction, pk=pk, church=church, deleted_at__isnull=True
        )

    @swagger_auto_schema(
        operation_description="Get income transaction details",
        responses={200: IncomeTransactionDetailSerializer()},
        tags=["Treasury - Income"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)
        serializer = IncomeTransactionDetailSerializer(
            transaction, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update income transaction",
        request_body=IncomeTransactionDetailSerializer,
        responses={200: IncomeTransactionDetailSerializer()},
        tags=["Treasury - Income"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)

        serializer = IncomeTransactionDetailSerializer(
            transaction, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete income transaction (soft delete)",
        responses={204: "Transaction deleted"},
        tags=["Treasury - Income"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)

        # Soft delete
        transaction.deleted_at = timezone.now()
        transaction.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# EXPENSE CATEGORY VIEWS
# ==========================================


class ExpenseCategoryView(APIView):
    """List all expense categories or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all expense categories",
        manual_parameters=[
            openapi.Parameter(
                "is_active",
                openapi.IN_QUERY,
                description="Filter by active status",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            )
        ],
        responses={200: ExpenseCategorySerializer(many=True)},
        tags=["Treasury - Expense Categories"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        categories = ExpenseCategory.objects.filter(church=church)

        # Filter by active status
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            categories = categories.filter(is_active=is_active.lower() == "true")

        serializer = ExpenseCategorySerializer(
            categories, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new expense category",
        request_body=ExpenseCategorySerializer,
        responses={201: ExpenseCategorySerializer(), 400: "Bad Request"},
        tags=["Treasury - Expense Categories"],
    )
    def post(self, request):
        serializer = ExpenseCategorySerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpenseCategoryDetailView(APIView):
    """Retrieve, update or delete an expense category"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(ExpenseCategory, pk=pk, church=church)

    @swagger_auto_schema(
        operation_description="Get expense category details",
        responses={200: ExpenseCategorySerializer()},
        tags=["Treasury - Expense Categories"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)
        serializer = ExpenseCategorySerializer(category, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update expense category",
        request_body=ExpenseCategorySerializer,
        responses={200: ExpenseCategorySerializer()},
        tags=["Treasury - Expense Categories"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)

        serializer = ExpenseCategorySerializer(
            category, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete expense category",
        responses={204: "Category deleted"},
        tags=["Treasury - Expense Categories"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        category = self.get_object(pk, church)

        # Check if category has transactions
        if category.transactions.filter(deleted_at__isnull=True).exists():
            return Response(
                {"error": "Cannot delete category with existing transactions"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# EXPENSE TRANSACTION VIEWS
# ==========================================


class ExpenseTransactionView(APIView):
    """List all expense transactions or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of expense transactions",
        manual_parameters=[
            openapi.Parameter(
                "start_date",
                openapi.IN_QUERY,
                description="Filter from date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "end_date",
                openapi.IN_QUERY,
                description="Filter to date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False,
            ),
            openapi.Parameter(
                "category_id",
                openapi.IN_QUERY,
                description="Filter by category ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "department_id",
                openapi.IN_QUERY,
                description="Filter by department ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={200: ExpenseTransactionListSerializer(many=True)},
        tags=["Treasury - Expenses"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        transactions = ExpenseTransaction.objects.filter(
            church=church, deleted_at__isnull=True
        ).select_related("category", "department")

        # Apply filters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        category_id = request.query_params.get("category_id")
        department_id = request.query_params.get("department_id")

        if start_date:
            transactions = transactions.filter(transaction_date__gte=start_date)
        if end_date:
            transactions = transactions.filter(transaction_date__lte=end_date)
        if category_id:
            transactions = transactions.filter(category_id=category_id)
        if department_id:
            transactions = transactions.filter(department_id=department_id)

        serializer = ExpenseTransactionListSerializer(
            transactions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new expense transaction",
        request_body=ExpenseTransactionDetailSerializer,
        responses={201: ExpenseTransactionDetailSerializer(), 400: "Bad Request"},
        tags=["Treasury - Expenses"],
    )
    def post(self, request):
        serializer = ExpenseTransactionDetailSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpenseTransactionDetailView(APIView):
    """Retrieve, update or delete an expense transaction"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(
            ExpenseTransaction, pk=pk, church=church, deleted_at__isnull=True
        )

    @swagger_auto_schema(
        operation_description="Get expense transaction details",
        responses={200: ExpenseTransactionDetailSerializer()},
        tags=["Treasury - Expenses"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)
        serializer = ExpenseTransactionDetailSerializer(
            transaction, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update expense transaction",
        request_body=ExpenseTransactionDetailSerializer,
        responses={200: ExpenseTransactionDetailSerializer()},
        tags=["Treasury - Expenses"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)

        serializer = ExpenseTransactionDetailSerializer(
            transaction, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete expense transaction (soft delete)",
        responses={204: "Transaction deleted"},
        tags=["Treasury - Expenses"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        transaction = self.get_object(pk, church)

        # Soft delete
        transaction.deleted_at = timezone.now()
        transaction.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# EXPENSE REQUEST VIEWS
# ==========================================


class ExpenseRequestView(APIView):
    """List all expense requests or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of expense requests",
        manual_parameters=[
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by status",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "department_id",
                openapi.IN_QUERY,
                description="Filter by department ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "priority",
                openapi.IN_QUERY,
                description="Filter by priority",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={200: ExpenseRequestListSerializer(many=True)},
        tags=["Treasury - Expense Requests"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        requests_qs = ExpenseRequest.objects.filter(church=church).select_related(
            "department", "category", "requested_by"
        )

        # Apply filters
        status_filter = request.query_params.get("status")
        department_id = request.query_params.get("department_id")
        priority = request.query_params.get("priority")

        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
        if department_id:
            requests_qs = requests_qs.filter(department_id=department_id)
        if priority:
            requests_qs = requests_qs.filter(priority=priority)

        serializer = ExpenseRequestListSerializer(
            requests_qs, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new expense request",
        request_body=ExpenseRequestDetailSerializer,
        responses={201: ExpenseRequestDetailSerializer(), 400: "Bad Request"},
        tags=["Treasury - Expense Requests"],
    )
    def post(self, request):
        serializer = ExpenseRequestDetailSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpenseRequestDetailView(APIView):
    """Retrieve, update or delete an expense request"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(ExpenseRequest, pk=pk, church=church)

    @swagger_auto_schema(
        operation_description="Get expense request details",
        responses={200: ExpenseRequestDetailSerializer()},
        tags=["Treasury - Expense Requests"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        expense_request = self.get_object(pk, church)
        serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update expense request",
        request_body=ExpenseRequestDetailSerializer,
        responses={200: ExpenseRequestDetailSerializer()},
        tags=["Treasury - Expense Requests"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        expense_request = self.get_object(pk, church)

        # Only allow updates if still in DRAFT or SUBMITTED status
        if expense_request.status not in ["DRAFT", "SUBMITTED"]:
            return Response(
                {"error": "Cannot update request in current status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ExpenseRequestDetailSerializer(
            expense_request,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete expense request",
        responses={204: "Request deleted"},
        tags=["Treasury - Expense Requests"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        expense_request = self.get_object(pk, church)

        # Only allow deletion if still in DRAFT
        if expense_request.status != "DRAFT":
            return Response(
                {"error": "Cannot delete request after submission"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expense_request.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# EXPENSE REQUEST APPROVAL ACTIONS
# ==========================================


@swagger_auto_schema(
    method="post",
    operation_description="Submit expense request for approval",
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_expense_request(request, pk):
    """Submit expense request for approval"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if expense_request.status != "DRAFT":
        return Response(
            {"error": "Only draft requests can be submitted"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Auto-approve if submitted by department head or elder in charge
    is_dept_head_or_elder = _can_approve_expense_as_dept_head_or_elder(
        request, expense_request
    )

    expense_request.status = (
        "DEPT_HEAD_APPROVED" if is_dept_head_or_elder else "SUBMITTED"
    )
    expense_request.requested_at = timezone.now()

    if is_dept_head_or_elder:
        expense_request.dept_head_approved_at = timezone.now()
        expense_request.dept_head_approved_by = request.user

    expense_request.save()
    AuditLog.log(
        request.user,
        "STATUS_CHANGE",
        expense_request,
        request=request,
        description=f"Expense request {expense_request.request_number} submitted for approval",
    )
    serializer = ExpenseRequestDetailSerializer(
        expense_request, context={"request": request}
    )
    return Response(serializer.data)


def _can_approve_expense_as_dept_head_or_elder(request, expense_request):
    """Check if user can approve: Department Head or Elder in charge of the department."""
    from departments.models import DepartmentHead
    from members.models import MemberLocation

    dept = expense_request.department
    if not dept:
        return False
    # Department Head: member whose email matches user, and is head of this dept
    member_location = MemberLocation.objects.filter(
        email__iexact=request.user.email, church=expense_request.church
    ).first()
    if (
        member_location
        and DepartmentHead.objects.filter(
            department=dept, member=member_location.member
        ).exists()
    ):
        return True
    # Elder in charge: department's elder_in_charge has system_user_id matching request.user
    elder = getattr(dept, "elder_in_charge", None)
    if (
        elder
        and elder.system_user_id
        and str(elder.system_user_id) == str(request.user.id)
    ):
        return True
    return False


@swagger_auto_schema(
    method="post",
    operation_description="Approve expense request (Department Head or Elder in charge)",
    request_body=ApproveExpenseRequestSerializer,
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_expense_request_dept_head(request, pk):
    """Approve expense request as Department Head or Elder in charge"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if not _can_approve_expense_as_dept_head_or_elder(request, expense_request):
        return Response(
            {
                "error": "Only the Department Head or Elder in charge of this department can approve"
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if expense_request.status != "SUBMITTED":
        return Response(
            {"error": "Request must be in SUBMITTED status"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ApproveExpenseRequestSerializer(data=request.data)
    if serializer.is_valid():
        expense_request.dept_head_approved_by = request.user
        expense_request.dept_head_approved_at = timezone.now()
        expense_request.status = "DEPT_HEAD_APPROVED"

        if serializer.validated_data.get("amount_approved"):
            expense_request.amount_approved = serializer.validated_data[
                "amount_approved"
            ]

        if serializer.validated_data.get("comments"):
            expense_request.approval_comments = serializer.validated_data["comments"]

        expense_request.save()
        AuditLog.log(
            request.user,
            "STATUS_CHANGE",
            expense_request,
            request=request,
            description=f"Expense request {expense_request.request_number} approved by Department Head",
        )
        response_serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def _can_approve_expense_as_first_elder(request, expense_request):
    """Check if user can approve: First Elder role OR Elder in charge of the department."""
    from accounts.models import Role, UserRole

    church = expense_request.church
    dept = expense_request.department
    user = request.user
    # First Elder role (church-level)
    first_elder_role = Role.objects.filter(name="First Elder").first()
    if (
        first_elder_role
        and UserRole.objects.filter(
            user=user, role=first_elder_role, church=church, is_active=True
        ).exists()
    ):
        return True
    # Elder in charge of this department
    if dept:
        elder = getattr(dept, "elder_in_charge", None)
        if elder and elder.system_user_id and str(elder.system_user_id) == str(user.id):
            return True
    return False


@swagger_auto_schema(
    method="post",
    operation_description="Approve expense request (First Elder or Elder in charge)",
    request_body=ApproveExpenseRequestSerializer,
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_expense_request_first_elder(request, pk):
    """Approve expense request as First Elder or Elder in charge"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if not _can_approve_expense_as_first_elder(request, expense_request):
        return Response(
            {
                "error": "Only First Elder or the Elder in charge of this department can approve"
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if expense_request.status != "DEPT_HEAD_APPROVED":
        return Response(
            {"error": "Request must be approved by Department Head first"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ApproveExpenseRequestSerializer(data=request.data)
    if serializer.is_valid():
        expense_request.first_elder_approved_by = request.user
        expense_request.first_elder_approved_at = timezone.now()
        expense_request.status = "FIRST_ELDER_APPROVED"
        expense_request.save()
        AuditLog.log(
            request.user,
            "STATUS_CHANGE",
            expense_request,
            request=request,
            description=f"Expense request {expense_request.request_number} approved by First Elder",
        )
        response_serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_description="Approve expense request (Treasurer - Final Approval)",
    request_body=ApproveExpenseRequestSerializer,
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_expense_request_treasurer(request, pk):
    """Approve expense request as Treasurer (final approval)"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if not (
        request.user.is_staff
        or request.user.is_superuser
        or has_custom_permission(
            request.user, "treasury.approve_expense", church=church
        )
    ):
        return Response(
            {
                "error": "Only users with treasury approval permission can approve at this stage."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if expense_request.status != "FIRST_ELDER_APPROVED":
        return Response(
            {"error": "Request must be approved by First Elder first"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ApproveExpenseRequestSerializer(data=request.data)
    if serializer.is_valid():
        expense_request.treasurer_approved_by = request.user
        expense_request.treasurer_approved_at = timezone.now()
        expense_request.status = "APPROVED"
        expense_request.save()
        AuditLog.log(
            request.user,
            "STATUS_CHANGE",
            expense_request,
            request=request,
            description=f"Expense request {expense_request.request_number} approved by Treasurer",
        )
        response_serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_description="Reject expense request",
    request_body=RejectExpenseRequestSerializer,
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_expense_request(request, pk):
    """Reject expense request"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if expense_request.status in ["APPROVED", "DISBURSED", "CANCELLED"]:
        return Response(
            {"error": "Cannot reject request in current status"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = RejectExpenseRequestSerializer(data=request.data)
    if serializer.is_valid():
        expense_request.status = "REJECTED"
        expense_request.rejection_reason = serializer.validated_data["rejection_reason"]
        expense_request.save()
        AuditLog.log(
            request.user,
            "STATUS_CHANGE",
            expense_request,
            request=request,
            description=f"Expense request {expense_request.request_number} rejected",
        )
        response_serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    operation_description="Disburse approved expense request",
    request_body=DisburseExpenseRequestSerializer,
    responses={200: ExpenseRequestDetailSerializer()},
    tags=["Treasury - Expense Requests"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disburse_expense_request(request, pk):
    """Disburse approved expense request"""
    church = getattr(request, "current_church", None) or request.user.church
    expense_request = get_object_or_404(ExpenseRequest, pk=pk, church=church)

    if expense_request.status != "APPROVED":
        return Response(
            {"error": "Only approved requests can be disbursed"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = DisburseExpenseRequestSerializer(data=request.data)
    if serializer.is_valid():
        # Create expense transaction
        from datetime import date

        year = date.today().year
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

        expense_transaction = ExpenseTransaction.objects.create(
            church=church,
            voucher_number=voucher_number,
            transaction_date=date.today(),
            category=expense_request.category,
            department=expense_request.department,
            amount=serializer.validated_data["disbursed_amount"],
            payment_method=serializer.validated_data["payment_method"],
            transaction_reference=serializer.validated_data.get(
                "transaction_reference", ""
            ),
            paid_to=expense_request.requested_by.get_full_name(),
            description=expense_request.purpose,
            requested_by=expense_request.requested_by,
            approved_by=expense_request.treasurer_approved_by,
            recorded_by=request.user,
            expense_request=expense_request,
            notes=serializer.validated_data.get("notes", ""),
        )

        # Update expense request
        expense_request.status = "DISBURSED"
        expense_request.disbursed_at = timezone.now()
        expense_request.disbursed_amount = serializer.validated_data["disbursed_amount"]
        expense_request.save()
        AuditLog.log(
            request.user,
            "STATUS_CHANGE",
            expense_request,
            request=request,
            description=f"Expense request {expense_request.request_number} disbursed",
        )
        response_serializer = ExpenseRequestDetailSerializer(
            expense_request, context={"request": request}
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# ASSET VIEWS
# ==========================================


class AssetView(APIView):
    """List all assets or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of assets",
        manual_parameters=[
            openapi.Parameter(
                "category",
                openapi.IN_QUERY,
                description="Filter by category",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "condition",
                openapi.IN_QUERY,
                description="Filter by condition",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "department_id",
                openapi.IN_QUERY,
                description="Filter by department ID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={200: AssetListSerializer(many=True)},
        tags=["Treasury - Assets"],
    )
    def get(self, request):
        church = getattr(request, "current_church", None) or request.user.church

        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        assets = Asset.objects.filter(
            church=church, deleted_at__isnull=True
        ).select_related("department", "custodian")

        # Apply filters
        category = request.query_params.get("category")
        condition = request.query_params.get("condition")
        department_id = request.query_params.get("department_id")

        if category:
            assets = assets.filter(category=category)
        if condition:
            assets = assets.filter(condition=condition)
        if department_id:
            assets = assets.filter(department_id=department_id)

        serializer = AssetListSerializer(
            assets, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new asset",
        request_body=AssetDetailSerializer,
        responses={201: AssetDetailSerializer(), 400: "Bad Request"},
        tags=["Treasury - Assets"],
    )
    def post(self, request):
        serializer = AssetDetailSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssetDetailView(APIView):
    """Retrieve, update or delete an asset"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, church):
        return get_object_or_404(Asset, pk=pk, church=church, deleted_at__isnull=True)

    @swagger_auto_schema(
        operation_description="Get asset details",
        responses={200: AssetDetailSerializer()},
        tags=["Treasury - Assets"],
    )
    def get(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        asset = self.get_object(pk, church)
        serializer = AssetDetailSerializer(asset, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update asset",
        request_body=AssetDetailSerializer,
        responses={200: AssetDetailSerializer()},
        tags=["Treasury - Assets"],
    )
    def put(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        asset = self.get_object(pk, church)

        serializer = AssetDetailSerializer(
            asset, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete asset (soft delete)",
        responses={204: "Asset deleted"},
        tags=["Treasury - Assets"],
    )
    def delete(self, request, pk):
        church = getattr(request, "current_church", None) or request.user.church
        asset = self.get_object(pk, church)

        # Soft delete
        asset.deleted_at = timezone.now()
        asset.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# STATISTICS & REPORTS
# ==========================================


@swagger_auto_schema(
    method="get",
    operation_description="Get treasury statistics and summary",
    manual_parameters=[
        openapi.Parameter(
            "start_date",
            openapi.IN_QUERY,
            description="Filter from date (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE,
            required=False,
        ),
        openapi.Parameter(
            "end_date",
            openapi.IN_QUERY,
            description="Filter to date (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE,
            required=False,
        ),
    ],
    responses={200: TreasuryStatisticsSerializer()},
    tags=["Treasury - Statistics"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_treasury_statistics(request):
    """Get treasury statistics"""
    church = getattr(request, "current_church", None) or request.user.church

    if not church:
        return Response(
            {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
        )

    # Date range
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    # Build filters
    income_filter = Q(church=church, deleted_at__isnull=True)
    expense_filter = Q(church=church, deleted_at__isnull=True)

    if start_date:
        income_filter &= Q(transaction_date__gte=start_date)
        expense_filter &= Q(transaction_date__gte=start_date)
    if end_date:
        income_filter &= Q(transaction_date__lte=end_date)
        expense_filter &= Q(transaction_date__lte=end_date)

    # Calculate totals
    total_income = IncomeTransaction.objects.filter(income_filter).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    total_expenses = ExpenseTransaction.objects.filter(expense_filter).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    net_balance = total_income - total_expenses

    # Income by category
    income_by_category = list(
        IncomeTransaction.objects.filter(income_filter)
        .values("category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Expenses by category
    expenses_by_category = list(
        ExpenseTransaction.objects.filter(expense_filter)
        .values("category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Expenses by department
    expenses_by_department = list(
        ExpenseTransaction.objects.filter(expense_filter)
        .values("department__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Pending expense requests
    pending_requests = ExpenseRequest.objects.filter(
        church=church,
        status__in=[
            "SUBMITTED",
            "DEPT_HEAD_APPROVED",
            "ELDER_APPROVED",
            "FIRST_ELDER_APPROVED",
            "APPROVED",
        ],
    ).count()

    # Total assets value
    total_assets_value = Asset.objects.filter(
        church=church, deleted_at__isnull=True
    ).aggregate(total=Sum("current_value"))["total"] or Decimal("0.00")

    data = {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "income_by_category": income_by_category,
        "expenses_by_category": expenses_by_category,
        "expenses_by_department": expenses_by_department,
        "pending_expense_requests": pending_requests,
        "total_assets_value": total_assets_value,
    }

    serializer = TreasuryStatisticsSerializer(data)
    return Response(serializer.data)
