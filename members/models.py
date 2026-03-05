import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Church


class MemberQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class MemberManager(models.Manager):
    def get_queryset(self):
        return MemberQuerySet(self.model, using=self._db).active()

    def all_objects(self):
        return MemberQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def deleted(self):
        return self.get_queryset().deleted()


class Member(models.Model):
    """Member Profile model - Phase 1B"""

    objects = MemberManager()

    class NotificationPreference(models.TextChoices):
        NONE = "NONE", "No notifications"
        EMAIL = "EMAIL", "Email only"
        SMS = "SMS", "SMS only"
        BOTH = "BOTH", "Email and SMS"

    TITLE_CHOICES = [
        ("", "-- Select Title --"),
        ("Mr", "Mr"),
        ("Mrs", "Mrs"),
        ("Miss", "Miss"),
        ("Dr", "Dr"),
        ("Rev", "Rev"),
        ("Pastor", "Pastor"),
        ("Elder", "Elder"),
        ("Deacon", "Deacon"),
        ("Deaconess", "Deaconess"),
    ]

    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
    ]

    MEMBERSHIP_STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("TRANSFER", "Transfer"),
        ("NEW_CONVERT", "New Convert"),
        ("VISITOR", "Visitor"),
        ("INACTIVE", "Inactive"),
    ]

    MARITAL_STATUS_CHOICES = [
        ("SINGLE", "Single"),
        ("MARRIED", "Married"),
        ("WIDOWED", "Widowed"),
        ("DIVORCED", "Divorced"),
    ]

    EDUCATION_CHOICES = [
        ("PRIMARY", "Primary"),
        ("SECONDARY", "Secondary/High School"),
        ("TERTIARY", "Tertiary/College"),
        ("GRADUATE", "Graduate"),
        ("POSTGRADUATE", "Postgraduate"),
    ]

    BAPTISM_STATUS_CHOICES = [
        ("BAPTISED", "Baptised"),
        ("NOT_BAPTISED", "Not Baptised"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church, on_delete=models.CASCADE, related_name="members", db_column="church_id"
    )

    # Personal Information
    title = models.CharField(
        max_length=20,
        choices=TITLE_CHOICES,
        blank=True,
        null=True,
        help_text="Person's title (e.g., Mr, Mrs, Dr, Rev)",
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(
        max_length=30, choices=MARITAL_STATUS_CHOICES, blank=True, null=True
    )
    national_id = models.CharField(max_length=50, blank=True, null=True)

    # User Account Information
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    notification_preference = models.CharField(
        max_length=5,
        choices=NotificationPreference.choices,
        default=NotificationPreference.EMAIL,
        help_text="Preferred method for receiving notifications",
    )
    last_login = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # Church Information
    membership_status = models.CharField(
        max_length=30, choices=MEMBERSHIP_STATUS_CHOICES, default="ACTIVE"
    )
    member_since = models.DateField()
    baptism_status = models.CharField(
        max_length=20,
        choices=BAPTISM_STATUS_CHOICES,
        blank=True,
        null=True,
        help_text="Whether the member is baptised or not",
    )

    # Education & Professional
    education_level = models.CharField(
        max_length=50, choices=EDUCATION_CHOICES, blank=True, null=True
    )
    occupation = models.CharField(max_length=100, blank=True, null=True)
    employer = models.CharField(max_length=150, blank=True, null=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relationship = models.CharField(
        max_length=100, blank=True, null=True
    )

    # System Access
    has_system_access = models.BooleanField(default=False)
    system_user_id = models.UUIDField(blank=True, null=True)

    # Additional
    profile_photo = models.TextField(blank=True, null=True)  # URL or base64
    notes = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def get_full_name(self):
        """Return the full name of the member"""
        name_parts = [self.first_name]
        if self.middle_name:
            name_parts.append(self.middle_name)
        name_parts.append(self.last_name)
        return " ".join(filter(None, name_parts))

    class Meta:
        db_table = "members"
        verbose_name = _("Member")
        verbose_name_plural = _("Members")
        indexes = [
            models.Index(fields=["church", "membership_status"]),
            models.Index(fields=["church", "deleted_at"]),
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        middle = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.first_name}{middle} {self.last_name}"

    def create_system_user(self, email, password=None):
        """
        Create a system user account for this member
        Returns the created user and password (None if no password was set)
        """
        from django.contrib.auth.hashers import make_password

        from accounts.models import User, UserRole
        from accounts.models.base_models import Role

        if not email:
            return None, None

        # Generate a random password if not provided
        if not password:
            password = User.objects.make_random_password()

        # Create the user
        user = User.objects.create(
            email=email,
            username=email,  # Use email as username
            first_name=self.first_name,
            last_name=self.last_name,
            church=self.church,
            is_active=True,
            email_verified=True,
        )

        # Set password
        user.set_password(password)
        user.save()

        # Assign default member role (level 4)
        try:
            member_role = Role.objects.get(level=4, church=self.church)
            UserRole.objects.create(user=user, role=member_role, church=self.church)
        except Role.DoesNotExist:
            # If no member role exists, we'll just skip role assignment
            pass

        # Update member with system user info
        self.has_system_access = True
        self.system_user_id = user.id
        self.save()

        return user, password


class MemberLocation(models.Model):
    """Member Contact & Location - Phase 1B"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField(
        Member, on_delete=models.CASCADE, related_name="location", db_column="member_id"
    )
    church = models.ForeignKey(Church, on_delete=models.CASCADE, db_column="church_id")

    phone_primary = models.CharField(max_length=50)
    phone_secondary = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(max_length=150, blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "member_locations"
        verbose_name = _("Member Location")
        verbose_name_plural = _("Member Locations")


class VisitorQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class VisitorManager(models.Manager):
    def get_queryset(self):
        return VisitorQuerySet(self.model, using=self._db).active()

    def all_objects(self):
        return VisitorQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def deleted(self):
        return self.get_queryset().deleted()


class Visitor(models.Model):
    """Visitor Registration - Phase 1B"""

    objects = VisitorManager()

    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church, on_delete=models.CASCADE, related_name="visitors", db_column="church_id"
    )

    full_name = models.CharField(max_length=200)
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, blank=True, null=True
    )
    phone = models.CharField(max_length=50)
    email = models.EmailField(max_length=150, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    first_visit_date = models.DateField()
    referral_source = models.CharField(max_length=100, blank=True, null=True)
    receive_updates = models.BooleanField(default=True)
    converted_to_member = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "visitors"
        verbose_name = _("Visitor")
        verbose_name_plural = _("Visitors")
        indexes = [
            models.Index(fields=["church", "converted_to_member"]),
            models.Index(fields=["first_visit_date"]),
        ]

    def __str__(self):
        return self.full_name
