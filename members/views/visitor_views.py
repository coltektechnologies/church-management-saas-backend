from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from members.models import Visitor
from members.serializers import VisitorSerializer, VisitorToMemberSerializer


class VisitorView(APIView):
    """List all visitors or create a new one"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of all visitors",
        responses={200: VisitorSerializer(many=True), 401: "Unauthorized"},
        tags=["Visitors"],
    )
    def get(self, request):
        visitors = Visitor.objects.filter(
            church=request.user.church, deleted_at__isnull=True
        )
        serializer = VisitorSerializer(visitors, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new visitor",
        request_body=VisitorSerializer,
        responses={201: VisitorSerializer(), 400: "Bad Request", 401: "Unauthorized"},
        tags=["Visitors"],
    )
    def post(self, request):
        serializer = VisitorSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VisitorDetailAPIView(APIView):
    """Retrieve, update or delete a visitor instance"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Visitor.objects.get(
                pk=pk, church=user.church, deleted_at__isnull=True
            )
        except Visitor.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Get visitor details",
        responses={
            200: VisitorSerializer(),
            404: "Visitor not found",
            401: "Unauthorized",
        },
        tags=["Visitors"],
    )
    def get(self, request, pk):
        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"detail": "Visitor not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = VisitorSerializer(visitor)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update visitor details",
        request_body=VisitorSerializer,
        responses={
            200: VisitorSerializer(),
            400: "Bad Request",
            401: "Unauthorized",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def put(self, request, pk):
        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"detail": "Visitor not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = VisitorSerializer(visitor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete a visitor",
        responses={
            204: "No Content",
            401: "Unauthorized",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def delete(self, request, pk):
        visitor = self.get_object(pk, request.user)
        if not visitor:
            return Response(
                {"detail": "Visitor not found"}, status=status.HTTP_404_NOT_FOUND
            )

        visitor.deleted_at = timezone.now()
        visitor.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VisitorToMemberView(APIView):
    """Convert a visitor to a church member"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Convert a visitor to a member",
        request_body=VisitorToMemberSerializer,
        responses={
            201: "Member created successfully",
            400: "Bad Request",
            401: "Unauthorized",
            404: "Visitor not found",
        },
        tags=["Visitors"],
    )
    def post(self, request):
        serializer = VisitorToMemberSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            member = serializer.save()
            return Response(
                {
                    "message": "Visitor converted to member successfully",
                    "member_id": str(member.id),
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
