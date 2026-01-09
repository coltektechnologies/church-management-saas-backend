import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Church
from members.models import Member


class Department(models.Model):
    """Department model - Phase 1B"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="departments",
        db_column="church_id",
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "departments"
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        unique_together = ("church", "code")
        indexes = [
            models.Index(fields=["church", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.church.name})"


class MemberDepartment(models.Model):
    """Member-Department assignment - Phase 1B"""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, db_column="member_id")
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, db_column="department_id"
    )
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")
    role_in_department = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = "member_departments"
        unique_together = ("member", "department")
        verbose_name = _("Member Department")
        verbose_name_plural = _("Member Departments")


class DepartmentHead(models.Model):
    """Department Head assignment - Phase 1B"""

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="heads",
        db_column="department_id",
    )
    member = models.ForeignKey(Member, on_delete=models.CASCADE, db_column="member_id")
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "department_heads"
        unique_together = ("department", "member")
        verbose_name = _("Department Head")
        verbose_name_plural = _("Department Heads")

    def __str__(self):
        return f"{self.member.full_name} - {self.department.name}"
