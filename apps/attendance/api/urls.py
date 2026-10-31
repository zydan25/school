"""URLs for Attendance REST APIs."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.attendance.api.views import (
    AttendanceExcuseRequestViewSet,
    AttendancePolicyViewSet,
    AttendanceRegisterViewSet,
    AttendanceReportsView,
    MyChildrenAttendanceAPIView,
    AttendanceScoreEntryViewSet,
    AttendanceScoringPolicyViewSet,
    AttendanceScoringViewSet,
    SchoolCalendarDayViewSet,
    AttendanceStatusTypeViewSet,
    CalendarEventViewSet,
    EarlyDepartureRequestViewSet,
    SchoolCalendarViewSet,
)

router = DefaultRouter()
router.register("policies", AttendancePolicyViewSet, basename="attendance-policy")
router.register("status-types", AttendanceStatusTypeViewSet, basename="attendance-status-type")
router.register("registers", AttendanceRegisterViewSet, basename="attendance-register")
router.register("excuses", AttendanceExcuseRequestViewSet, basename="attendance-excuse")
router.register("early-departures", EarlyDepartureRequestViewSet, basename="attendance-early-departure")
router.register("calendars", SchoolCalendarViewSet, basename="attendance-calendar")
router.register("calendar-days", SchoolCalendarDayViewSet, basename="attendance-calendar-day")
router.register("calendar-events", CalendarEventViewSet, basename="attendance-calendar-event")
router.register("scoring", AttendanceScoringViewSet, basename="attendance-scoring")
router.register("scoring-policies", AttendanceScoringPolicyViewSet, basename="attendance-scoring-policy")
router.register("score-entries", AttendanceScoreEntryViewSet, basename="attendance-score-entry")

urlpatterns = [
    path("", include(router.urls)),
    path("me/children/records/", MyChildrenAttendanceAPIView.as_view(), name="my-children-attendance"),
    path("reports/<str:report_type>/", AttendanceReportsView.as_view(), name="attendance-report"),
]
