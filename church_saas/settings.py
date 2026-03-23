import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# Security
# SECRET_KEY = config("SECRET_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
# DEBUG = config("DEBUG", default=True, cast=bool)
DEBUG = os.getenv("DEBUG", default=True).lower() == "true"
# ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Application definition
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Your apps
    "accounts",
    "members",
    "departments",
    "secretariat",
    "treasury",
    "announcements",
    "notifications",
    "core",
    "reports",
    "analytics",
    "files",
    "backup",
    # Third party apps
    "dal",
    "dal_select2",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # For token rotation
    "corsheaders",
    "django_filters",
    "drf_yasg",
    "guardian",
    "django_celery_beat",
    "django_celery_results",
    "django_rq",  # Django RQ for background tasks
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "crum.CurrentRequestUserMiddleware",
    # Add ChurchContextMiddleware
    "accounts.middleware.ChurchContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "church_saas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "church_saas.wsgi.application"

# Database - PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="church_saas_db"),
            "USER": config("DB_USER", default="church_admin"),
            "PASSWORD": config("DB_PASSWORD", default="password"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5433"),
        }
    }
# DATABASES["default"]= dj_database_url.parse(DATABASE_URL)
# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Accra"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# WhiteNoise configuration
WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_ALLOW_ALL_ORIGINS = True

# Enable WhiteNoise storage backend for static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Ensure the directory exists
os.makedirs(STATIC_ROOT, exist_ok=True)

# Ensure STATIC_ROOT exists
os.makedirs(STATIC_ROOT, exist_ok=True)

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Log files (must exist before logging.config runs — e.g. Render has no logs/ in repo)
LOGS_DIR = BASE_DIR / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

# JWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS Settings
# Primary hosted frontend URL (emails, SMS links, defaults). No trailing slash.
FRONTEND_BASE_URL = os.getenv(
    "FRONTEND_BASE_URL",
    "https://opendoor-xi.vercel.app",
).rstrip("/")

# Allowed browser origins for API calls. Always includes local dev; add production via
# FRONTEND_BASE_URL and/or CORS_ALLOWED_ORIGINS (comma-separated) on Render/Vercel.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]
if FRONTEND_BASE_URL and FRONTEND_BASE_URL not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_BASE_URL)

_cors_extra = os.getenv("CORS_ALLOWED_ORIGINS", "")
for _raw in _cors_extra.split(","):
    _origin = _raw.strip().rstrip("/")
    if _origin and _origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_origin)

# Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",  # Using DB 1 for cache
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 5,  # seconds
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "church_saas",
        "TIMEOUT": 3600,  # 1 hour
    }
}

# Session cache
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# RQ (Redis Queue) Configuration
RQ_QUEUES = {
    "default": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        "DEFAULT_TIMEOUT": 360,
    },
    "high": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        "DEFAULT_TIMEOUT": 360,
    },
    "low": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        "DEFAULT_TIMEOUT": 360,
    },
}

# RQ Settings
RQ_SHOW_ADMIN_LINK = True

# Swagger settings
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"}
    },
    "USE_SESSION_AUTH": False,
}

AUTHENTICATION_BACKENDS = [
    "accounts.backends.ChurchAuthBackend",  # Our custom authentication backend
    "accounts.backends.SafeModelBackend",  # Fallback, handles duplicate emails across churches
    "guardian.backends.ObjectPermissionBackend",  # For object-level permissions
]


# Django Guardian settings
ANONYMOUS_USER_NAME = None  # Disable anonymous user creation

# Base URL configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/0"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

# Twilio Test Credentials
TWILIO_TEST_ACCOUNT_SID = os.getenv("TWILIO_TEST_ACCOUNT_SID")

# Logging Configuration (paths under LOGS_DIR; directory created at import time)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{message}",
            "style": "{",
        },
        "simple_level": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple_level",
            "level": "DEBUG",
        },
        "console_notifications": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "DEBUG",
        },
        "django_file": {
            "class": "logging.FileHandler",
            "filename": str(LOGS_DIR / "django.log"),
            "formatter": "verbose",
            "level": "DEBUG",
        },
        "registration_file": {
            "class": "logging.FileHandler",
            "filename": str(LOGS_DIR / "registration_debug.log"),
            "formatter": "verbose",
            "level": "DEBUG",
        },
    },
    "loggers": {
        "notifications": {
            "handlers": ["console_notifications", "django_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django": {
            "handlers": ["registration_file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "accounts": {
            "handlers": ["registration_file", "console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
    "root": {
        "handlers": ["console", "django_file"],
        "level": "INFO",
    },
}

# Frontend URL Configuration (used in notification emails/SMS - do not set to localhost in production)
_DEFAULT_FRONTEND_LOGIN_URL = "https://opendoor-xi.vercel.app/login"
FRONTEND_LOGIN_URL = os.getenv("FRONTEND_LOGIN_URL", _DEFAULT_FRONTEND_LOGIN_URL)
FRONTEND_URL = os.getenv("FRONTEND_URL", FRONTEND_BASE_URL)

# Email Configuration
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "kyerematengcollins93@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"OpenDoor <{EMAIL_HOST_USER}>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL  # For error messages sent to ADMINS and MANAGERS

# mNotify SMS Configuration
MNOTIFY_API_KEY = os.getenv("MNOTIFY_API_KEY", "")  # Set in environment variables
MNOTIFY_SENDER_ID = os.getenv(
    "MNOTIFY_SENDER_ID", "Open door"
)  # Default sender ID for SMS messages
TWILIO_TEST_AUTH_TOKEN = os.getenv("TWILIO_TEST_AUTH_TOKEN")

# Cloudinary (File Management & Media)
# Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET in .env (never commit secret)
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
# File upload limits
FILE_MAX_SIZE_MB = int(os.getenv("FILE_MAX_SIZE_MB", 20))
FILE_ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
FILE_ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
]
FILE_ALLOWED_VIDEO_TYPES = ["video/mp4", "video/webm", "video/quicktime"]
FILE_ALLOWED_TYPES = (
    FILE_ALLOWED_IMAGE_TYPES + FILE_ALLOWED_DOCUMENT_TYPES + FILE_ALLOWED_VIDEO_TYPES
)

# Backup (default: media/backups/)
BACKUP_ROOT = os.getenv("BACKUP_ROOT", "") or os.path.join(BASE_DIR, "media", "backups")
