"""Top-down department expense budget allocations (admin)."""

from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services.dashboard import _cache_key
from departments.models import Department, DepartmentExpenseAllocation, Program


def _church_from_request(request):
    return getattr(request, "current_church", None) or getattr(
        request.user, "church", None
    )


class DepartmentExpenseAllocationView(APIView):
    """
    GET: list all departments with optional admin allocation + rolled-up program expenses.
    PUT: replace allocations for a fiscal year (partial list OK — omitted departments unchanged).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"detail": "Church context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            fy = int(request.query_params.get("fiscal_year") or date.today().year)
        except (ValueError, TypeError):
            fy = date.today().year

        departments = Department.objects.filter(
            church=church, deleted_at__isnull=True, is_active=True
        ).order_by("name")

        alloc_rows = DepartmentExpenseAllocation.objects.filter(
            church=church, fiscal_year=fy
        ).select_related("department")
        alloc_by_dept = {str(a.department_id): a.expense_budget for a in alloc_rows}

        result = []
        total_admin = Decimal("0")
        total_programs = Decimal("0")

        for d in departments:
            prog_sum = Program.objects.filter(department=d).aggregate(
                s=Sum("total_expenses")
            )["s"] or Decimal("0")
            total_programs += prog_sum
            admin_val = alloc_by_dept.get(str(d.id))
            if admin_val is not None:
                total_admin += admin_val
            result.append(
                {
                    "id": str(d.id),
                    "name": d.name,
                    "code": d.code,
                    "expense_budget_from_programs": float(prog_sum),
                    "expense_budget_admin": (
                        float(admin_val) if admin_val is not None else None
                    ),
                }
            )

        return Response(
            {
                "fiscal_year": fy,
                "departments": result,
                "totals": {
                    "from_programs": float(total_programs),
                    "admin_allocated_sum": float(total_admin),
                },
            }
        )

    def put(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"detail": "Church context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = request.data or {}
        try:
            fy = int(body.get("fiscal_year"))
        except (ValueError, TypeError):
            return Response(
                {"detail": "fiscal_year is required and must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allocations = body.get("allocations")
        if not isinstance(allocations, list):
            return Response(
                {"detail": "allocations must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dept_ids_in_church = set(
            str(x)
            for x in Department.objects.filter(
                church=church, deleted_at__isnull=True, is_active=True
            ).values_list("id", flat=True)
        )

        with transaction.atomic():
            for row in allocations:
                if not isinstance(row, dict):
                    continue
                did = row.get("department_id")
                if did is None:
                    continue
                sid = str(did)
                if sid not in dept_ids_in_church:
                    continue

                raw = row.get("expense_budget")
                if raw is None or raw == "":
                    DepartmentExpenseAllocation.objects.filter(
                        church=church, department_id=sid, fiscal_year=fy
                    ).delete()
                    continue

                try:
                    amount = Decimal(str(raw))
                except Exception:
                    return Response(
                        {"detail": f"Invalid expense_budget for department {sid}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if amount < 0:
                    return Response(
                        {"detail": "expense_budget cannot be negative"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                DepartmentExpenseAllocation.objects.update_or_create(
                    church=church,
                    department_id=sid,
                    fiscal_year=fy,
                    defaults={"expense_budget": amount},
                )

        # Invalidate analytics cache for this church + fiscal year
        cache.delete(_cache_key(str(church.id), "department_budgets", fiscal_year=fy))

        return self.get(request)
