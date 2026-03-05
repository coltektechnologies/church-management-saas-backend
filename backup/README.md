# Backup & Data Export (Phase 5.4)

All endpoints require **platform admin** (JWT with `is_platform_admin=True`).

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/backup/create/` | Create full DB backup (dumpdata). Body: optional `notes`. |
| GET | `/api/admin/backup/list/` | List backup records (id, path, size, created_at). |
| POST | `/api/admin/backup/restore/` | Restore from backup. Body: `backup_id` (UUID). **Destructive.** |
| GET | `/api/admin/export/tenant-data/?church_id=<uuid>` | Export one church's data as JSON (GDPR-style). Returns file download. |
| POST | `/api/admin/import/tenant-data/` | Import tenant data. Body: JSON export, or form `file` / `data`. Optional `target_church_id` to migrate to another church. |

## Automated backup

Celery Beat runs `backup.tasks.run_automated_backup` daily at 02:00. Backups are stored under `BACKUP_ROOT` (default: `media/backups/`). Set `BACKUP_ROOT` in settings or env to change location.

## Tenant export (GDPR)

Exports all church-related data: Church, Users, Members, Departments, Programs, Treasury, Announcements, Files, Reports, AuditLog, etc. Use for data portability or migration. Import can remap to a different church (`target_church_id`) for tenant migration.

## Migrations

```bash
python manage.py migrate backup
```
