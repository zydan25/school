from django.urls import path

from apps.payroll.api.views import (
    PayrollRunApproveAPIView,
    PayrollRunDetailAPIView,
    PayrollRunDisburseAPIView,
    PayrollRunGenerateAPIView,
    PayrollRunListAPIView,
    PayrollRunPostAPIView,
    PayrollRunReverseAPIView,
)

urlpatterns = [
    path("runs/", PayrollRunListAPIView.as_view(), name="payroll-run-list"),
    path("runs/<uuid:pk>/", PayrollRunDetailAPIView.as_view(), name="payroll-run-detail"),
    path("runs/generate/", PayrollRunGenerateAPIView.as_view(), name="payroll-run-generate"),
    path("runs/<uuid:pk>/approve/", PayrollRunApproveAPIView.as_view(), name="payroll-run-approve"),
    path("runs/<uuid:pk>/post/", PayrollRunPostAPIView.as_view(), name="payroll-run-post"),
    path("runs/<uuid:pk>/disburse/", PayrollRunDisburseAPIView.as_view(), name="payroll-run-disburse"),
    path("runs/<uuid:pk>/reverse/", PayrollRunReverseAPIView.as_view(), name="payroll-run-reverse"),
]
