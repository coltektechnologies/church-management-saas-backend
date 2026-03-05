import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Church(models.Model):
    """Church/Tenant model with subscription support"""

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
        ("TRIAL", "Trial"),
        ("INACTIVE", "Inactive"),
    ]

    CHURCH_SIZE_CHOICES = [
        ("SMALL", "Small (1-100 members)"),
        ("MEDIUM", "Medium (101-500 members)"),
        ("LARGE", "Large (500+ members)"),
    ]

    SUBSCRIPTION_PLAN_CHOICES = [
        ("FREE", "Free - Unlimited"),
        ("TRIAL", "Free Trial (30 Days)"),
        ("BASIC", "Basic - $14/month"),
        ("PREMIUM", "Premium - $20/month"),
        ("ENTERPRISE", "Enterprise - $30/month"),
    ]

    BILLING_CYCLE_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("YEARLY", "Yearly"),
    ]

    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=150, unique=True)
    subdomain = models.CharField(
        max_length=100,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
                message="Subdomain must be 3-63 characters, lowercase letters, numbers, and hyphens only.",
            )
        ],
    )

    # Church Details
    denomination = models.CharField(max_length=150, blank=True, null=True)
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    church_size = models.CharField(
        max_length=20, choices=CHURCH_SIZE_CHOICES, default="SMALL"
    )

    # Contact Information
    phone = models.CharField(max_length=50, blank=True, null=True)

    # Media
    logo = models.ImageField(upload_to="churches/logo", blank=True, null=True)

    # Settings
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="TRIAL")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Subscription fields
    subscription_plan = models.CharField(
        max_length=20, choices=SUBSCRIPTION_PLAN_CHOICES, default="TRIAL"
    )
    billing_cycle = models.CharField(
        max_length=20, choices=BILLING_CYCLE_CHOICES, default="MONTHLY"
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_starts_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    # Payment Integration (Paystack)
    paystack_customer_code = models.CharField(max_length=100, blank=True, null=True)
    paystack_subscription_code = models.CharField(max_length=100, blank=True, null=True)
    last_payment_reference = models.CharField(max_length=100, blank=True, null=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)

    # Additional Settings
    enable_online_giving = models.BooleanField(default=False)
    enable_sms_notifications = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    max_users = models.IntegerField(
        default=50, help_text="Maximum users allowed based on plan"
    )

    class Meta:
        db_table = "churches"
        verbose_name = _("Church")
        verbose_name_plural = _("Churches")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["subdomain"]),
            models.Index(fields=["country", "city"]),
            models.Index(fields=["subscription_plan"]),
        ]

    def __str__(self):
        return self.name

    @property
    def full_domain(self):
        """Get full subdomain URL"""
        return f"{self.subdomain}.opendoor.com"

    @property
    def is_trial_active(self):
        """Check if trial is still active"""
        if self.status == "TRIAL" and self.trial_ends_at:
            return timezone.now() < self.trial_ends_at
        return False

    @property
    def is_subscription_active(self):
        """Check if subscription is active"""
        if self.subscription_ends_at:
            return timezone.now() < self.subscription_ends_at
        return False

    @property
    def days_until_expiry(self):
        """Get days until trial/subscription expires"""
        if self.status == "TRIAL" and self.trial_ends_at:
            delta = self.trial_ends_at - timezone.now()
            return max(0, delta.days)
        elif self.subscription_ends_at:
            delta = self.subscription_ends_at - timezone.now()
            return max(0, delta.days)
        return 0

    @property
    def plan_price(self):
        """Get monthly price for current plan (in GHS - Ghana Cedis)"""
        prices = {
            "FREE": 0,
            "TRIAL": 0,
            "BASIC": 84,  # ~84 GHS/month (≈ $14)
            "PREMIUM": 120,  # ~120 GHS/month (≈ $20)
            "ENTERPRISE": 180,  # ~180 GHS/month (≈ $30)
        }
        return prices.get(self.subscription_plan, 0)

    def activate_subscription(self, plan, billing_cycle, payment_reference):
        """Activate a subscription (paid or free)"""
        from datetime import timedelta

        self.subscription_plan = plan
        self.billing_cycle = billing_cycle
        self.subscription_starts_at = timezone.now()

        # FREE plan: No payment, no expiry, no SMS/email notifications
        if plan == "FREE":
            self.status = "ACTIVE"
            self.subscription_ends_at = None
            self.next_billing_date = None
            self.max_users = 60
            self.last_payment_reference = None
            self.last_payment_date = None
            self.enable_sms_notifications = False
            self.enable_email_notifications = False
        else:
            # Paid plans: Set payment info and expiry
            self.status = "ACTIVE"
            self.last_payment_reference = payment_reference
            self.last_payment_date = timezone.now()

            # Set subscription end date
            if billing_cycle == "MONTHLY":
                self.subscription_ends_at = timezone.now() + timedelta(days=30)
                self.next_billing_date = timezone.now() + timedelta(days=30)
            else:  # YEARLY
                self.subscription_ends_at = timezone.now() + timedelta(days=365)
                self.next_billing_date = timezone.now() + timedelta(days=365)

            # Set max users based on plan
            if plan == "BASIC":
                self.max_users = 50
            elif plan == "PREMIUM":
                self.max_users = 200
            elif plan == "ENTERPRISE":
                self.max_users = 1000

        self.save()

    def suspend(self, reason=None):
        """Suspend church account"""
        self.status = "SUSPENDED"
        self.save()

    def soft_delete(self):
        """Soft delete church"""
        self.deleted_at = timezone.now()
        self.status = "INACTIVE"
        self.save()


