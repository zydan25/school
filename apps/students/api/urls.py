from django.urls import include, path

from apps.students.api.views import (
    StudentDetailAPIView,
    StudentGraduateAPIView,
    StudentListAPIView,
    StudentAccountBindingAPIView,
    StudentMovementListAPIView,
    StudentTransferAPIView,
    StudentImportPreviewAPIView,
    StudentImportCommitAPIView,
    StudentExportAPIView,
    StudentPromoteAPIView,
    StudentRetainAPIView,
    StudentWithdrawAPIView,
)

urlpatterns = [
    path("import/preview/", StudentImportPreviewAPIView.as_view(), name="student-import-preview"),
    path("import/commit/", StudentImportCommitAPIView.as_view(), name="student-import-commit"),
    path("export/", StudentExportAPIView.as_view(), name="student-export"),
    path("", StudentListAPIView.as_view(), name="student-list"),
    path("<uuid:pk>/account/", StudentAccountBindingAPIView.as_view(), name="student-account-binding"),
    path("<uuid:pk>/transfer/", StudentTransferAPIView.as_view(), name="student-transfer"),
    path("<uuid:pk>/movements/", StudentMovementListAPIView.as_view(), name="student-movements"),
    path("<uuid:pk>/", StudentDetailAPIView.as_view(), name="student-detail"),
    path("<uuid:pk>/promote/", StudentPromoteAPIView.as_view(), name="student-promote"),
    path("<uuid:pk>/retain/", StudentRetainAPIView.as_view(), name="student-retain"),
    path("<uuid:pk>/graduate/", StudentGraduateAPIView.as_view(), name="student-graduate"),
    path("<uuid:pk>/withdraw/", StudentWithdrawAPIView.as_view(), name="student-withdraw"),
    path("", include("apps.students.api.support_urls")),
]
