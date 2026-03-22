"""
Dashboard & analytics: aggregated stats, KPIs, trends with caching.
All queries are church-scoped.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Church
from announcements.models import Announcement
from departments.models import Department, MemberDepartment, Program
from members.models import Member
from treasury.models import Asset, ExpenseRequest, ExpenseTransaction, IncomeTransaction

# Cache TTL in seconds (5 min for near real-time dashboards)
DASHBOARD_CACHE_TTL = 300


def _cache_key(church_id: str, key: str, **extra) -> str:
    parts = ["analytics", str(church_id), key]
    for k, v in sorted(extra.items()):
        parts.append(f"{k}={v}")
    return ":".join(parts)


class DashboardService:
    def __init__(self, church: Church):
        self.church = church
        self._cid = str(church.id)

    def _get_cached(self, key: str, builder, **extra) -> dict:
        ckey = _cache_key(self._cid, key, **extra)
        data = cache.get(ckey)
        if data is not None:
            return data
        data = builder()
        cache.set(ckey, data, DASHBOARD_CACHE_TTL)
        return data

    # ---------- Dashboard: Secretariat ----------
    def dashboard_secretariat(self) -> dict:
        """Announcements + programs pending secretariat approval."""

        def _build():
            announcements = Announcement.objects.filter(church=self.church)
            by_status = dict(
                announcements.values("status")
                .annotate(c=Count("id"))
                .values_list("status", "c")
            )
            programs = Program.objects.filter(church=self.church)
            pending_secretariat = programs.filter(
                submitted_to_secretariat=True,
                secretariat_approved=False,
                status__in=["SUBMITTED", "ELDER_APPROVED"],
            ).count()
            return {
                "announcements": {
                    "total": announcements.count(),
                    "by_status": by_status,
                    "draft": by_status.get("DRAFT", 0),
                    "published": by_status.get("PUBLISHED", 0),
                    "pending_review": by_status.get("PENDING_REVIEW", 0),
                },
                "programs_pending_secretariat": pending_secretariat,
                "programs_total": programs.count(),
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("dashboard_secretariat", _build)

    # ---------- Dashboard: Treasury ----------
    def dashboard_treasury(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> dict:
        today = timezone.localdate()
        date_from = date_from or (today - timedelta(days=30))
        date_to = date_to or today

        def _build():
            inc_q = IncomeTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=date_from,
                transaction_date__lte=date_to,
                deleted_at__isnull=True,
            )
            exp_q = ExpenseTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=date_from,
                transaction_date__lte=date_to,
                deleted_at__isnull=True,
            )
            total_income = inc_q.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            total_expenses = exp_q.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            pending = ExpenseRequest.objects.filter(
                church=self.church,
                status__in=[
                    "SUBMITTED",
                    "DEPT_HEAD_APPROVED",
                    "FIRST_ELDER_APPROVED",
                    "TREASURER_APPROVED",
                    "APPROVED",
                ],
            ).count()
            assets_value = Asset.objects.filter(
                church=self.church, deleted_at__isnull=True
            ).aggregate(s=Sum("current_value"))["s"] or Decimal("0")
            return {
                "period": {"date_from": str(date_from), "date_to": str(date_to)},
                "total_income": str(total_income),
                "total_expenses": str(total_expenses),
                "net_balance": str(total_income - total_expenses),
                "pending_expense_requests": pending,
                "total_assets_value": str(assets_value),
                "income_transaction_count": inc_q.count(),
                "expense_transaction_count": exp_q.count(),
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached(
            "dashboard_treasury", _build, df=str(date_from), dt=str(date_to)
        )

    # ---------- Dashboard: Department by id ----------
    def dashboard_department(self, department_id: str) -> dict:
        def _build():
            dept = Department.objects.filter(
                church=self.church, id=department_id
            ).first()
            if not dept:
                return {"error": "Department not found", "department_id": department_id}
            member_count = MemberDepartment.objects.filter(
                department_id=department_id, deleted_at__isnull=True
            ).count()
            programs = Program.objects.filter(department_id=department_id)
            by_status = dict(
                programs.values("status")
                .annotate(c=Count("id"))
                .values_list("status", "c")
            )
            budget_totals = programs.aggregate(
                total_income=Sum("total_income"),
                total_expenses=Sum("total_expenses"),
                total_net=Sum("net_budget"),
            )
            return {
                "department": {
                    "id": str(dept.id),
                    "name": dept.name,
                    "code": dept.code,
                    "is_active": dept.is_active,
                },
                "member_count": member_count,
                "programs_total": programs.count(),
                "programs_by_status": by_status,
                "budget_summary": {
                    "total_income": str(budget_totals["total_income"] or 0),
                    "total_expenses": str(budget_totals["total_expenses"] or 0),
                    "net_budget": str(budget_totals["total_net"] or 0),
                },
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("dashboard_department", _build, dept=department_id)

    # ---------- Dashboard: Admin ----------
    def dashboard_admin(self) -> dict:
        def _build():
            members_total = Member.objects.filter(
                church=self.church, deleted_at__isnull=True
            ).count()
            departments_total = Department.objects.filter(
                church=self.church, deleted_at__isnull=True
            ).count()
            announcements_total = Announcement.objects.filter(
                church=self.church
            ).count()
            programs_total = Program.objects.filter(church=self.church).count()
            today = timezone.localdate()
            month_start = today.replace(day=1)
            inc = IncomeTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=month_start,
                transaction_date__lte=today,
                deleted_at__isnull=True,
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
            exp = ExpenseTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=month_start,
                transaction_date__lte=today,
                deleted_at__isnull=True,
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
            pending_expenses = ExpenseRequest.objects.filter(
                church=self.church,
                status__in=[
                    "SUBMITTED",
                    "DEPT_HEAD_APPROVED",
                    "FIRST_ELDER_APPROVED",
                    "TREASURER_APPROVED",
                    "APPROVED",
                ],
            ).count()
            return {
                "members_total": members_total,
                "departments_total": departments_total,
                "announcements_total": announcements_total,
                "programs_total": programs_total,
                "current_month_income": str(inc),
                "current_month_expenses": str(exp),
                "current_month_net": str(inc - exp),
                "pending_expense_requests": pending_expenses,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("dashboard_admin", _build)

    # ---------- Analytics: Members stats ----------
    def members_stats(self) -> dict:
        def _build():
            today = timezone.localdate()
            month_start = today.replace(day=1)
            if month_start.month == 1:
                last_month_start = (month_start - timedelta(days=1)).replace(day=1)
            else:
                last_month_start = month_start.replace(month=month_start.month - 1)

            qs = Member.objects.filter(church=self.church, deleted_at__isnull=True)
            total = qs.count()
            by_status = list(qs.values("membership_status").annotate(count=Count("id")))
            by_gender = list(qs.values("gender").annotate(count=Count("id")))
            status_map = {s["membership_status"]: s["count"] for s in by_status}
            active_count = status_map.get("ACTIVE", 0)
            inactive_count = status_map.get("INACTIVE", 0)
            pending_count = status_map.get("NEW_CONVERT", 0)
            new_this_month = qs.filter(created_at__date__gte=month_start).count()
            new_last_month = qs.filter(
                created_at__date__gte=last_month_start,
                created_at__date__lt=month_start,
            ).count()

            prev_total = total - new_this_month
            total_change = (
                round(new_this_month / prev_total * 100, 1)
                if prev_total and prev_total > 0
                else 0
            )
            new_change = (
                round((new_this_month - new_last_month) / new_last_month * 100, 1)
                if new_last_month and new_last_month > 0
                else (100 if new_this_month > 0 else 0)
            )
            prev_active = max(0, active_count - new_this_month)
            active_change = (
                round(new_this_month / prev_active * 100, 1)
                if prev_active > 0
                else (100 if active_count > 0 else 0)
            )
            inactive_change_val = (
                round(-new_this_month / inactive_count * 100, 1)
                if inactive_count and inactive_count > 0
                else 0
            )

            return {
                "total_members": total,
                "total_change_percent": total_change,
                "active_members": active_count,
                "active_change_percent": active_change,
                "inactive_members": inactive_count,
                "inactive_change_percent": inactive_change_val,
                "new_members_this_month": new_this_month,
                "new_members_change_percent": new_change,
                "pending_approvals": pending_count,
                "by_membership_status": by_status,
                "by_gender": by_gender,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("members_stats", _build)

    # ---------- Analytics: Finance trends ----------
    def finance_trends(self, period_days: int = 90) -> dict:
        today = timezone.localdate()
        date_from = today - timedelta(days=period_days)

        def _build():
            inc = (
                IncomeTransaction.objects.filter(
                    church=self.church,
                    transaction_date__gte=date_from,
                    transaction_date__lte=today,
                    deleted_at__isnull=True,
                )
                .annotate(month=TruncMonth("transaction_date"))
                .values("month")
                .annotate(total=Sum("amount"), count=Count("id"))
                .order_by("month")
            )
            exp = (
                ExpenseTransaction.objects.filter(
                    church=self.church,
                    transaction_date__gte=date_from,
                    transaction_date__lte=today,
                    deleted_at__isnull=True,
                )
                .annotate(month=TruncMonth("transaction_date"))
                .values("month")
                .annotate(total=Sum("amount"), count=Count("id"))
                .order_by("month")
            )
            income_trend = [
                {
                    "month": r["month"].strftime("%Y-%m") if r["month"] else None,
                    "total": str(r["total"]),
                    "count": r["count"],
                }
                for r in inc
            ]
            expense_trend = [
                {
                    "month": r["month"].strftime("%Y-%m") if r["month"] else None,
                    "total": str(r["total"]),
                    "count": r["count"],
                }
                for r in exp
            ]
            return {
                "period_days": period_days,
                "date_from": str(date_from),
                "date_to": str(today),
                "income_by_month": income_trend,
                "expenses_by_month": expense_trend,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("finance_trends", _build, days=period_days)

    # ---------- Analytics: Finance KPIs ----------
    def finance_kpis(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> dict:
        today = timezone.localdate()
        date_from = date_from or (today.replace(day=1))
        date_to = date_to or today

        def _build():
            inc_q = IncomeTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=date_from,
                transaction_date__lte=date_to,
                deleted_at__isnull=True,
            )
            exp_q = ExpenseTransaction.objects.filter(
                church=self.church,
                transaction_date__gte=date_from,
                transaction_date__lte=date_to,
                deleted_at__isnull=True,
            )
            total_income = inc_q.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            total_expenses = exp_q.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            inc_count = inc_q.count()
            exp_count = exp_q.count()
            return {
                "period": {"date_from": str(date_from), "date_to": str(date_to)},
                "total_income": str(total_income),
                "total_expenses": str(total_expenses),
                "net_cash_flow": str(total_income - total_expenses),
                "income_transaction_count": inc_count,
                "expense_transaction_count": exp_count,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached(
            "finance_kpis", _build, df=str(date_from), dt=str(date_to)
        )

    # ---------- Analytics: Tithe & Offerings ----------
    def tithe_offering_stats(self, period_months: int = 9) -> dict:
        today = timezone.localdate()
        month_start = today.replace(day=1)
        base = IncomeTransaction.objects.filter(
            church=self.church,
            deleted_at__isnull=True,
        )
        tithe_base = base.filter(category__code="TITHE")
        offering_base = base.exclude(category__code="TITHE")

        def _build():
            monthly_trend = []
            for i in range(period_months - 1, -1, -1):
                if month_start.month - i <= 0:
                    yr = month_start.year - 1
                    m = month_start.month - i + 12
                else:
                    yr = month_start.year
                    m = month_start.month - i
                dt = date(yr, m, 1)
                end_dt = (dt.replace(day=28) + timedelta(days=4)).replace(
                    day=1
                ) - timedelta(days=1)
                tithe_sum = tithe_base.filter(
                    transaction_date__gte=dt,
                    transaction_date__lte=end_dt,
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                offering_sum = offering_base.filter(
                    transaction_date__gte=dt,
                    transaction_date__lte=end_dt,
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                monthly_trend.append(
                    {
                        "month": dt.strftime("%b %y"),
                        "tithe": float(tithe_sum),
                        "offering": float(offering_sum),
                    }
                )

            this_month_tithe = tithe_base.filter(
                transaction_date__gte=month_start,
                transaction_date__lte=today,
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
            this_month_offering = offering_base.filter(
                transaction_date__gte=month_start,
                transaction_date__lte=today,
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")

            def week_sums(qs):
                w1 = qs.filter(
                    transaction_date__day__gte=1,
                    transaction_date__day__lte=7,
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                w2 = qs.filter(
                    transaction_date__day__gte=8,
                    transaction_date__day__lte=14,
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                w3 = qs.filter(
                    transaction_date__day__gte=15,
                    transaction_date__day__lte=21,
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                w4 = qs.filter(transaction_date__day__gte=22).aggregate(
                    s=Sum("amount")
                )["s"] or Decimal("0")
                return [
                    {"name": "W1", "value": float(w1)},
                    {"name": "W2", "value": float(w2)},
                    {"name": "W3", "value": float(w3)},
                    {"name": "W4", "value": float(w4)},
                ]

            tithe_month_qs = tithe_base.filter(
                transaction_date__gte=month_start,
                transaction_date__lte=today,
            )
            offering_month_qs = offering_base.filter(
                transaction_date__gte=month_start,
                transaction_date__lte=today,
            )
            tithe_weeks = week_sums(tithe_month_qs)
            offering_weeks = week_sums(offering_month_qs)

            return {
                "monthly_trend": monthly_trend,
                "this_month": {
                    "tithe_total": str(this_month_tithe),
                    "offering_total": str(this_month_offering),
                    "tithe_by_week": tithe_weeks,
                    "offering_by_week": offering_weeks,
                },
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("tithe_offering_stats", _build, months=period_months)

    # ---------- Analytics: Announcements stats ----------
    def announcements_stats(self) -> dict:
        def _build():
            qs = Announcement.objects.filter(church=self.church)
            total = qs.count()
            by_status = list(qs.values("status").annotate(count=Count("id")))
            by_priority = list(qs.values("priority").annotate(count=Count("id")))
            return {
                "total": total,
                "by_status": by_status,
                "by_priority": by_priority,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("announcements_stats", _build)

    # ---------- Analytics: Member contributions (for treasury dashboard) ----------
    def member_contributions(
        self,
        limit: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict:
        """
        Aggregated income contributions by member for treasury dashboard.
        Returns members who have contributed (via IncomeTransaction with member FK),
        with total amount, last contribution date, and contribution history.
        """
        today = timezone.localdate()
        date_from = date_from or (today - timedelta(days=365))
        date_to = date_to or today

        def _build():
            from django.db.models import Max

            base = IncomeTransaction.objects.filter(
                church=self.church,
                deleted_at__isnull=True,
                transaction_date__gte=date_from,
                transaction_date__lte=date_to,
                member__isnull=False,
            ).select_related("member", "category")

            # Aggregate by member
            agg = (
                base.values("member_id")
                .annotate(
                    total=Sum("amount"),
                    last_date=Max("transaction_date"),
                    count=Count("id"),
                )
                .order_by("-total")[:limit]
            )

            result = []
            for row in agg:
                member = Member.objects.filter(
                    id=row["member_id"], church=self.church, deleted_at__isnull=True
                ).first()
                if not member:
                    continue

                # Recent contributions for this member
                contribs = (
                    base.filter(member_id=row["member_id"])
                    .order_by("-transaction_date")[:10]
                    .values("transaction_date", "amount", "category__name")
                )
                contributions = [
                    {
                        "date": str(c["transaction_date"]),
                        "amount": float(c["amount"]),
                        "type": c["category__name"] or "Other",
                    }
                    for c in contribs
                ]

                result.append(
                    {
                        "id": str(member.id),
                        "name": member.full_name or "Unknown",
                        "avatar": getattr(member, "profile_photo", None) or "",
                        "phone": member.phone_number or "",
                        "status": member.membership_status or "ACTIVE",
                        "total_amount": float(row["total"]),
                        "last_date": str(row["last_date"]),
                        "contributions": contributions,
                    }
                )
            return {
                "contributors": result,
                "period": {"date_from": str(date_from), "date_to": str(date_to)},
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached(
            "member_contributions",
            _build,
            limit=limit,
            df=str(date_from),
            dt=str(date_to),
        )

    # ---------- Analytics: Department budgets (for treasury dashboard) ----------
    def department_budgets(self) -> dict:
        """
        Per-department budget allocated vs utilized for treasury dashboard.
        allocated = sum of Program.total_expenses (expense budget) per department.
        utilized = sum of ExpenseTransaction amounts per department.
        """
        from treasury.models import ExpenseTransaction

        def _build():
            depts = Department.objects.filter(
                church=self.church, deleted_at__isnull=True, is_active=True
            ).order_by("name")

            result = []
            for d in depts:
                # Allocated: program expense budgets
                allocated = Program.objects.filter(department=d).aggregate(
                    s=Sum("total_expenses")
                )["s"] or Decimal("0")
                # Utilized: actual expense transactions for this department
                utilized = ExpenseTransaction.objects.filter(
                    department=d, church=self.church, deleted_at__isnull=True
                ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
                result.append(
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "allocated": float(allocated),
                        "utilized": float(utilized),
                    }
                )
            return {
                "departments": result,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("department_budgets", _build)

    # ---------- Analytics: Departments performance ----------
    def departments_performance(self) -> dict:
        def _build():
            depts = Department.objects.filter(
                church=self.church, deleted_at__isnull=True
            )
            result = []
            for d in depts:
                member_count = MemberDepartment.objects.filter(
                    department=d, deleted_at__isnull=True
                ).count()
                programs = Program.objects.filter(department=d)
                completed = programs.filter(status="COMPLETED").count()
                in_progress = programs.filter(status="IN_PROGRESS").count()
                approved = programs.filter(status="APPROVED").count()
                result.append(
                    {
                        "department_id": str(d.id),
                        "department_name": d.name,
                        "member_count": member_count,
                        "programs_total": programs.count(),
                        "programs_completed": completed,
                        "programs_in_progress": in_progress,
                        "programs_approved": approved,
                    }
                )
            return {
                "departments": result,
                "generated_at": timezone.now().isoformat(),
            }

        return self._get_cached("departments_performance", _build)
