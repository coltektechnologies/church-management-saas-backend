# Reports & Analytics (Phase 4)

## Overview

The `reports` app provides a generic report generation engine with filtering, date ranges, caching, scheduled execution, and export to PDF, Excel, and CSV.

## Features

- **Generic report service** (`reports.services.ReportGenerationService`): single entry point for all report types with optional caching
- **Report filtering & date ranges**: query params `date_from`, `date_to`, plus filters like `membership_status`, `status`
- **Caching**: in-memory (Django cache) + DB (`ReportCache` model) with configurable TTL
- **Scheduled reports**: `ScheduledReport` model + Celery Beat task `reports.tasks.run_scheduled_reports` (hourly)
- **Exports**: PDF (reportlab), Excel (openpyxl), CSV (stdlib) via `?format=pdf|xlsx|csv`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/members/` | Members report |
| GET | `/api/reports/members/growth/` | Members growth by month |
| GET | `/api/reports/members/demographics/` | Demographics (gender, status, etc.) |
| GET | `/api/reports/departments/` | Departments summary |
| GET | `/api/reports/finance/income/` | Income report |
| GET | `/api/reports/finance/expenses/` | Expenses report |
| GET | `/api/reports/finance/balance-sheet/` | Balance sheet |
| GET | `/api/reports/finance/cash-flow/` | Cash flow |
| GET | `/api/reports/announcements/` | Announcements report |
| GET | `/api/reports/audit-trail/` | Audit trail |
| POST | `/api/reports/custom/` | Custom report (body: `report_type`, `date_from`, `date_to`, `filters`) |
| GET | `/api/reports/scheduled/` | List scheduled reports |
| POST | `/api/reports/schedule/` | Create scheduled report |

All GET report endpoints accept optional query params:

- `date_from`, `date_to`: YYYY-MM-DD
- `format`: `json` (default), `pdf`, `xlsx`, `csv` (returns file download)

## Permissions

Views use `IsAuthenticated`. Church context is taken from `request.current_church` or `request.user.church`. You can add a custom permission (e.g. `REPORTS.VIEW`) in `accounts.permissions` and apply it to report views.

## Running migrations

```bash
python manage.py migrate reports
```

## Celery

Scheduled reports run hourly via Celery Beat (`reports.tasks.run_scheduled_reports`). Ensure Celery worker and beat are running.
