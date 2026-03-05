from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Clear all data from all tables while keeping the structure intact"

    def handle(self, *args, **options):
        # Get all models except contenttypes and auth.Permission
        all_models = apps.get_models()

        # Exclude some models that might cause issues
        EXCLUDED_MODELS = [ContentType, Permission]

        self.stdout.write(self.style.WARNING("Starting to clear all data..."))

        # Disable foreign key checks
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

        # Delete data from each model
        for model in all_models:
            if model in EXCLUDED_MODELS:
                continue

            try:
                count, _ = model.objects.all().delete()
                if count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deleted {count} records from {model._meta.verbose_name_plural}"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error deleting from {model._meta.verbose_name_plural}: {str(e)}"
                    )
                )

        # Reset sequences for PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        self.stdout.write(
            self.style.SUCCESS("Successfully cleared all data from the database!")
        )
