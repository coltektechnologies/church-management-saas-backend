import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Church(models.Model):
    """Church/Tenant model - Phase 1A"""

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
        ("TRIAL", "Trial"),
        ("INACTIVE", "Inactive"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    denomination = models.CharField(max_length=150, blank=True, null=True)
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    logo = models.ImageField(upload_to="churches/logo", blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "churches"
        verbose_name = _("Church")
        verbose_name_plural = _("Churches")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["country", "city"]),
        ]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """System User model - Phase 1A"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="users",
        db_column="church_id",
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=50, blank=True, null=True)
    mfa_enabled = models.BooleanField(default=False)
    is_platform_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
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
    """Role model - Phase 1A"""

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["level", "name"]

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Permission model - Phase 1A"""

    MODULE_CHOICES = [
        ("MEMBERS", "Members"),
        ("TREASURY", "Treasury"),
        ("SECRETARIAT", "Secretariat"),
        ("DEPARTMENTS", "Departments"),
        ("ANNOUNCEMENTS", "Announcements"),
        ("REPORTS", "Reports"),
        ("SETTINGS", "Settings"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    module = models.CharField(
        max_length=50, choices=MODULE_CHOICES, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.module}: {self.code}"


class RolePermission(models.Model):
    """Role-Permission mapping - Phase 1A"""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, db_column="permission_id"
    )

    class Meta:
        db_table = "role_permissions"
        unique_together = ("role", "permission")
        verbose_name = _("Role Permission")
        verbose_name_plural = _("Role Permissions")


class UserRole(models.Model):
    """User-Role assignment per church - Phase 1A"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")

    class Meta:
        db_table = "user_roles"
        unique_together = ("user", "role", "church")
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        indexes = [
            models.Index(fields=["church"]),
            models.Index(fields=["user", "church"]),
        ]
