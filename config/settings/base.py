"""Shared and security-conscious Django settings."""
from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
from django.templatetags.static import static
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key-change-before-deploy")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost").split(",") if host.strip()]

INSTALLED_APPS = [
    "unfold.apps.BasicAppConfig",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "apps.core.apps.PlatformAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.tenants.apps.TenantsConfig",
    "apps.academics.apps.AcademicsConfig",
    "apps.platform.apps.PlatformConfig",
    "apps.auditlog.apps.AuditlogConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.api.apps.ApiConfig",
    "apps.staff.apps.StaffConfig",
    "apps.students.apps.StudentsConfig",
    "apps.timetable.apps.TimetableConfig",
    "apps.assignments.apps.AssignmentsConfig",
    "apps.assessments.apps.AssessmentsConfig",
    "apps.copilot.apps.CopilotConfig",
    "apps.attendance.apps.AttendanceConfig",
    "apps.student_fees.apps.StudentFeesConfig",
    "apps.accounting.apps.AccountingConfig",
    "apps.payroll.apps.PayrollConfig",
    "apps.assets.apps.AssetsConfig",
    "apps.inventory.apps.InventoryConfig",
    "apps.school_services.apps.SchoolServicesConfig",
    "apps.reports.apps.ReportsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.tenants.middleware.SchoolContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
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
                "apps.core.context_processors.platform_context",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", "postgresql://school:school@127.0.0.1:5432/school"),
        conn_max_age=60,
        conn_health_checks=True,
    )
}
if "postgresql" in DATABASES["default"].get("ENGINE", "") or "psycopg" in DATABASES["default"].get("ENGINE", ""):
    DATABASES["default"]["OPTIONS"] = {**DATABASES["default"].get("OPTIONS", {}), "connect_timeout": 10}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.accounts.backends.PlatformAccessBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "ar")
LANGUAGES = [("ar", "العربية"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Aden")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

API_SESSION_LIFETIME_DAYS = int(os.getenv("API_SESSION_LIFETIME_DAYS", "30"))
PHONE_OTP_DELIVERY_BACKEND = os.getenv("PHONE_OTP_DELIVERY_BACKEND", "").strip()
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@school.local")
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "school",
        },
    }
else:
    # Safe local fallback; production should set REDIS_URL so throttles are
    # shared between all Gunicorn workers and application instances.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "school-default",
        },
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.BearerOrTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "VERSION_PARAM": "version",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 30,
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/minute",
        "login_phone": "5/minute",
        "login_device": "10/minute",
        "registration": "3/hour",
        "registration_phone": "3/hour",
        "otp_request": "3/hour",
        "otp_request_phone": "3/hour",
        "otp_verify": "8/minute",
        "otp_verify_phone": "5/hour",
        "password_reset": "3/hour",
        "password_reset_phone": "3/hour",
    },
}

UNFOLD = {
    "SITE_TITLE": "سكول | الإدارة المركزية",
    "SITE_HEADER": "سكول",
    "SITE_SUBHEADER": "منصة إدارة المدارس والمؤسسات التعليمية",
    "SITE_URL": "/",
    "SITE_ICON": lambda request: static("images/school-mark.svg"),
    "SITE_LOGO": lambda request: static("images/school-mark.svg"),
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    "DASHBOARD_CALLBACK": "apps.core.dashboard.dashboard_callback",
    "STYLES": [lambda request: static("admin/css/school-admin.css")],
    "SCRIPTS": [lambda request: static("admin/js/school-admin.js")],
    "COLORS": {
        "primary": {
            "50": "239, 246, 255", "100": "219, 234, 254", "200": "191, 219, 254",
            "300": "147, 197, 253", "400": "96, 165, 250", "500": "59, 130, 246",
            "600": "37, 99, 235", "700": "29, 78, 216", "800": "30, 64, 175",
            "900": "30, 58, 138", "950": "23, 37, 84",
        }
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        # Both sites use the same visual shell but expose route-specific navigation.
        "navigation": [
            *__import__("apps.core.navigation", fromlist=["central_navigation"]).central_navigation(),
            *__import__("apps.core.navigation", fromlist=["school_navigation"]).school_navigation(),
        ],
    },
}
