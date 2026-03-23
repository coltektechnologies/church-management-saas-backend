import logging
import time
import uuid

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AuditLog,
    Church,
    ChurchGroup,
    ChurchGroupMember,
    Permission,
    RegistrationSession,
    Role,
    RolePermission,
    User,
    UserRole,
)
from .paystack import PaystackAPI
from .serializers import (
    ChangePasswordSerializer,
    ChurchGroupMemberCreateSerializer,
    ChurchGroupMemberSerializer,
    ChurchGroupSerializer,
    ChurchListSerializer,
    ChurchLoginSerializer,
    ChurchRegistrationCompleteSerializer,
    ChurchRegistrationStep1Serializer,
    ChurchRegistrationStep2Serializer,
    ChurchRegistrationStep3Serializer,
    ChurchSerializer,
    LoginSerializer,
    PermissionSerializer,
    RegisterSerializer,
    RolePermissionSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserListSerializer,
    UserRoleSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)

# ==========================================
# CHURCH VIEWS
# ==========================================


class ChurchView(APIView):
    """List all churches or create a new one"""

    permission_classes = [IsAuthenticated]  # ✅ Add authentication

    @swagger_auto_schema(
        operation_description="Get list of all churches",
        responses={200: ChurchListSerializer(many=True), 401: "Unauthorized"},
        tags=["Churches"],
    )
    def get(self, request):
        # Platform admins see all churches
        if request.user.is_platform_admin:
            churches = Church.objects.filter(deleted_at__isnull=True)
        else:
            # Regular users see only their church
            churches = Church.objects.filter(
                id=request.user.church_id, deleted_at__isnull=True
            )

        serializer = ChurchListSerializer(
            churches, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new church (Platform admins only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "country", "region", "city"],
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Church name",
                    example="Victory Chapel International",
                ),
                "denomination": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Church denomination",
                    example="Seventh-day Adventist",
                ),
                "country": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Country", example="Ghana"
                ),
                "region": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Region/State",
                    example="Greater Accra",
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City", example="Accra"
                ),
                "address": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Physical address",
                    example="123 Liberation Road, Accra",
                ),
                "timezone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Timezone",
                    example="Africa/Accra",
                    default="UTC",
                ),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Currency code",
                    example="GHS",
                    default="USD",
                ),
            },
        ),
        responses={
            201: ChurchSerializer(),
            400: "Bad Request - Validation errors",
            403: "Forbidden - Platform admins only",
        },
        tags=["Churches"],
    )
    def post(self, request):
        # Only platform admins can create churches
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can create churches"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChurchSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChurchDetailAPIView(APIView):
    """Retrieve, update or delete a church instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """Get church with permission check"""
        try:
            church = Church.objects.get(pk=pk, deleted_at__isnull=True)

            # Platform admins can access any church
            if user.is_platform_admin:
                return church

            # Regular users can only access their own church
            if user.church_id == church.id:
                return church

            return None
        except Church.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get church details by ID",
        responses={200: ChurchSerializer(), 403: "Forbidden", 404: "Church not found"},
        tags=["Churches"],
    )
    def get(self, request, pk):
        church = self.get_object(pk, request.user)
        if church is None:
            return Response(
                {"error": "Church not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChurchSerializer(church, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update church details",
        request_body=ChurchSerializer,
        responses={
            200: ChurchSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Church not found",
        },
        tags=["Churches"],
    )
    def put(self, request, pk):
        church = self.get_object(pk, request.user)
        if church is None:
            return Response(
                {"error": "Church not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChurchSerializer(
            church, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a church (soft delete - Platform admins only)",
        responses={
            204: "Church deleted successfully",
            403: "Forbidden",
            404: "Church not found",
        },
        tags=["Churches"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can delete churches"},
                status=status.HTTP_403_FORBIDDEN,
            )

        church = self.get_object(pk, request.user)
        if church is None:
            return Response(
                {"error": "Church not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Soft delete
        church.deleted_at = timezone.now()
        church.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# USER VIEWS
# ==========================================


class UserView(APIView):
    """List all users or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all users",
        manual_parameters=[
            openapi.Parameter(
                "church_id",
                openapi.IN_QUERY,
                description="Filter users by church ID (UUID) - Platform admins only",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
            openapi.Parameter(
                "is_active",
                openapi.IN_QUERY,
                description="Filter by active status",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={200: UserListSerializer(many=True), 401: "Unauthorized"},
        tags=["Users"],
    )
    def get(self, request):
        # Platform admins can see all users
        if request.user.is_platform_admin:
            users = User.objects.filter(deleted_at__isnull=True)

            # Filter by church if provided
            church_id = request.query_params.get("church_id")
            if church_id:
                users = users.filter(church_id=church_id)
        else:
            # Regular users see only their church's users
            users = User.objects.filter(
                church=request.user.church, deleted_at__isnull=True
            )

        # Filter by active status if provided
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            users = users.filter(is_active=is_active.lower() == "true")

        serializer = UserListSerializer(users, many=True, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new user with optional auto-generated credentials",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "church"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    description="User email address (required)",
                    example="pastor@church.com",
                ),
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Username (auto-generated if not provided)",
                    example="john.doe",
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Password (auto-generated if not provided, min 8 characters)",
                    example="SecurePass123!",
                ),
                "password_confirm": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Required if password is provided",
                    example="SecurePass123!",
                ),
                "church": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Church ID (UUID)",
                    example="550e8400-e29b-41d4-a716-446655440000",
                ),
                "phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Phone number (required for SMS notifications)",
                    example="+233244123456",
                ),
                "first_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="First name (required if username not provided)",
                    example="John",
                ),
                "last_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Last name (required if username not provided)",
                    example="Doe",
                ),
                "send_credentials": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Whether to send credentials via email/SMS (default: true)",
                    default=True,
                ),
                "notification_preference": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["email", "sms", "both"],
                    default="email",
                    description="How to send credentials (email/sms/both)",
                ),
                "church_groups": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
                    ),
                    description="Optional list of church group UUIDs to add the user to (for auto role assignment)",
                ),
            },
        ),
        responses={
            201: UserSerializer(),
            400: "Bad Request - Validation errors",
            403: "Forbidden - Insufficient permissions or user limit reached",
        },
        tags=["Users"],
    )
    def post(self, request):
        # Build data: church admins can omit church (defaults to their church)
        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )
        if not data.get("church") and getattr(request.user, "church_id", None):
            data["church"] = str(request.user.church_id)

        church_id = data.get("church")
        if not church_id:
            return Response(
                {
                    "church": [
                        "This field is required (or login as a church admin to use your church)."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_platform_admin:
            if str(request.user.church_id) != str(church_id):
                return Response(
                    {"error": "You can only create users in your own church"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = UserCreateSerializer(
            data=data,
            context={"request": request},
        )

        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response(
                    UserSerializer(user, context={"request": request}).data,
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.error(f"Error creating user: {str(e)}")
                return Response(
                    {"error": "An error occurred while creating the user"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailAPIView(APIView):
    """Retrieve, update or delete a user instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """Get user with permission check"""
        try:
            target_user = User.objects.get(pk=pk, deleted_at__isnull=True)

            # Platform admins can access any user
            if user.is_platform_admin:
                return target_user

            # Users can access themselves
            if user.id == target_user.id:
                return target_user

            # Users can access other users in their church
            if user.church_id == target_user.church_id:
                return target_user

            return None
        except User.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get user details by ID",
        responses={200: UserSerializer(), 403: "Forbidden", 404: "User not found"},
        tags=["Users"],
    )
    def get(self, request, pk):
        user = self.get_object(pk, request.user)
        if user is None:
            return Response(
                {"error": "User not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update user details (NOT password - use change-password endpoint)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, example="newemail@church.com"
                ),
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING, example="new_username"
                ),
                "phone": openapi.Schema(
                    type=openapi.TYPE_STRING, example="+233244999888"
                ),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Jane"),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Smith"),
                "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
            },
        ),
        responses={
            200: UserSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "User not found",
        },
        tags=["Users"],
    )
    def put(self, request, pk):
        user = self.get_object(pk, request.user)
        if user is None:
            return Response(
                {"error": "User not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Use UserUpdateSerializer (no password field)
        serializer = UserUpdateSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(user, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a user (soft delete)",
        responses={
            204: "User deleted successfully",
            403: "Forbidden",
            404: "User not found",
        },
        tags=["Users"],
    )
    def delete(self, request, pk):
        user = self.get_object(pk, request.user)
        if user is None:
            return Response(
                {"error": "User not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Can't delete yourself
        if user.id == request.user.id:
            return Response(
                {"error": "You cannot delete your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Soft delete
        user.deleted_at = timezone.now()
        user.is_active = False
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# AUTHENTICATION VIEWS
# ==========================================


class LoginAPIView(APIView):
    """User login endpoint"""

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Login with email and password. Returns JWT tokens.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "password"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    description="User email address",
                    example="pastor@church.com",
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="User password",
                    example="SecurePass123!",
                ),
                "church_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Optional. Church ID to disambiguate when same email exists in multiple churches. Omit to use the user's church (works when email is unique or platform admin/staff).",
                    example="550e8400-e29b-41d4-a716-446655440000",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Login successful",
                examples={
                    "application/json": {
                        "user": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "email": "pastor@church.com",
                            "username": "pastor_john",
                        },
                        "tokens": {
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                        },
                    }
                },
            ),
            400: "Bad Request - Invalid credentials",
            401: "Unauthorized",
        },
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "user": UserSerializer(user, context={"request": request}).data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordAPIView(APIView):
    """Change password endpoint"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Change user password",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["old_password", "new_password", "new_password_confirm"],
            properties={
                "old_password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Current password",
                    example="OldPass123!",
                ),
                "new_password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="New password (min 8 characters)",
                    example="NewSecurePass123!",
                ),
                "new_password_confirm": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Confirm new password",
                    example="NewSecurePass123!",
                ),
            },
        ),
        responses={
            200: "Password changed successfully",
            400: "Bad Request - Validation errors",
        },
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            # Set new password
            request.user.set_password(serializer.validated_data["new_password"])
            request.user.save()

            return Response({"message": "Password changed successfully"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# Registration Views
# ==========================================


class RegisterAPIView(APIView):
    """User registration endpoint - Platform admins only"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Register a new church and admin user (Platform admins only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
                "church_name",
                "country",
                "region",
                "city",
                "admin_username",
                "admin_email",
                "admin_password",
            ],
            properties={
                # Church details
                "church_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Name of the church",
                    example="Grace Community Church",
                ),
                "denomination": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Denomination (optional)",
                    example="Baptist",
                ),
                "country": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Country",
                    example="United States",
                ),
                "region": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="State/Region",
                    example="California",
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City", example="Los Angeles"
                ),
                "address": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Street address (optional)",
                    example="123 Main St",
                ),
                "timezone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Timezone (defaults to UTC)",
                    example="America/Los_Angeles",
                ),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Currency code (defaults to USD)",
                    example="USD",
                ),
                # Admin user details
                "admin_username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Admin username",
                    example="pastorjohn",
                ),
                "admin_email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    description="Admin email address",
                    example="pastor@example.com",
                ),
                "admin_password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Admin password (min 8 characters)",
                    example="SecurePass123!",
                    min_length=8,
                ),
                "admin_first_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Admin first name (optional)",
                    example="John",
                ),
                "admin_last_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Admin last name (optional)",
                    example="Doe",
                ),
                "admin_phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Admin phone number (optional)",
                    example="+1234567890",
                ),
            },
        ),
        responses={
            201: "User registered successfully",
            400: "Bad Request - Validation errors",
            403: "Forbidden - Platform admins only",
        },
        tags=["Registration"],
    )
    def post(self, request):
        # Only platform admins can use this endpoint
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform admins can use this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            # Save will return the admin user object
            admin_user = serializer.save()

            # Generate JWT tokens for the admin user
            refresh = RefreshToken.for_user(admin_user)

            # Serialize the user data
            user_data = UserSerializer(admin_user, context={"request": request}).data

            return Response(
                {
                    "user": user_data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# ROLE VIEWS (Keep your existing code - it's good!)
# ==========================================


class RoleView(APIView):
    """List all roles or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all roles",
        responses={200: RoleSerializer(many=True)},
        tags=["Roles & Permissions"],
    )
    def get(self, request):
        roles = Role.objects.all()
        serializer = RoleSerializer(roles, many=True, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new role (Platform admins only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "level"],
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Role name",
                    example="Church Secretary",
                ),
                "level": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Role level (1-5)",
                    example=2,
                    enum=[1, 2, 3, 4, 5],
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Role description",
                    example="Manages church records and communications",
                ),
            },
        ),
        responses={201: RoleSerializer(), 400: "Bad Request", 403: "Forbidden"},
        tags=["Roles & Permissions"],
    )
    def post(self, request):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can create roles"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RoleSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleDetailAPIView(APIView):
    """Retrieve, update or delete a role instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Role.objects.get(pk=pk)
        except Role.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get role details by ID",
        responses={200: RoleSerializer(), 404: "Role not found"},
        tags=["Roles & Permissions"],
    )
    def get(self, request, pk):
        role = self.get_object(pk)
        if role is None:
            return Response(
                {"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoleSerializer(role, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update a role (Platform admins only)",
        request_body=RoleSerializer,
        responses={
            200: RoleSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Role not found",
        },
        tags=["Roles & Permissions"],
    )
    def put(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can update roles"},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = self.get_object(pk)
        if role is None:
            return Response(
                {"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoleSerializer(
            role, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a role (Platform admins only)",
        responses={
            204: "Role deleted successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Role not found",
        },
        tags=["Roles & Permissions"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can delete roles"},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = self.get_object(pk)
        if role is None:
            return Response(
                {"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if role is in use before deleting
        if UserRole.objects.filter(role=role).exists():
            return Response(
                {"error": "Cannot delete role that is assigned to users"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# PERMISSION VIEWS
# ==========================================


class PermissionView(APIView):
    """
    List all permissions or create a new one
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all permissions",
        manual_parameters=[
            openapi.Parameter(
                "module",
                openapi.IN_QUERY,
                description="Filter by module (MEMBERS, TREASURY, SECRETARIAT, etc.)",
                type=openapi.TYPE_STRING,
                required=False,
                enum=[
                    "MEMBERS",
                    "TREASURY",
                    "SECRETARIAT",
                    "DEPARTMENTS",
                    "ANNOUNCEMENTS",
                    "REPORTS",
                    "SETTINGS",
                ],
            )
        ],
        responses={200: PermissionSerializer(many=True)},
        tags=["Roles & Permissions"],
    )
    def get(self, request):
        permissions = Permission.objects.all()

        # Filter by module if provided
        module = request.query_params.get("module")
        if module:
            permissions = permissions.filter(module=module)

        serializer = PermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new permission",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["code", "module"],
            properties={
                "code": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Permission code (unique)",
                    example="members.view_financial",
                ),
                "module": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Module name",
                    example="MEMBERS",
                    enum=[
                        "MEMBERS",
                        "TREASURY",
                        "SECRETARIAT",
                        "DEPARTMENTS",
                        "ANNOUNCEMENTS",
                        "REPORTS",
                        "SETTINGS",
                    ],
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Permission description",
                    example="View member financial data (tithe, offerings)",
                ),
            },
        ),
        responses={201: PermissionSerializer(), 400: "Bad Request"},
        tags=["Roles & Permissions"],
    )
    def post(self, request):
        serializer = PermissionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# PERMISSION DETAIL VIEW
