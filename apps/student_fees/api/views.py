from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    has_school_permission,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.models import SchoolMembership
from apps.academics.models import AcademicYear
from apps.auditlog.services import record_event
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
from apps.students.models import Guardian, Student
from apps.tenants.models import School


def _resolve_school(request):
    school = resolve_active_school(request)
    if school is not None or getattr(request, "school_context_error", None):
        return school
    if not request.user or not request.user.is_authenticated:
        return None

    # Student/guardian accounts may be profile-linked without a staff-style
    # membership. Resolve only a school directly linked to that account.
    school_ids = set(Student.objects.filter(
        user=request.user, is_archived=False,
        school__status=School.Status.ACTIVE, school__is_archived=False,
    ).values_list("school_id", flat=True))
    school_ids.update(Guardian.objects.filter(
        user=request.user, is_archived=False,
        school__status=School.Status.ACTIVE, school__is_archived=False,
    ).values_list("school_id", flat=True))

    # A legacy profile may have no membership row; but an existing suspended,
    # expired or departed membership must never be bypassed by the profile link.
    membership_rows = SchoolMembership.objects.filter(
        user=request.user, school_id__in=school_ids,
    ).values_list("school_id", "status", "expires_at")
    blocked_school_ids = {
        school_id for school_id, member_status, expires_at in membership_rows
        if member_status != SchoolMembership.Status.ACTIVE
        or (expires_at is not None and expires_at <= timezone.now())
    }
    school_ids.difference_update(blocked_school_ids)

    linked_schools = School.objects.filter(
        pk__in=school_ids, status=School.Status.ACTIVE, is_archived=False,
    )

    requested_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    requested_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")
    if requested_id:
        return linked_schools.filter(pk=requested_id).first()
    if requested_code:
        return linked_schools.filter(code=requested_code.strip().upper()).first()
    return linked_schools.first() if linked_schools.count() == 1 else None


def _scope_student_finance_read(queryset, request, school, permission_codename):
    """
    Restrict financial records to the school finance team or the student's own
    authenticated account / linked guardian. Never trust a requested student ID.
    """
    active_branch = getattr(request, "branch", None)
    if active_branch is not None:
        queryset = queryset.filter(branch=active_branch)
    elif request.query_params.get("branch"):
        queryset = queryset.filter(branch_id=request.query_params["branch"])

    finance_read_roles = FINANCIAL_ROLES | {
        "cashier", "admin", "school-admin", "school_admin",
        "school-director", "school_director", "principal",
        "school-principal", "general-manager", "general_manager",
    }
    if has_school_roles(request.user, school, finance_read_roles):
        return queryset
    if has_school_permission(
        user=request.user, school=school, permission=permission_codename,
    ):
        return queryset

    related_students = Student.objects.filter(
        school=school,
        is_archived=False,
    ).filter(
        Q(user=request.user)
        | Q(
            guardians__guardian__user=request.user,
            guardians__school=school,
            guardians__is_archived=False,
            guardians__guardian__is_archived=False,
        )
    )
    if not related_students.exists():
        raise PermissionDenied("لا تملك صلاحية الاطلاع على البيانات المالية لهذا الطالب.")
    return queryset.filter(student__in=related_students).distinct()


class StudentInvoiceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        qs = StudentInvoice.objects.filter(school=school, is_archived=False).select_related(
            "student", "academic_year"
        )
        qs = _scope_student_finance_read(
            qs, request, school, "student_fees.view_studentinvoice",
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

        student_queryset = Student.objects.filter(
            school=school, is_archived=False,
        )
        if getattr(request, "branch", None):
            student_queryset = student_queryset.filter(branch=request.branch)
        student = get_object_or_404(student_queryset, pk=data["student_id"])
        academic_year = get_object_or_404(
            AcademicYear, pk=data["academic_year_id"], school=school,
        )
        if academic_year.branch_id and academic_year.branch_id != student.branch_id:
            raise ValidationError({"academic_year_id": "السنة الدراسية تتبع فرعاً مختلفاً عن الطالب."})

        items_data = data["items"]
        total_items_amount = sum(
            (item["amount"] for item in items_data), Decimal("0.00"),
        )
        item_discounts = sum(
            (item.get("discount_amount", Decimal("0.00")) for item in items_data),
            Decimal("0.00"),
        )
        invoice_discount = data.get("discount_amount", Decimal("0.00"))
        if invoice_discount >= total_items_amount:
            raise ValidationError({
                "discount_amount": "يجب أن يبقى مبلغ مستحق موجب بعد الخصم الأولي؛ للإعفاء الكامل استخدم مسار طلب الإعفاء.",
            })
        if item_discounts > invoice_discount:
            raise ValidationError({
                "items": "مجموع الخصومات التفصيلية لا يجوز أن يتجاوز إجمالي خصم الفاتورة.",
            })

        normalized_items = []
        categories = {}
        for item in items_data:
            category_queryset = FeeCategory.objects.filter(
                school=school, is_archived=False,
            )
            if student.branch_id:
                category_queryset = category_queryset.filter(
                    Q(branch__isnull=True) | Q(branch=student.branch),
                )
            else:
                category_queryset = category_queryset.filter(branch__isnull=True)
            category = get_object_or_404(category_queryset, pk=item["fee_category_id"])
            categories[str(category.pk)] = category
            normalized_items.append((
                str(category.pk),
                item.get("description", "") or category.name,
                item["amount"],
                item.get("discount_amount", Decimal("0.00")),
            ))
        normalized_items.sort()

        issue_date = data.get("issue_date") or timezone.localdate()
        idempotency_key = data["idempotency_key"].strip()

        with transaction.atomic():
            # Serialize invoice creation per school so the same idempotency key
            # cannot race across two different student rows.
            School.objects.select_for_update().get(pk=school.pk)
            student = Student.objects.select_for_update().get(
                pk=student.pk, school=school, is_archived=False,
            )
            existing = StudentInvoice.objects.select_for_update().filter(
                school=school, idempotency_key=idempotency_key,
            ).first()
            if existing:
                existing_items = sorted(
                    (
                        str(item.fee_category_id),
                        item.description,
                        item.amount,
                        item.discount_amount,
                    )
                    for item in existing.items.order_by(
                        "fee_category_id", "description", "pk",
                    )
                )
                if (
                    existing.student_id != student.pk
                    or existing.branch_id != student.branch_id
                    or existing.academic_year_id != academic_year.pk
                    or existing.issue_date != issue_date
                    or existing.due_date != data["due_date"]
                    or existing.discount_amount != invoice_discount
                    or existing.notes != data.get("notes", "")
                    or existing.total_amount != total_items_amount
                    or existing_items != normalized_items
                ):
                    raise ValidationError({
                        "idempotency_key": "مفتاح منع التكرار مستخدم مسبقاً لبيانات فاتورة مختلفة.",
                    })
                return Response(
                    StudentInvoiceDetailSerializer(existing).data,
                    status=status.HTTP_200_OK,
                )

            import uuid
            inv_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            invoice = StudentInvoice.objects.create(
                school=school,
                branch=student.branch,
                student=student,
                academic_year=academic_year,
                invoice_number=inv_number,
                idempotency_key=idempotency_key,
                issue_date=issue_date,
                due_date=data["due_date"],
                discount_amount=invoice_discount,
                notes=data.get("notes", ""),
                total_amount=Decimal("0.00"),
            )

            for category_id, description, amount, discount in normalized_items:
                StudentInvoiceItem.objects.create(
                    school=school,
                    branch=invoice.branch,
                    invoice=invoice,
                    fee_category=categories[category_id],
                    description=description,
                    amount=amount,
                    discount_amount=discount,
                )

            invoice.total_amount = total_items_amount
            invoice.save(update_fields=["total_amount", "updated_at"])

            # Auto-post to accounting journal within the invoice transaction.
            post_student_invoice_to_journal(invoice)

        record_event(
            action="student_fees.invoice_created",
            description="إنشاء فاتورة رسوم طالب وربط قيد الاستحقاق المحاسبي.",
            actor=request.user, school=school, obj=invoice,
            metadata={
                "student_id": str(student.pk),
                "invoice_number": invoice.invoice_number,
                "total_amount": str(invoice.total_amount),
                "discount_amount": str(invoice.discount_amount),
            },
            request=request,
        )
        detail_serializer = StudentInvoiceDetailSerializer(invoice)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class StudentInvoiceDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentInvoiceDetailSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        queryset = StudentInvoice.objects.filter(
            school=school, is_archived=False,
        ).select_related("student", "academic_year").prefetch_related("items__fee_category")
        return _scope_student_finance_read(
            queryset, self.request, school, "student_fees.view_studentinvoice",
        )


class PaymentReceiptListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        qs = PaymentReceipt.objects.filter(school=school, is_archived=False).select_related(
            "student", "invoice"
        )
        qs = _scope_student_finance_read(
            qs, request, school, "student_fees.view_paymentreceipt",
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

        student_queryset = Student.objects.filter(
            school=school, is_archived=False,
        )
        if getattr(request, "branch", None):
            student_queryset = student_queryset.filter(branch=request.branch)
        student = get_object_or_404(student_queryset, pk=data["student_id"])
        invoice = None
        if data.get("invoice_id"):
            invoice = get_object_or_404(
                StudentInvoice, pk=data["invoice_id"],
                school=school, student=student, branch=student.branch,
                is_archived=False,
            )

        idempotency_key = data.get("idempotency_key", "").strip()

        def matches_existing(existing):
            return (
                existing.student_id == student.pk
                and existing.branch_id == student.branch_id
                and existing.invoice_id == (invoice.pk if invoice else None)
                and existing.amount == data["amount"]
                and existing.payment_method == data.get(
                    "payment_method", PaymentReceipt.PaymentMethod.CASH,
                )
                and existing.reference_number == data.get("reference_number", "")
                and existing.notes == data.get("notes", "")
                and (
                    "paid_at" not in data
                    or existing.paid_at == data["paid_at"]
                )
            )

        if idempotency_key:
            existing = PaymentReceipt.objects.filter(
                school=school, idempotency_key=idempotency_key,
            ).first()
            if existing:
                if not matches_existing(existing):
                    raise ValidationError(
                        {"idempotency_key": "مفتاح منع التكرار مستخدم لعملية مالية ببيانات مختلفة."}
                    )
                return Response(
                    PaymentReceiptListSerializer(existing).data,
                    status=status.HTTP_200_OK,
                )

        import uuid
        receipt_num = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        receipt = PaymentReceipt(
            school=school,
            branch=student.branch,
            student=student,
            invoice=invoice,
            receipt_number=receipt_num,
            amount=data["amount"],
            payment_method=data.get("payment_method", PaymentReceipt.PaymentMethod.CASH),
            reference_number=data.get("reference_number", ""),
            idempotency_key=idempotency_key,
            paid_at=data.get("paid_at") or timezone.now(),
            received_by=request.user,
            notes=data.get("notes", ""),
        )
        try:
            with transaction.atomic():
                # The school lock covers idempotency keys even when competing
                # requests target different student rows.
                School.objects.select_for_update().get(pk=school.pk)
                receipt.save()
        except (IntegrityError, DjangoValidationError):
            if not idempotency_key:
                raise
            existing = PaymentReceipt.objects.filter(
                school=school, idempotency_key=idempotency_key,
            ).first()
            if not existing or not matches_existing(existing):
                raise ValidationError(
                    {"idempotency_key": "تعذر إعادة استخدام مفتاح منع التكرار لهذه البيانات."}
                )

            return Response(
                PaymentReceiptListSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

        record_event(
            action="student_fees.receipt_created",
            description="تسجيل سند قبض وتحديث تخصيصات الفاتورة والرصيد الدائن.",
            actor=request.user, school=school, obj=receipt,
            metadata={
                "student_id": str(student.pk),
                "invoice_id": str(invoice.pk) if invoice else None,
                "amount": str(receipt.amount),
                "payment_method": receipt.payment_method,
            },
            request=request,
        )
        out_serializer = PaymentReceiptListSerializer(receipt)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class PaymentReceiptDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentReceiptListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        queryset = PaymentReceipt.objects.filter(
            school=school, is_archived=False,
        ).select_related("student", "invoice")
        return _scope_student_finance_read(
            queryset, self.request, school, "student_fees.view_paymentreceipt",
        )


class PaymentReceiptReverseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")

        receipt_queryset = PaymentReceipt.objects.filter(
            school=school, is_archived=False,
        )
        if getattr(request, "branch", None):
            receipt_queryset = receipt_queryset.filter(branch=request.branch)
        receipt = get_object_or_404(receipt_queryset, pk=pk)
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "student_fees.change_paymentreceipt")
        serializer = ReverseReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        reverse_payment_receipt(receipt=receipt, reason=reason, reversed_by=request.user)
        record_event(
            action="student_fees.receipt_reversed",
            description="عكس سند قبض مع إعادة تخصيصاته وأثره في الرصيد.",
            actor=request.user, school=school, obj=receipt,
            metadata={"reason": reason, "receipt_number": receipt.receipt_number},
            request=request,
        )

        return Response({
            "message": f"تم إلغاء وعكس سند القبض #{receipt.receipt_number} بنجاح وتسوية القيود المحاسبية ورصيد الطالب.",
            "receipt_number": receipt.receipt_number,
            "is_cancelled": True,
        }, status=status.HTTP_200_OK)
