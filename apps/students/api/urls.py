from django.urls import include, path

from apps.students.api.views import (
    StudentDetailAPIView,
    StudentGraduateAPIView,
    StudentListAPIView,
    StudentPromoteAPIView,
    StudentRetainAPIView,
    StudentWithdrawAPIView,
)

urlpatterns = [
    path("", StudentListAPIView.as_view(), name="student-list"),
    path("<uuid:pk>/", StudentDetailAPIView.as_view(), name="student-detail"),
    path("<uuid:pk>/promote/", StudentPromoteAPIView.as_view(), name="student-promote"),
    path("<uuid:pk>/retain/", StudentRetainAPIView.as_view(), name="student-retain"),
    path("<uuid:pk>/graduate/", StudentGraduateAPIView.as_view(), name="student-graduate"),
    path("<uuid:pk>/withdraw/", StudentWithdrawAPIView.as_view(), name="student-withdraw"),
    path("", include("apps.students.api.support_urls")),
]
