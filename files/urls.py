from django.urls import path

from .views import (FileDetailView, FileListView, FileUploadMultipleView,
                    FileUploadView)

app_name = "files"

urlpatterns = [
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path(
        "upload-multiple/",
        FileUploadMultipleView.as_view(),
        name="file-upload-multiple",
    ),
    path("list/", FileListView.as_view(), name="file-list"),
    path("<uuid:id>/", FileDetailView.as_view(), name="file-detail"),
]
