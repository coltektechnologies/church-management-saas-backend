"""
Admin-only view: upload file form (uploads to Cloudinary and creates ChurchFile).
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from accounts.models import Church
from files.models import ChurchFile
from files.services import CloudinaryFileService


class FileUploadForm(forms.Form):
    church = forms.ModelChoiceField(
        queryset=Church.objects.none(),
        required=True,
        label="Church",
    )
    file = forms.FileField(required=True, label="File")
    subfolder = forms.CharField(
        required=False,
        max_length=100,
        label="Subfolder (optional)",
        help_text="e.g. documents, bulletins",
    )
    description = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Description (optional)",
    )

    def __init__(self, *args, church_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if church_queryset is not None:
            self.fields["church"].queryset = church_queryset
        else:
            self.fields["church"].queryset = Church.objects.all().order_by("name")


@staff_member_required
def admin_upload_file(request):
    """Render upload form and handle POST: upload to Cloudinary, create ChurchFile."""
    # If user has one church and is not superuser, preselect it
    user_church = getattr(request.user, "church_id", None)
    qs = Church.objects.all().order_by("name")
    if not request.user.is_superuser and user_church:
        qs = qs.filter(id=user_church)

    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES, church_queryset=qs)
        if form.is_valid():
            church = form.cleaned_data["church"]
            file_obj = form.cleaned_data["file"]
            subfolder = (form.cleaned_data.get("subfolder") or "").strip()
            description = (form.cleaned_data.get("description") or "").strip()
            try:
                service = CloudinaryFileService(church)
                church_file = service.upload(
                    file_obj,
                    uploaded_by_id=request.user.id,
                    subfolder=subfolder,
                    description=description,
                )
                messages.success(
                    request,
                    f'File "{church_file.original_filename}" uploaded to {church.name}.',
                )
                return redirect("admin:files_churchfile_changelist")
            except ValueError as e:
                form.add_error("file", str(e))
            except Exception as e:
                form.add_error(None, f"Upload failed: {e}")
    else:
        form = FileUploadForm(church_queryset=qs)
        if not request.user.is_superuser and user_church:
            form.fields["church"].initial = user_church

    # Show who will be recorded as uploader (always pass to template)
    try:
        fn = getattr(request.user, "get_full_name", None)
        name = (fn() if callable(fn) else None) or ""
        name = (name or "").strip()
        uploaded_by_display = (
            name or getattr(request.user, "email", None) or str(request.user)
        )
    except Exception:
        uploaded_by_display = str(request.user)
    return render(
        request,
        "admin/files/churchfile/upload_form.html",
        {
            "form": form,
            "title": "Upload file to Cloudinary",
            "uploaded_by_display": uploaded_by_display,
        },
    )