class User(AbstractUser):
    """System User model - Enhanced version"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="users",
        db_column="church_id",
        null=True,
        blank=True,
    )

    # Additional Fields
    phone = models.CharField(max_length=50, blank=True, null=True)
    profile_image = models.ImageField(upload_to="users/profiles", blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")],
        blank=True,
        null=True,
    )
    address = models.TextField(blank=True, null=True)

    # Security
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True, null=True)
    is_platform_admin = models.BooleanField(default=False)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)

    # Password Reset
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_expires = models.DateTimeField(null=True, blank=True)

    # Email Verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )

    # Timestamps
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def clean(self):
        super().clean()
        # Ensure email is unique for the church (or unique for platform admins)
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email)

            # Check for duplicate email within the same church
            if self.church:
                qs = self.__class__.objects.filter(
                    email__iexact=self.email, church=self.church
                )
            else:
                # For platform admins (church is None), email must be globally unique
                qs = self.__class__.objects.filter(
                    email__iexact=self.email, church__isnull=True
                )

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if qs.exists():
                raise ValidationError(
                    {
                        "email": "A user with this email already exists for this organization."
                    }
                )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "church"],
                name="unique_email_per_church",
                condition=models.Q(church__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["email"],
                name="unique_email_for_platform_admins",
                condition=models.Q(church__isnull=True),
            ),
        ]
        db_table = "users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        indexes = [
            models.Index(fields=["church", "is_active"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_platform_admin"]),
        ]
        constraints = [
            # Email unique per church (NULL church for platform admins)
            models.UniqueConstraint(
                fields=["email", "church"],
                name="unique_email_per_church",
                condition=models.Q(church__isnull=False),
            ),
            # Email unique for platform admins
            models.UniqueConstraint(
                fields=["email"],
                name="unique_email_platform_admin",
                condition=models.Q(is_platform_admin=True),
            ),
        ]

    def __str__(self):
        if self.is_platform_admin:
            return f"{self.username} (Platform Admin)"
        return f"{self.username} ({self.church.name if self.church else 'No Church'})"

    @property
    def full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def is_account_locked(self):
        """Check if account is locked"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False

    def lock_account(self, minutes=30):
        """Lock account for specified minutes"""
        from datetime import timedelta

        self.account_locked_until = timezone.now() + timedelta(minutes=minutes)
        self.save()

    def unlock_account(self):
        """Unlock user account"""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save()

    def record_failed_login(self):
        """Record failed login attempt"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account(30)  # Lock for 30 minutes
        self.save()

    def record_successful_login(self):
        """Record successful login"""
        self.failed_login_attempts = 0
        self.last_login = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        # Special handling for Guardian's AnonymousUser
        if self.username == "AnonymousUser":
            self.is_platform_admin = True
            self.church = None
        # Platform admins don't need a church
        elif self.is_platform_admin:
            self.church = None
        # Regular users MUST have a church (only check on creation)
        elif not self.church and not self.pk:
            raise ValueError("Regular users must belong to a church")

        super().save(*args, **kwargs)


class Role(models.Model):
    """Role model - Enhanced version"""

    ROLE_LEVELS = [
        (1, "Super Admin (Pastor/First Elder)"),
        (2, "Core Admin (Secretary/Treasurer)"),
        (3, "Department Head"),
        (4, "Member"),
        (5, "Visitor"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    level = models.IntegerField(choices=ROLE_LEVELS)
    description = models.TextField(blank=True, null=True)
    is_system_role = models.BooleanField(
        default=False, help_text="System roles cannot be deleted or modified"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "roles"
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["level", "name"]

    def __str__(self):
        return self.name

    @property
    def permission_count(self):
        """Get count of permissions for this role"""
        return self.rolepermission_set.count()


class Permission(models.Model):
    """Permission model - Enhanced version"""

    MODULE_CHOICES = [
        ("MEMBERS", "Members"),
        ("TREASURY", "Treasury"),
        ("SECRETARIAT", "Secretariat"),
        ("DEPARTMENTS", "Departments"),
        ("ANNOUNCEMENTS", "Announcements"),
        ("REPORTS", "Reports"),
        ("SETTINGS", "Settings"),
        ("ATTENDANCE", "Attendance"),
        ("EVENTS", "Events"),
        ("COMMUNICATIONS", "Communications"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    module = models.CharField(
        max_length=50, choices=MODULE_CHOICES, blank=True, null=True
    )
    is_system_permission = models.BooleanField(
        default=False, help_text="System permissions cannot be deleted"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.module}: {self.code}" if self.module else self.code


class RolePermission(models.Model):
    """Role-Permission mapping - Enhanced version"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, db_column="permission_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_permissions"
        unique_together = ("role", "permission")
        verbose_name = _("Role Permission")
        verbose_name_plural = _("Role Permissions")

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class UserRole(models.Model):
    """User-Role assignment per church - Enhanced version"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_roles"
        unique_together = ("user", "role", "church")
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        indexes = [
            models.Index(fields=["church"]),
            models.Index(fields=["user", "church"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.role.name} @ {self.church.name}"


class AuditLog(models.Model):
    """Audit log for tracking important actions"""

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("PERMISSION_CHANGE", "Permission Change"),
        ("STATUS_CHANGE", "Status Change"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    church = models.ForeignKey(Church, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.model_name} by {self.user}"
