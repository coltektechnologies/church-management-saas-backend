import logging
import threading
from datetime import date
from decimal import Decimal

from django.db.models import Prefetch, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.notification_utils import church_can_use_sms_email
from departments.models import MemberDepartment
from members.member_serializers import MemberCreateSerializer
from members.models import Member, MemberLocation
from members.serializers import (
    MemberLocationSerializer,
    MemberSelfServiceUpdateSerializer,
    MemberSerializer,
)
from members.tasks import run_member_credentials_delivery
from treasury.models import IncomeTransaction, MemberPledge
from treasury.serializers import MemberPledgeSerializer

logger = logging.getLogger(__name__)

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

            # Handle system access and notifications (matches serializer: user is created when
            # has_system_access OR send_credentials_via_email OR send_credentials_via_sms, with email)
            password = getattr(serializer, "generated_password", None)
            if password and serializer.validated_data.get("email"):
                response_data["system_access_created"] = True
                response_data["email"] = serializer.validated_data["email"]
                response_data["username"] = (
                    getattr(serializer, "generated_username", None)
                    or serializer.validated_data["email"]
                )
                response_data["password"] = password

                # Deliver credentials on a daemon thread (no Celery worker required).
                send_email = serializer.validated_data.get(
                    "send_credentials_via_email", False
                )
                send_sms = serializer.validated_data.get(
                    "send_credentials_via_sms", False
                )
                if password and (send_email or send_sms):
                    member_email = getattr(
                        getattr(member, "location", None), "email", None
                    ) or serializer.validated_data.get("email")
                    member_phone = getattr(
                        getattr(member, "location", None), "phone_primary", None
                    )
                    login_username = getattr(
                        serializer, "generated_username", None
                    ) or serializer.validated_data.get("email")
                    church = getattr(member, "church", None) or getattr(
                        request.user, "church", None
                    )
                    allow_staff_invite = False
                    actor = request.user
                    if actor.is_authenticated:
                        if getattr(actor, "is_platform_admin", False):
                            allow_staff_invite = True
                        elif (
                            getattr(actor, "church_id", None)
                            and church
                            and str(actor.church_id) == str(church.id)
                        ):
                            allow_staff_invite = True
                    if not church_can_use_sms_email(
                        church,
                        allow_initial_admin=False,
                        allow_staff_invite=allow_staff_invite,
                    ):
                        response_data["credentials_delivery_queued"] = False
                        response_data["credentials_delivery_skipped_reason"] = (
                            "Outbound email and SMS are disabled for FREE-plan churches. "
                            "Upgrade the church plan or use TRIAL/BASIC+ to send credentials."
                        )
                    else:

                        def _deliver():
                            run_member_credentials_delivery(
                                str(member.id),
                                password,
                                send_email,
                                send_sms,
                                member_email,
                                member_phone,
                                login_username=login_username,
                                allow_staff_invite=allow_staff_invite,
                            )

                        threading.Thread(target=_deliver, daemon=True).start()
                        response_data["credentials_delivery_queued"] = True
                        response_data["credentials_delivery_note"] = (
                            "Delivery runs in the background; check logs if email/SMS "
                            "does not arrive (SMTP, mNotify, and DEFAULT_FROM_EMAIL must be configured)."
                        )

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
        dept_links = MemberDepartment.objects.filter(
            deleted_at__isnull=True
        ).select_related("department")
        qs = Member.objects.filter(deleted_at__isnull=True)
        if getattr(request.user, "is_platform_admin", False):
            cid = request.query_params.get("church_id")
            if cid:
                qs = qs.filter(church_id=cid)
            else:
                # No tenant on platform user: return a recent slice across all churches
                qs = qs.order_by("-created_at")[:500]
        else:
            if not request.user.church_id:
                return Response([])
            qs = qs.filter(church_id=request.user.church_id)
        members = qs.prefetch_related("location").prefetch_related(
            Prefetch("memberdepartment_set", queryset=dept_links)
        )
        serializer = MemberSerializer(members, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, format=None):
        """Create a new member (same as POST /api/members/create/)."""
        return MemberCreateView().post(request, format)


