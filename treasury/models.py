import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User
from departments.models import Department
from members.models import Member

# ==========================================
# INCOME MODELS
# ==========================================

# Church / conference split for harvest income (must match IncomeCategory.code for those rows).
HARVEST_ALLOCATION_CODES = frozenset(
    {"HARVEST", "ANNUAL_HARVEST", "THANKSGIVING_HARVEST"}
)


class IncomeCategory(models.Model):
    """Income categories (Tithe, Offerings, etc.)"""

    PREDEFINED_CATEGORIES = [
        ("TITHE", "Tithe"),
        ("GENERAL_OFFERING", "General Offering"),
        ("LOOSE_OFFERING", "Loose Offering"),
        ("SABBATH_SCHOOL", "Sabbath School Offering"),
        ("PROJECT_OFFERING", "Project Offering"),
        ("THANKSGIVING", "Thanksgiving Offering"),
        ("HARVEST", "Harvest"),
        ("ANNUAL_HARVEST", "Annual Harvest"),
        ("THANKSGIVING_HARVEST", "Thanksgiving Harvest"),
        ("SPECIAL_OFFERING", "Special Offering"),
        ("DONATION", "Donation"),
        ("FUNDRAISING", "Fundraising"),
        ("OTHER", "Other Income"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="income_categories",
        db_column="church_id",
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "income_categories"
        verbose_name = _("Income Category")
        verbose_name_plural = _("Income Categories")
        unique_together = ("church", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.church.name})"


def ensure_default_income_categories_for_church(church):
    """
    Create standard income categories (Tithe, Offering, …) when a church has none.

    Used by the income category list API so new churches are usable without manual
    seeding. Idempotent after the first row exists. Concurrent first requests may hit
    IntegrityError; that is ignored so one winning transaction is enough.
    """
    if church is None:
        return
    if IncomeCategory.objects.filter(church=church).exists():
        return
    try:
        with transaction.atomic():
            for code, name in IncomeCategory.PREDEFINED_CATEGORIES:
                IncomeCategory.objects.create(
                    church=church,
                    code=code,
                    name=name,
                    description="",
                    is_active=True,
                )
    except IntegrityError:
        pass


class MemberPledge(models.Model):
    """Member giving commitment; treasury records payments against it via IncomeTransaction.pledge."""

    STATUS_ACTIVE = "ACTIVE"
    STATUS_FULFILLED = "FULFILLED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Active")),
        (STATUS_FULFILLED, _("Fulfilled")),
        (STATUS_CANCELLED, _("Cancelled")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="member_pledges",
        db_column="church_id",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="pledges",
    )
    pledge_year = models.PositiveIntegerField(
        help_text=_("Calendar year this pledge applies to."),
    )
    title = models.CharField(max_length=200, blank=True)
    target_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    notes = models.TextField(blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "member_pledges"
        verbose_name = _("Member pledge")
        verbose_name_plural = _("Member pledges")
        ordering = ["-pledge_year", "-created_at"]
        indexes = [
            models.Index(fields=["church", "member", "pledge_year"]),
        ]

    def __str__(self):
        return f"Pledge {self.pledge_year} — {self.target_amount}"

    def fulfilled_amount(self):
        total = self.income_payments.filter(deleted_at__isnull=True).aggregate(
            total=Sum("amount")
        )["total"]
        return total if total is not None else Decimal("0.00")

    def sync_status_from_payments(self):
        """Set fulfilled when sum of linked income reaches target (excluding cancelled)."""
        if self.status == self.STATUS_CANCELLED:
            return
        total = self.fulfilled_amount()
        if total >= self.target_amount:
            if self.status != self.STATUS_FULFILLED:
                self.status = self.STATUS_FULFILLED
                self.fulfilled_at = timezone.now()
                self.save(update_fields=["status", "fulfilled_at", "updated_at"])
        elif self.status == self.STATUS_FULFILLED:
            self.status = self.STATUS_ACTIVE
            self.fulfilled_at = None
            self.save(update_fields=["status", "fulfilled_at", "updated_at"])


class IncomeTransaction(models.Model):
    """Income/Revenue transactions"""

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHEQUE", "Cheque"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CARD", "Card Payment"),
        ("OTHER", "Other"),
    ]

    SERVICE_TYPE_CHOICES = [
        ("SABBATH_SERVICE", "Sabbath Service"),
        ("MID_WEEK", "Mid-week Service"),
        ("SPECIAL_EVENT", "Special Event"),
        ("WALK_IN", "Walk-in Contribution"),
        ("ONLINE", "Online Contribution"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="income_transactions",
        db_column="church_id",
    )

    # Transaction Details
    receipt_number = models.CharField(max_length=50, unique=True)
    transaction_date = models.DateField()
    category = models.ForeignKey(
        IncomeCategory, on_delete=models.PROTECT, related_name="transactions"
    )
    service_type = models.CharField(
        max_length=30, choices=SERVICE_TYPE_CHOICES, default="SABBATH_SERVICE"
    )

    # Amount Details
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    amount_in_words = models.CharField(max_length=500, blank=True)

    # Payment Details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=150, blank=True, null=True)

    # Contributor Details
    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="income_contributions",
    )
    contributor_name = models.CharField(max_length=200, blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)

    # Allocation (if project-specific)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="income_allocations",
    )
    project_name = models.CharField(max_length=200, blank=True, null=True)

    pledge = models.ForeignKey(
        MemberPledge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="income_payments",
    )

    # Recording Details
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="recorded_income"
    )
    witnessed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="witnessed_income",
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "income_transactions"
        verbose_name = _("Income Transaction")
        verbose_name_plural = _("Income Transactions")
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["church", "transaction_date"]),
            models.Index(fields=["category", "transaction_date"]),
            models.Index(fields=["receipt_number"]),
            models.Index(fields=["member"]),
            models.Index(fields=["pledge"]),
        ]

    def __str__(self):
        return f"{self.receipt_number} - {self.amount} ({self.category.name})"


