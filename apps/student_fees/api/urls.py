from django.urls import path

from apps.student_fees.api.views import (
    PaymentReceiptListCreateAPIView,
    PaymentReceiptReverseAPIView,
    StudentInvoiceDetailAPIView,
    StudentInvoiceListCreateAPIView,
)
from apps.student_fees.api.workflow_views import (
    ApplyCreditToInvoiceAPIView,
    FeeCategoryDetailAPIView,
    FeeCategoryListCreateAPIView,
    FeeDiscountPolicyAPIView,
    FeeDiscountRequestDecisionAPIView,
    FeeDiscountRequestListCreateAPIView,
    FeeInstallmentListAPIView,
    FeeInstallmentPlanListCreateAPIView,
    FeeStructureDetailAPIView,
    FeeStructureListCreateAPIView,
    PaymentAllocationListAPIView,
    RefundStudentCreditAPIView,
    StudentCreditTransactionListAPIView,
    StudentCreditTransactionReverseAPIView,
    StudentFeeStatementAPIView,
)

urlpatterns = [
    # Existing invoice and receipt contracts remain the canonical endpoints.
    path("invoices/", StudentInvoiceListCreateAPIView.as_view(), name="invoice-list-create"),
    path("invoices/<uuid:pk>/", StudentInvoiceDetailAPIView.as_view(), name="invoice-detail"),
    path("receipts/", PaymentReceiptListCreateAPIView.as_view(), name="receipt-list-create"),
    path("receipts/<uuid:pk>/reverse/", PaymentReceiptReverseAPIView.as_view(), name="receipt-reverse"),

    # Fee catalogue and annual/grade/branch structures.
    path("categories/", FeeCategoryListCreateAPIView.as_view(), name="fee-category-list-create"),
    path("categories/<uuid:pk>/", FeeCategoryDetailAPIView.as_view(), name="fee-category-detail"),
    path("structures/", FeeStructureListCreateAPIView.as_view(), name="fee-structure-list-create"),
    path("structures/<uuid:pk>/", FeeStructureDetailAPIView.as_view(), name="fee-structure-detail"),

    # Installment schedules and the allocation ledger.
    path("installment-plans/", FeeInstallmentPlanListCreateAPIView.as_view(), name="fee-installment-plan-list-create"),
    path("installments/", FeeInstallmentListAPIView.as_view(), name="fee-installment-list"),
    path("allocations/", PaymentAllocationListAPIView.as_view(), name="fee-payment-allocation-list"),

    # Student credit ledger, settlement, refunds, and statements.
    path("credit-transactions/", StudentCreditTransactionListAPIView.as_view(), name="student-credit-transaction-list"),
    path("credit-transactions/<uuid:pk>/reverse/", StudentCreditTransactionReverseAPIView.as_view(), name="student-credit-transaction-reverse"),
    path("invoices/<uuid:invoice_id>/apply-credit/", ApplyCreditToInvoiceAPIView.as_view(), name="student-invoice-apply-credit"),
    path("students/<uuid:student_id>/refund-credit/", RefundStudentCreditAPIView.as_view(), name="student-credit-refund"),
    path("students/<uuid:student_id>/statement/", StudentFeeStatementAPIView.as_view(), name="student-fee-statement"),

    # Discount/exemption policy and approval workflow.
    path("discount-policy/", FeeDiscountPolicyAPIView.as_view(), name="fee-discount-policy"),
    path("discount-requests/", FeeDiscountRequestListCreateAPIView.as_view(), name="fee-discount-request-list-create"),
    path("discount-requests/<uuid:pk>/<str:decision>/", FeeDiscountRequestDecisionAPIView.as_view(), name="fee-discount-request-decision"),
]
