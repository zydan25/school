from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "الأساس المشترك"


class PlatformAdminConfig(AdminConfig):
    """Install the Unfold-powered site as Django's default admin site."""
    default_site = "apps.core.admin_site.PlatformAdminSite"
