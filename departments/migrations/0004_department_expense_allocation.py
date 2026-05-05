# Generated manually for DepartmentExpenseAllocation

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0003_alter_departmenthead_head_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentExpenseAllocation",
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
                    "fiscal_year",
                    models.PositiveIntegerField(
                        help_text="Calendar or fiscal year label (e.g. 2026)."
                    ),
                ),
                (
                    "expense_budget",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Admin-approved expense envelope for this department.",
                        max_digits=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "church",
                    models.ForeignKey(
                        db_column="church_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="department_expense_allocations",
                        to="accounts.church",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        db_column="department_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expense_allocations",
                        to="departments.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Department expense allocation",
                "verbose_name_plural": "Department expense allocations",
                "db_table": "department_expense_allocations",
            },
        ),
        migrations.AddConstraint(
            model_name="departmentexpenseallocation",
            constraint=models.UniqueConstraint(
                fields=("church", "department", "fiscal_year"),
                name="uniq_expense_alloc_church_dept_year",
            ),
        ),
        migrations.AddIndex(
            model_name="departmentexpenseallocation",
            index=models.Index(
                fields=["church", "fiscal_year"],
                name="department_e_church_i_ad84db_idx",
            ),
        ),
    ]
