from django.urls import path

from apps.payroll.api.hr_views import (
    EmployeeContractDetailAPIView,
    EmployeeContractListCreateAPIView,
    EmployeeLoanAdvanceListCreateAPIView,
    EmployeeLoanApproveAPIView,
    EmployeeLoanDisburseAPIView,
    EmployeeLoanRepaymentsAPIView,
)
from apps.payroll.api.views import (
    PayrollRunApproveAPIView,
    PayrollRunDetailAPIView,
    PayrollRunDisburseAPIView,
    PayrollRunGenerateAPIView,
    PayrollRunListAPIView,
    PayrollRunPostAPIView,
    PayrollRunReverseAPIView,
    MyPayslipDetailAPIView,
    MyPayslipListAPIView,
)

urlpatterns = [
    path("me/payslips/", MyPayslipListAPIView.as_view(), name="my-payslips"),
    path("me/payslips/<uuid:pk>/", MyPayslipDetailAPIView.as_view(), name="my-payslip-detail"),
    path("contracts/", EmployeeContractListCreateAPIView.as_view(), name="employee-contract-list-create"),
    path("contracts/<uuid:pk>/", EmployeeContractDetailAPIView.as_view(), name="employee-contract-detail"),
    path("loans/", EmployeeLoanAdvanceListCreateAPIView.as_view(), name="employee-loan-list-create"),
    path("loans/repayments/", EmployeeLoanRepaymentsAPIView.as_view(), name="employee-loan-repayments"),
    path("loans/<uuid:pk>/approve/", EmployeeLoanApproveAPIView.as_view(), name="employee-loan-approve"),
    path("loans/<uuid:pk>/disburse/", EmployeeLoanDisburseAPIView.as_view(), name="employee-loan-disburse"),
    path("runs/", PayrollRunListAPIView.as_view(), name="payroll-run-list"),
    path("runs/<uuid:pk>/", PayrollRunDetailAPIView.as_view(), name="payroll-run-detail"),
    path("runs/generate/", PayrollRunGenerateAPIView.as_view(), name="payroll-run-generate"),
    path("runs/<uuid:pk>/approve/", PayrollRunApproveAPIView.as_view(), name="payroll-run-approve"),
    path("runs/<uuid:pk>/post/", PayrollRunPostAPIView.as_view(), name="payroll-run-post"),
    path("runs/<uuid:pk>/disburse/", PayrollRunDisburseAPIView.as_view(), name="payroll-run-disburse"),
    path("runs/<uuid:pk>/reverse/", PayrollRunReverseAPIView.as_view(), name="payroll-run-reverse"),
]
