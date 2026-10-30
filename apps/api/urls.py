from django.urls import include, path

from apps.api.views import AvailableSchoolsView, CurrentUserView, HealthView, SwitchSchoolContextView

app_name = "api"
urlpatterns = [
    path("<str:version>/health/", HealthView.as_view(), name="health"),
    path("<str:version>/me/", CurrentUserView.as_view(), name="current-user"),
    path("<str:version>/schools/", AvailableSchoolsView.as_view(), name="available-schools"),
    path("<str:version>/school-context/", SwitchSchoolContextView.as_view(), name="switch-school-context"),
    path("<str:version>/copilot/", include("apps.copilot.api.urls")),
    path("<str:version>/reports/", include("apps.reports.urls")),
]
