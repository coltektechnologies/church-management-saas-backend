from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Church, Permission, Role, RolePermission, User, UserRole
from .serializers import (ChangePasswordSerializer, ChurchListSerializer,
                          ChurchSerializer, LoginSerializer,
                          PermissionSerializer, RegisterSerializer,
                          RolePermissionSerializer, RoleSerializer,
                          UserCreateSerializer, UserListSerializer,
                          UserRoleSerializer, UserSerializer,
                          UserUpdateSerializer)

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
        operation_description="Create a new user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "username", "password", "password_confirm", "church"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    description="User email address",
                    example="pastor@church.com",
                ),
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Username",
                    example="pastor_john",
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Password (min 8 characters)",
                    example="SecurePass123!",
                ),
                "password_confirm": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="password",
                    description="Confirm password",
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
                    description="Phone number",
                    example="+233244123456",
                ),
                "first_name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="First name", example="John"
                ),
                "last_name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Last name", example="Doe"
                ),
            },
        ),
        responses={
            201: UserSerializer(),
            400: "Bad Request - Validation errors",
            403: "Forbidden",
        },
        tags=["Users"],
    )
    def post(self, request):
        # Check permission to create users
        church_id = request.data.get("church")

        if not request.user.is_platform_admin:
            # Regular users can only create users in their own church
            if str(request.user.church_id) != str(church_id):
                return Response(
                    {"error": "You can only create users in your own church"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = UserCreateSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserSerializer(user, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
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
                    description="Church ID (required for non-platform admins)",
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
    """User registration endpoint"""

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new church and admin user",
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
            401: "Unauthorized",
        },
        tags=["Registration"],
    )
    def post(self, request):
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
        operation_description="Assign a role to a user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["user", "role", "church"],
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
                "church": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Church ID",
                    example="750e8400-e29b-41d4-a716-446655440002",
                ),
            },
        ),
        responses={201: UserRoleSerializer(), 400: "Bad Request", 403: "Forbidden"},
        tags=["Roles & Permissions"],
    )
    def post(self, request):
        church_id = request.data.get("church")

        # Check permission
        if not request.user.is_platform_admin:
            if str(request.user.church_id) != str(church_id):
                return Response(
                    {"error": "You can only assign roles in your own church"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = UserRoleSerializer(data=request.data, context={"request": request})
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
