from django.urls import include, path
from rest_framework import permissions
from rest_framework.schemas import get_schema_view

from apps.api.views import (
    APILoginView,
    APILogoutView,
    AvailableSchoolsView,
    CurrentUserView,
    HealthView,
    SwitchSchoolContextView,
    PhoneRegistrationAPIView,
    PhoneVerificationAPIView,
    ResendPhoneVerificationAPIView,
    PasswordResetRequestAPIView,
    PasswordResetConfirmAPIView,
    PasswordChangeAPIView,
    DeviceSessionsAPIView,
    DeviceSessionRevokeAPIView,
    DeviceSessionsRevokeAllAPIView,
    DeviceSessionRefreshAPIView,
)

schema_view = get_schema_view(
    title="School ERP Platform API",
    description="توثيق واجهات برمجة التطبيقات لمنصة سكول لإدارة المدارس والمؤسسات التعليمية",
    version="1.0.0",
    permission_classes=[permissions.AllowAny],
)

app_name = "api"
urlpatterns = [
    path("<str:version>/health/", HealthView.as_view(), name="health"),
    path("<str:version>/openapi/", schema_view, name="openapi-schema"),
    path("<str:version>/auth/login/", APILoginView.as_view(), name="auth-login"),
    path("<str:version>/auth/logout/", APILogoutView.as_view(), name="auth-logout"),
    path("<str:version>/auth/register/", PhoneRegistrationAPIView.as_view(), name="auth-register"),
    path("<str:version>/auth/phone/verify/", PhoneVerificationAPIView.as_view(), name="auth-phone-verify"),
    path("<str:version>/auth/phone/resend/", ResendPhoneVerificationAPIView.as_view(), name="auth-phone-resend"),
    path("<str:version>/auth/password/reset/request/", PasswordResetRequestAPIView.as_view(), name="auth-password-reset-request"),
    path("<str:version>/auth/password/reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="auth-password-reset-confirm"),
    path("<str:version>/auth/password/change/", PasswordChangeAPIView.as_view(), name="auth-password-change"),
    path("<str:version>/auth/sessions/", DeviceSessionsAPIView.as_view(), name="auth-device-sessions"),
    path("<str:version>/auth/sessions/refresh/", DeviceSessionRefreshAPIView.as_view(), name="auth-device-session-refresh"),
    path("<str:version>/auth/sessions/revoke-all/", DeviceSessionsRevokeAllAPIView.as_view(), name="auth-device-sessions-revoke-all"),
    path("<str:version>/auth/sessions/<uuid:session_id>/revoke/", DeviceSessionRevokeAPIView.as_view(), name="auth-device-session-revoke"),
    path("<str:version>/me/", CurrentUserView.as_view(), name="current-user"),
    path("<str:version>/schools/", AvailableSchoolsView.as_view(), name="available-schools"),
    path("<str:version>/school-context/", SwitchSchoolContextView.as_view(), name="switch-school-context"),
    path("<str:version>/copilot/", include("apps.copilot.api.urls")),
    path("<str:version>/reports/", include("apps.reports.urls")),
    path("<str:version>/notifications/", include("apps.notifications.api.urls")),
    path("<str:version>/timetable/", include("apps.timetable.urls")),
    path("<str:version>/students/", include("apps.students.api.urls")),
    path("<str:version>/fees/", include("apps.student_fees.api.urls")),
    path("<str:version>/staff/", include("apps.staff.api.urls")),
    path("<str:version>/payroll/", include("apps.payroll.api.urls")),
    path("<str:version>/attendance/", include("apps.attendance.api.urls")),
    path("<str:version>/inventory/", include("apps.inventory.api.urls")),
    path("<str:version>/assets/", include("apps.assets.api.urls")),
    path("<str:version>/school-services/", include("apps.school_services.api.urls")),
    path("<str:version>/app/", include("apps.api.v1.urls")),
]
