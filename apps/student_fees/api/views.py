from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.academics.models import AcademicYear
from apps.accounting.services.auto_posting import post_student_invoice_to_journal
from apps.student_fees.api.serializers import (
    CreatePaymentReceiptSerializer,
    CreateStudentInvoiceSerializer,
    PaymentReceiptListSerializer,
    ReverseReceiptSerializer,
    StudentInvoiceDetailSerializer,
    StudentInvoiceListSerializer,
)
from apps.student_fees.models import (
    FeeCategory,
    PaymentReceipt,
    StudentInvoice,
    StudentInvoiceItem,
    reverse_payment_receipt,
)
from apps.students.models import Student


def _resolve_school(request):
    return resolve_active_school(request)


class StudentInvoiceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        qs = StudentInvoice.objects.filter(school=school, is_archived=False).select_related(
            "student", "academic_year"
        )
        student_id = request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        year_id = request.query_params.get("academic_year")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        serializer = StudentInvoiceListSerializer(qs.order_by("-issue_date", "-created_at")[:100], many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "student_fees.add_studentinvoice")

        serializer = CreateStudentInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(Student, pk=data["student_id"], school=school, is_archived=False)
        academic_year = get_object_or_404(AcademicYear, pk=data["academic_year_id"], school=school)

        items_data = data["items"]
        if not items_data:
            raise ValidationError("يجب إضافة بند واحد على الأقل في الفاتورة.")

        with transaction.atomic():
            import uuid
            inv_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            invoice = StudentInvoice.objects.create(
                school=school,
                student=student,
                academic_year=academic_year,
                invoice_number=inv_number,
                issue_date=data.get("issue_date") or timezone.localdate(),
                due_date=data["due_date"],
                discount_amount=data.get("discount_amount", Decimal("0.00")),
                notes=data.get("notes", ""),
                total_amount=Decimal("0.00"),
            )

            total_items_amount = Decimal("0.00")
            for item in items_data:
                category = get_object_or_404(FeeCategory, pk=item["fee_category_id"], school=school)
                amt = item["amount"]
                total_items_amount += amt
                StudentInvoiceItem.objects.create(
                    school=school,
                    invoice=invoice,
                    fee_category=category,
                    description=item.get("description", "") or category.name,
                    amount=amt,
                )

            invoice.total_amount = total_items_amount
            invoice.save(update_fields=["total_amount", "updated_at"])

            # Auto-post to accounting journal
            post_student_invoice_to_journal(invoice)

        detail_serializer = StudentInvoiceDetailSerializer(invoice)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class StudentInvoiceDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentInvoiceDetailSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return StudentInvoice.objects.filter(school=school, is_archived=False).select_related(
            "student", "academic_year"
        ).prefetch_related("items__fee_category")


class PaymentReceiptListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        qs = PaymentReceipt.objects.filter(school=school, is_archived=False).select_related(
            "student", "invoice"
        )
        student_id = request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        invoice_id = request.query_params.get("invoice")
        if invoice_id:
            qs = qs.filter(invoice_id=invoice_id)
        include_cancelled = request.query_params.get("include_cancelled")
        if not include_cancelled or include_cancelled.lower() not in ["true", "1"]:
            qs = qs.filter(is_cancelled=False)
        serializer = PaymentReceiptListSerializer(qs.order_by("-paid_at")[:100], many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        serializer = CreatePaymentReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "student_fees.add_paymentreceipt")
        data = serializer.validated_data

        student = get_object_or_404(Student, pk=data["student_id"], school=school, is_archived=False)
        invoice = None
        if data.get("invoice_id"):
            invoice = get_object_or_404(StudentInvoice, pk=data["invoice_id"], school=school, is_archived=False)

        import uuid
        receipt_num = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        receipt = PaymentReceipt(
            school=school,
            student=student,
            invoice=invoice,
            receipt_number=receipt_num,
            amount=data["amount"],
            payment_method=data.get("payment_method", PaymentReceipt.PaymentMethod.CASH),
            reference_number=data.get("reference_number", ""),
            paid_at=data.get("paid_at") or timezone.now(),
            received_by=request.user,
            notes=data.get("notes", ""),
        )
        receipt.save()

        out_serializer = PaymentReceiptListSerializer(receipt)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class PaymentReceiptDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentReceiptListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return PaymentReceipt.objects.filter(school=school, is_archived=False).select_related("student", "invoice")


class PaymentReceiptReverseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")

        receipt = get_object_or_404(PaymentReceipt, pk=pk, school=school, is_archived=False)
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "student_fees.change_paymentreceipt")
        serializer = ReverseReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        reverse_payment_receipt(receipt=receipt, reason=reason, reversed_by=request.user)

        return Response({
            "message": f"تم إلغاء وعكس سند القبض #{receipt.receipt_number} بنجاح وتسوية القيود المحاسبية ورصيد الطالب.",
            "receipt_number": receipt.receipt_number,
            "is_cancelled": True,
        }, status=status.HTTP_200_OK)
