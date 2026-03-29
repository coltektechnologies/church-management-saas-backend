# Generated manually: add HEAD vs ASSISTANT roles on DepartmentHead.

from django.db import migrations, models


def dedupe_department_heads(apps, schema_editor):
    DepartmentHead = apps.get_model("departments", "DepartmentHead")
    seen_departments = set()
    for dh in DepartmentHead.objects.all().order_by("id"):
        dept_id = dh.department_id
        if dept_id in seen_departments:
            dh.delete()
        else:
            seen_departments.add(dept_id)


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="departmenthead",
            name="head_role",
            field=models.CharField(
                choices=[("HEAD", "Department head"), ("ASSISTANT", "Assistant head")],
                db_index=True,
                default="HEAD",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(dedupe_department_heads, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="departmenthead",
            unique_together={("department", "head_role")},
        ),
    ]
