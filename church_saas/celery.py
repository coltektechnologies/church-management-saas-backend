from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")

app = Celery("church_saas")

# Configure Celery using settings from Django settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs
app.autodiscover_tasks()

# Celery Beat Schedule (for periodic tasks)
app.conf.beat_schedule = {
    # Process scheduled notifications every 5 minutes
    "process-scheduled-notifications": {
        "task": "notifications.tasks.process_scheduled_notifications",
        "schedule": crontab(minute="*/5"),
    },
    # Process recurring notification schedules every 5 minutes (daily/weekly/monthly/yearly)
    "process-recurring-notification-schedules": {
        "task": "notifications.tasks.process_recurring_notification_schedules",
        "schedule": crontab(minute="*/5"),
    },
    # Send service reminders every Saturday
    "send-service-reminders": {
        "task": "notifications.tasks.send_service_reminders",
        "schedule": crontab(day_of_week=6, hour=10, minute=0),
    },
    # Send birthday greetings daily
    "send-birthday-greetings": {
        "task": "notifications.tasks.send_birthday_greetings",
        "schedule": crontab(hour=8, minute=0),
    },
    # Run scheduled reports every hour
    "run-scheduled-reports": {
        "task": "reports.tasks.run_scheduled_reports",
        "schedule": crontab(minute=0),
    },
    # File cleanup: purge soft-deleted files from Cloudinary daily
    "cleanup-deleted-files": {
        "task": "files.tasks.cleanup_deleted_files",
        "schedule": crontab(hour=3, minute=0),
    },
    # Automated full DB backup daily at 02:00
    "run-automated-backup": {
        "task": "backup.tasks.run_automated_backup",
        "schedule": crontab(hour=2, minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
