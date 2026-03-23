from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Church
from accounts.permissions import user_may_access_church_id

from .models import Department


class DepartmentsByChurchListView(APIView):
    """
    GET /api/departments/by-church/?church_id=<uuid>
    Requires JWT; user must belong to that church (or be platform admin).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        church_id = request.query_params.get("church_id")
        if not church_id:
            return Response({"error": "church_id parameter is required"}, status=400)

        if not user_may_access_church_id(request.user, church_id):
            return Response(
                {"detail": "You do not have access to this church."}, status=403
            )

        church = get_object_or_404(Church, id=church_id)

        departments = Department.objects.filter(church=church, is_active=True).values(
            "id", "name"
        )
        return Response(list(departments))
