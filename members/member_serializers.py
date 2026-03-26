import re

from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from rest_framework import serializers

from accounts.models import Role, User, UserRole
from departments.models import Department, MemberDepartment
from members.models import Member, MemberLocation


def generate_username_from_member(member):
    """Auto-generate a unique username from member first/last name (e.g. kwame.mensah)."""
    first = (member.first_name or "").strip().lower()
    last = (member.last_name or "").strip().lower()
    # Sanitize: only letters, digits, dots, underscores
    first = re.sub(r"[^a-z0-9.]", "", first)
    last = re.sub(r"[^a-z0-9.]", "", last)
    base = f"{first}.{last}" if first and last else (first or last or "user")
    base = base[:148]  # leave room for _99
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}_{n}"
        n += 1
        if n > 999:
            username = f"{base}_{get_random_string(6).lower()}"
            break
    return username


class EmergencyContactSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200, required=True)
    relationship = serializers.CharField(max_length=100, required=True)
    phone_number = serializers.CharField(max_length=20, required=True)


class MemberCreateSerializer(serializers.ModelSerializer):
    # Personal Information
    title = serializers.ChoiceField(
        choices=[
            ("Mr", "Mr"),
            ("Mrs", "Mrs"),
            ("Miss", "Miss"),
            ("Dr", "Dr"),
            ("Rev", "Rev"),
            ("Pastor", "Pastor"),
            ("Elder", "Elder"),
            ("Deacon", "Deacon"),
            ("Deaconess", "Deaconess"),
        ],
        required=True,
    )
    first_name = serializers.CharField(max_length=100, required=True)
    middle_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=100, required=True)
    gender = serializers.ChoiceField(choices=Member.GENDER_CHOICES, required=True)
    date_of_birth = serializers.DateField(required=True)
    marital_status = serializers.ChoiceField(
        choices=Member.MARITAL_STATUS_CHOICES, required=True
    )
    national_id = serializers.CharField(max_length=50, required=True)

    # Contact Information
    phone_number = serializers.CharField(max_length=20, required=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    occupation = serializers.CharField(max_length=100, required=True)
    residential_address = serializers.CharField(required=True)
    city = serializers.CharField(max_length=100, required=True)
    region = serializers.ChoiceField(
        choices=[
            ("Ahafo", "Ahafo"),
            ("Ashanti", "Ashanti"),
            ("Bono East", "Bono East"),
            ("Bono", "Bono"),
            ("Central", "Central"),
            ("Eastern", "Eastern"),
            ("Greater Accra", "Greater Accra"),
            ("North East", "North East"),
            ("Northern", "Northern"),
            ("Oti", "Oti"),
            ("Savannah", "Savannah"),
            ("Upper East", "Upper East"),
            ("Upper West", "Upper West"),
            ("Volta", "Volta"),
            ("Western North", "Western North"),
            ("Western", "Western"),
            ("Other", "Other"),
        ],
        required=True,
    )
    custom_region = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )

    # Emergency Contact
    emergency_contact = EmergencyContactSerializer(required=True)

    # Church Information
    member_since = serializers.DateField(required=True)
    membership_status = serializers.ChoiceField(
        choices=Member.MEMBERSHIP_STATUS_CHOICES, required=True
    )
    baptism_status = serializers.ChoiceField(
        choices=Member.BAPTISM_STATUS_CHOICES,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Whether the member is baptised or not",
    )
    education_level = serializers.ChoiceField(
        choices=Member.EDUCATION_CHOICES, required=True
    )
    interested_departments = serializers.ListField(
        child=serializers.CharField(), required=True
    )

    # Admin Notes
    admin_notes = serializers.CharField(required=False, allow_blank=True)

    # System Access
    has_system_access = serializers.BooleanField(default=False, required=False)
    system_access_username = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="Login username. Auto-generated from member name (e.g. firstname.lastname) if not provided.",
    )
    system_access_password = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="Login password. If not provided, a random password is generated.",
    )

    # Notification Options
    send_credentials_via_email = serializers.BooleanField(
        default=False, required=False, help_text="Send login credentials via email"
    )
    send_credentials_via_sms = serializers.BooleanField(
        default=False, required=False, help_text="Send login credentials via SMS"
    )

    class Meta:
        model = Member
        fields = [
            # Personal Information
            "title",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "marital_status",
            "national_id",
            # Contact Information
            "phone_number",
            "email",
            "occupation",
            "residential_address",
            "city",
            "region",
            "custom_region",
            # Emergency Contact
            "emergency_contact",
            # Church Information
            "member_since",
            "membership_status",
            "baptism_status",
            "education_level",
            "interested_departments",
            # Admin Notes & System Access
            "admin_notes",
            "has_system_access",
            "system_access_username",
            "system_access_password",
            # Notification Preferences
            "send_credentials_via_email",
            "send_credentials_via_sms",
        ]

    def validate(self, data):
        # If region is "Other" and custom_region is not provided
        if data.get("region") == "Other" and not data.get("custom_region"):
            raise serializers.ValidationError(
                {
                    "custom_region": 'Please specify the region name when selecting "Other"'
                }
            )

        # Check if email already exists in the same church
        church = self.context["request"].user.church
        if (
            data.get("email")
            and User.objects.filter(email=data["email"], church=church).exists()
        ):
            raise serializers.ValidationError(
                {"email": "A user with this email already exists in this church."}
            )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.user.church

        # Extract emergency contact data
        emergency_contact_data = validated_data.pop("emergency_contact", {})
        interested_departments = validated_data.pop("interested_departments", [])

        # Handle region
        region = validated_data.pop("region")
        if region == "Other":
            region = validated_data.pop("custom_region", "Other")

        # Create Member
        member = Member.objects.create(
            church=church,
            title=validated_data["title"],
            first_name=validated_data["first_name"],
            middle_name=validated_data.get("middle_name", ""),
            last_name=validated_data["last_name"],
            gender=validated_data["gender"],
            date_of_birth=validated_data["date_of_birth"],
            marital_status=validated_data["marital_status"],
            national_id=validated_data["national_id"],
            membership_status=validated_data["membership_status"],
            member_since=validated_data["member_since"],
            baptism_status=validated_data.get("baptism_status"),
            education_level=validated_data["education_level"],
            occupation=validated_data["occupation"],
            notes=validated_data.get("admin_notes", ""),
        )

        # Create MemberLocation
        MemberLocation.objects.create(
            member=member,
            church=church,
            phone_primary=validated_data["phone_number"],
            email=validated_data.get("email", ""),
            address=validated_data["residential_address"],
            city=validated_data["city"],
            region=region,
            country="Ghana",  # Default to Ghana as per requirements
        )

        # Create Emergency Contact (as a note for now, can be a separate model)
        emergency_note = (
            f"Emergency Contact:\n"
            f"Name: {emergency_contact_data['full_name']}\n"
            f"Relationship: {emergency_contact_data['relationship']}\n"
            f"Phone: {emergency_contact_data['phone_number']}"
        )
        member.notes = (
            f"{member.notes}\n\n{emergency_note}" if member.notes else emergency_note
        )
        member.save()

        # Add to departments
        for dept_name in interested_departments:
            try:
                department = Department.objects.get(
                    name__iexact=dept_name, church=church
                )
                MemberDepartment.objects.create(
                    member=member,
                    department=department,
                    is_active=True,
                    date_joined=member.member_since,
                )
            except Department.DoesNotExist:
                # Skip if department doesn't exist
                pass

        # Implicit system access: if sending credentials via email or SMS, create system access
        has_system_access = validated_data.get("has_system_access", False)
        send_email = validated_data.get("send_credentials_via_email", False)
        send_sms = validated_data.get("send_credentials_via_sms", False)
        if (has_system_access or send_email or send_sms) and validated_data.get(
            "email"
        ):
            raw_username = (validated_data.get("system_access_username") or "").strip()
            username = (
                raw_username if raw_username else generate_username_from_member(member)
            )
            password = validated_data.get("system_access_password", "").strip()
            self._create_system_user(
                member,
                validated_data["email"],
                church,
                username=username,
                password=password,
                phone_number=(validated_data.get("phone_number") or "").strip(),
            )

        return member

    def _create_system_user(
        self,
        member,
        email,
        church,
        username=None,
        password=None,
        phone_number=None,
    ):
        # Use provided username or email; generate password if not provided
        username = (username or email).strip()
        password = password or get_random_string(12)

        # Store for response (so view can return username/password to client)
        self.generated_username = username
        self.generated_password = password

        phone = (phone_number or "").strip() or None

        # Create the user
        user = User.objects.create(
            email=email,
            username=username,
            first_name=member.first_name,
            last_name=member.last_name,
            church=church,
            phone=phone,
            is_active=True,
            email_verified=True,  # Assuming email is verified if coming from admin
        )

        # Set password
        user.set_password(password)
        user.save()

        # Assign default member role (level 4 = Member). Role is global; UserRole links to church.
        try:
            member_role = Role.objects.get(level=4)
            UserRole.objects.create(user=user, role=member_role, church=church)
        except Role.DoesNotExist:
            # Handle case where member role doesn't exist
            pass

        # Email/SMS delivery runs in MemberCreateView on a background thread.
