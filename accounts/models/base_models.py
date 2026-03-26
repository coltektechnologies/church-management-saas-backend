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
        ("TRIAL", "Free Trial (30 Days)"),
        ("FREE", "Free Forever (1 Admin)"),
        ("BASIC", "Basic - 29 GHS/month (5 Admins)"),
        ("PREMIUM", "Premium - 79 GHS/month (Unlimited)"),
        ("ENTERPRISE", "Enterprise"),
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
    denomination = models.CharField(max_length=150, blank=True, null=True)

    # Location
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    tagline = models.CharField(max_length=500, blank=True, null=True)
    mission = models.TextField(blank=True, null=True)

    # Theme / Branding (frontend defaults: primary #0B2A4A, accent #2FC4B2)
    primary_color = models.CharField(max_length=20, default="#0B2A4A", blank=True)
    accent_color = models.CharField(max_length=20, default="#2FC4B2", blank=True)
    sidebar_color = models.CharField(max_length=20, default="#0B2A4A", blank=True)
    background_color = models.CharField(max_length=20, default="#F8FAFC", blank=True)
    dark_mode = models.BooleanField(default=False)

    # Service times: [{"id": "uuid", "day": "Sunday", "time": "09:00", "label": "..."}]
    service_times = models.JSONField(default=list, blank=True)

    # Configuration
    church_size = models.CharField(
        max_length=10, choices=CHURCH_SIZE_CHOICES, default="MEDIUM"
    )
    logo = models.ImageField(upload_to="church_logos/", blank=True, null=True)
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=3, default="GHS")
    max_users = models.PositiveIntegerField(default=50)

    # Subscription
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    subscription_plan = models.CharField(
        max_length=20, choices=SUBSCRIPTION_PLAN_CHOICES, default="TRIAL"
    )
    billing_cycle = models.CharField(
        max_length=10, choices=BILLING_CYCLE_CHOICES, blank=True, null=True
    )
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    subscription_starts_at = models.DateTimeField(blank=True, null=True)
    subscription_ends_at = models.DateTimeField(blank=True, null=True)
    next_billing_date = models.DateTimeField(blank=True, null=True)

    # Payment Integration
    paystack_customer_code = models.CharField(max_length=100, blank=True, null=True)
    paystack_subscription_code = models.CharField(max_length=100, blank=True, null=True)
    last_payment_reference = models.CharField(max_length=100, blank=True, null=True)
    last_payment_date = models.DateTimeField(blank=True, null=True)

    # Features
    enable_online_giving = models.BooleanField(default=False)
    enable_sms_notifications = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    # Platform admins can turn this off to block all tenant logins/API access (JWT + login).
    platform_access_enabled = models.BooleanField(
        default=True,
        help_text="When False, church users cannot log in or use the API until re-enabled.",
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Church"
        verbose_name_plural = "Churches"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def full_domain(self):
        """Return the full domain for the church"""
        from django.conf import settings

        return f"{self.subdomain}.{settings.ROOT_DOMAIN}"

    @property
    def is_trial_active(self):
        """Check if the trial is still active"""
        # For FREE plans, always return True as they don't expire
        if self.subscription_plan == "FREE" and self.status == "TRIAL":
            return True

        if self.status != "TRIAL" or not self.trial_ends_at:
            return False

        return timezone.now() <= self.trial_ends_at

    @property
    def is_subscription_active(self):
        """Check if the subscription is currently active"""
        # For FREE plans, always return True as they don't expire
        if self.subscription_plan == "FREE":
            return True

        # For paid plans, return True if status is ACTIVE
        if self.status == "ACTIVE":
            # If subscription_ends_at is set, check if it's in the future
            if self.subscription_ends_at:
                return timezone.now() <= self.subscription_ends_at
            return True

        return False

    @property
    def days_until_expiry(self):
        """Number of days until subscription/trial expires"""
        now = timezone.now()
        if self.is_trial_active and self.trial_ends_at:
            return (self.trial_ends_at - now).days
        elif self.is_subscription_active and self.subscription_ends_at:
            return (self.subscription_ends_at - now).days
        return 0

    def get_plan_price(self, is_yearly=False):
        """Get the current plan price"""
        prices = {
            "FREE": {"monthly": 0, "yearly": 0, "users": 60},
            "BASIC": {"monthly": 29, "yearly": 288, "users": 5},
            "PREMIUM": {
                "monthly": 79,
                "yearly": 780,
                "users": float("inf"),
            },  # Unlimited users
        }
        plan = prices.get(self.subscription_plan, prices["FREE"])
        cycle = "yearly" if is_yearly else "monthly"
        return plan[cycle], plan["users"]

    @property
    def plan_price(self):
        """Get the current plan price (backward compatibility)"""
        return self.get_plan_price(is_yearly=False)[0]

    @property
    def user_count(self):
        """Get the number of active users"""
        return self.users.filter(is_active=True).count()

    def clean(self):
        """Custom validation"""
        # Handle FREE plan - never expires, no SMS/email notifications
        if self.subscription_plan == "FREE":
            self.status = "ACTIVE"
            self.billing_cycle = None
            self.trial_ends_at = None
            self.enable_sms_notifications = False
            self.enable_email_notifications = False
        # Handle TRIAL plan - keep status TRIAL, respect trial_ends_at for 30-day expiry
        elif self.subscription_plan == "TRIAL":
            self.status = "TRIAL"
            self.billing_cycle = None
        # Handle paid plans
        else:
            self.status = "ACTIVE"
            if not self.billing_cycle:
                self.billing_cycle = "MONTHLY"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class User(AbstractUser):
    """System User model - Enhanced version"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Override the email field to be non-unique
    email = models.EmailField(_("email address"), unique=False, blank=True, null=True)

    # Use email as the username field
    USERNAME_FIELD = "email"

    # Remove username from required fields since we use email
    REQUIRED_FIELDS = ["username"]

    class Meta:
        # Add unique constraint on email and church
        unique_together = ("email", "church")

    # Link to church (null for platform admins)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="users",
        db_column="church_id",
        null=True,
        blank=True,
    )

    # Extended user fields
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

    # Login tracking
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)

    # Notification preferences
    NOTIFICATION_PREFERENCES = [
        ("email", "Email Only"),
        ("sms", "SMS Only"),
        ("both", "Both Email and SMS"),
        ("none", "No Notifications"),
    ]
    notification_preference = models.CharField(
        max_length=10,
        choices=NOTIFICATION_PREFERENCES,
        default="email",
        help_text="Preferred method for receiving notifications",
    )

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )

    # Password reset
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_expires = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Authentication settings
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_account_locked(self):
        """Check if account is locked"""
        if self.account_locked_until:
            if timezone.now() < self.account_locked_until:
                return True
            self.unlock_account()
        return False

    def lock_account(self, minutes=30):
        """Lock account for specified minutes"""
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save(update_fields=["account_locked_until"])

    def unlock_account(self):
        """Unlock user account"""
        if self.account_locked_until:
            self.account_locked_until = None
            self.failed_login_attempts = 0
            self.save(update_fields=["account_locked_until", "failed_login_attempts"])

    def record_failed_login(self):
        """Record failed login attempt"""
        self.failed_login_attempts += 1

        # Lock account after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.lock_account()

        self.save(update_fields=["failed_login_attempts", "account_locked_until"])

    def record_successful_login(self):
        """Record successful login"""
        self.last_login = timezone.now()
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save(
            update_fields=[
                "last_login",
                "failed_login_attempts",
                "account_locked_until",
            ]
        )

    def clean(self):
        """Custom validation"""
        if self.is_platform_admin and not self.is_superuser:
            self.is_staff = True
            self.is_superuser = True

    def save(self, *args, **kwargs):
        self.clean()

        # Set email to lowercase
        if self.email:
            self.email = self.email.lower()

        # Generate email verification token if not set
        if not self.email_verification_token and not self.email_verified:
            self.email_verification_token = str(uuid.uuid4())

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
        ordering = ["level", "name"]

    def __str__(self):
        return self.name

    @property
    def permission_count(self):
        """Get count of permissions for this role"""
        return self.role_permissions.count()

    @property
    def permissions(self):
        """Get all permissions for this role"""
        from .permission import Permission

        return Permission.objects.filter(
            id__in=self.role_permissions.values_list("permission_id", flat=True)
        )


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
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.get_module_display()}: {self.code}"


class RolePermission(models.Model):
    """Role-Permission mapping - Enhanced version"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        db_column="role_id",
        related_name="role_permissions",  # Add related_name here
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, db_column="permission_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("role", "permission")
        ordering = ["role__name", "permission__code"]

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class ChurchGroup(models.Model):
    """
    Multi-tenant group per church. When users are added to the group,
    they automatically get the group's role (and its permissions).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="church_groups",
        db_column="church_id",
    )
    name = models.CharField(max_length=100)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="church_groups",
        db_column="role_id",
        help_text="Role automatically assigned to users in this group",
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "church_groups"
        ordering = ["name"]
        unique_together = ("church", "name")

    def __str__(self):
        return f"{self.name} ({self.church.name})"


class ChurchGroupMember(models.Model):
    """User membership in a church group. User gets group.role automatically."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        ChurchGroup,
        on_delete=models.CASCADE,
        related_name="members",
        db_column="church_group_id",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="church_group_memberships",
        db_column="user_id",
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_group_members",
        db_column="added_by_id",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "church_group_members"
        unique_together = ("group", "user")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"


class UserRole(models.Model):
    """User-Role assignment per church - Enhanced version (manual assignment)"""

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
        unique_together = ("user", "role", "church")
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.user.email} - {self.role.name} at {self.church.name}"


