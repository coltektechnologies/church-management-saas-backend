import logging
import re
import threading
from datetime import datetime, timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger(__name__)
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .constants import CHURCH_PLATFORM_DISABLED_MESSAGE
from .models import (
    AuditLog,
    Church,
    ChurchGroup,
    ChurchGroupMember,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from .models.payment import Payment
from .tasks import run_registration_credentials_delivery

# ==========================================
# UTILITY VALIDATORS
# ==========================================


def validate_password_strength(password):
    """Custom password validation"""
    if len(password) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise serializers.ValidationError(
            "Password must contain at least one uppercase letter"
        )

    if not re.search(r"[a-z]", password):
        raise serializers.ValidationError(
            "Password must contain at least one lowercase letter"
        )

    if not re.search(r"\d", password):
        raise serializers.ValidationError("Password must contain at least one digit")

    # Optionally check against Django's built-in validators
    try:
        validate_password(password)
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages))


# ==========================================
# Church Registration serializers
# ==========================================


class ChurchRegistrationStep1Serializer(serializers.Serializer):
    """Step 1: Church Information"""

    # Church Details
    church_name = serializers.CharField(max_length=255, trim_whitespace=True)
    church_email = serializers.EmailField()
    subdomain = serializers.CharField(max_length=63)
    denomination = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )

    # Location
    country = serializers.CharField(max_length=100)
    region = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    address = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    church_size = serializers.ChoiceField(choices=Church.CHURCH_SIZE_CHOICES)

    def validate_church_name(self, value):
        """Validate church name"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Church name must be at least 3 characters"
            )
        return value.strip()

    def validate_church_email(self, value):
        """Validate church email is unique"""
        value = value.lower()
        if Church.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered")
        return value

    def validate_subdomain(self, value):
        """Validate subdomain format and uniqueness"""
        value = value.lower().strip()

        # Length check
        if len(value) < 3 or len(value) > 63:
            raise serializers.ValidationError(
                "Subdomain must be between 3 and 63 characters"
            )

        # Format check: alphanumeric and hyphens, must start/end with alphanumeric
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", value):
            raise serializers.ValidationError(
                "Subdomain can only contain lowercase letters, numbers, and hyphens. "
                "It must start and end with a letter or number."
            )

        # No consecutive hyphens
        if "--" in value:
            raise serializers.ValidationError(
                "Subdomain cannot contain consecutive hyphens"
            )

        # Check reserved subdomains
        reserved = [
            "www",
            "api",
            "admin",
            "mail",
            "smtp",
            "ftp",
            "webmail",
            "cpanel",
            "app",
            "dashboard",
            "portal",
            "system",
            "support",
            "help",
            "docs",
            "cdn",
            "static",
            "media",
            "assets",
        ]
        if value in reserved:
            raise serializers.ValidationError("This subdomain is reserved")

        # Check uniqueness
        if Church.objects.filter(subdomain=value).exists():
            raise serializers.ValidationError("This subdomain is already taken")

        return value


class ChurchRegistrationStep2Serializer(serializers.Serializer):
    """Step 2: Primary Admin Information"""

    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, trim_whitespace=True)
    admin_email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=50)
    position = serializers.ChoiceField(
        choices=[
            ("PASTOR", "Pastor"),
            ("FIRST_ELDER", "First Elder"),
            ("SENIOR_PASTOR", "Senior Pastor"),
            ("PRESIDING_ELDER", "Presiding Elder"),
        ]
    )
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_first_name(self, value):
        """Validate first name"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError(
                "First name must be at least 2 characters"
            )
        return value.strip()

    def validate_last_name(self, value):
        """Validate last name"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters")
        return value.strip()

    def validate_admin_email(self, value):
        """Validate admin email is unique"""
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered")
        return value

    def validate_phone_number(self, value):
        """Validate phone number format"""
        # Remove spaces and special characters
        cleaned = re.sub(r"[^\d+]", "", value)
        if len(cleaned) < 10:
            raise serializers.ValidationError("Please enter a valid phone number")
        return value

    def validate_password(self, value):
        """Validate password strength"""
        validate_password_strength(value)
        return value

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return attrs


class ChurchRegistrationStep3Serializer(serializers.Serializer):
    """Step 3: Subscription Plan Selection"""

    subscription_plan = serializers.ChoiceField(
        choices=[
            ("TRIAL", "30-Day Free Trial"),
            ("FREE", "Free"),
            ("BASIC", "Basic"),
            ("PREMIUM", "Premium"),
            ("ENTERPRISE", "Enterprise"),
        ]
    )
    # Values that mean 2-week trial (14 days); everything else = 30-day trial
    TRIAL_2WEEK_VALUES = ("14", "2 weeks", "2_weeks", "2weeks")

    billing_cycle = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='MONTHLY, YEARLY (paid); "2 weeks" or "14" = 2-week trial, "" = 30-day trial (TRIAL plan)',
    )

    def _is_trial_2_weeks(self, cycle):
        return (cycle or "").strip().lower() in {
            v.lower() for v in self.TRIAL_2WEEK_VALUES
        }

    def get_plan_details(self, plan, cycle):
        """Get plan pricing details"""
        monthly_prices = {
            "TRIAL": {
                "price": 0,
                "users": 50,
                "features": [
                    "Full platform access",
                    "All features",
                    "No payment required",
                ],
                "description_30": "Try all features free for 30 days",
                "description_2weeks": "Try all features free for 2 weeks",
            },
            "FREE": {
                "price": 0,
                "users": 60,
                "features": [
                    "Basic Reporting",
                    "Email Support",
                    "Up to 60 users",
                    "No Expiry",
                ],
                "description": "Up to 60 users, free forever",
            },
            "BASIC": {
                "price": 1,
                "users": 50,
                "features": ["Basic Reporting", "Email Support", "Up to 50 users"],
                "description": "Finance tracking, SMS alerts, and 5 admin accounts.",
            },
            "PREMIUM": {
                "price": 20,
                "users": 200,
                "features": [
                    "Advanced Reporting",
                    "Priority Support",
                    "SMS Notifications",
                    "Up to 200 users",
                ],
                "description": "Advanced analytics, unlimited admins and full coordination",
            },
            "ENTERPRISE": {
                "price": 30,
                "users": 1000,
                "features": [
                    "Custom Reporting",
                    "24/7 Support",
                    "API Access",
                    "Custom Integrations",
                    "Up to 1000 users",
                ],
                "description": "Custom features, enterprise security, and priority support",
            },
        }

        plan_info = monthly_prices.get(plan, monthly_prices["BASIC"])
        price = plan_info["price"]

        # TRIAL and FREE plans: No payment required
        if plan in ("TRIAL", "FREE"):
            if plan == "TRIAL" and self._is_trial_2_weeks(cycle):
                description = plan_info.get(
                    "description_2weeks", "Try all features free for 2 weeks"
                )
                billing_cycle_display = "2 weeks"
            elif plan == "TRIAL":
                description = plan_info.get(
                    "description_30", "Try all features free for 30 days"
                )
                billing_cycle_display = "FREE"
            else:
                description = plan_info["description"]
                billing_cycle_display = "FREE"
            return {
                "monthly_price": 0,
                "total_price": 0,
                "discount_amount": 0,
                "billing_cycle": billing_cycle_display,
                "max_users": 9999,
                "requires_payment": False,
                "features": plan_info["features"],
                "description": description,
                "amount_cents": 0,
            }

        # Paid plans: Apply yearly discount (2 months free = 10 months billing)
        if cycle == "YEARLY":
            total_price = price * 10
            discount_amount = price * 2
        else:
            total_price = price
            discount_amount = 0

        return {
            "monthly_price": price,
            "total_price": total_price,
            "discount_amount": discount_amount,
            "billing_cycle": cycle,
            "max_users": plan_info["users"],
            "requires_payment": True,
            "features": plan_info["features"],
            "description": plan_info["description"],
            "amount_cents": total_price * 100,  # Convert to cents for payment processor
        }


class ChurchRegistrationCompleteSerializer(serializers.Serializer):
    """Complete Registration Data - Final step after payment"""

    # Step 1 data
    church_name = serializers.CharField()
    church_email = serializers.EmailField()
    subdomain = serializers.CharField()
    denomination = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField()
    region = serializers.CharField()
    city = serializers.CharField()
    address = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    church_size = serializers.CharField()

    # Step 2 data
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    admin_email = serializers.EmailField()
    phone_number = serializers.CharField()
    position = serializers.CharField()
    password = serializers.CharField(write_only=True)

    # Step 3 data
    subscription_plan = serializers.CharField()
    billing_cycle = serializers.CharField()

    # Payment data
    payment_reference = serializers.CharField()
    payment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )

    @transaction.atomic
    def create(self, validated_data):
        """Create church and admin user after successful payment"""

        plan = validated_data["subscription_plan"]
        is_free = plan == "FREE"
        is_trial = plan == "TRIAL"

        # 2-week trial: '14', '2 weeks', '2_weeks', '2weeks' (case-insensitive)
        _bc = (validated_data.get("billing_cycle") or "").strip().lower()
        _trial_2weeks = _bc in ("14", "2 weeks", "2_weeks", "2weeks")

        # TRIAL: 2 weeks (14 days) or 30 days; FREE: no expiry; paid: no trial
        if is_trial:
            trial_days = 14 if _trial_2weeks else 30
            trial_ends_at = timezone.now() + timedelta(days=trial_days)
            church_status = "TRIAL"
            billing_cycle = None
        elif is_free:
            trial_ends_at = None
            church_status = "TRIAL"
            billing_cycle = None
        else:
            trial_ends_at = None
            church_status = "ACTIVE"
            billing_cycle = validated_data["billing_cycle"]

        # Create church
        church = Church.objects.create(
            name=validated_data["church_name"],
            email=validated_data["church_email"],
            subdomain=validated_data["subdomain"],
            denomination=validated_data.get("denomination", ""),
            country=validated_data["country"],
            region=validated_data["region"],
            city=validated_data["city"],
            address=validated_data.get("address", ""),
            phone=validated_data.get("phone", ""),
            church_size=validated_data["church_size"],
            status=church_status,
            subscription_plan=plan,
            billing_cycle=billing_cycle,
            trial_ends_at=trial_ends_at,
            # Set subscription dates for paid plans only (1 year from now)
            subscription_ends_at=(
                timezone.now() + timedelta(days=365)
                if plan not in ("FREE", "TRIAL")
                else None
            ),
            subscription_starts_at=(
                timezone.now() if plan not in ("FREE", "TRIAL") else None
            ),
            last_payment_reference=validated_data["payment_reference"],
            timezone="Africa/Accra",  # Default, can be updated later
            currency="GHS",
            enable_sms_notifications=False if is_free else True,
            enable_email_notifications=False if is_free else True,
        )

        # Set max users based on plan (TRIAL gets 50 like BASIC)
        plan_limits = {
            "TRIAL": 50,
            "FREE": 60,
            "BASIC": 50,
            "PREMIUM": 200,
            "ENTERPRISE": 1000,
        }
        church.max_users = plan_limits.get(plan, 50)
        church.save()

        # Record the payment
        try:
            payment_amount = validated_data.get("payment_amount", 0)
            payment = Payment.objects.create(
                church=church,
                amount=payment_amount,
                currency=church.currency,
                reference=validated_data["payment_reference"],
                payment_method="PAYSTACK" if payment_amount > 0 else "FREE",
                status="SUCCESSFUL",
                subscription_plan=validated_data["subscription_plan"],
                billing_cycle=billing_cycle or plan,
                payment_date=timezone.now(),
                payment_details={
                    "registration": True,
                    "plan": validated_data["subscription_plan"],
                    "billing_cycle": validated_data["billing_cycle"],
                    "amount_paid": float(payment_amount),
                    "currency": church.currency,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            logger.info(
                f"Payment recorded for church {church.name}: {payment_amount} {church.currency}"
            )
        except Exception as e:
            logger.error(
                f"Error recording payment for church {church.name}: {str(e)}",
                exc_info=True,
            )

        # Create admin user
        username = validated_data["admin_email"].split("@")[0]
        # Ensure username is unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        admin_user = User.objects.create_user(
            username=username,
            email=validated_data["admin_email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone=validated_data["phone_number"],
            church=church,
            is_staff=True,
            is_platform_admin=False,
            email_verified=True,  # Auto-verify on registration
        )

        # Determine role based on position
        position_role_map = {
            "PASTOR": "Pastor",
            "SENIOR_PASTOR": "Pastor",
            "FIRST_ELDER": "First Elder",
            "PRESIDING_ELDER": "First Elder",
        }
        role_name = position_role_map.get(validated_data["position"], "Pastor")

        # Get or create role
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                "level": 1,
                "description": f"{role_name} - Full administrative access",
                "is_system_role": True,
            },
        )

        # Assign role to user
        UserRole.objects.create(
            user=admin_user,
            role=role,
            church=church,
            assigned_by=admin_user,  # Self-assigned during registration
        )

        # Send credentials on a daemon thread so SMTP/SMS does not block the response.
        # Using only Celery .delay() is insufficient on hosts with Redis but no worker:
        # the task is accepted into the queue but never runs, so users get no email/SMS.
        password = validated_data["password"]
        preference = (
            "both"
            if (admin_user.email and admin_user.phone)
            else ("email" if admin_user.email else "sms")
        )
        uid = str(admin_user.id)

        def _deliver():
            run_registration_credentials_delivery(uid, password, preference)

        threading.Thread(target=_deliver, daemon=True).start()

        # Create audit log
        AuditLog.objects.create(
            user=admin_user,
            church=church,
            action="CREATE",
            model_name="Church",
            object_id=str(church.id),
            description=f"Church registration completed: {church.name}",
        )

        return {"church": church, "user": admin_user, "role": role}


class ChurchLoginSerializer(serializers.Serializer):
    """Login with church subdomain and user credentials"""

    subdomain = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Authenticate user"""
        subdomain = attrs.get("subdomain").lower()
        email = attrs.get("email").lower()
        password = attrs.get("password")

        try:
            # Find church by subdomain
            church = Church.objects.get(subdomain=subdomain)

            if not church.platform_access_enabled:
                raise serializers.ValidationError(
                    {"non_field_errors": CHURCH_PLATFORM_DISABLED_MESSAGE}
                )

            # Find user in this church
            user = User.objects.get(email=email, church=church, is_active=True)

            # Check if account is locked
            if user.is_account_locked:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Account is temporarily locked due to multiple failed login attempts. Please try again later."
                    }
                )

            # Verify password
            if not user.check_password(password):
                user.record_failed_login()
                raise serializers.ValidationError(
                    {"non_field_errors": "Invalid credentials"}
                )

            # Check church subscription status
            if church.status == "SUSPENDED":
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Church account is suspended. Please contact support."
                    }
                )

            if church.status == "INACTIVE":
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Church account is inactive. Please contact support."
                    }
                )

            # Check trial expiry
            if church.status == "TRIAL" and not church.is_trial_active:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": f"Trial period has expired. Please subscribe to continue."
                    }
                )

            # Check subscription expiry - skip for FREE plans
            if (
                church.status == "ACTIVE"
                and church.subscription_plan != "FREE"
                and not church.is_subscription_active
            ):
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Subscription has expired. Please renew to continue."
                    }
                )

            # Successful login
            user.record_successful_login()

            attrs["user"] = user
            attrs["church"] = church
            return attrs

        except Church.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid church subdomain"}
            )
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid credentials"}
            )


