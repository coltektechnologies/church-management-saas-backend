# File Management (Phase 5.1) – Cloudinary

## Setup

1. **Environment variables** (in `.env`; never commit the secret):

   ```env
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=845419382116136
   CLOUDINARY_API_SECRET=your_api_secret
   ```

   Get `CLOUDINARY_CLOUD_NAME` from your [Cloudinary Dashboard](https://console.cloudinary.com/).
   **Do not put `CLOUDINARY_API_SECRET` in code or in version control.**

2. **Optional** (defaults in code):

   ```env
   FILE_MAX_SIZE_MB=20
   ```

3. **Migrations**:

   ```bash
   python manage.py migrate files
   ```

## Folder structure

Uploads are stored in Cloudinary under:

- **`{church_name}/files/`** – base folder for the church (church name sanitized, lowercased).
- **`{church_name}/files/{subfolder}/`** – optional subfolder per upload (e.g. `documents`, `bulletins`).

So each church has its own root folder, with optional subfolders inside it.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/files/upload/` | Single file (multipart: `file`, optional `subfolder`, `description`, `tags`) |
| POST | `/api/files/upload-multiple/` | Multiple files (form: `files[]` or `file_1`, `file_2`, ...; optional `subfolder`) |
| GET | `/api/files/list/` | List church files (optional `?subfolder=`, `?is_image=true`) |
| GET | `/api/files/<uuid:id>/` | File metadata by ID |
| DELETE | `/api/files/<uuid:id>/` | Soft-delete file (cleanup from Cloudinary runs via scheduled task) |

All require authentication and are church-scoped (`current_church` or `user.church`).

## Features

- **Validation**: Allowed types (images, PDF, Office, text, video) and max size (default 20 MB).
- **Image compression**: Images uploaded with `quality=auto:good` and `fetch_format=auto`.
- **Access control**: Only users with church context can list/read/delete that church’s files.
- **Versioning**: Cloudinary version stored in `cloudinary_version` on each file.
- **Cleanup**: Soft-deleted files are purged from Cloudinary by the `cleanup_deleted_files` Celery task (daily at 03:00).
