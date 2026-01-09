import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Church


class Member(models.Model):
    """Member Profile model - Phase 1B"""

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church, on_delete=models.CASCADE, related_name="members", db_column="church_id"
    )

    # Personal Information
    title = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(
        max_length=30, choices=MARITAL_STATUS_CHOICES, blank=True, null=True
    )
    national_id = models.CharField(max_length=50, blank=True, null=True)

    # Church Information
    membership_status = models.CharField(
        max_length=30, choices=MEMBERSHIP_STATUS_CHOICES, default="ACTIVE"
    )
    member_since = models.DateField()

    # Education & Professional
    education_level = models.CharField(
        max_length=50, choices=EDUCATION_CHOICES, blank=True, null=True
    )
    occupation = models.CharField(max_length=100, blank=True, null=True)
    employer = models.CharField(max_length=150, blank=True, null=True)

    # Additional
    profile_photo = models.TextField(blank=True, null=True)  # URL or base64
    notes = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

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


class Visitor(models.Model):
    """Visitor Registration - Phase 1B"""

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
