from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    has_school_permission,
    has_school_roles,
    require_school_role_or_permission,
)
from apps.auditlog.services import record_event
from apps.student_fees.api.serializers import (
    ApplyCreditBalanceSerializer,
    CreateFeeDiscountRequestSerializer,
    CreateInstallmentPlanSerializer,
    FeeCategorySerializer,
    FeeDiscountPolicySerializer,
    FeeDiscountRequestSerializer,
    FeeInstallmentPlanSerializer,
    FeeInstallmentSerializer,
    FeeStructureSerializer,
    PaymentAllocationSerializer,
    RefundStudentCreditSerializer,
    StudentCreditTransactionSerializer,
    StudentInvoiceListSerializer,
    PaymentReceiptListSerializer,
)
from apps.student_fees.api.views import _resolve_school, _scope_student_finance_read
from apps.student_fees.models import (
    FeeCategory,
    FeeDiscountPolicy,
    FeeDiscountRequest,
    FeeInstallment,
    FeeInstallmentPlan,
    FeeStructure,
    PaymentAllocation,
    PaymentReceipt,
    StudentCreditTransaction,
    StudentInvoice,
    apply_credit_balance_to_invoice,
    approve_fee_discount_request,
    refund_student_credit,
    reject_fee_discount_request,
    reverse_credit_refund,
    reverse_credit_usage,
    submit_fee_discount_request,
)
from apps.students.models import Student


def _school_or_deny(request):
    school = _resolve_school(request)
    if school is None:
        raise PermissionDenied("لم يتم تحديد مدرسة نشطة لهذا الحساب.")
    return school


def _require_finance(request, school, permission):
    require_school_role_or_permission(
        request, school, FINANCIAL_ROLES, permission,
    )


def _scope_branch(queryset, request, *, include_global=False):
    """Apply the active branch scope without trusting a caller-supplied branch override."""
    branch = getattr(request, "branch", None)
    if branch is None:
        branch_id = request.query_params.get("branch")
        if not branch_id:
            return queryset
        predicate = Q(branch_id=branch_id)
        if include_global:
            predicate |= Q(branch__isnull=True)
        return queryset.filter(predicate)

    predicate = Q(branch=branch)
    if include_global:
        predicate |= Q(branch__isnull=True)
    return queryset.filter(predicate)


def _validate_branch_payload(request, serializer):
    branch = getattr(request, "branch", None)
    requested_branch = serializer.validated_data.get("branch")
    if branch is not None and requested_branch is not None and requested_branch.pk != branch.pk:
        raise ValidationError("لا يمكن إنشاء أو ربط سجل مالي خارج الفرع النشط.")


def _ensure_student_statement_access(request, school, student):
    read_roles = FINANCIAL_ROLES | {
        "cashier", "admin", "school-admin", "school_admin",
        "school-director", "school_director", "principal",
        "school-principal", "general-manager", "general_manager",
    }
    if has_school_roles(request.user, school, read_roles):
        return
    if all(
        has_school_permission(
            user=request.user, school=school, permission=permission,
        )
        for permission in (
            "student_fees.view_studentinvoice",
            "student_fees.view_paymentreceipt",
            "student_fees.view_studentcredittransaction",
        )
    ):
        return
    related = Student.objects.filter(
        pk=student.pk, school=school, is_archived=False,
    ).filter(
        Q(user=request.user)
        | Q(
            guardians__guardian__user=request.user,
            guardians__school=school,
            guardians__is_archived=False,
            guardians__guardian__is_archived=False,
        )
    ).exists()
    if not related:
        raise PermissionDenied("لا تملك صلاحية الاطلاع على كشف حساب هذا الطالب.")


def _audit(request, school, action, description, obj, metadata=None):
    record_event(
        action=action, description=description, actor=request.user,
        school=school, obj=obj, metadata=metadata or {}, request=request,
    )


class FeeCategoryListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feecategory")
        queryset = _scope_branch(
            FeeCategory.objects.filter(school=school, is_archived=False),
            request, include_global=True,
        ).order_by("name")
        return Response(FeeCategorySerializer(queryset, many=True).data)

    def post(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.add_feecategory")
        serializer = FeeCategorySerializer(data=request.data, context={"school": school, "branch": getattr(request, "branch", None)})
        serializer.is_valid(raise_exception=True)
        _validate_branch_payload(request, serializer)
        category = serializer.save(
            school=school,
            branch=getattr(request, "branch", None) or serializer.validated_data.get("branch"),
        )
        _audit(request, school, "student_fees.category_created", "إنشاء تصنيف رسوم.", category)
        return Response(FeeCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class FeeCategoryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feecategory")
        queryset = _scope_branch(
            FeeCategory.objects.filter(school=school, is_archived=False),
            request, include_global=True,
        )
        return school, get_object_or_404(queryset, pk=pk)

    def get(self, request, pk, **kwargs):
        school, category = self.get_object(request, pk)
        return Response(FeeCategorySerializer(category).data)

    def patch(self, request, pk, **kwargs):
        school, category = self.get_object(request, pk)
        _require_finance(request, school, "student_fees.change_feecategory")
        if "branch" in request.data:
            raise ValidationError({"branch": "لا يمكن نقل تصنيف الرسوم بين الفروع بعد إنشائه."})
        serializer = FeeCategorySerializer(category, data=request.data, partial=True, context={"school": school, "branch": getattr(request, "branch", None)})
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        _audit(request, school, "student_fees.category_updated", "تعديل تصنيف رسوم.", category)
        return Response(FeeCategorySerializer(category).data)

    def delete(self, request, pk, **kwargs):
        school, category = self.get_object(request, pk)
        _require_finance(request, school, "student_fees.delete_feecategory")
        category.archive(actor=request.user, reason="أرشفة تصنيف الرسوم عبر API")
        _audit(request, school, "student_fees.category_archived", "أرشفة تصنيف رسوم.", category)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeeStructureListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feestructure")
        queryset = _scope_branch(
            FeeStructure.objects.filter(school=school, is_archived=False),
            request, include_global=True,
        )
        for param in ("academic_year", "grade_level", "fee_category"):
            value = request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{f"{param}_id": value})
        return Response(FeeStructureSerializer(queryset.select_related(
            "academic_year", "grade_level", "fee_category", "branch",
        ).order_by("academic_year__starts_on", "grade_level__sequence"), many=True).data)

    def post(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.add_feestructure")
        serializer = FeeStructureSerializer(data=request.data, context={"school": school, "branch": getattr(request, "branch", None)})
        serializer.is_valid(raise_exception=True)
        _validate_branch_payload(request, serializer)
        structure = serializer.save(
            school=school,
            branch=getattr(request, "branch", None) or serializer.validated_data.get("branch"),
        )
        _audit(request, school, "student_fees.structure_created", "إنشاء هيكل رسوم.", structure)
        return Response(FeeStructureSerializer(structure).data, status=status.HTTP_201_CREATED)


class FeeStructureDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feestructure")
        queryset = _scope_branch(
            FeeStructure.objects.filter(school=school, is_archived=False),
            request, include_global=True,
        )
        return school, get_object_or_404(queryset, pk=pk)

    def get(self, request, pk, **kwargs):
        school, structure = self.get_object(request, pk)
        return Response(FeeStructureSerializer(structure).data)

    def patch(self, request, pk, **kwargs):
        school, structure = self.get_object(request, pk)
        _require_finance(request, school, "student_fees.change_feestructure")
        if "branch" in request.data:
            raise ValidationError({"branch": "لا يمكن نقل هيكل الرسوم بين الفروع بعد إنشائه."})
        serializer = FeeStructureSerializer(structure, data=request.data, partial=True, context={"school": school, "branch": getattr(request, "branch", None)})
        serializer.is_valid(raise_exception=True)
        structure = serializer.save()
        _audit(request, school, "student_fees.structure_updated", "تعديل هيكل الرسوم.", structure)
        return Response(FeeStructureSerializer(structure).data)

    def delete(self, request, pk, **kwargs):
        school, structure = self.get_object(request, pk)
        _require_finance(request, school, "student_fees.delete_feestructure")
        structure.archive(actor=request.user, reason="أرشفة هيكل الرسوم عبر API")
        _audit(request, school, "student_fees.structure_archived", "أرشفة هيكل الرسوم.", structure)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeeInstallmentPlanListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feeinstallmentplan")
        queryset = _scope_branch(
            FeeInstallmentPlan.objects.filter(school=school, is_archived=False),
            request,
        ).select_related("student", "invoice").prefetch_related("installments")
        for param, field in (
            ("student", "student_id"), ("invoice", "invoice_id"),
        ):
            if request.query_params.get(param):
                queryset = queryset.filter(**{field: request.query_params[param]})
        return Response(FeeInstallmentPlanSerializer(queryset, many=True).data)

    def post(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.add_feeinstallmentplan")
        serializer = CreateInstallmentPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student_queryset = _scope_branch(
            Student.objects.filter(school=school, is_archived=False), request,
        )
        student = get_object_or_404(student_queryset, pk=data["student_id"])
        invoice = get_object_or_404(
            StudentInvoice, pk=data["invoice_id"], school=school,
            student=student, branch=student.branch, is_archived=False,
        )
        if invoice.status == StudentInvoice.Status.CANCELLED:
            raise ValidationError("لا يمكن جدولة فاتورة ملغاة.")
        plan_amount = sum(
            (item["amount"] for item in data["installments"]), Decimal("0.00"),
        )

        with transaction.atomic():
            # Lock the invoice so two concurrent requests cannot create parallel plans.
            invoice = StudentInvoice.objects.select_for_update().get(
                pk=invoice.pk, school=school, student=student,
                is_archived=False,
            )
            if invoice.installment_plans.filter(is_archived=False).exists():
                raise ValidationError("للفاتورة خطة تقسيط نشطة مسبقاً.")
            if plan_amount != invoice.remaining_amount:
                raise ValidationError({
                    "installments": (
                        f"مجموع الأقساط ({plan_amount}) يجب أن يساوي المتبقي "
                        f"على الفاتورة ({invoice.remaining_amount})."
                    ),
                })
            plan = FeeInstallmentPlan.objects.create(
                school=school, branch=invoice.branch,
                student=student, invoice=invoice,
                plan_name=data["plan_name"], total_amount=plan_amount,
                number_of_installments=len(data["installments"]),
                notes=data.get("notes", ""),
            )
            for index, installment in enumerate(data["installments"], start=1):
                FeeInstallment.objects.create(
                    school=school, branch=invoice.branch, plan=plan,
                    installment_number=index,
                    title=installment["title"],
                    amount=installment["amount"],
                    due_date=installment["due_date"],
                )
        _audit(
            request, school, "student_fees.installment_plan_created",
            "إنشاء خطة تقسيط لفاتورة طالب.", plan,
            {"invoice_id": str(invoice.pk), "amount": str(plan_amount)},
        )
        plan.refresh_from_db()
        return Response(
            FeeInstallmentPlanSerializer(plan).data,
            status=status.HTTP_201_CREATED,
        )


class FeeInstallmentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feeinstallment")
        queryset = _scope_branch(
            FeeInstallment.objects.filter(school=school, is_archived=False),
            request,
        ).select_related("plan", "plan__student", "plan__invoice")
        for param, field in (
            ("student", "plan__student_id"),
            ("invoice", "plan__invoice_id"),
            ("plan", "plan_id"),
            ("status", "status"),
        ):
            if request.query_params.get(param):
                queryset = queryset.filter(**{field: request.query_params[param]})
        return Response(FeeInstallmentSerializer(queryset.order_by(
            "due_date", "installment_number",
        ), many=True).data)


class PaymentAllocationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_paymentallocation")
        queryset = _scope_branch(
            PaymentAllocation.objects.filter(school=school, is_archived=False),
            request,
        ).select_related("receipt", "credit_transaction", "invoice", "installment")
        for param, field in (
            ("student", "invoice__student_id"),
            ("invoice", "invoice_id"),
            ("receipt", "receipt_id"),
            ("status", "status"),
        ):
            if request.query_params.get(param):
                queryset = queryset.filter(**{field: request.query_params[param]})
        return Response(PaymentAllocationSerializer(queryset.order_by(
            "-allocated_at",
        )[:500], many=True).data)


class StudentCreditTransactionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        queryset = _scope_branch(
            StudentCreditTransaction.objects.filter(school=school, is_archived=False),
            request,
        ).select_related("student", "invoice", "receipt", "source_receipt")
        queryset = _scope_student_finance_read(
            queryset, request, school, "student_fees.view_studentcredittransaction",
        )
        if request.query_params.get("student"):
            queryset = queryset.filter(student_id=request.query_params["student"])
        if request.query_params.get("invoice"):
            queryset = queryset.filter(invoice_id=request.query_params["invoice"])
        if request.query_params.get("type"):
            queryset = queryset.filter(transaction_type=request.query_params["type"])
        return Response(StudentCreditTransactionSerializer(queryset.order_by(
            "-created_at",
        )[:300], many=True).data)


class ApplyCreditToInvoiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.change_studentinvoice")
        serializer = ApplyCreditBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice_queryset = _scope_branch(
            StudentInvoice.objects.filter(school=school, is_archived=False),
            request,
        )
        invoice = get_object_or_404(invoice_queryset, pk=invoice_id)
        try:
            tx = apply_credit_balance_to_invoice(
                student=invoice.student, invoice=invoice,
                amount=serializer.validated_data["amount"],
                user=request.user,
                idempotency_key=serializer.validated_data["idempotency_key"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        _audit(
            request, school, "student_fees.credit_applied",
            "استخدام رصيد دائن لسداد فاتورة.", tx,
            {"invoice_id": str(invoice.pk), "amount": str(tx.amount)},
        )
        return Response(
            StudentCreditTransactionSerializer(tx).data,
            status=status.HTTP_201_CREATED,
        )


class RefundStudentCreditAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, student_id, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.add_studentcredittransaction")
        serializer = RefundStudentCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_queryset = _scope_branch(
            Student.objects.filter(school=school, is_archived=False), request,
        )
        student = get_object_or_404(student_queryset, pk=student_id)
        data = serializer.validated_data
        try:
            tx = refund_student_credit(
                student=student, amount=data["amount"],
                payment_method=data["payment_method"],
                reference=data.get("reference", ""), user=request.user,
                idempotency_key=data["idempotency_key"].strip(),
            )
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        _audit(
            request, school, "student_fees.credit_refunded",
            "صرف مبلغ من الرصيد الدائن للطالب.", tx,
            {"amount": str(tx.amount), "payment_method": tx.refund_payment_method},
        )
        return Response(
            StudentCreditTransactionSerializer(tx).data,
            status=status.HTTP_201_CREATED,
        )


class StudentCreditTransactionReverseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.change_studentcredittransaction")
        reason = str(request.data.get("reason", "")).strip()
        if len(reason) < 3 or len(reason) > 500:
            raise ValidationError({"reason": "سبب العكس مطلوب (3 إلى 500 حرف)."})
        tx_queryset = StudentCreditTransaction.objects.filter(
            school=school, is_archived=False,
        )
        tx_queryset = _scope_branch(tx_queryset, request)
        tx = get_object_or_404(tx_queryset, pk=pk)
        try:
            if tx.transaction_type == StudentCreditTransaction.TransactionType.USAGE:
                reversal = reverse_credit_usage(
                    tx, reason=reason, reversed_by=request.user,
                )
            elif tx.transaction_type == StudentCreditTransaction.TransactionType.REFUND:
                reversal = reverse_credit_refund(
                    tx, reason=reason, reversed_by=request.user,
                )
            else:
                raise ValidationError(
                    "لا يعكس الإيداع أو التسوية يدوياً؛ عكس الإيداع يتم من سند القبض المصدر."
                )
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        _audit(
            request, school, "student_fees.credit_transaction_reversed",
            "عكس حركة رصيد دائن بسبب موثق.", reversal,
            {"source_transaction_id": str(tx.pk), "reason": reason},
        )
        return Response(StudentCreditTransactionSerializer(reversal).data)


class StudentFeeStatementAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id, **kwargs):
        school = _school_or_deny(request)
        student_queryset = _scope_branch(
            Student.objects.filter(school=school, is_archived=False), request,
        )
        student = get_object_or_404(student_queryset, pk=student_id)
        invoices = _scope_branch(
            StudentInvoice.objects.filter(
                school=school, student=student, is_archived=False,
            ), request,
        ).select_related("academic_year", "student")
        _ensure_student_statement_access(request, school, student)
        receipts = _scope_branch(
            PaymentReceipt.objects.filter(
                school=school, student=student, is_archived=False,
            ), request,
        ).select_related("invoice", "student").order_by("-paid_at")
        credit_transactions = _scope_branch(
            StudentCreditTransaction.objects.filter(
                school=school, student=student, is_archived=False,
            ), request,
        ).select_related("invoice", "receipt", "source_receipt").order_by("-created_at")
        installment_plans = _scope_branch(
            FeeInstallmentPlan.objects.filter(
                school=school, student=student, is_archived=False,
            ), request,
        ).select_related("student", "invoice").prefetch_related("installments").order_by("-created_at")

        as_of = timezone.localdate()
        aging = {
            "not_due": Decimal("0.00"),
            "1_30": Decimal("0.00"),
            "31_60": Decimal("0.00"),
            "61_90": Decimal("0.00"),
            "over_90": Decimal("0.00"),
        }
        for invoice in invoices:
            if (
                invoice.status == StudentInvoice.Status.CANCELLED
                or invoice.remaining_amount <= Decimal("0.00")
            ):
                continue
            days = (as_of - invoice.due_date).days
            if days <= 0:
                aging["not_due"] += invoice.remaining_amount
            elif days <= 30:
                aging["1_30"] += invoice.remaining_amount
            elif days <= 60:
                aging["31_60"] += invoice.remaining_amount
            elif days <= 90:
                aging["61_90"] += invoice.remaining_amount
            else:
                aging["over_90"] += invoice.remaining_amount

        invoice_rows = list(invoices.order_by("-issue_date", "-created_at"))
        active_invoice_rows = [
            invoice for invoice in invoice_rows
            if invoice.status != StudentInvoice.Status.CANCELLED
        ]
        receipt_rows = list(receipts[:300])
        transaction_rows = list(credit_transactions[:300])
        installment_plan_rows = list(installment_plans[:100])
        latest_credit_transaction = StudentCreditTransaction.objects.filter(
            school=school, student=student, is_archived=False,
        ).order_by("-created_at", "-pk").first()
        credit_ledger_balance = (
            latest_credit_transaction.balance_after
            if latest_credit_transaction else Decimal("0.00")
        )
        credit_balance_matches_ledger = credit_ledger_balance == student.credit_balance
        total_invoiced = sum((item.total_amount for item in active_invoice_rows), Decimal("0.00"))
        total_discounts = sum((item.discount_amount for item in active_invoice_rows), Decimal("0.00"))
        total_paid = sum((item.paid_amount for item in active_invoice_rows), Decimal("0.00"))
        total_due = sum((item.remaining_amount for item in active_invoice_rows), Decimal("0.00"))
        return Response({
            "student": {
                "id": str(student.pk),
                "student_id_number": student.student_id_number,
                "name": student.get_full_name(),
                "credit_balance": student.credit_balance,
            },
            "as_of": as_of,
            "summary": {
                "total_invoiced": total_invoiced,
                "total_discounts": total_discounts,
                "total_paid": total_paid,
                "total_due": total_due,
                "credit_balance": student.credit_balance,
                "credit_ledger_balance": credit_ledger_balance,
                "credit_balance_matches_ledger": credit_balance_matches_ledger,
            },
            "aging": aging,
            "invoices": StudentInvoiceListSerializer(invoice_rows, many=True).data,
            "receipts": PaymentReceiptListSerializer(receipt_rows, many=True).data,
            "installment_plans": FeeInstallmentPlanSerializer(
                installment_plan_rows, many=True,
            ).data,
            "credit_transactions": StudentCreditTransactionSerializer(
                transaction_rows, many=True,
            ).data,
        })


class FeeDiscountPolicyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_policy(self, school):
        return FeeDiscountPolicy.objects.get_or_create(school=school)[0]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feediscountpolicy")
        policy = self.get_policy(school)
        return Response(FeeDiscountPolicySerializer(policy).data)

    def patch(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.change_feediscountpolicy")
        policy = self.get_policy(school)
        serializer = FeeDiscountPolicySerializer(
            policy, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        _audit(request, school, "student_fees.discount_policy_updated", "تعديل سياسة الخصومات.", policy)
        return Response(FeeDiscountPolicySerializer(policy).data)


class FeeDiscountRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.view_feediscountrequest")
        queryset = _scope_branch(
            FeeDiscountRequest.objects.filter(school=school, is_archived=False),
            request,
        ).select_related("invoice", "invoice__student", "requested_by", "approved_by")
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        if request.query_params.get("student"):
            queryset = queryset.filter(invoice__student_id=request.query_params["student"])
        return Response(FeeDiscountRequestSerializer(queryset.order_by(
            "-created_at",
        )[:300], many=True).data)

    def post(self, request, **kwargs):
        school = _school_or_deny(request)
        _require_finance(request, school, "student_fees.add_feediscountrequest")
        serializer = CreateFeeDiscountRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        invoice_queryset = _scope_branch(
            StudentInvoice.objects.filter(school=school, is_archived=False),
            request,
        )
        invoice = get_object_or_404(invoice_queryset, pk=data["invoice_id"])
        try:
            discount = submit_fee_discount_request(
                invoice=invoice, amount=data["amount"],
                reason=data["reason"], requested_by=request.user,
                idempotency_key=data["idempotency_key"].strip(),
            )
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        if discount.status == FeeDiscountRequest.Status.APPROVED:
            _audit(
                request, school, "student_fees.discount_auto_approved",
                "اعتماد طلب الخصم تلقائياً ضمن حدود سياسة المدرسة.",
                discount,
                {"invoice_id": str(invoice.pk), "amount": str(discount.amount)},
            )
        else:
            _audit(
                request, school, "student_fees.discount_requested",
                "تسجيل طلب خصم أو إعفاء بانتظار الاعتماد.", discount,
                {"invoice_id": str(invoice.pk), "amount": str(discount.amount)},
            )
        return Response(
            FeeDiscountRequestSerializer(discount).data,
            status=status.HTTP_201_CREATED,
        )


class FeeDiscountRequestDecisionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, decision, **kwargs):
        school = _school_or_deny(request)
        permission = (
            "student_fees.change_feediscountrequest"
            if decision in {"approve", "reject"}
            else None
        )
        if permission is None:
            raise ValidationError("قرار الخصم غير معروف.")
        _require_finance(request, school, permission)
        discount_queryset = _scope_branch(
            FeeDiscountRequest.objects.filter(school=school, is_archived=False),
            request,
        )
        discount = get_object_or_404(discount_queryset, pk=pk)
        notes = str(request.data.get("reason", "")).strip()
        try:
            if decision == "approve":
                discount = approve_fee_discount_request(
                    discount, approved_by=request.user, decision_notes=notes,
                )
                action = "student_fees.discount_approved"
                description = "اعتماد طلب خصم بعد التحقق من سياسة المدرسة."
            else:
                discount = reject_fee_discount_request(
                    discount, rejected_by=request.user, reason=notes,
                )
                action = "student_fees.discount_rejected"
                description = "رفض طلب خصم وتوثيق سبب القرار."
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        _audit(
            request, school, action, description, discount,
            {"reason": notes, "invoice_id": str(discount.invoice_id)},
        )
        return Response(FeeDiscountRequestSerializer(discount).data)