class AuditLog(models.Model):
    """Audit log for tracking important actions across the application"""

    ACTION_CHOICES = [
        # CRUD Operations
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("VIEW", "View"),
        # Authentication
        ("LOGIN", "Login"),
        ("LOGIN_FAILED", "Login Failed"),
        ("LOGOUT", "Logout"),
        ("PASSWORD_CHANGE", "Password Changed"),
        ("PASSWORD_RESET", "Password Reset"),
        # Permissions
        ("PERMISSION_CHANGE", "Permission Changed"),
        ("ROLE_CHANGE", "Role Changed"),
        ("STATUS_CHANGE", "Status Changed"),
        # System Events
        ("SYSTEM", "System Event"),
        ("IMPORT", "Data Import"),
        ("EXPORT", "Data Export"),
        ("BACKUP", "Backup Created"),
        ("RESTORE", "Data Restored"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed the action",
    )
    church = models.ForeignKey(
        Church,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Church/tenant where the action was performed",
    )
    action = models.CharField(
        max_length=50, choices=ACTION_CHOICES, help_text="Type of action performed"
    )
    model_name = models.CharField(
        max_length=100, help_text="Name of the affected model"
    )
    object_id = models.CharField(max_length=100, help_text="ID of the affected object")
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Content type of the affected model",
    )
    description = models.TextField(help_text="Detailed description of the action")
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON field storing changed fields and their values",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user who performed the action",
    )
    user_agent = models.TextField(
        blank=True, null=True, help_text="User agent string from the request"
    )
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional metadata about the action"
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_index=True,
        help_text="When the action was performed",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["model_name"]),
            models.Index(fields=["user"]),
            models.Index(fields=["church"]),
        ]

    def __str__(self):
        church_name = self.church.name if self.church else "System"
        return f"{self.get_action_display()} {self.model_name} - {church_name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def content_object(self):
        """Get the related object if it still exists"""
        if not self.content_type:
            return None
        try:
            model = self.content_type.model_class()
            return model.objects.get(pk=self.object_id)
        except:
            return None

    @classmethod
    def log(
        cls,
        user,
        action,
        instance,
        request=None,
        changes=None,
        description=None,
        **kwargs,
    ):
        """Helper method to create an audit log entry. Pass description= for custom message."""
        from core.audit import AuditLogger

        if description is not None:
            kwargs["description"] = description
        return AuditLogger.log_action(
            user, action, instance, request, changes, **kwargs
        )