class IncomeAllocation(models.Model):
    """
    Auto-created split of income between Church and Conference.

    Rules (see treasury.signals.create_income_allocations):
    Tithe: 100% Conference. General + loose offering: 50% / 50%.
    Harvest (HARVEST, ANNUAL_HARVEST, THANKSGIVING_HARVEST): 80% Church, 20% Conference.
    All other income: 100% Church.
    """

    DESTINATION_CHURCH = "CHURCH"
    DESTINATION_CONFERENCE = "CONFERENCE"

    DESTINATION_CHOICES = [
        (DESTINATION_CHURCH, "Church"),
        (DESTINATION_CONFERENCE, "Conference"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        IncomeTransaction,
        on_delete=models.CASCADE,
        related_name="allocations",
        db_column="income_transaction_id",
    )
    destination = models.CharField(max_length=20, choices=DESTINATION_CHOICES)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Percentage of total (e.g. 50.00, 100.00)",
    )

    class Meta:
        db_table = "income_allocations"
        verbose_name = _("Income Allocation")
        verbose_name_plural = _("Income Allocations")
        ordering = ["transaction", "destination"]

    def __str__(self):
        return f"{self.transaction.receipt_number} → {self.destination}: {self.amount} ({self.percentage}%)"


# ==========================================
# EXPENSE MODELS
# ==========================================


class ExpenseCategory(models.Model):
    """Expense categories"""

    PREDEFINED_CATEGORIES = [
        ("UTILITIES", "Utilities"),
        ("MAINTENANCE", "Maintenance & Repairs"),
        ("SALARIES", "Staff Salaries & Allowances"),
        ("EVENT_EXPENSES", "Event Expenses"),
        ("OFFICE_SUPPLIES", "Office Supplies"),
        ("MINISTRY_PROGRAMS", "Ministry Programs"),
        ("OUTREACH", "Outreach & Evangelism"),
        ("TRANSPORTATION", "Transportation"),
        ("BANK_CHARGES", "Bank Charges"),
        ("OTHER", "Other Expenses"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="expense_categories",
        db_column="church_id",
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expense_categories"
        verbose_name = _("Expense Category")
        verbose_name_plural = _("Expense Categories")
        unique_together = ("church", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.church.name})"


class ExpenseTransaction(models.Model):
    """Expense/Payment transactions"""

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHEQUE", "Cheque"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CARD", "Card Payment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="expense_transactions",
        db_column="church_id",
    )

    # Transaction Details
    voucher_number = models.CharField(max_length=50, unique=True)
    transaction_date = models.DateField()
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="transactions"
    )

    # Department/Cost Center
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="expenses"
    )

    # Amount Details
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    amount_in_words = models.CharField(max_length=500, blank=True)

    # Payment Details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=150, blank=True, null=True)

    # Recipient Details
    paid_to = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=50, blank=True, null=True)
    recipient_id = models.CharField(max_length=50, blank=True, null=True)

    # Description
    description = models.TextField()

    # Authorization
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_expenses",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="recorded_expenses"
    )

    # Linked to expense request (if applicable)
    expense_request = models.ForeignKey(
        "ExpenseRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "expense_transactions"
        verbose_name = _("Expense Transaction")
        verbose_name_plural = _("Expense Transactions")
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["church", "transaction_date"]),
            models.Index(fields=["category", "transaction_date"]),
            models.Index(fields=["department", "transaction_date"]),
            models.Index(fields=["voucher_number"]),
        ]

    def __str__(self):
        return f"{self.voucher_number} - {self.amount} ({self.category.name})"


