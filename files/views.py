"""
File management API: upload (single/multiple), get, list, delete.
Church-scoped; access control via church context.
"""

from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models.base_models import AuditLog

from .models import ChurchFile
from .serializers import ChurchFileListSerializer, ChurchFileSerializer
from .services import CloudinaryFileService


def _church_from_request(request):
    return getattr(request, "current_church", None) or getattr(
        request.user, "church", None
    )


def _get_church_file(church, file_id) -> ChurchFile | None:
    return (
        ChurchFile.objects.filter(church=church, deleted_at__isnull=True)
        .filter(id=file_id)
        .first()
    )


class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Upload a single file to Cloudinary in the church's folder (church_name/files/subfolder).",
        manual_parameters=[
            openapi.Parameter(
                "file", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True
            ),
            openapi.Parameter(
                "subfolder", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False
            ),
            openapi.Parameter(
                "description", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False
            ),
        ],
        tags=["Files"],
    )
    def post(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        subfolder = (request.data.get("subfolder") or "").strip()[:100]
        description = (request.data.get("description") or "").strip()[:500]
        tags = request.data.get("tags")
        if isinstance(tags, list):
            tags = [str(t)[:50] for t in tags[:20]]
        else:
            tags = []

        try:
            service = CloudinaryFileService(church)
            church_file = service.upload(
                file_obj,
                uploaded_by_id=request.user.id,
                subfolder=subfolder,
                description=description,
                tags=tags or None,
            )
            AuditLog.log(
                request.user,
                "CREATE",
                church_file,
                request=request,
                description=f"File uploaded: {church_file.original_filename}"
                + (f" to {subfolder}/" if subfolder else ""),
            )
            return Response(
                ChurchFileSerializer(church_file).data, status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Upload failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FileUploadMultipleView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Upload multiple files. Use form field 'files' multiple times or 'file_1', 'file_2', ...",
        manual_parameters=[
            openapi.Parameter(
                "subfolder", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False
            ),
        ],
        tags=["Files"],
    )
    def post(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Support both: multiple "files" and "file_1", "file_2"
        file_list = list(request.FILES.getlist("files"))
        if not file_list:
            for key in sorted(request.FILES.keys()):
                if key.startswith("file_"):
                    file_list.append(request.FILES[key])
        if not file_list:
            return Response(
                {"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        subfolder = (request.data.get("subfolder") or "").strip()[:100]
        service = CloudinaryFileService(church)
        created = []
        errors = []

        for f in file_list:
            try:
                church_file = service.upload(
                    f,
                    uploaded_by_id=request.user.id,
                    subfolder=subfolder,
                )
                created.append(ChurchFileSerializer(church_file).data)
            except ValueError as e:
                errors.append({"filename": getattr(f, "name", ""), "error": str(e)})
            except Exception as e:
                errors.append({"filename": getattr(f, "name", ""), "error": str(e)})

        return Response(
            {"uploaded": created, "errors": errors},
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )


class FileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get file metadata by ID.", tags=["Files"]
    )
    def get(self, request, id):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        church_file = _get_church_file(church, id)
        if not church_file:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(ChurchFileSerializer(church_file).data)

    @swagger_auto_schema(
        operation_description="Soft-delete file (removed from list; Cloudinary cleanup via task).",
        tags=["Files"],
    )
    def delete(self, request, id):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        church_file = _get_church_file(church, id)
        if not church_file:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        church_file.deleted_at = timezone.now()
        church_file.save(update_fields=["deleted_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List church files with optional subfolder filter.",
        manual_parameters=[
            openapi.Parameter("subfolder", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("is_image", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
        ],
        tags=["Files"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        qs = ChurchFile.objects.filter(church=church, deleted_at__isnull=True).order_by(
            "-created_at"
        )
        subfolder = (request.query_params.get("subfolder") or "").strip()
        if subfolder:
            qs = qs.filter(subfolder=subfolder)
        is_image = request.query_params.get("is_image")
        if is_image is not None:
            qs = qs.filter(is_image=is_image.lower() == "true")
        serializer = ChurchFileListSerializer(qs, many=True)
        return Response(serializer.data)
