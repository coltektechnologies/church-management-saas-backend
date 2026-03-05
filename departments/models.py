import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
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

    # Elder in charge of this department (first approval step for programs)
    elder_in_charge = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_as_elder",
        verbose_name=_("Elder in charge"),
        help_text=_(
            "The elder who oversees this department and approves programs first"
        ),
    )

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
    assigned_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

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
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        db_column="church_id",
        verbose_name=_("Church"),
        help_text=_("The church this department head belongs to"),
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "department_heads"
        unique_together = ("department", "member")
        verbose_name = _("Department Head")
        verbose_name_plural = _("Department Heads")

    def clean(self):
        super().clean()

        # If we have a department but no church, set church from department
        if not self.church_id and self.department_id:
            self.church = self.department.church

        # If we have a member but no church, set church from member
        if not self.church_id and self.member_id:
            self.church = self.member.church

        # If we still don't have a church, we can't validate
        if not self.church_id:
            return

        # Ensure department belongs to the selected church
        if self.department_id and self.department.church_id != self.church_id:
            raise ValidationError(
                {
                    "department": _(
                        "Selected department does not belong to the selected church"
                    )
                }
            )

        # Ensure member belongs to the selected church
        if self.member_id and self.member.church_id != self.church_id:
            raise ValidationError(
                {"member": _("Selected member does not belong to the selected church")}
            )

    def save(self, *args, **kwargs):
        # Set church from department if not set
        if not self.church_id and self.department_id:
            self.church = self.department.church

        # Ensure member belongs to the same church
        if self.member_id and not self.church_id == self.member.church_id:
            self.church = self.member.church

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member.full_name} - {self.department.name}"


