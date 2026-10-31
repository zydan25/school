from django.urls import path

from apps.student_fees.api.views import (
    PaymentReceiptListCreateAPIView,
    PaymentReceiptReverseAPIView,
    StudentInvoiceDetailAPIView,
    StudentInvoiceListCreateAPIView,
)

urlpatterns = [
    path("invoices/", StudentInvoiceListCreateAPIView.as_view(), name="invoice-list-create"),
    path("invoices/<uuid:pk>/", StudentInvoiceDetailAPIView.as_view(), name="invoice-detail"),
    path("receipts/", PaymentReceiptListCreateAPIView.as_view(), name="receipt-list-create"),
    path("receipts/<uuid:pk>/reverse/", PaymentReceiptReverseAPIView.as_view(), name="receipt-reverse"),
]
