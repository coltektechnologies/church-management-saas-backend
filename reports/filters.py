"""
Report query filters: date range and common filter params.
"""

from datetime import date

from django.utils import timezone


def parse_date(value: str) -> date | None:
    """Parse YYYY-MM-DD string to date."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, TypeError):
        return None


def get_report_filters(request) -> dict:
    """
    Build filters dict from request query params (excludes date range; use get_date_range_from_request).
    - membership_status: for member reports
    - status: for announcements
    - department_id: optional scope
    """
    filters = {}
    if request.query_params.get("membership_status"):
        filters["membership_status"] = request.query_params.get("membership_status")
    if request.query_params.get("status"):
        filters["status"] = request.query_params.get("status")
    if request.query_params.get("department_id"):
        filters["department_id"] = request.query_params.get("department_id")
    return filters


def get_date_range_from_request(request) -> tuple[date | None, date | None]:
    """Return (date_from, date_to) from query params."""
    return (
        parse_date(request.query_params.get("date_from") or ""),
        parse_date(request.query_params.get("date_to") or ""),
    )
