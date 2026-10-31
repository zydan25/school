"""Extra routes for the student support API; existing routes stay intact."""
from django.urls import path

from apps.students.api.support_views import (
    AdministrativeSummonAttendAPIView,
    AdministrativeSummonDetailAPIView,
    AdministrativeSummonListCreateAPIView,
    SchoolComplaintDetailAPIView,
    SchoolComplaintListCreateAPIView,
    SchoolComplaintReviewAPIView,
    StudentIncidentDetailAPIView,
    StudentIncidentListCreateAPIView,
    StudentIncidentNotifyParentsAPIView,
    StudentIncidentResolveAPIView,
    StudentIncidentSeenAPIView,
)

urlpatterns = [
    path("incidents/", StudentIncidentListCreateAPIView.as_view(), name="student-incident-list-create"),
    path("incidents/<uuid:pk>/", StudentIncidentDetailAPIView.as_view(), name="student-incident-detail"),
    path("incidents/<uuid:pk>/notify-parents/", StudentIncidentNotifyParentsAPIView.as_view(), name="student-incident-notify-parents"),
    path("incidents/<uuid:pk>/seen/", StudentIncidentSeenAPIView.as_view(), name="student-incident-seen"),
    path("incidents/<uuid:pk>/resolve/", StudentIncidentResolveAPIView.as_view(), name="student-incident-resolve"),
    path("summons/", AdministrativeSummonListCreateAPIView.as_view(), name="student-summon-list-create"),
    path("summons/<uuid:pk>/", AdministrativeSummonDetailAPIView.as_view(), name="student-summon-detail"),
    path("summons/<uuid:pk>/attend/", AdministrativeSummonAttendAPIView.as_view(), name="student-summon-attend"),
    path("complaints/", SchoolComplaintListCreateAPIView.as_view(), name="student-complaint-list-create"),
    path("complaints/<uuid:pk>/", SchoolComplaintDetailAPIView.as_view(), name="student-complaint-detail"),
    path("complaints/<uuid:pk>/review/", SchoolComplaintReviewAPIView.as_view(), name="student-complaint-review"),
]
