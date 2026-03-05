# Generated migration for files app

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChurchFile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("public_id", models.CharField(db_index=True, max_length=500)),
                ("secure_url", models.URLField(max_length=1000)),
                ("resource_type", models.CharField(default="image", max_length=20)),
                (
                    "cloudinary_version",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("folder", models.CharField(max_length=300)),
                ("subfolder", models.CharField(blank=True, default="", max_length=100)),
                ("original_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("is_image", models.BooleanField(default=False)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "church",
                    models.ForeignKey(
                        db_column="church_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="church_files",
                        to="accounts.church",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_files",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Church file",
                "verbose_name_plural": "Church files",
                "db_table": "church_files",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="churchfile",
            index=models.Index(
                fields=["church", "deleted_at"], name="church_file_church__idx"
            ),
        ),
        migrations.AddIndex(
            model_name="churchfile",
            index=models.Index(
                fields=["church", "subfolder"], name="church_file_subfolder_idx"
            ),
        ),
    ]
