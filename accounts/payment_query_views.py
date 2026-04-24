"""Read-only payment listing (Paystack / internal payment log) for platform and church scope."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models.payment import Payment
from .serializers import PaymentListSerializer


class PlatformPaymentListView(APIView):
    """
    GET /api/auth/payments/
    Query: status=FAILED|PENDING|SUCCESSFUL, church_id=uuid, page_size=1-500
    Platform admins: all rows. Other users: their church only.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = Payment.objects.select_related("church").order_by("-payment_date")

        if getattr(user, "is_platform_admin", False):
            tenant_id = None
        else:
            tenant_id = getattr(user, "church_id", None)
            if not tenant_id:
                return Response(
                    {"detail": "Church scope required for payment history."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            qs = qs.filter(church_id=tenant_id)

        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st.strip().upper())

        raw_church = request.query_params.get("church_id")
        if raw_church:
            if getattr(user, "is_platform_admin", False):
                qs = qs.filter(church_id=raw_church)
            elif str(tenant_id) != str(raw_church):
                return Response(
                    {"detail": "Cannot query another church's payments."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                qs = qs.filter(church_id=raw_church)

        try:
            page_size = int(request.query_params.get("page_size", 100))
        except ValueError:
            page_size = 100
        page_size = max(1, min(page_size, 500))

        total = qs.count()
        rows = qs[:page_size]
        ser = PaymentListSerializer(rows, many=True)
        return Response({"results": ser.data, "count": total})
