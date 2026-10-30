from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.tenants.school_admin import school_admin_site


def landing(_request):
    return JsonResponse({
        "name": "School", "name_ar": "سكول",
        "message": "منصة إدارة المدارس والمؤسسات التعليمية",
        "status": "foundation-ready",
    })

urlpatterns = [
    path("", landing, name="home"),
    path("admin/", admin.site.urls),
    path("school-admin/", school_admin_site.urls),
    path("api/", include("apps.api.urls")),
]