# ==========================================
# EXPENSE REQUEST & APPROVAL WORKFLOW
# ==========================================


class ExpenseRequest(models.Model):
    """Expense request with approval workflow"""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("DEPT_HEAD_APPROVED", "Department Head Approved"),
        ("TREASURER_APPROVED", "Treasurer Approved"),
        ("FIRST_ELDER_APPROVED", "First Elder Approved"),
        ("APPROVED", "Fully Approved"),
        ("REJECTED", "Rejected"),
        ("DISBURSED", "Disbursed"),
        ("CANCELLED", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="expense_requests",
        db_column="church_id",
    )

    # Request Details
    request_number = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="expense_requests"
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expense_requests"
    )

    # Amount & Description
    amount_requested = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    amount_approved = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    purpose = models.TextField()
    justification = models.TextField()
    required_by_date = models.DateField()

    # Status & Priority
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT")
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM"
    )

    # Requester
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_expense_requests",
    )
    requested_at = models.DateTimeField(null=True, blank=True)

    # Approval Chain
    dept_head_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dept_head_expense_approvals",
    )
    dept_head_approved_at = models.DateTimeField(null=True, blank=True)

    first_elder_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="first_elder_expense_approvals",
    )
    first_elder_approved_at = models.DateTimeField(null=True, blank=True)

    treasurer_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treasurer_expense_approvals",
    )
    treasurer_approved_at = models.DateTimeField(null=True, blank=True)

    # Rejection/Comments
    rejection_reason = models.TextField(blank=True, null=True)
    approval_comments = models.TextField(blank=True, null=True)

    # Disbursement
    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursed_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expense_requests"
        verbose_name = _("Expense Request")
        verbose_name_plural = _("Expense Requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "status"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["request_number"]),
            models.Index(fields=["required_by_date"]),
        ]

    def __str__(self):
        return f"{self.request_number} - {self.amount_requested} ({self.get_status_display()})"

    @property
    def approval_progress(self):
        """Calculate approval progress percentage"""
        stages = [
            self.dept_head_approved_at,
            self.treasurer_approved_at,
            self.first_elder_approved_at,
        ]
        completed = sum(1 for stage in stages if stage is not None)
        return (completed / 3) * 100


# ==========================================
# ASSETS
# ==========================================


class Asset(models.Model):
    """Church assets tracking"""

    ASSET_CATEGORY_CHOICES = [
        ("LAND_BUILDING", "Land & Buildings"),
        ("FURNITURE", "Furniture & Fixtures"),
        ("EQUIPMENT", "Equipment"),
        ("VEHICLE", "Vehicles"),
        ("IT_EQUIPMENT", "IT Equipment"),
        ("MUSICAL_INSTRUMENTS", "Musical Instruments"),
        ("BOOKS", "Books & Library"),
        ("OTHER", "Other Assets"),
    ]

    CONDITION_CHOICES = [
        ("EXCELLENT", "Excellent"),
        ("GOOD", "Good"),
        ("FAIR", "Fair"),
        ("POOR", "Poor"),
        ("DAMAGED", "Damaged"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church, on_delete=models.CASCADE, related_name="assets", db_column="church_id"
    )

    # Asset Details
    name = models.CharField(max_length=200)
    asset_tag = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=30, choices=ASSET_CATEGORY_CHOICES)
    serial_number = models.CharField(max_length=100, blank=True, null=True)

    # Purchase Details
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=15, decimal_places=2)
    supplier = models.CharField(max_length=200, blank=True, null=True)

    # Current Status
    current_value = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default="GOOD"
    )

    # Location & Custodian
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    custodian = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_assets",
    )

    # Warranty & Insurance
    warranty_expiry = models.DateField(null=True, blank=True)
    insurance_policy = models.CharField(max_length=100, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assets"
        verbose_name = _("Asset")
        verbose_name_plural = _("Assets")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["church", "category"]),
            models.Index(fields=["asset_tag"]),
        ]

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"