# ==========================================


class PermissionDetailAPIView(APIView):
    """Retrieve, update or delete a permission instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Permission.objects.get(pk=pk)
        except Permission.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get permission details by ID",
        responses={200: PermissionSerializer(), 404: "Permission not found"},
        tags=["Roles & Permissions"],
    )
    def get(self, request, pk):
        permission = self.get_object(pk)
        if permission is None:
            return Response(
                {"error": "Permission not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PermissionSerializer(permission, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update permission details (Platform admins only)",
        request_body=PermissionSerializer,
        responses={
            200: PermissionSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Permission not found",
        },
        tags=["Roles & Permissions"],
    )
    def put(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can update permissions"},
                status=status.HTTP_403_FORBIDDEN,
            )

        permission = self.get_object(pk)
        if permission is None:
            return Response(
                {"error": "Permission not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PermissionSerializer(
            permission, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a permission (Platform admins only)",
        responses={
            204: "Permission deleted successfully",
            403: "Forbidden",
            404: "Permission not found",
        },
        tags=["Roles & Permissions"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can delete permissions"},
                status=status.HTTP_403_FORBIDDEN,
            )

        permission = self.get_object(pk)
        if permission is None:
            return Response(
                {"error": "Permission not found"}, status=status.HTTP_404_NOT_FOUND
            )

        permission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# ROLE-PERMISSION MAPPING VIEWS
# ==========================================


class RolePermissionView(APIView):
    """List all role-permission mappings or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all role-permission mappings",
        manual_parameters=[
            openapi.Parameter(
                "role_id",
                openapi.IN_QUERY,
                description="Filter by role ID",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
            openapi.Parameter(
                "permission_id",
                openapi.IN_QUERY,
                description="Filter by permission ID",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
        ],
        responses={200: RolePermissionSerializer(many=True)},
        tags=["Roles & Permissions"],
    )
    def get(self, request):
        role_permissions = RolePermission.objects.all()

        # Filter by role if provided
        role_id = request.query_params.get("role_id")
        if role_id:
            role_permissions = role_permissions.filter(role_id=role_id)

        # Filter by permission if provided
        permission_id = request.query_params.get("permission_id")
        if permission_id:
            role_permissions = role_permissions.filter(permission_id=permission_id)

        serializer = RolePermissionSerializer(
            role_permissions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Assign a permission to a role (Platform admins only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["role", "permission"],
            properties={
                "role": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Role ID",
                    example="550e8400-e29b-41d4-a716-446655440000",
                ),
                "permission": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Permission ID",
                    example="650e8400-e29b-41d4-a716-446655440001",
                ),
            },
        ),
        responses={
            201: RolePermissionSerializer(),
            400: "Bad Request",
            403: "Forbidden",
        },
        tags=["Roles & Permissions"],
    )
    def post(self, request):
        if not request.user.is_platform_admin:
            return Response(
                {
                    "error": "Only platform administrators can assign permissions to roles"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RolePermissionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RolePermissionDetailAPIView(APIView):
    """Delete a role-permission mapping"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return RolePermission.objects.get(pk=pk)
        except RolePermission.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Remove permission from role (Platform admins only)",
        responses={
            204: "Permission removed from role successfully",
            403: "Forbidden",
            404: "Role-Permission mapping not found",
        },
        tags=["Roles & Permissions"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {
                    "error": "Only platform administrators can remove permissions from roles"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        role_permission = self.get_object(pk)
        if role_permission is None:
            return Response(
                {"error": "Role-Permission mapping not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        role_permission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# USER-ROLE MAPPING VIEWS
# ==========================================


class UserRoleView(APIView):
    """List all user-role assignments or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all user-role assignments",
        manual_parameters=[
            openapi.Parameter(
                "user_id",
                openapi.IN_QUERY,
                description="Filter by user ID",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
            openapi.Parameter(
                "role_id",
                openapi.IN_QUERY,
                description="Filter by role ID",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
            openapi.Parameter(
                "church_id",
                openapi.IN_QUERY,
                description="Filter by church ID",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
        ],
        responses={200: UserRoleSerializer(many=True)},
        tags=["Roles & Permissions"],
    )
    def get(self, request):
        # Platform admins see all assignments
        if request.user.is_platform_admin:
            user_roles = UserRole.objects.all()
        else:
            # Regular users see only their church's assignments
            user_roles = UserRole.objects.filter(church=request.user.church)

        # Apply filters
        user_id = request.query_params.get("user_id")
        if user_id:
            user_roles = user_roles.filter(user_id=user_id)

        role_id = request.query_params.get("role_id")
        if role_id:
            user_roles = user_roles.filter(role_id=role_id)

        church_id = request.query_params.get("church_id")
        if church_id and request.user.is_platform_admin:
            user_roles = user_roles.filter(church_id=church_id)

        serializer = UserRoleSerializer(
            user_roles, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Assign a role to a user. Church is taken from the authenticated user (Bearer token); no church_id in payload.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["user", "role"],
            properties={
                "user": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="User ID",
                    example="550e8400-e29b-41d4-a716-446655440000",
                ),
                "role": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Role ID",
                    example="650e8400-e29b-41d4-a716-446655440001",
                ),
            },
        ),
        responses={201: UserRoleSerializer(), 400: "Bad Request", 403: "Forbidden"},
        tags=["Roles & Permissions"],
    )
    def post(self, request):
        # Use authenticated user's church (no church_id in payload)
        church = getattr(request.user, "church", None)
        if not church:
            return Response(
                {"church": ["You must belong to a church to assign roles."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )
        data["church"] = str(church.id)

        serializer = UserRoleSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRoleDetailAPIView(APIView):
    """Remove a role from a user"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            user_role = UserRole.objects.get(pk=pk)

            # Platform admins can access any user role
            if user.is_platform_admin:
                return user_role

            # Regular users can only manage roles in their church
            if user.church_id == user_role.church_id:
                return user_role

            return None
        except UserRole.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Remove role from user",
        responses={
            204: "Role removed from user successfully",
            403: "Forbidden",
            404: "User-Role assignment not found",
        },
        tags=["Roles & Permissions"],
    )
    def delete(self, request, pk):
        user_role = self.get_object(pk, request.user)
        if user_role is None:
            return Response(
                {"error": "User-Role assignment not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# CHURCH GROUP VIEWS
# ==========================================


class ChurchGroupView(APIView):
    """List church groups or create a new one"""

    permission_classes = [IsAuthenticated]

    def _get_church(self, request):
        church_id = request.query_params.get("church_id") or request.data.get("church")
        if church_id and request.user.is_platform_admin:
            try:
                return Church.objects.get(id=church_id)
            except Church.DoesNotExist:
                return None
        return request.user.church

    @swagger_auto_schema(
        operation_description="Get list of church groups",
        manual_parameters=[
            openapi.Parameter(
                "church_id",
                openapi.IN_QUERY,
                description="Church ID (platform admin only)",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=False,
            ),
        ],
        responses={200: ChurchGroupSerializer(many=True)},
        tags=["Church Groups"],
    )
    def get(self, request):
        church = self._get_church(request)
        if not church:
            return Response(
                {"error": "Church required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.is_platform_admin and church != request.user.church:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        groups = ChurchGroup.objects.filter(church=church).select_related("role")
        serializer = ChurchGroupSerializer(
            groups, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a church group",
        request_body=ChurchGroupSerializer,
        responses={201: ChurchGroupSerializer(), 400: "Bad Request", 403: "Forbidden"},
        tags=["Church Groups"],
    )
    def post(self, request):
        church = self._get_church(request)
        if not church:
            church_id = request.data.get("church")
            if church_id:
                try:
                    church = Church.objects.get(id=church_id)
                except Church.DoesNotExist:
                    pass
            if not church:
                church = request.user.church
        if not church:
            return Response(
                {"error": "Church required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.is_platform_admin and church != request.user.church:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = {**request.data, "church": church.id}
        serializer = ChurchGroupSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChurchGroupDetailAPIView(APIView):
    """Retrieve, update, or delete a church group"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            group = ChurchGroup.objects.select_related("role", "church").get(pk=pk)
            if user.is_platform_admin or group.church_id == user.church_id:
                return group
            return None
        except ChurchGroup.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get church group details",
        responses={200: ChurchGroupSerializer(), 404: "Not found"},
        tags=["Church Groups"],
    )
    def get(self, request, pk):
        group = self.get_object(pk, request.user)
        if group is None:
            return Response(
                {"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = ChurchGroupSerializer(group, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update church group",
        request_body=ChurchGroupSerializer,
        responses={200: ChurchGroupSerializer(), 400: "Bad Request", 404: "Not found"},
        tags=["Church Groups"],
    )
    def put(self, request, pk):
        group = self.get_object(pk, request.user)
        if group is None:
            return Response(
                {"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = ChurchGroupSerializer(
            group, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete church group",
        responses={204: "Deleted", 404: "Not found"},
        tags=["Church Groups"],
    )
    def delete(self, request, pk):
        group = self.get_object(pk, request.user)
        if group is None:
            return Response(
                {"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND
            )
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChurchGroupMemberView(APIView):
    """List members of a group or add a user to the group"""

    permission_classes = [IsAuthenticated]

    def get_group(self, pk, user):
        try:
            group = ChurchGroup.objects.get(pk=pk)
            if user.is_platform_admin or group.church_id == user.church_id:
                return group
            return None
        except ChurchGroup.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get list of group members",
        responses={200: ChurchGroupMemberSerializer(many=True)},
        tags=["Church Groups"],
    )
    def get(self, request, pk):
        group = self.get_group(pk, request.user)
        if group is None:
            return Response(
                {"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND
            )
        members = ChurchGroupMember.objects.filter(group=group).select_related(
            "user", "group"
        )
        serializer = ChurchGroupMemberSerializer(members, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Add user to group (auto-assigns group's role)",
        request_body=ChurchGroupMemberCreateSerializer,
        responses={
            201: ChurchGroupMemberSerializer(),
            400: "Bad Request",
            404: "Not found",
        },
        tags=["Church Groups"],
    )
    def post(self, request, pk):
        group = self.get_group(pk, request.user)
        if group is None:
            return Response(
                {"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = ChurchGroupMemberCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user_id = serializer.validated_data["user_id"]
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if user.church_id != group.church_id:
            return Response(
                {"error": "User must belong to the same church as the group"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member, created = ChurchGroupMember.objects.get_or_create(
            group=group,
            user=user,
            defaults={"added_by": request.user},
        )
        if not created:
            return Response(
                {"error": "User is already in this group"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        s = ChurchGroupMemberSerializer(member)
        return Response(s.data, status=status.HTTP_201_CREATED)


class ChurchGroupMemberDetailAPIView(APIView):
    """Remove a user from a group"""

    permission_classes = [IsAuthenticated]

    def get_object(self, group_pk, member_pk, user):
        try:
            member = ChurchGroupMember.objects.select_related("group").get(pk=member_pk)
            if member.group_id != group_pk:
                return None
            if user.is_platform_admin or member.group.church_id == user.church_id:
                return member
            return None
        except ChurchGroupMember.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Remove user from group",
        responses={204: "Removed", 404: "Not found"},
        tags=["Church Groups"],
    )
    def delete(self, request, pk, member_pk):
        member = self.get_object(pk, member_pk, request.user)
        if member is None:
            return Response(
                {"error": "Group member not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# MULTI-STEP REGISTRATION FLOW (with payment)
# ==========================================

# Plan IDs and display names for the registration plans API (must match serializer choices)
REGISTRATION_PLAN_CHOICES = [
    ("TRIAL", "30-Day Free Trial"),
    ("FREE", "Free"),
    ("BASIC", "Basic"),
    ("PREMIUM", "Premium"),
    ("ENTERPRISE", "Enterprise"),
]


@api_view(["GET"])
@permission_classes([AllowAny])
def registration_plans(request):
    """
    Return list of subscription plans for the frontend (pricing, features, etc.).
    Single source of truth for registration plan options.
    """
    serializer = ChurchRegistrationStep3Serializer()
    plans = []
    for plan_id, plan_name in REGISTRATION_PLAN_CHOICES:
        details_m = serializer.get_plan_details(plan_id, "MONTHLY")
        details_y = (
            serializer.get_plan_details(plan_id, "YEARLY")
            if plan_id not in ("TRIAL", "FREE")
            else details_m
        )
        monthly_price = details_m.get("monthly_price", 0) or details_m.get(
            "total_price", 0
        )
        yearly_price = (
            details_y.get("total_price", 0) if plan_id not in ("TRIAL", "FREE") else 0
        )
        plans.append(
            {
                "id": plan_id,
                "name": plan_name,
                "monthly_price": monthly_price,
                "yearly_price": yearly_price,
                "description": details_m.get("description", ""),
                "features": details_m.get("features", []),
                "requires_payment": details_m.get("requires_payment", False),
            }
        )
    return Response(plans)


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_step1(request):
    """
    Step 1: Validate and store church information in database
    """
    serializer = ChurchRegistrationStep1Serializer(data=request.data)
    if serializer.is_valid():
        # Create a new registration session with church data under 'church' key
        session = RegistrationSession.objects.create(
            step=1,
            data={"church": serializer.validated_data},  # Store under 'church' key
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        return Response(
            {
                "status": "success",
                "message": "Church information validated",
                "session_id": str(session.id),
                "data": serializer.validated_data,
            }
        )
    return Response(
        {"status": "error", "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_step2(request):
    """
    Step 2: Validate and store admin information in database
    """
    session_id = request.data.get("session_id")
    if not session_id:
        return Response(
            {"status": "error", "message": "Session ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Get the registration session (allow step=1 or step=2 so user can go Back and re-submit)
        session = RegistrationSession.objects.get(
            Q(id=session_id)
            & (Q(step=1) | Q(step=2))
            & Q(expires_at__gt=timezone.now())
        )
    except RegistrationSession.DoesNotExist:
        return Response(
            {
                "status": "error",
                "message": "Please complete step 1 first or session expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ChurchRegistrationStep2Serializer(data=request.data)
    if serializer.is_valid():
        # Update the session with step 2 data
        session.data["admin"] = serializer.validated_data
        session.step = 2
        session.expires_at = timezone.now() + timezone.timedelta(hours=1)
        session.save()

        return Response(
            {
                "status": "success",
                "message": "Admin information validated",
                "session_id": str(session.id),
                "data": {
                    "email": serializer.validated_data["admin_email"],
                    "first_name": serializer.validated_data["first_name"],
                    "last_name": serializer.validated_data["last_name"],
                    "position": serializer.validated_data["position"],
                },
            }
        )
    return Response(
        {"status": "error", "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_step3(request):
    """
    Step 3: Select subscription plan and get pricing details
    """
    session_id = request.data.get("session_id")
    if not session_id:
        return Response(
            {"status": "error", "message": "Session ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Get the registration session (allow step=2 or step=3 so user can go Back and re-submit)
        session = RegistrationSession.objects.get(
            Q(id=session_id)
            & (Q(step=2) | Q(step=3))
            & Q(expires_at__gt=timezone.now())
        )
    except RegistrationSession.DoesNotExist:
        return Response(
            {
                "status": "error",
                "message": "Please complete step 2 first or session expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ChurchRegistrationStep3Serializer(data=request.data)
    if serializer.is_valid():
        # Update the session with step 3 data
        session.data["plan"] = serializer.validated_data
        session.step = 3
        session.expires_at = timezone.now() + timezone.timedelta(hours=1)
        session.save()

        plan = serializer.validated_data["subscription_plan"]
        cycle = serializer.validated_data["billing_cycle"]

        # Get plan details and pricing
        plan_details = serializer.get_plan_details(plan, cycle)

        return Response(
            {
                "status": "success",
                "message": "Subscription plan selected",
                "session_id": str(session.id),
                "plan_details": plan_details,
            }
        )
    return Response(
        {"status": "error", "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _normalize_billing_cycle(value, subscription_plan=None):
    """For FREE use 'FREE'; for TRIAL allow '14' (14-day) or default to 'FREE' (30-day); for paid use 'MONTHLY' when empty."""
    raw = (value or "").strip()
    if raw:
        return raw
    if subscription_plan == "FREE":
        return "FREE"
    if subscription_plan == "TRIAL":
        return "FREE"  # 30-day trial when empty; send "14" for 14-day trial
    return "MONTHLY"


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_initialize_payment(request):
    """
    Step 4: Initialize Paystack payment for registration (or skip for FREE plan)
    """
    session_id = request.data.get("session_id")
    if not session_id:
        return Response(
            {"status": "error", "message": "Session ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        session = RegistrationSession.objects.get(
            id=session_id, expires_at__gt=timezone.now()
        )
    except RegistrationSession.DoesNotExist:
        return Response(
            {
                "status": "error",
                "message": (
                    "Registration session not found or expired. "
                    "Please start signup again from the beginning."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except (ValueError, TypeError, ValidationError):
        return Response(
            {"status": "error", "message": "Invalid session id."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Must have completed plan selection (step 3 on server)
    if session.step < 3:
        plan_stub = session.data.get("plan") or {}
        if plan_stub.get("subscription_plan"):
            session.step = 3
            session.save(update_fields=["step", "updated_at"])
        else:
            return Response(
                {
                    "status": "error",
                    "message": (
                        "Please complete the subscription plan step before paying. "
                        "Go back and continue from plan selection."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Get data from session with proper structure handling
    step1_data = session.data.get("church", {}) or {
        k: v
        for k, v in session.data.items()
        if k not in ["admin", "plan", "payment_reference"]
    }
    step2_data = session.data.get("admin", {})
    step3_data = session.data.get("plan", {})

    logger.info(f"[Initialize Payment] Step1 data: {step1_data}")
    logger.info(f"[Initialize Payment] Step2 data: {step2_data}")
    logger.info(f"[Initialize Payment] Step3 data: {step3_data}")

    try:
        step3_serializer = ChurchRegistrationStep3Serializer(data=step3_data)
        if not step3_serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": (
                        "Subscription data is missing or invalid. "
                        "Go back to the plan step and select your plan again."
                    ),
                    "errors": step3_serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vd = step3_serializer.validated_data
        sub_plan = vd["subscription_plan"]
        billing_cycle = (vd.get("billing_cycle") or "").strip() or "MONTHLY"
        if billing_cycle.upper() in ("MONTHLY", "YEARLY"):
            billing_cycle = billing_cycle.upper()

        plan_details = step3_serializer.get_plan_details(sub_plan, billing_cycle)

        # Check if it's FREE or TRIAL plan - complete registration immediately (no verify-payment needed)
        if sub_plan in ("FREE", "TRIAL"):
            if not all(
                [
                    step1_data.get("church_name"),
                    step1_data.get("church_email"),
                    step1_data.get("subdomain"),
                ]
            ):
                return Response(
                    {
                        "status": "error",
                        "message": "Missing required church information. Please complete step 1.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not all(
                [
                    step2_data.get("first_name"),
                    step2_data.get("last_name"),
                    step2_data.get("admin_email"),
                    step2_data.get("password"),
                ]
            ):
                return Response(
                    {
                        "status": "error",
                        "message": "Missing required admin information. Please complete step 2.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            prefix = sub_plan
            reference = f"{prefix}_{session_id}_{int(time.time())}"

            # Build registration data and complete registration in one step
            registration_data = {
                "church_name": step1_data.get("church_name"),
                "church_email": step1_data.get("church_email"),
                "subdomain": step1_data.get("subdomain"),
                "denomination": step1_data.get("denomination", ""),
                "country": step1_data.get("country"),
                "region": step1_data.get("region"),
                "city": step1_data.get("city"),
                "address": step1_data.get("address", ""),
                "website": step1_data.get("website", ""),
                "phone": step2_data.get("phone_number", ""),
                "church_size": step1_data.get("church_size"),
                "first_name": step2_data.get("first_name"),
                "last_name": step2_data.get("last_name"),
                "admin_email": step2_data.get("admin_email"),
                "phone_number": step2_data.get("phone_number"),
                "position": step2_data.get("position"),
                "password": step2_data.get("password"),
                "subscription_plan": sub_plan,
                "billing_cycle": _normalize_billing_cycle(
                    vd.get("billing_cycle"), sub_plan
                ),
                "payment_reference": reference,
                "payment_amount": 0,
            }

            serializer = ChurchRegistrationCompleteSerializer(data=registration_data)
            if serializer.is_valid():
                result = serializer.save()
                session.delete()
                refresh = RefreshToken.for_user(result["user"])
                return Response(
                    {
                        "status": "success",
                        "message": "Registration completed successfully",
                        "user": UserSerializer(result["user"]).data,
                        "church": ChurchSerializer(result["church"]).data,
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {"status": "error", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Paid plans: Initialize Paystack payment
        admin_email = (step2_data.get("admin_email") or "").strip()
        if not admin_email:
            return Response(
                {
                    "status": "error",
                    "message": (
                        "Missing admin email from registration. "
                        "Please go back and complete the admin details step."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference = f"REG_{session_id}_{int(time.time())}"

        paystack = PaystackAPI()

        logger.info(
            "Initializing Paystack payment: email=%s, amount=%s, plan=%s",
            admin_email,
            plan_details["total_price"],
            sub_plan,
        )

        response = paystack.initialize_transaction(
            email=admin_email,
            amount=float(plan_details["total_price"]),
            reference=reference,
            metadata={
                "session_id": str(session_id),
                "purpose": "church_registration",
                "subscription_plan": sub_plan,
                "billing_cycle": _normalize_billing_cycle(
                    vd.get("billing_cycle"), sub_plan
                ),
                "church_name": step1_data.get("church_name", "Church"),
                "admin_email": admin_email,
            },
        )

        if response.get("status") is True:
            payload = response.get("data") or {}
            authorization_url = payload.get("authorization_url")
            if not authorization_url:
                logger.error(
                    "Paystack returned success but no authorization_url: %s", response
                )
                return Response(
                    {
                        "status": "error",
                        "message": "Payment gateway did not return a checkout URL. Try again later.",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            session.data["payment_reference"] = reference
            session.save()

            return Response(
                {
                    "status": "success",
                    "authorization_url": authorization_url,
                    "access_code": payload.get("access_code", ""),
                    "reference": reference,
                    "amount": plan_details["total_price"],
                    "session_id": str(session.id),
                    "requires_payment": True,
                },
                status=status.HTTP_200_OK,
            )

        paystack_msg = (
            response.get("message") or "Failed to initialize payment with Paystack"
        )
        logger.warning("Paystack initialize failed: %s", paystack_msg)
        return Response(
            {
                "status": "error",
                "message": paystack_msg,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(
            f"Error initializing registration payment: {str(e)}", exc_info=True
        )
        return Response(
            {
                "status": "error",
                "message": "An error occurred while processing payment",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_verify_payment(request):
    """
    Step 5: Verify payment and complete church registration
    (Skips payment verification for FREE plan)
    """
    session_id = request.data.get("session_id")
    reference = request.data.get("reference")

    if not session_id:
        return Response(
            {"status": "error", "message": "Session ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Get the registration session
        session = RegistrationSession.objects.get(
            id=session_id, step=3, expires_at__gt=timezone.now()
        )
    except RegistrationSession.DoesNotExist:
        return Response(
            {
                "status": "error",
                "message": "Registration session expired or invalid. Please start over.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get data from session with proper error handling
    logger.info(f"Session data: {session.data}")  # Debug log

    # Check if church data is under 'church' key or at root
    if "church" in session.data:
        step1_data = session.data["church"]
    else:
        # If not under 'church' key, the data is at the root
        step1_data = {
            k: v
            for k, v in session.data.items()
            if k not in ["admin", "plan", "payment_reference"]
        }

    step2_data = session.data.get("admin", {})
    step3_data = session.data.get("plan", {})

    logger.info(f"Step1 data: {step1_data}")  # Debug log
    logger.info(f"Step2 data: {step2_data}")  # Debug log
    logger.info(f"Step3 data: {step3_data}")  # Debug log

    # Check if required data exists
    if not all(
        [
            step1_data.get("church_name"),
            step1_data.get("church_email"),
            step1_data.get("subdomain"),
        ]
    ):
        return Response(
            {
                "status": "error",
                "message": "Missing required church information. Please start registration again.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not all(
        [
            step2_data.get("first_name"),
            step2_data.get("last_name"),
            step2_data.get("admin_email"),
            step2_data.get("password"),
        ]
    ):
        return Response(
            {
                "status": "error",
                "message": "Missing required admin information. Please complete step 2 again.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not step3_data.get("subscription_plan"):
        return Response(
            {
                "status": "error",
                "message": "No subscription plan selected. Please complete step 3 again.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if it's FREE or TRIAL plan - skip payment verification
    if step3_data["subscription_plan"] in ("FREE", "TRIAL"):
        # For FREE plan, no payment verification needed
        # Get reference from session if it exists, otherwise generate one
        reference = session.data.get("payment_reference")
        if not reference:
            prefix = step3_data["subscription_plan"]
            reference = f"{prefix}_{session_id}_{int(time.time())}"
        payment_amount = 0

        # Save the reference to session for verification
        session.data["payment_reference"] = reference
        session.save()  # 1 hour expiry

        # Combine all data for final registration with proper field mapping
        registration_data = {
            # Step 1 data
            "church_name": step1_data.get("church_name"),
            "church_email": step1_data.get("church_email"),
            "subdomain": step1_data.get("subdomain"),
            "denomination": step1_data.get("denomination", ""),
            "country": step1_data.get("country"),
            "region": step1_data.get("region"),
            "city": step1_data.get("city"),
            "address": step1_data.get("address", ""),
            "website": step1_data.get("website", ""),
            "phone": step2_data.get("phone_number", ""),  # Using phone from admin info
            "church_size": step1_data.get("church_size"),
            # Step 2 data
            "first_name": step2_data.get("first_name"),
            "last_name": step2_data.get("last_name"),
            "admin_email": step2_data.get("admin_email"),
            "phone_number": step2_data.get("phone_number"),
            "position": step2_data.get("position"),
            "password": step2_data.get("password"),
            # Step 3 data
            "subscription_plan": step3_data.get("subscription_plan"),
            "billing_cycle": _normalize_billing_cycle(
                step3_data.get("billing_cycle"), step3_data.get("subscription_plan")
            ),
            # Payment data
            "payment_reference": reference,
            "payment_amount": payment_amount,
        }

        # Create church and admin user
        serializer = ChurchRegistrationCompleteSerializer(data=registration_data)

        if serializer.is_valid():
            result = serializer.save()

            # Delete the session after successful registration
            session.delete()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(result["user"])

            return Response(
                {
                    "status": "success",
                    "message": "Registration completed successfully",
                    "user": UserSerializer(result["user"]).data,
                    "church": ChurchSerializer(result["church"]).data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"status": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    else:
        # Verify payment with Paystack for paid plans
        if not reference:
            return Response(
                {
                    "status": "error",
                    "message": "Payment reference is required for paid plans",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        paystack = PaystackAPI()
        verification = paystack.verify_transaction(reference)

        # Update payment status based on verification
        try:
            from .models import Payment

            payment = Payment.objects.filter(reference=reference).first()

            if (
                verification.get("status")
                and verification["data"]["status"] == "success"
            ):
                # Payment successful
                payment_amount = (
                    verification["data"]["amount"] / 100
                )  # Convert from kobo

                if payment:
                    payment.status = "SUCCESSFUL"
                    payment.amount = payment_amount
                    payment.payment_date = timezone.now()
                    payment.payment_details.update(
                        {
                            "status": "success",
                            "verified_at": timezone.now().isoformat(),
                            "paystack_reference": verification["data"].get("reference"),
                            "paystack_message": verification["message"],
                        }
                    )
                    payment.save()
            else:
                # Payment failed
                if payment:
                    payment.status = "FAILED"
                    payment.payment_details.update(
                        {
                            "status": "failed",
                            "verified_at": timezone.now().isoformat(),
                            "paystack_reference": verification.get("data", {}).get(
                                "reference"
                            ),
                            "paystack_message": verification.get(
                                "message", "Payment verification failed"
                            ),
                            "failure_reason": verification.get("data", {}).get(
                                "gateway_response"
                            ),
                        }
                    )
                    payment.save()

                return Response(
                    {
                        "status": "error",
                        "message": "Payment verification failed",
                        "details": verification.get("data", {}).get(
                            "gateway_response", "Payment was not successful"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Error updating payment status: {str(e)}", exc_info=True)
            # Continue with the registration even if payment update fails
            payment_amount = (
                verification["data"]["amount"] / 100 if verification.get("data") else 0
            )

        # Combine all data for final registration
        registration_data = {
            **step1_data,
            **step2_data,
            **step3_data,
            "payment_reference": reference,
            "payment_amount": payment_amount,
        }
        # Normalize empty billing_cycle: FREE/TRIAL -> 'FREE' (free forever), paid -> 'MONTHLY'
        registration_data["billing_cycle"] = _normalize_billing_cycle(
            registration_data.get("billing_cycle"),
            registration_data.get("subscription_plan"),
        )

        # Create church and admin user
        serializer = ChurchRegistrationCompleteSerializer(data=registration_data)

        if serializer.is_valid():
            result = serializer.save()

            # Delete the session after successful registration
            session.delete()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(result["user"])

            return Response(
                {
                    "status": "success",
                    "message": "Registration completed successfully",
                    "user": UserSerializer(result["user"]).data,
                    "church": ChurchSerializer(result["church"]).data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"status": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def registration_payment_callback(request):
    """
    Handle Paystack redirect after payment
    This is where Paystack redirects users after payment
    """
    reference = request.query_params.get("reference")

    if not reference:
        return Response(
            {"status": "error", "message": "Payment reference is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Extract session_id from reference (format: REG_{session_id}_{timestamp})
    try:
        parts = reference.split("_")
        session_id = parts[1] if len(parts) >= 3 else None

        if not session_id:
            return Response(
                {"status": "error", "message": "Invalid payment reference"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return session_id and reference for frontend to complete registration
        return Response(
            {
                "status": "success",
                "message": "Payment received. Please complete registration.",
                "reference": reference,
                "session_id": session_id,
                "next_step": "registration/verify-payment/",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error processing payment callback: {str(e)}", exc_info=True)
        return Response(
            {
                "status": "error",
                "message": "An error occurred processing payment callback",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
