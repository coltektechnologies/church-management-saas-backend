from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import Church, Permission, Role, RolePermission, User, UserRole

# ==========================================
# CHURCH SERIALIZERS
# ==========================================


class ChurchSerializer(serializers.ModelSerializer):
    """Complete church serializer with logo handling"""

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Church
        fields = [
            "id",
            "name",
            "denomination",
            "country",
            "region",
            "city",
            "logo",
            "logo_url",
            "address",
            "timezone",
            "currency",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "deleted_at"]

    def get_logo_url(self, obj):
        """Get full URL for logo"""
        if obj.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None


class ChurchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for church lists"""

    class Meta:
        model = Church
        fields = ["id", "name", "city", "country", "status"]
        read_only_fields = ["id"]


# ==========================================
# USER SERIALIZERS
# ==========================================


class UserSerializer(serializers.ModelSerializer):
    """User detail serializer"""

    church_name = serializers.CharField(source="church.name", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "church",
            "church_name",
            "is_platform_admin",
            "is_active",
            "is_staff",
            "mfa_enabled",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_platform_admin",
            "last_login",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight user list serializer"""

    church_name = serializers.CharField(source="church.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "church_name",
            "is_active",
            "is_platform_admin",
        ]
        read_only_fields = ["id"]


class UserCreateSerializer(serializers.ModelSerializer):
    """User creation with password handling"""

    password = serializers.CharField(
        write_only=True, required=True, min_length=8, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
            "church",
            "is_active",
        ]

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def validate_email(self, value):
        """Validate email uniqueness per church"""
        church = self.initial_data.get("church")
        if church:
            if User.objects.filter(email=value, church_id=church).exists():
                raise serializers.ValidationError(
                    "User with this email already exists in this church"
                )
        return value

    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """User update serializer (no password)"""

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "mfa_enabled",
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Password change serializer"""

    old_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, write_only=True, min_length=8, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        """Validate new passwords match"""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password": "New passwords do not match"}
            )
        return attrs

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


# ==========================================
# AUTHENTICATION SERIALIZERS
# ==========================================


class LoginSerializer(serializers.Serializer):
    """Login serializer - not a ModelSerializer"""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    church_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Required for non-platform admin users",
    )

    def validate(self, attrs):
        """Authenticate user"""
        email = attrs.get("email")
        password = attrs.get("password")
        church_id = attrs.get("church_id")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
            church_id=church_id,
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials or church ID")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    """Church registration (onboarding) serializer"""

    # Church details
    church_name = serializers.CharField(max_length=255)
    denomination = serializers.CharField(max_length=150, required=False)
    country = serializers.CharField(max_length=100)
    region = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    address = serializers.CharField(required=False)
    timezone = serializers.CharField(max_length=50, default="UTC")
    currency = serializers.CharField(max_length=10, default="USD")

    # Admin user details
    admin_username = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    admin_first_name = serializers.CharField(max_length=150, required=False)
    admin_last_name = serializers.CharField(max_length=150, required=False)
    admin_phone = serializers.CharField(max_length=50, required=False)

    def validate_admin_email(self, value):
        """Ensure email is unique globally"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered")
        return value

    def create(self, validated_data):
        """Create church and admin user"""
        from django.db import transaction

        with transaction.atomic():
            # Create church
            church = Church.objects.create(
                name=validated_data["church_name"],
                denomination=validated_data.get("denomination", ""),
                country=validated_data["country"],
                region=validated_data["region"],
                city=validated_data["city"],
                address=validated_data.get("address", ""),
                timezone=validated_data.get("timezone", "UTC"),
                currency=validated_data.get("currency", "USD"),
                status="TRIAL",  # New churches start in trial
            )

            # Create admin user
            admin_user = User.objects.create_user(
                username=validated_data["admin_username"],
                email=validated_data["admin_email"],
                password=validated_data["admin_password"],
                first_name=validated_data.get("admin_first_name", ""),
                last_name=validated_data.get("admin_last_name", ""),
                phone=validated_data.get("admin_phone", ""),
                church=church,
                is_staff=True,  # Church admin has staff access
                is_platform_admin=False,
            )

            # Assign Pastor/Admin role (if exists)
            try:
                pastor_role = Role.objects.get(name="Pastor")
                UserRole.objects.create(
                    user=admin_user, role=pastor_role, church=church
                )
            except Role.DoesNotExist:
                pass

            return admin_user


# ==========================================
# ROLE & PERMISSION SERIALIZERS
# ==========================================


class PermissionSerializer(serializers.ModelSerializer):
    """Permission serializer"""

    class Meta:
        model = Permission
        fields = ["id", "code", "description", "module", "created_at"]
        read_only_fields = ["id", "created_at"]


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer with permissions"""

    permissions = PermissionSerializer(
        many=True, read_only=True, source="rolepermission_set.permission"
    )
    permission_count = serializers.SerializerMethodField()
    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "level",
            "level_display",
            "description",
            "permissions",
            "permission_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_permission_count(self, obj):
        """Count permissions for this role"""
        return obj.rolepermission_set.count()


class RolePermissionSerializer(serializers.ModelSerializer):
    """Role-Permission assignment serializer"""

    role_name = serializers.CharField(source="role.name", read_only=True)
    permission_code = serializers.CharField(source="permission.code", read_only=True)

    class Meta:
        model = RolePermission
        fields = ["id", "role", "role_name", "permission", "permission_code"]
        read_only_fields = ["id"]


class UserRoleSerializer(serializers.ModelSerializer):
    """User-Role assignment serializer"""

    user_email = serializers.CharField(source="user.email", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    church_name = serializers.CharField(source="church.name", read_only=True)

    class Meta:
        model = UserRole
        fields = [
            "id",
            "user",
            "user_email",
            "role",
            "role_name",
            "church",
            "church_name",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        """Ensure user belongs to the church"""
        user = attrs.get("user")
        church = attrs.get("church")

        if user.church != church:
            raise serializers.ValidationError("User must belong to the church")

        # Check if assignment already exists
        if UserRole.objects.filter(
            user=user, role=attrs.get("role"), church=church
        ).exists():
            raise serializers.ValidationError(
                "This user already has this role in this church"
            )

        return attrs


# ==========================================
# DASHBOARD/STATS SERIALIZERS (Base Serializer)
# ==========================================


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics - not backed by model"""

    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_members = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    pending_announcements = serializers.IntegerField()
