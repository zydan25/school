from django.urls import path

from apps.staff.api.views import (
    LeaveRequestApproveRejectAPIView,
    LeaveRequestListCreateAPIView,
    StaffAttendanceListCreateAPIView,
    StaffMemberListAPIView,
)

urlpatterns = [
    path("members/", StaffMemberListAPIView.as_view(), name="staff-list"),
    path("leaves/", LeaveRequestListCreateAPIView.as_view(), name="leave-list-create"),
    path("leaves/<uuid:pk>/action/", LeaveRequestApproveRejectAPIView.as_view(), name="leave-action"),
    path("attendance/", StaffAttendanceListCreateAPIView.as_view(), name="attendance-list-create"),
]
