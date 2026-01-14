from django.db import transaction
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Member, MemberLocation, Visitor
from .serializers import (MemberLocationSerializer, MemberSerializer,
                          VisitorSerializer, VisitorToMemberSerializer)

# ==========================================
# MEMBER VIEWS
# ==========================================


class MemberView(APIView):
    """List all members or create a new one"""

    permission_classes = [IsAuthenticated]  # ✅ Add authentication

    @swagger_auto_schema(
        operation_description="Get list of all members",
        responses={200: MemberSerializer(many=True), 401: "Unauthorized"},
        tags=["Members"],
    )
    def get(self, request):
        members = Member.objects.filter(church=request.user.church)
        serializer = MemberSerializer(members, many=True, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new member",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "title": openapi.Schema(type=openapi.TYPE_STRING, example="Mr"),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="John"),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Doe"),
                "gender": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["MALE", "FEMALE"], example="MALE"
                ),
                "marital_status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["SINGLE", "MARRIED", "WIDOWED", "DIVORCED"],
                    example="SINGLE",
                ),
                "national_id": openapi.Schema(
                    type=openapi.TYPE_STRING, example="GHA-1234567-89"
                ),
                "membership_status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["ACTIVE", "TRANSFER", "NEW_CONVERT", "VISITOR", "INACTIVE"],
                    example="ACTIVE",
                ),
                "member_since": openapi.Schema(
                    type=openapi.TYPE_STRING, example="2022-01-01"
                ),
                "education_level": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[
                        "PRIMARY",
                        "SECONDARY",
                        "TERTIARY",
                        "GRADUATE",
                        "POSTGRADUATE",
                    ],
                    example="PRIMARY",
                ),
                "occupation": openapi.Schema(
                    type=openapi.TYPE_STRING, example="Software Engineer"
                ),
                "employer": openapi.Schema(
                    type=openapi.TYPE_STRING, example="Tech Company"
                ),
                "profile_photo": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="https://example.com/profile_photo.jpg",
                ),
                "notes": openapi.Schema(
                    type=openapi.TYPE_STRING, example="Notes about the member"
                ),
            },
        ),
        responses={201: MemberSerializer(), 400: "Bad Request", 401: "Unauthorized"},
        tags=["Members"],
    )
    def post(self, request):
        serializer = MemberSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberDetailAPIView(APIView):
    """Retrieve, update or delete a member instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """Get member with permission check"""
        try:
            member = Member.objects.get(pk=pk, deleted_at__isnull=True)

            # Platform admins can access any member
            if user.is_platform_admin:
                return member

            # Regular users can only access their own members
            if user.church_id == member.church_id:
                return member

            return None
        except Member.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get member details by ID",
        responses={200: MemberSerializer(), 403: "Forbidden", 404: "Member not found"},
        tags=["Members"],
    )
    def get(self, request, pk):
        member = self.get_object(pk, request.user)
        if member is None:
            return Response(
                {"error": "Member not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MemberSerializer(member, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update member details",
        request_body=MemberSerializer,
        responses={
            200: MemberSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Member not found",
        },
        tags=["Members"],
    )
    def put(self, request, pk):
        member = self.get_object(pk, request.user)
        if member is None:
            return Response(
                {"error": "Member not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MemberSerializer(
            member, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a member (soft delete - Platform admins only)",
        responses={
            204: "Member deleted successfully",
            403: "Forbidden",
            404: "Member not found",
        },
        tags=["Members"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can delete members"},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = self.get_object(pk, request.user)
        if member is None:
            return Response(
                {"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Soft delete
        member.deleted_at = timezone.now()
        member.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# Visitor VIEWS
# ==========================================
class VisitorView(APIView):
    """List all visitors or create a new one"""

    permission_classes = [IsAuthenticated]  # ✅ Add authentication

    @swagger_auto_schema(
        operation_description="Get list of all visitors",
        responses={200: VisitorSerializer(many=True), 401: "Unauthorized"},
        tags=["Visitors"],
    )
    def get(self, request):
        visitors = Visitor.objects.filter(church=request.user.church)
        serializer = VisitorSerializer(
            visitors, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new visitor",
        required=["full_name", "phone", "first_visit_date"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["full_name", "phone", "first_visit_date"],
            properties={
                "full_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="John Doe",
                    description="Visitor's full name",
                ),
                "gender": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["MALE", "FEMALE"],
                    example="MALE",
                    description="Gender of the visitor",
                ),
                "phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="+233501234567",
                    description="Primary phone number",
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="john@example.com",
                    description="Email address (optional)",
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Accra",
                    description="City of the visitor (optional)",
                ),
                "first_visit_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    example="2026-01-14",
                    description="Date of first visit",
                ),
                "referral_source": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Friend",
                    description="How the visitor heard about the church",
                ),
                "receive_updates": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    example=True,
                    description="Whether the visitor wants updates",
                ),
            },
        ),
        responses={201: VisitorSerializer(), 400: "Bad Request", 401: "Unauthorized"},
        tags=["Visitors"],
    )
    def post(self, request):
        serializer = VisitorSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# Visitor Detail View
# ==========================================


class VisitorDetailAPIView(APIView):
    """Retrieve, Create, update or delete a visitor instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            visitor = Visitor.objects.get(pk=pk, deleted_at__isnull=True)

            # Platform admins can access any visitor
            if user.is_platform_admin:
                return visitor

            # Regular users can only access their own visitors
            if user.church_id == visitor.church_id:
                return visitor

            return None
        except Visitor.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Create a new visitor",
        required=["full_name", "phone", "first_visit_date"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["full_name", "phone", "first_visit_date"],
            properties={
                "full_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="John Doe",
                    description="Visitor's full name",
                ),
                "gender": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["MALE", "FEMALE"],
                    example="MALE",
                    description="Gender of the visitor",
                ),
                "phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="+233501234567",
                    description="Primary phone number",
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="john@example.com",
                    description="Email address (optional)",
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Accra",
                    description="City of the visitor (optional)",
                ),
                "first_visit_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    example="2026-01-14",
                    description="Date of first visit",
                ),
                "referral_source": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Friend",
                    description="How the visitor heard about the church",
                ),
                "receive_updates": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    example=True,
                    description="Whether the visitor wants updates",
                ),
            },
        ),
        responses={201: VisitorSerializer(), 400: "Bad Request", 401: "Unauthorized"},
        tags=["Visitors"],
    )
    def post(self, request):
        serializer = VisitorSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Get visitor details by ID",
        responses={
            200: VisitorSerializer(),
            403: "Forbidden",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def get(self, request, pk):
        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"error": "Visitor not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VisitorSerializer(visitor, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update visitor details by ID",
        request_body=VisitorSerializer,
        responses={
            200: VisitorSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def put(self, request, pk):
        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"error": "Visitor not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VisitorSerializer(
            visitor, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a visitor (soft delete - Platform admins only)",
        responses={
            204: "Visitor deleted successfully",
            403: "Forbidden",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def delete(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {"error": "Only platform administrators can delete visitors"},
                status=status.HTTP_403_FORBIDDEN,
            )

        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"error": "Visitor not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Soft delete
        visitor.deleted_at = timezone.now()
        visitor.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# VISITOR TO MEMBER CONVERSION VIEW
# ==========================================
class VisitorToMemberView(APIView):
    """Convert a visitor to a church member"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Convert a visitor to a church member",
        request_body=VisitorToMemberSerializer,
        responses={
            201: MemberSerializer(),
            400: "Bad Request",
            403: "Forbidden",
            404: "Visitor not found",
        },
        tags=["Members"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = VisitorToMemberSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            member = serializer.save()
            member_serializer = MemberSerializer(member, context={"request": request})
            return Response(member_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