def _current_member_queryset(request):
    """Queryset for the member row linked to `request.user` (portal account)."""
    church_id = getattr(request.user, "church_id", None)
    if not church_id:
        return None
    uid = request.user.id
    dept_links = MemberDepartment.objects.filter(
        deleted_at__isnull=True
    ).select_related("department")
    return (
        Member.objects.filter(
            deleted_at__isnull=True,
            church_id=church_id,
            system_user_id=uid,
        )
        .select_related("location")
        .prefetch_related(
            Prefetch("memberdepartment_set", queryset=dept_links),
        )
    )


class CurrentMemberProfileAPIView(APIView):
    """
    Return or update the church member row linked to the authenticated portal user
    (`Member.system_user_id` == `request.user.id`).
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Get the member profile for the currently authenticated user "
            "(member portal accounts linked via system_user_id)."
        ),
        responses={
            200: MemberSerializer(),
            404: "No member profile linked to this account",
            401: "Unauthorized",
        },
        tags=["Members"],
    )
    def get(self, request):
        qs = _current_member_queryset(request)
        if qs is None:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = qs.first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MemberSerializer(member, context={"request": request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description=(
            "Update allowed fields on the linked member profile (self-service). "
            "Nested `location` updates contact & address. `profile_photo` accepts a URL or "
            "a data URL string."
        ),
        request_body=MemberSelfServiceUpdateSerializer,
        responses={
            200: MemberSerializer(),
            400: "Validation error",
            404: "No member profile linked to this account",
            401: "Unauthorized",
        },
        tags=["Members"],
    )
    def patch(self, request):
        qs = _current_member_queryset(request)
        if qs is None:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = qs.first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MemberSelfServiceUpdateSerializer(
            member, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        fresh = qs.filter(pk=member.pk).first()
        out = MemberSerializer(fresh, context={"request": request})
        return Response(out.data)


class MemberMyGivingSummaryAPIView(APIView):
    """
    YTD total and recent income rows for the member linked to the current user.
    Only transactions with `member` set to that member are included.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Giving summary for the portal member: calendar YTD total of "
            "`IncomeTransaction` rows tied to their member record, plus recent items."
        ),
        responses={
            200: openapi.Response(
                "Giving summary",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "ytd_total": openapi.Schema(type=openapi.TYPE_STRING),
                        "recent": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "id": openapi.Schema(type=openapi.TYPE_STRING),
                                    "transaction_date": openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATE,
                                    ),
                                    "category_name": openapi.Schema(
                                        type=openapi.TYPE_STRING
                                    ),
                                    "amount": openapi.Schema(type=openapi.TYPE_STRING),
                                },
                            ),
                        ),
                    },
                ),
            ),
            404: "No member profile linked to this account",
            401: "Unauthorized",
        },
        tags=["Members"],
    )
    def get(self, request):
        church_id = getattr(request.user, "church_id", None)
        if not church_id:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        uid = request.user.id
        member = Member.objects.filter(
            deleted_at__isnull=True,
            church_id=church_id,
            system_user_id=uid,
        ).first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )

        base_qs = IncomeTransaction.objects.filter(
            church_id=church_id,
            member=member,
            deleted_at__isnull=True,
        ).select_related("category")

        today = timezone.now().date()
        year_start = date(today.year, 1, 1)
        ytd_qs = base_qs.filter(transaction_date__gte=year_start)
        agg = ytd_qs.aggregate(total=Sum("amount"))
        total = agg["total"] if agg["total"] is not None else Decimal("0.00")

        ytd_tithe = Decimal("0.00")
        ytd_offering = Decimal("0.00")
        ytd_other = Decimal("0.00")
        for row in ytd_qs.values(
            "category_id", "category__name", "category__code"
        ).annotate(cat_total=Sum("amount")):
            part = row["cat_total"] if row["cat_total"] is not None else Decimal("0.00")
            name = (row["category__name"] or "").lower()
            code = (row["category__code"] or "").upper()
            if "tithe" in name or code == "TITHE":
                ytd_tithe += part
            elif "offer" in name or code == "OFFERING":
                ytd_offering += part
            else:
                ytd_other += part

        recent_qs = base_qs.order_by("-transaction_date", "-created_at")[:8]
        recent = [
            {
                "id": str(t.id),
                "transaction_date": t.transaction_date.isoformat(),
                "category_name": t.category.name if t.category_id else "",
                "amount": str(t.amount),
            }
            for t in recent_qs
        ]

        history_qs = base_qs.order_by("-transaction_date", "-created_at")[:250]
        history = []
        for t in history_qs:
            history.append(
                {
                    "id": str(t.id),
                    "receipt_number": t.receipt_number,
                    "transaction_date": t.transaction_date.isoformat(),
                    "category_name": t.category.name if t.category_id else "",
                    "amount": str(t.amount),
                    "payment_method": t.get_payment_method_display(),
                }
            )

        return Response(
            {
                "ytd_total": str(total),
                "ytd_tithe": str(ytd_tithe),
                "ytd_offering": str(ytd_offering),
                "ytd_other": str(ytd_other),
                "recent": recent,
                "history": history,
            }
        )


