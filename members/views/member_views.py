from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from members.member_serializers import MemberCreateSerializer
from members.models import Member, MemberLocation
from members.serializers import MemberLocationSerializer, MemberSerializer

# ==========================================
# MEMBER VIEWS
# ==========================================


class MemberCreateView(APIView):
    """
    Create a new member with all required information
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new member with all details",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
                "title",
                "first_name",
                "last_name",
                "gender",
                "date_of_birth",
                "marital_status",
                "national_id",
                "phone_number",
                "occupation",
                "residential_address",
                "city",
                "region",
                "emergency_contact",
                "member_since",
                "membership_status",
                "education_level",
                "interested_departments",
            ],
            properties={
                # Personal Information
                "title": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[
                        "Mr",
                        "Mrs",
                        "Miss",
                        "Dr",
                        "Rev",
                        "Pastor",
                        "Elder",
                        "Deacon",
                        "Deaconess",
                    ],
                ),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, maxLength=100),
                "middle_name": openapi.Schema(type=openapi.TYPE_STRING, maxLength=100),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, maxLength=100),
                "gender": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["MALE", "FEMALE"]
                ),
                "date_of_birth": openapi.Schema(
                    type=openapi.FORMAT_DATE, example="1990-01-01"
                ),
                "marital_status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["SINGLE", "MARRIED", "WIDOWED", "DIVORCED"],
                ),
                "national_id": openapi.Schema(type=openapi.TYPE_STRING, maxLength=50),
                # Contact Information
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING, maxLength=20),
                "email": openapi.Schema(type=openapi.FORMAT_EMAIL),
                "occupation": openapi.Schema(type=openapi.TYPE_STRING, maxLength=100),
                "residential_address": openapi.Schema(type=openapi.TYPE_STRING),
                "city": openapi.Schema(type=openapi.TYPE_STRING, maxLength=100),
                "region": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[
                        "Ahafo",
                        "Ashanti",
                        "Bono East",
                        "Bono",
                        "Central",
                        "Eastern",
                        "Greater Accra",
                        "North East",
                        "Northern",
                        "Oti",
                        "Savannah",
                        "Upper East",
                        "Upper West",
                        "Volta",
                        "Western North",
                        "Western",
                        "Other",
                    ],
                ),
                "custom_region": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Required if region is 'Other'",
                ),
                # Emergency Contact
                "emergency_contact": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=["full_name", "relationship", "phone_number"],
                    properties={
                        "full_name": openapi.Schema(
                            type=openapi.TYPE_STRING, maxLength=200
                        ),
                        "relationship": openapi.Schema(
                            type=openapi.TYPE_STRING, maxLength=100
                        ),
                        "phone_number": openapi.Schema(
                            type=openapi.TYPE_STRING, maxLength=20
                        ),
                    },
                ),
                # Church Information
                "member_since": openapi.Schema(
                    type=openapi.FORMAT_DATE, example="2023-01-01"
                ),
                "membership_status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["ACTIVE", "TRANSFER", "NEW_CONVERT", "VISITOR", "INACTIVE"],
                    default="ACTIVE",
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
                ),
                "interested_departments": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING),
                    description="List of department names the member is interested in",
                ),
                # Admin Notes & System Access
                "admin_notes": openapi.Schema(type=openapi.TYPE_STRING),
                "has_system_access": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    default=False,
                    description="Whether to create system access for this member",
                ),
                "send_credentials_via_email": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    default=False,
                    description="Send login credentials via email (requires has_system_access and email)",
                ),
                "send_credentials_via_sms": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    default=False,
                    description="Send login credentials via SMS (requires has_system_access and phone_number)",
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Member created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.FORMAT_UUID),
                        "full_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "member_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "system_access_created": openapi.Schema(
                            type=openapi.TYPE_BOOLEAN,
                            description="Whether system access was created",
                        ),
                        "email": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_EMAIL,
                            description="Email address used for system access",
                            read_only=True,
                        ),
                        "email_sent": openapi.Schema(
                            type=openapi.TYPE_BOOLEAN,
                            description="Whether credentials were sent via email",
                        ),
                        "sms_sent": openapi.Schema(
                            type=openapi.TYPE_BOOLEAN,
                            description="Whether credentials were sent via SMS",
                        ),
                        "notification_error": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Error message if notification sending failed",
                        ),
                    },
                ),
            ),
            400: "Bad Request - Invalid data",
            401: "Unauthorized - Authentication required",
        },
        tags=["Members"],
    )
    def post(self, request, format=None):
        serializer = MemberCreateSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            member = serializer.save()

            response_data = {
                "id": member.id,
                "full_name": member.full_name,
                "member_id": str(member.id),  # Or any other member identifier
                "message": "Member created successfully",
            }

            # Handle system access and notifications
            if serializer.validated_data.get(
                "has_system_access"
            ) and serializer.validated_data.get("email"):
                response_data["system_access_created"] = True
                response_data["email"] = serializer.validated_data["email"]

                # Get the generated password from the serializer if it exists
                password = getattr(serializer, "generated_password", None)

                # Send credentials if requested
                if password:
                    try:
                        from members.services.credential_service import (
                            send_credentials_email, send_credentials_sms)

                        # Send email if requested and email exists
                        if (
                            serializer.validated_data.get("send_credentials_via_email")
                            and member.email
                        ):
                            send_credentials_email(member, member.email, password)
                            response_data["email_sent"] = True

                        # Send SMS if requested and phone number exists
                        if (
                            serializer.validated_data.get("send_credentials_via_sms")
                            and member.phone_number
                        ):
                            send_credentials_sms(
                                member, member.phone_number, password, member.email
                            )
                            response_data["sms_sent"] = True

                    except Exception as e:
                        # Log the error but don't fail the request
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to send credentials: {str(e)}")
                        response_data["notification_error"] = str(e)

            return Response(response_data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberView(APIView):
    """List all members or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all members",
        responses={200: MemberSerializer(many=True), 401: "Unauthorized"},
        tags=["Members"],
    )
    def get(self, request):
        members = Member.objects.filter(
            church=request.user.church, deleted_at__isnull=True
        )
        serializer = MemberSerializer(members, many=True, context={"request": request})
        return Response(serializer.data)


class MemberDetailAPIView(APIView):
    """Retrieve, update or delete a member instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Member.objects.get(
                pk=pk, church=user.church, deleted_at__isnull=True
            )
        except Member.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get member details",
        responses={
            200: MemberSerializer(),
            404: "Member not found",
            401: "Unauthorized",
        },
        tags=["Members"],
    )
    def get(self, request, pk):
        member = self.get_object(pk, request.user)
        if not member:
            return Response(
                {"detail": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = MemberSerializer(member, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update member details",
        request_body=MemberSerializer,
        responses={
            200: MemberSerializer(),
            400: "Bad Request",
            401: "Unauthorized",
            404: "Member not found",
        },
        tags=["Members"],
    )
    def put(self, request, pk):
        member = self.get_object(pk, request.user)
        if not member:
            return Response(
                {"detail": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = MemberSerializer(
            member, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a member",
        responses={
            204: "No Content",
            401: "Unauthorized",
            404: "Member not found",
        },
        tags=["Members"],
    )
    def delete(self, request, pk):
        member = self.get_object(pk, request.user)
        if not member:
            return Response(
                {"detail": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )

        member.deleted_at = timezone.now()
        member.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