# ==========================================
# AUTHENTICATION SERIALIZERS
# ==========================================


class RegisterSerializer(serializers.Serializer):
    """Serializer for church and admin user registration"""

    # Church fields
    church_name = serializers.CharField(max_length=255)
    denomination = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    country = serializers.CharField(max_length=100)
    region = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    address = serializers.CharField(required=False, allow_blank=True)
    timezone = serializers.CharField(default="UTC")
    currency = serializers.CharField(default="USD")

    # Admin user fields
    admin_username = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    admin_first_name = serializers.CharField(required=False, allow_blank=True)
    admin_last_name = serializers.CharField(required=False, allow_blank=True)
    admin_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_admin_email(self, value):
        """Ensure email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered")
        return value.lower()

    def validate_admin_username(self, value):
        """Ensure username is unique"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken")
        return value

    def validate_admin_password(self, value):
        """Validate password strength"""
        validate_password_strength(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create church and admin user"""
        # Extract church data
        church_data = {
            "name": validated_data["church_name"],
            "denomination": validated_data.get("denomination", ""),
            "country": validated_data["country"],
            "region": validated_data["region"],
            "city": validated_data["city"],
            "address": validated_data.get("address", ""),
            "timezone": validated_data.get("timezone", "UTC"),
            "currency": validated_data.get("currency", "USD"),
            "status": "TRIAL",
            "subscription_plan": "TRIAL",
            "trial_ends_at": timezone.now() + timedelta(days=30),  # 30-day trial
        }

        # Create church
        church = Church.objects.create(**church_data)

        # Create admin user
        user_data = {
            "username": validated_data["admin_username"],
            "email": validated_data["admin_email"],
            "password": validated_data["admin_password"],
            "first_name": validated_data.get("admin_first_name", ""),
            "last_name": validated_data.get("admin_last_name", ""),
            "phone": validated_data.get("admin_phone", ""),
            "church": church,
            "is_staff": True,
            "is_active": True,
            "is_platform_admin": False,
            "email_verified": True,  # Auto-verify admin email
        }

        admin_user = User.objects.create_user(**user_data)

        # Create and assign Pastor role
        pastor_role, created = Role.objects.get_or_create(
            name="Pastor",
            defaults={
                "level": 1,
                "description": "Church administrator with full access",
                "is_system_role": True,
            },
        )

        UserRole.objects.create(
            user=admin_user,
            role=pastor_role,
            church=church,
            assigned_by=admin_user,
            is_active=True,
        )

        # Create audit log
        AuditLog.objects.create(
            user=admin_user,
            church=church,
            action="CREATE",
            model_name="User",
            object_id=str(admin_user.id),
            description=f"Admin user created during registration: {admin_user.email}",
        )

        return admin_user


class LoginSerializer(serializers.Serializer):
    """Login serializer for user authentication"""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    church_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        """Authenticate user"""
        email = attrs.get("email").lower()
        password = attrs.get("password")
        church_id = attrs.get("church_id")

        # Find user by email (and church_id if provided)
        qs = User.objects.filter(email__iexact=email, is_active=True)
        if church_id:
            qs = qs.filter(church_id=church_id)
            user = qs.first()
        else:
            # No church_id: prefer platform admin, then staff, then first match
            user = qs.filter(is_platform_admin=True).first()
            if not user:
                user = qs.filter(is_staff=True).first()
            if not user:
                user = qs.first()

        if not user:
            raise serializers.ValidationError({"email": "Invalid email or password"})

        # Verify password
        if not user.check_password(password):
            raise serializers.ValidationError({"password": "Invalid email or password"})

        if user.church and not getattr(user, "is_platform_admin", False):
            if not user.church.platform_access_enabled:
                raise serializers.ValidationError(
                    {"non_field_errors": CHURCH_PLATFORM_DISABLED_MESSAGE}
                )

        # If church_id was provided, verify user belongs to that church
        if church_id and user.church and str(user.church.id) != str(church_id):
            raise serializers.ValidationError(
                {"church_id": "User is not associated with this church"}
            )

        # Check church status if user belongs to a church
        if user.church:
            church = user.church
            if church.status not in ["TRIAL", "ACTIVE"]:
                raise serializers.ValidationError(
                    {"non_field_errors": "Church account is not active"}
                )

            if church.status == "TRIAL" and not church.is_trial_active:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Trial period has expired. Please subscribe to continue."
                    }
                )

            if church.status == "ACTIVE" and not church.is_subscription_active:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Subscription has expired. Please renew to continue."
                    }
                )

        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Blacklist a refresh token for the authenticated user."""

    refresh = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        try:
            token = RefreshToken(attrs["refresh"])
        except TokenError as e:
            raise serializers.ValidationError({"refresh": [str(e)]}) from e
        token_uid = token.get(api_settings.USER_ID_CLAIM)
        if token_uid is None or str(token_uid) != str(request.user.id):
            raise serializers.ValidationError(
                {"refresh": ["Refresh token does not match the authenticated user."]}
            )
        attrs["_token"] = token
        return attrs

    def create(self, validated_data):
        token = validated_data.pop("_token")
        token.blacklist()
        return self.context["request"].user


# ==========================================
# CHURCH SERIALIZERS
# ==========================================


class ChurchSerializer(serializers.ModelSerializer):
    """Complete church serializer with all details"""

    logo_url = serializers.SerializerMethodField()
    full_domain = serializers.ReadOnlyField()
    is_trial_active = serializers.ReadOnlyField()
    is_subscription_active = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()
    plan_price = serializers.ReadOnlyField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Church
        fields = [
            "id",
            "name",
            "email",
            "subdomain",
            "denomination",
            "country",
            "region",
            "city",
            "address",
            "phone",
            "website",
            "tagline",
            "mission",
            "church_size",
            "logo",
            "logo_url",
            "full_domain",
            "timezone",
            "currency",
            "status",
            "subscription_plan",
            "billing_cycle",
            "trial_ends_at",
            "subscription_starts_at",
            "subscription_ends_at",
            "next_billing_date",
            "is_trial_active",
            "is_subscription_active",
            "days_until_expiry",
            "plan_price",
            "max_users",
            "user_count",
            "enable_online_giving",
            "enable_sms_notifications",
            "enable_email_notifications",
            "platform_access_enabled",
            "primary_color",
            "accent_color",
            "sidebar_color",
            "background_color",
            "dark_mode",
            "service_times",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
            "trial_ends_at",
            "subscription_starts_at",
            "subscription_ends_at",
            "platform_access_enabled",
        ]

    def get_logo_url(self, obj):
        """Get full URL for logo (Cloudinary and other storages often return absolute URLs)."""
        if not obj.logo:
            return None
        url = obj.logo.url
        if url.startswith("http://") or url.startswith("https://"):
            return url
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_user_count(self, obj):
        """Get active user count"""
        return obj.users.filter(is_active=True).count()


class ChurchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for church lists"""

    user_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Church
        fields = [
            "id",
            "name",
            "subdomain",
            "city",
            "country",
            "status",
            "status_display",
            "subscription_plan",
            "user_count",
            "platform_access_enabled",
            "created_at",
        ]
        read_only_fields = ["id"]

    def get_user_count(self, obj):
        """Get active user count"""
        return obj.users.filter(is_active=True).count()


class ChurchPlatformAccessSerializer(serializers.Serializer):
    """Platform admin only: enable or disable tenant access (login + API)."""

    platform_access_enabled = serializers.BooleanField(required=True)


class ChurchUpdateSerializer(serializers.ModelSerializer):
    """Church update serializer"""

    class Meta:
        model = Church
        fields = [
            "name",
            "denomination",
            "country",
            "region",
            "city",
            "address",
            "phone",
            "website",
            "tagline",
            "mission",
            "logo",
            "timezone",
            "currency",
            "enable_online_giving",
            "enable_sms_notifications",
            "enable_email_notifications",
            "primary_color",
            "accent_color",
            "sidebar_color",
            "background_color",
            "dark_mode",
            "service_times",
        ]


# ==========================================
# USER SERIALIZERS
# ==========================================


class UserSerializer(serializers.ModelSerializer):
    """User detail serializer"""

    church_name = serializers.CharField(source="church.name", read_only=True)
    church_subdomain = serializers.CharField(source="church.subdomain", read_only=True)
    full_name = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

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
            "profile_image",
            "profile_image_url",
            "date_of_birth",
            "gender",
            "address",
            "church",
            "church_name",
            "church_subdomain",
            "is_platform_admin",
            "is_active",
            "is_staff",
            "mfa_enabled",
            "email_verified",
            "roles",
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
            "email_verified",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_profile_image_url(self, obj):
        """Get full URL for profile image"""
        if obj.profile_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None

    def get_roles(self, obj):
        """Get user's roles"""
        user_roles = UserRole.objects.filter(user=obj, is_active=True).select_related(
            "role"
        )
        return [
            {"id": str(ur.role.id), "name": ur.role.name, "level": ur.role.level}
            for ur in user_roles
        ]


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight user list serializer"""

    church_name = serializers.CharField(source="church.name", read_only=True)
    full_name = serializers.SerializerMethodField()
    primary_role_name = serializers.SerializerMethodField()
    church_group_ids = serializers.SerializerMethodField()

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
            "church_name",
            "is_active",
            "is_staff",
            "last_login",
            "created_at",
            "primary_role_name",
            "church_group_ids",
        ]
        read_only_fields = ["id"]

    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_primary_role_name(self, obj):
        """Highest-privilege active role (lowest `Role.level` value)."""
        roles = [ur for ur in obj.userrole_set.all() if ur.is_active]
        if not roles:
            return ""
        best = min(roles, key=lambda ur: ur.role.level)
        return best.role.name

    def get_church_group_ids(self, obj):
        return [str(m.group_id) for m in obj.church_group_memberships.all()]


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""

    email = serializers.EmailField(required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "address",
            "is_active",
            "profile_image",
        ]
        read_only_fields = ["email"]  # Email updates should be handled separately

    def validate_email(self, value):
        """Ensure email is unique within the church"""
        request = self.context.get("request")
        if not request:
            return value

        user = request.user
        if User.objects.filter(email=value.lower()).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def update(self, instance, validated_data):
        """Update user and log changes"""
        # Log changes before updating
        changes = {}
        for field in validated_data:
            if getattr(instance, field) != validated_data[field]:
                changes[field] = {
                    "old": getattr(instance, field),
                    "new": validated_data[field],
                }

        # Perform the update
        user = super().update(instance, validated_data)

        # Create audit log if there were changes
        if changes and hasattr(instance, "church"):
            AuditLog.objects.create(
                user=(
                    self.context.get("request").user
                    if self.context.get("request")
                    else user
                ),
                church=instance.church,
                action="USER_UPDATED",
                model_name="User",
                object_id=str(user.id),
                description=f"User {user.email} profile updated",
                metadata={"changes": changes},
            )

        return user


import secrets
import string


class UserCreateSerializer(serializers.ModelSerializer):
    """User creation with password handling and auto-generation"""

    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        style={"input_type": "password"},
        help_text="Leave empty to auto-generate a secure password",
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        help_text="Required if password is provided",
    )
    send_credentials = serializers.BooleanField(
        required=False, default=True, help_text="Send credentials via email/SMS"
    )
    notification_preference = serializers.ChoiceField(
        choices=[("email", "Email"), ("sms", "SMS"), ("both", "Both")],
        default="email",
        required=False,
        help_text="How to send credentials (email/sms/both)",
    )
    church_groups = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="Optional list of church group UUIDs to add the user to (for auto role assignment)",
    )

    def generate_username(self, first_name, last_name, username=None):
        """Generate a unique username from first and last name or provided username"""
        if not username:
            base_username = f"{first_name.lower()}.{last_name.lower()}"
        else:
            base_username = username.lower()

        username = base_username
        count = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{count}"
            count += 1

        return username

    def generate_password(self, length=12):
        """Generate a secure random password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(length))
            # Ensure password meets complexity requirements
            if (
                any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%^&*" for c in password)
            ):
                return password

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
            "date_of_birth",
            "gender",
            "address",
            "church",
            "is_active",
            "send_credentials",
            "notification_preference",
            "church_groups",
        ]
        extra_kwargs = {
            "church": {"required": False, "allow_null": True},
            # Omit in API; we derive from first_name/last_name in validate() / validate_username.
            "username": {"required": False, "allow_blank": True},
        }

    def validate_email(self, value):
        """Validate email uniqueness per church"""
        if not value:
            raise serializers.ValidationError("Email is required")
        request = self.context.get("request")
        church = getattr(request.user, "church", None) if request else None
        if not church and self.initial_data.get("church"):
            from .models import Church

            try:
                church = Church.objects.get(id=self.initial_data["church"])
            except (Church.DoesNotExist, (ValueError, TypeError)):
                pass
        if church and User.objects.filter(email=value.lower(), church=church).exists():
            raise serializers.ValidationError(
                "A user with this email already exists in this church."
            )
        return value.lower()

    def validate_username(self, value):
        """Validate or generate username"""
        if value:
            # If username is provided, ensure it's unique or modify it
            value = self.generate_username(
                first_name=self.initial_data.get("first_name", ""),
                last_name=self.initial_data.get("last_name", ""),
                username=value,
            )
        elif self.initial_data.get("first_name") and self.initial_data.get("last_name"):
            # Generate username from first and last name if not provided
            value = self.generate_username(
                first_name=self.initial_data["first_name"],
                last_name=self.initial_data["last_name"],
            )
        else:
            raise serializers.ValidationError(
                "Username is required if first_name and last_name are not provided"
            )

        return value.lower() if value else None

    def validate_password(self, value):
        """Validate password strength if provided"""
        if value:
            validate_password_strength(value)
        return value

    def validate(self, attrs):
        """Validate credentials and handle auto-generation"""
        request = self.context.get("request")
        if (
            not attrs.get("church")
            and request
            and getattr(request.user, "church", None)
        ):
            attrs["church"] = request.user.church

        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        # If password is provided, ensure confirmation matches
        if password and password_confirm and password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}
            )

        # If no password provided, generate one
        if not password:
            attrs["password"] = self.generate_password()
            attrs["password_confirm"] = attrs["password"]
            attrs["auto_generated_password"] = True

        # Generate username if not provided
        if (
            not attrs.get("username")
            and attrs.get("first_name")
            and attrs.get("last_name")
        ):
            attrs["username"] = self.generate_username(
                attrs["first_name"], attrs["last_name"]
            )

        # Check if church has reached user limit
        church = attrs.get("church")
        if church:
            active_users = User.objects.filter(church=church, is_active=True).count()
            if active_users >= church.max_users:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": f"Church has reached maximum user limit ({church.max_users}). Please upgrade your plan."
                    }
                )

        return attrs

    def create(self, validated_data):
        """Create user with hashed password and send credentials if needed"""
        # Remove non-model fields
        password_confirm = validated_data.pop("password_confirm", None)
        send_credentials = validated_data.pop("send_credentials", True)
        notification_preference = validated_data.pop("notification_preference", "email")
        auto_generated_password = validated_data.pop("auto_generated_password", False)
        church_groups = validated_data.pop("church_groups", []) or []

        # Store password before hashing
        password = validated_data.get("password")

        try:
            # Remove is_active from validated_data to avoid duplicate parameter
            validated_data.pop("is_active", None)

            # Create user with explicit is_active=True and is_staff=True (can access admin)
            user = User.objects.create_user(
                **validated_data,
                is_active=True,
                is_staff=True,
            )

            # Optionally add user to church groups (same church only)
            if church_groups and user.church_id:
                request = self.context.get("request")
                added_by = (
                    request.user if request and request.user.is_authenticated else None
                )
                for group_id in church_groups:
                    try:
                        group = ChurchGroup.objects.get(
                            id=group_id, church_id=user.church_id
                        )
                        ChurchGroupMember.objects.get_or_create(
                            group=group,
                            user=user,
                            defaults={"added_by": added_by},
                        )
                    except ChurchGroup.DoesNotExist:
                        pass  # Skip invalid or wrong-church groups

            # Send credentials if requested (email and/or SMS per notification_preference)
            can_email = notification_preference in ("email", "both") and bool(
                user.email
            )
            can_sms = notification_preference in ("sms", "both") and bool(user.phone)
            if send_credentials and (can_email or can_sms):
                from members.services.credential_service import (
                    send_credentials as deliver_credentials,
                )

                request = self.context.get("request")
                allow_staff_invite = False
                if request and request.user.is_authenticated:
                    if getattr(request.user, "is_platform_admin", False):
                        allow_staff_invite = True
                    elif (
                        getattr(request.user, "church_id", None)
                        and user.church_id
                        and str(request.user.church_id) == str(user.church_id)
                    ):
                        allow_staff_invite = True

                try:
                    outcome = deliver_credentials(
                        user=user,
                        password=password,
                        notification_preference=notification_preference,
                        request=request,
                        allow_staff_invite=allow_staff_invite,
                    )
                    if outcome.get("success"):
                        AuditLog.objects.create(
                            user=user,
                            action="CREDENTIALS_SENT",
                            description=(
                                f"Login credentials sent ({notification_preference}) "
                                f"to {user.email or ''} / {user.phone or ''}".strip(),
                            ),
                            church=user.church,
                            metadata={
                                "notification_method": notification_preference,
                                "auto_generated": auto_generated_password,
                                "email_sent": outcome.get("email_sent"),
                                "sms_sent": outcome.get("sms_sent"),
                            },
                        )
                    else:
                        err = outcome.get("error", "Unknown delivery failure")
                        logger.error(
                            "Credential delivery failed for user %s: %s",
                            user.email or user.id,
                            err,
                        )
                        AuditLog.objects.create(
                            user=user,
                            action="CREDENTIALS_FAILED",
                            description=f"Failed to send login credentials: {err}",
                            church=user.church,
                            metadata={
                                "error": err,
                                "notification_method": notification_preference,
                            },
                        )
                except Exception as e:
                    logger.error(
                        "Failed to send credentials to %s: %s",
                        user.email or user.id,
                        str(e),
                    )
                    AuditLog.objects.create(
                        user=user,
                        action="CREDENTIALS_FAILED",
                        description=f"Failed to send login credentials: {str(e)}",
                        church=user.church,
                        metadata={
                            "error": str(e),
                            "notification_method": notification_preference,
                        },
                    )

            return user

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise serializers.ValidationError(
                {"error": f"Failed to create user: {str(e)}"}
            )

    def update(self, instance, validated_data):
        """Update user and log changes"""
        user = super().update(instance, validated_data)

        # Create audit log
        if user.church:
            AuditLog.objects.create(
                user=(
                    self.context.get("request").user
                    if self.context.get("request")
                    else user
                ),
                church=user.church,
                action="UPDATE",
                model_name="User",
                object_id=str(user.id),
                description=f"User updated: {user.email}",
            )

        return user


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

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

    def validate_new_password(self, value):
        """Validate new password strength"""
        validate_password_strength(value)
        return value

    def validate(self, attrs):
        """Validate new passwords match and different from old"""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords do not match"}
            )

        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from old password"}
            )

        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Request password reset"""

    email = serializers.EmailField()
    subdomain = serializers.CharField()

    def validate(self, attrs):
        """Validate user exists"""
        email = attrs.get("email").lower()
        subdomain = attrs.get("subdomain").lower()

        try:
            church = Church.objects.get(subdomain=subdomain)
            user = User.objects.get(email=email, church=church, is_active=True)
            attrs["user"] = user
            attrs["church"] = church
        except (Church.DoesNotExist, User.DoesNotExist):
            # Don't reveal if user exists or not for security
            pass

        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirm password reset with token"""

    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        """Validate password strength"""
        validate_password_strength(value)
        return value

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match"}
            )
        return attrs


