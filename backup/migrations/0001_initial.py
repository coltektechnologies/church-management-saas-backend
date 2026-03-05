import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BackupRecord",
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
                ("backup_type", models.CharField(default="full", max_length=20)),
                ("file_path", models.CharField(max_length=500)),
                (
                    "file_size_bytes",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
            ],
            options={"db_table": "backup_records", "ordering": ["-created_at"]},
        ),
    ]
