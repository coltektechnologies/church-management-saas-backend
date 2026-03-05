# Generated manually for 5-step program submission flow

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0003_alter_departmenthead_church"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="programbudgetitem",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PERSONNEL_STAFF", "Personnel & Staff"),
                    ("PROGRAM_ACTIVITY", "Program & Activity"),
                    ("EQUIPMENT_SUPPLIES", "Equipment & Supplies"),
                    ("CUSTOM", "Custom"),
                ],
                help_text="Budget category for 5-step submission flow",
                max_length=30,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="programbudgetitem",
            name="quantity",
            field=models.PositiveIntegerField(
                default=1, help_text="Quantity for expense items"
            ),
        ),
        migrations.AlterField(
            model_name="programbudgetitem",
            name="item_type",
            field=models.CharField(
                choices=[("INCOME", "Income"), ("EXPENSE", "Expense")],
                default="EXPENSE",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="programbudgetitem",
            name="description",
            field=models.CharField(max_length=300),
        ),
        migrations.AlterField(
            model_name="program",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="program",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="fiscal_year",
            field=models.PositiveIntegerField(
                blank=True, help_text="Budget fiscal year", null=True
            ),
        ),
        migrations.AddField(
            model_name="program",
            name="budget_title",
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="budget_overview",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="submitted_by_department_head",
            field=models.BooleanField(
                default=True,
                help_text="False if submitter selected a department they are not head of",
            ),
        ),
        migrations.AddField(
            model_name="program",
            name="department_head_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="department_head_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="department_head_phone",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="strategic_objectives",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="expected_impact",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="ministry_benefits",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="previous_year_comparison",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="number_of_beneficiaries",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="implementation_timeline",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="elder_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="program",
            name="elder_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="elder_notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="elder_rejected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="elder_rejected_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="elder_rejected_programs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="ProgramDocument",
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
                (
                    "file",
                    models.FileField(
                        max_length=500, upload_to="program_documents/%Y/%m/"
                    ),
                ),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                (
                    "file_size",
                    models.PositiveIntegerField(
                        default=0, help_text="File size in bytes"
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "program",
                    models.ForeignKey(
                        db_column="program_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="departments.program",
                    ),
                ),
            ],
            options={
                "verbose_name": "Program Document",
                "verbose_name_plural": "Program Documents",
                "db_table": "program_documents",
                "ordering": ["-uploaded_at"],
            },
        ),
    ]