# ==========================================
# ROLE & PERMISSION SERIALIZERS
# ==========================================


class PermissionSerializer(serializers.ModelSerializer):
    """Permission serializer"""

    module_display = serializers.CharField(source="get_module_display", read_only=True)

    class Meta:
        model = Permission
        fields = [
            "id",
            "code",
            "description",
            "module",
            "module_display",
            "is_system_permission",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "is_system_permission"]


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer with permissions"""

    permissions = serializers.SerializerMethodField()
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
            "is_system_role",
            "permissions",
            "permission_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_system_role"]

    def get_permissions(self, obj):
        """Get all permissions for this role"""
        role_perms = RolePermission.objects.filter(role=obj).select_related(
            "permission"
        )
        return PermissionSerializer(
            [rp.permission for rp in role_perms], many=True
        ).data

    def get_permission_count(self, obj):
        """Count permissions for this role"""
        return RolePermission.objects.filter(role=obj).count()


class RoleListSerializer(serializers.ModelSerializer):
    """Lightweight role list"""

    level_display = serializers.CharField(source="get_level_display", read_only=True)
    permission_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "name", "level", "level_display", "permission_count"]

    def get_permission_count(self, obj):
        """Count permissions"""
        return RolePermission.objects.filter(role=obj).count()


class RolePermissionSerializer(serializers.ModelSerializer):
    """Role-Permission assignment serializer"""

    role_name = serializers.CharField(source="role.name", read_only=True)
    permission_code = serializers.CharField(source="permission.code", read_only=True)
    permission_description = serializers.CharField(
        source="permission.description", read_only=True
    )

    class Meta:
        model = RolePermission
        fields = [
            "id",
            "role",
            "role_name",
            "permission",
            "permission_code",
            "permission_description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        """Prevent duplicate assignments"""
        role = attrs.get("role")
        permission = attrs.get("permission")

        if RolePermission.objects.filter(role=role, permission=permission).exists():
            raise serializers.ValidationError(
                "This permission is already assigned to this role"
            )

        return attrs


# ==========================================
# CHURCH GROUP SERIALIZERS
# ==========================================


class ChurchGroupSerializer(serializers.ModelSerializer):
    """Church group serializer"""

    role_name = serializers.CharField(source="role.name", read_only=True)
    church_name = serializers.CharField(source="church.name", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = ChurchGroup
        fields = [
            "id",
            "church",
            "church_name",
            "name",
            "role",
            "role_name",
            "description",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.members.count()

    def create(self, validated_data):
        request = self.context.get("request")
        if request and not validated_data.get("church") and request.user.church:
            validated_data["church"] = request.user.church
        return super().create(validated_data)


class ChurchGroupMemberSerializer(serializers.ModelSerializer):
    """Church group member serializer"""

    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    role_name = serializers.CharField(source="group.role.name", read_only=True)

    class Meta:
        model = ChurchGroupMember
        fields = [
            "id",
            "group",
            "group_name",
            "user",
            "user_email",
            "user_name",
            "role_name",
            "added_by",
            "added_at",
        ]
        read_only_fields = ["id", "added_at"]


class ChurchGroupMemberCreateSerializer(serializers.Serializer):
    """Add user to group"""

    user_id = serializers.UUIDField()

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found")
        return value


# ==========================================
# USER-ROLE SERIALIZERS
# ==========================================


class UserRoleSerializer(serializers.ModelSerializer):
    """User-Role assignment serializer"""

    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    church_name = serializers.CharField(source="church.name", read_only=True)
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "role",
            "role_name",
            "church",
            "church_name",
            "assigned_by",
            "assigned_by_name",
            "assigned_at",
            "is_active",
        ]
        read_only_fields = ["id", "assigned_at"]
        extra_kwargs = {"church": {"required": False}}

    def get_assigned_by_name(self, obj):
        """Get name of user who assigned the role"""
        if obj.assigned_by:
            return obj.assigned_by.full_name
        return None

    def validate(self, attrs):
        """Ensure user belongs to the church (church is set from request by the view)."""
        user = attrs.get("user")
        church = attrs.get("church")
        if not church:
            raise serializers.ValidationError(
                {
                    "church": "Church is required. Use an authenticated user that belongs to a church."
                }
            )
        if user.church != church:
            raise serializers.ValidationError(
                {"user": "User must belong to the church"}
            )

        # Check if active assignment already exists
        if UserRole.objects.filter(
            user=user, role=attrs.get("role"), church=church, is_active=True
        ).exists():
            raise serializers.ValidationError(
                "This user already has an active assignment for this role in this church"
            )

        return attrs

    def create(self, validated_data):
        """Create user role and log action"""
        user_role = super().create(validated_data)

        # Create audit log
        AuditLog.objects.create(
            user=(
                self.context.get("request").user
                if self.context.get("request")
                else user_role.user
            ),
            church=user_role.church,
            action="PERMISSION_CHANGE",
            model_name="UserRole",
            object_id=str(user_role.id),
            description=f'Role "{user_role.role.name}" assigned to {user_role.user.email}',
        )

        return user_role


# ==========================================
# DASHBOARD/STATS SERIALIZERS
# ==========================================


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics - not backed by model"""

    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    inactive_users = serializers.IntegerField()
    total_members = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    pending_announcements = serializers.IntegerField()
    subscription_status = serializers.CharField()
    days_until_expiry = serializers.IntegerField()
    user_limit = serializers.IntegerField()
    user_percentage = serializers.FloatField()


class AuditLogSerializer(serializers.ModelSerializer):
    """Audit log serializer"""

    user_name = serializers.CharField(source="user.full_name", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_name",
            "church",
            "action",
            "action_display",
            "model_name",
            "object_id",
            "description",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