class MemberMyPledgesAPIView(APIView):
    """List or create pledges for the portal member linked to the current user."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List pledges for the authenticated member.",
        responses={200: MemberPledgeSerializer(many=True)},
        tags=["Members"],
    )
    def get(self, request):
        qs = _current_member_queryset(request)
        if qs is None:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = qs.first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        pledges = MemberPledge.objects.filter(
            member=member, church_id=member.church_id
        ).order_by("-pledge_year", "-created_at")
        serializer = MemberPledgeSerializer(
            pledges, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description=(
            "Create a pledge (calendar year + target amount). Progress updates when "
            "treasury records income linked to this pledge."
        ),
        request_body=MemberPledgeSerializer,
        responses={201: MemberPledgeSerializer()},
        tags=["Members"],
    )
    def post(self, request):
        qs = _current_member_queryset(request)
        if qs is None:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = qs.first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MemberPledgeSerializer(
            data=request.data,
            context={
                "request": request,
                "member": member,
                "church": member.church,
            },
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberMyPledgeDetailAPIView(APIView):
    """Cancel a pledge (member-only)."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Cancel your pledge (PATCH with status CANCELLED only).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING, enum=["CANCELLED"]),
            },
            required=["status"],
        ),
        responses={200: MemberPledgeSerializer()},
        tags=["Members"],
    )
    def patch(self, request, pk):
        qs = _current_member_queryset(request)
        if qs is None:
            return Response(
                {"detail": "No church context for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = qs.first()
        if not member:
            return Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        pledge = MemberPledge.objects.filter(
            pk=pk, member=member, church_id=member.church_id
        ).first()
        if not pledge:
            return Response(
                {"detail": "Pledge not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if pledge.status == MemberPledge.STATUS_CANCELLED:
            return Response(
                {"detail": "Pledge is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if pledge.status == MemberPledge.STATUS_FULFILLED:
            return Response(
                {"detail": "Cannot cancel a fulfilled pledge."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        st = request.data.get("status")
        if st != MemberPledge.STATUS_CANCELLED:
            return Response(
                {"detail": "You can only cancel a pledge (set status to CANCELLED)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pledge.status = MemberPledge.STATUS_CANCELLED
        pledge.fulfilled_at = None
        pledge.save(update_fields=["status", "fulfilled_at", "updated_at"])
        out = MemberPledgeSerializer(pledge, context={"request": request})
        return Response(out.data)


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