class ProgramBudgetItem(models.Model):
    """Budget item for a program (income or expense)"""

    BUDGET_ITEM_TYPES = [
        ("INCOME", "Income"),
        ("EXPENSE", "Expense"),
    ]

    BUDGET_CATEGORIES = [
        ("PERSONNEL_STAFF", "Personnel & Staff"),
        ("PROGRAM_ACTIVITY", "Program & Activity"),
        ("EQUIPMENT_SUPPLIES", "Equipment & Supplies"),
        ("CUSTOM", "Custom"),
    ]

    INCOME_SOURCES = [
        ("CHURCH_COFFERS", "Church Coffers"),
        ("SILVER_COLLECTION", "Silver Collection"),
        ("HARVEST", "Harvest"),
        ("DONATION", "Donation"),
        ("OUTSOURCE", "Outsource"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        "Program",
        on_delete=models.CASCADE,
        related_name="budget_items",
        null=True,
        blank=True,
    )
    item_type = models.CharField(
        max_length=10, choices=BUDGET_ITEM_TYPES, default="EXPENSE"
    )
    category = models.CharField(
        max_length=30,
        choices=BUDGET_CATEGORIES,
        blank=True,
        null=True,
        help_text="Budget category for 5-step submission flow",
    )
    income_source = models.CharField(
        max_length=20, choices=INCOME_SOURCES, null=True, blank=True
    )
    description = models.CharField(max_length=300)
    quantity = models.PositiveIntegerField(
        default=1, help_text="Quantity for expense items"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Total amount in GHS (quantity × unit price)",
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "program_budget_items"
        verbose_name = _("Program Budget Item")
        verbose_name_plural = _("Program Budget Items")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.description} - {self.amount}"


class Program(models.Model):
    """Combined Program, Budget and Activity tracking"""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted for Review"),  # Waiting for Elder
        ("ELDER_APPROVED", "Approved by Department Elder"),  # Waiting for Secretariat
        ("SECRETARIAT_APPROVED", "Approved by Secretariat"),  # Waiting for Treasury
        ("TREASURY_APPROVED", "Approved by Treasury"),
        ("APPROVED", "Fully Approved"),
        ("REJECTED", "Rejected"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    SUBMISSION_TYPES = [
        ("BOTH", "Both Secretariat & Treasury"),
        ("SECRETARIAT_ONLY", "Secretariat Only"),
        ("TREASURY_ONLY", "Treasury Only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="programs"
    )
    church = models.ForeignKey(Church, on_delete=models.CASCADE)

    # Program Details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True, null=True)

    # Step 1: Basic Information (5-step flow)
    fiscal_year = models.PositiveIntegerField(
        null=True, blank=True, help_text="Budget fiscal year"
    )
    budget_title = models.CharField(max_length=300, blank=True, null=True)
    budget_overview = models.TextField(blank=True, null=True)
    submitted_by_department_head = models.BooleanField(
        default=True,
        help_text="False if submitter selected a department they are not head of",
    )
    department_head_name = models.CharField(max_length=200, blank=True, null=True)
    department_head_email = models.EmailField(blank=True, null=True)
    department_head_phone = models.CharField(max_length=50, blank=True, null=True)

    # Step 3: Justification
    strategic_objectives = models.TextField(blank=True, null=True)
    expected_impact = models.TextField(blank=True, null=True)
    ministry_benefits = models.TextField(blank=True, null=True)
    previous_year_comparison = models.TextField(blank=True, null=True)
    number_of_beneficiaries = models.PositiveIntegerField(null=True, blank=True)
    implementation_timeline = models.TextField(blank=True, null=True)

    # Budget Summary (auto-calculated)
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Submission and Approvals
    submission_type = models.CharField(
        max_length=20,
        choices=SUBMISSION_TYPES,
        default="BOTH",
        help_text="Which departments need to approve this program?",
    )

    def budget_summary(self):
        return f"Income: {self.total_income:.2f}, Expenses: {self.total_expenses:.2f}, Net: {self.net_budget:.2f}"

    submitted_to_secretariat = models.BooleanField(default=False)
    submitted_to_treasury = models.BooleanField(default=False)
    secretariat_approved = models.BooleanField(default=False)
    treasury_approved = models.BooleanField(default=False)
    secretariat_approved_at = models.DateTimeField(null=True, blank=True)
    treasury_approved_at = models.DateTimeField(null=True, blank=True)
    secretariat_notes = models.TextField(blank=True, null=True)
    treasury_notes = models.TextField(blank=True, null=True)

    # Department Elder (first approval step)
    elder_approved = models.BooleanField(default=False)
    elder_approved_at = models.DateTimeField(null=True, blank=True)
    elder_notes = models.TextField(blank=True, null=True)
    elder_rejected_at = models.DateTimeField(null=True, blank=True)
    elder_rejected_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="elder_rejected_programs",
    )

    # Tracking
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_programs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_programs",
    )
    rejection_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "programs"
        verbose_name = _("Program")
        verbose_name_plural = _("Programs")
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Calculate budget totals before saving
        self._calculate_budget_totals()
        super().save(*args, **kwargs)

    def _calculate_budget_totals(self):
        """Calculate and update budget totals"""
        if not self.pk:  # New instance
            return

        items = self.budget_items.all()
        self.total_income = sum(
            item.amount for item in items if item.item_type == "INCOME"
        )
        self.total_expenses = sum(
            item.amount for item in items if item.item_type == "EXPENSE"
        )
        self.net_budget = self.total_income - self.total_expenses

    def submit_for_approval(self, submit_to_secretariat=True, submit_to_treasury=True):
        """Submit program for approval to selected departments"""
        if self.status != "DRAFT" and self.status != "REJECTED":
            return False

        self.status = "SUBMITTED"
        self.submitted_at = timezone.now()

        if submit_to_secretariat:
            self.submitted_to_secretariat = True
        if submit_to_treasury:
            self.submitted_to_treasury = True

        # Auto-approve if not required to submit to a department
        if not self.submitted_to_secretariat and not self.submitted_to_treasury:
            self.status = "APPROVED"
            self.approved_at = timezone.now()

        self.save()
        return True

    def approve(self, approved_by, department_type, notes=None):
        """Approve program for a specific department"""
        if department_type == "SECRETARIAT":
            self.secretariat_approved = True
            self.secretariat_approved_at = timezone.now()
            self.secretariat_notes = notes
        elif department_type == "TREASURY":
            self.treasury_approved = True
            self.treasury_approved_at = timezone.now()
            self.treasury_notes = notes

        # Check if all required approvals are complete
        secretariat_required = self.submitted_to_secretariat
        treasury_required = self.submitted_to_treasury

        secretariat_ok = not secretariat_required or self.secretariat_approved
        treasury_ok = not treasury_required or self.treasury_approved

        if secretariat_ok and treasury_ok:
            self.status = "APPROVED"
            self.approved_at = timezone.now()
        elif secretariat_ok and not treasury_required:
            self.status = "SECRETARIAT_APPROVED"
        elif treasury_ok and not secretariat_required:
            self.status = "TREASURY_APPROVED"

        self.save()
        return True

    def reject(self, rejected_by, reason):
        """Reject the program"""
        self.status = "REJECTED"
        self.rejected_at = timezone.now()
        self.rejected_by = rejected_by
        self.rejection_reason = reason
        self.save()
        return True

    @property
    def is_fully_approved(self):
        """Check if program has all required approvals"""
        secretariat_ok = not self.submitted_to_secretariat or self.secretariat_approved
        treasury_ok = not self.submitted_to_treasury or self.treasury_approved
        return secretariat_ok and treasury_ok

    @property
    def is_approved(self):
        return self.status == "APPROVED"

    @property
    def duration_days(self):
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1


class DepartmentActivity(models.Model):
    """Department Activity - Phase 1B"""

    ACTIVITY_STATUS_CHOICES = [
        ("PLANNED", "Planned"),
        ("ONGOING", "Ongoing"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="activities",
        db_column="department_id",
    )
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=ACTIVITY_STATUS_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()

    location = models.CharField(max_length=200, blank=True, null=True)
    expected_attendance = models.IntegerField(blank=True, null=True)
    actual_attendance = models.IntegerField(blank=True, null=True)

    budget_allocated = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_spent = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_activities",
        db_column="created_by_id",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "department_activities"
        verbose_name = _("Department Activity")
        verbose_name_plural = _("Department Activities")
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["department", "status"]),
            models.Index(fields=["church", "deleted_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["start_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.department.name}"


class ProgramDocument(models.Model):
    """Supporting document for a program (max 10MB per file)"""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="documents",
        db_column="program_id",
    )
    file = models.FileField(upload_to="program_documents/%Y/%m/", max_length=500)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "program_documents"
        verbose_name = _("Program Document")
        verbose_name_plural = _("Program Documents")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename or str(self.file.name)

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, "size"):
            self.file_size = self.file.size
        super().save(*args, **kwargs)
