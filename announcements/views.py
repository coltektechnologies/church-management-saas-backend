from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (Announcement, AnnouncementAttachment,
                     AnnouncementCategory, AnnouncementTemplate)
from .serializers import (AnnouncementAttachmentSerializer,
                          AnnouncementCategorySerializer,
                          AnnouncementCreateSerializer,
                          AnnouncementDetailSerializer,
                          AnnouncementListSerializer,
                          AnnouncementTemplateSerializer,
                          AnnouncementUpdateStatusSerializer)


class AnnouncementCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing announcement categories.
    """

    queryset = AnnouncementCategory.objects.all()
    serializer_class = AnnouncementCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Filter categories by the current user's church
        """
        qs = super().get_queryset()
        if hasattr(self.request.user, "church"):
            return qs.filter(church=self.request.user.church)
        return qs.none()

    def perform_create(self, serializer):
        """Set the church to the current user's church"""
        if hasattr(self.request.user, "church"):
            serializer.save(church=self.request.user.church)
        else:
            raise serializers.ValidationError("User is not associated with any church.")


class AnnouncementTemplateViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing announcement templates.
    """

    queryset = AnnouncementTemplate.objects.all()
    serializer_class = AnnouncementTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name", "subject", "content"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Filter templates by the current user's church
        """
        qs = super().get_queryset()
        if hasattr(self.request.user, "church"):
            return qs.filter(church=self.request.user.church)
        return qs.none()

    def perform_create(self, serializer):
        """Set the church to the current user's church"""
        if hasattr(self.request.user, "church"):
            serializer.save(church=self.request.user.church)
        else:
            raise serializers.ValidationError("User is not associated with any church.")


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing announcements.
    """

    queryset = Announcement.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "status",
        "priority",
        "is_featured",
        "is_pinned",
        "category",
        "created_by",
    ]
    search_fields = ["title", "content"]
    ordering_fields = ["publish_at", "created_at", "priority"]
    ordering = ["-publish_at", "-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return AnnouncementListSerializer
        elif self.action == "retrieve":
            return AnnouncementDetailSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return AnnouncementCreateSerializer
        return AnnouncementDetailSerializer

    def get_queryset(self):
        """
        Filter announcements based on user permissions and query parameters
        """
        qs = super().get_queryset()

        # Filter by church
        if hasattr(self.request.user, "church"):
            qs = qs.filter(church=self.request.user.church)
        else:
            return qs.none()

        # Filter by status
        status_param = self.request.query_params.get("status", None)
        if status_param:
            qs = qs.filter(status=status_param)

        # Filter by date range
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)

        if start_date:
            qs = qs.filter(publish_at__gte=start_date)
        if end_date:
            qs = qs.filter(publish_at__lte=end_date)

        # For non-admin users, only show published or their own announcements
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            qs = qs.filter(Q(status="PUBLISHED") | Q(created_by=self.request.user))

        return qs

    def perform_create(self, serializer):
        """Set the created_by user and church when creating an announcement"""
        if hasattr(self.request.user, "church"):
            serializer.save(
                created_by=self.request.user, church=self.request.user.church
            )
        else:
            raise serializers.ValidationError("User is not associated with any church.")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit an announcement for review"""
        announcement = self.get_object()
        if announcement.status != "DRAFT":
            return Response(
                {"error": "Only draft announcements can be submitted for review."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement.status = "PENDING_REVIEW"
        announcement.save()
        # TODO: Add notification for approvers
        return Response({"status": "submitted for review"})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve an announcement"""
        announcement = self.get_object()
        if announcement.status != "PENDING_REVIEW":
            return Response(
                {"error": "Only announcements pending review can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement.status = "APPROVED"
        announcement.approved_by = request.user
        announcement.approved_at = timezone.now()
        announcement.save()
        # TODO: Add notification for creator
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject an announcement"""
        announcement = self.get_object()
        if announcement.status != "PENDING_REVIEW":
            return Response(
                {"error": "Only announcements pending review can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AnnouncementUpdateStatusSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        announcement.status = "REJECTED"
        announcement.rejection_reason = serializer.validated_data.get(
            "rejection_reason"
        )
        announcement.save()
        # TODO: Add notification for creator
        return Response({"status": "rejected"})

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish an approved announcement"""
        announcement = self.get_object()
        if announcement.status != "APPROVED":
            return Response(
                {"error": "Only approved announcements can be published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement.status = "PUBLISHED"
        if not announcement.publish_at:
            announcement.publish_at = timezone.now()
        announcement.save()
        # TODO: Add notification for subscribers
        return Response({"status": "published"})

    @action(detail=False)
    def pending(self, request):
        """Get all announcements pending review"""
        qs = self.get_queryset().filter(status="PENDING_REVIEW")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def published(self, request):
        """Get all published announcements"""
        qs = self.get_queryset().filter(status="PUBLISHED")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, url_path="stats/summary")
    def stats_summary(self, request):
        """Get summary statistics for announcements"""
        qs = self.get_queryset()

        # Basic counts
        total = qs.count()
        by_status = qs.values("status").annotate(count=Count("id"))
        by_priority = qs.values("priority").annotate(count=Count("id"))

        # Time-based stats with timezone awareness
        now = timezone.now()
        today = now.date()
        this_week = now - timezone.timedelta(days=7)
        this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        recent_stats = {
            "today": qs.filter(created_at__date=now.date()).count(),
            "this_week": qs.filter(created_at__gte=this_week).count(),
            "this_month": qs.filter(created_at__gte=this_month).count(),
        }

        # Category distribution
        category_stats = (
            qs.values("category__name")
            .annotate(
                count=Count("id"),
                published_count=Count("id", filter=Q(status="PUBLISHED")),
                draft_count=Count("id", filter=Q(status="DRAFT")),
            )
            .order_by("-count")
        )

        # User contribution
        user_stats = (
            qs.values("created_by__first_name", "created_by__last_name")
            .annotate(
                count=Count("id"),
                published_count=Count("id", filter=Q(status="PUBLISHED")),
            )
            .order_by("-count")[:5]
        )  # Top 5 contributors

        return Response(
            {
                "total_announcements": total,
                "by_status": by_status,
                "by_priority": by_priority,
                "recent": recent_stats,
                "by_category": category_stats,
                "top_contributors": user_stats,
            }
        )

    @action(detail=False, url_path="stats/timeline")
    def stats_timeline(self, request):
        """Get announcement statistics over time"""
        from django.db.models.functions import TruncDate, TruncMonth

        qs = self.get_queryset()
        time_range = request.query_params.get(
            "range", "month"
        )  # 'day', 'week', 'month', 'year'

        if time_range == "day":
            trunc = TruncDate("created_at")
        else:  # default to month
            trunc = TruncMonth("created_at")

        timeline = (
            qs.annotate(period=trunc)
            .values("period")
            .annotate(
                total=Count("id"),
                published=Count("id", filter=Q(status="PUBLISHED")),
                approved=Count("id", filter=Q(status="APPROVED")),
                pending=Count("id", filter=Q(status="PENDING_REVIEW")),
            )
            .order_by("period")
        )

        return Response({"time_range": time_range, "data": timeline})


class AnnouncementAttachmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing announcement attachments.
    """

    queryset = AnnouncementAttachment.objects.all()
    serializer_class = AnnouncementAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter attachments by announcement and user permissions
        """
        qs = super().get_queryset()
        announcement_id = self.kwargs.get("announcement_id")

        if announcement_id:
            qs = qs.filter(announcement_id=announcement_id)

            # Check if user has permission to view this announcement's attachments
            announcement = Announcement.objects.filter(id=announcement_id).first()

            if not announcement:
                return qs.none()

            if not (
                self.request.user.is_staff
                or self.request.user == announcement.created_by
                or announcement.status == "PUBLISHED"
            ):
                return qs.none()

        return qs

    def perform_create(self, serializer):
        """Set the announcement for new attachments"""
        announcement_id = self.kwargs.get("announcement_id")
        if announcement_id:
            try:
                announcement = Announcement.objects.get(
                    id=announcement_id,
                    created_by=self.request.user,  # Only allow adding attachments to own announcements
                )
                serializer.save(announcement=announcement)
            except Announcement.DoesNotExist:
                raise serializers.ValidationError(
                    "Announcement not found or permission denied."
                )
        else:
            raise serializers.ValidationError("Announcement ID is required.")
