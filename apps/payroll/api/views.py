from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    HR_ROLES,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounting.models import Account
from apps.payroll.api.serializers import (
    DisbursePayrollSerializer,
    GeneratePayrollSerializer,
    PayrollRunDetailSerializer,
    PayrollRunListSerializer,
    ReversePayrollSerializer,
)
from apps.payroll.models import PayrollRun
from apps.payroll.services import (
    disburse_payroll_run,
    generate_monthly_payroll,
    post_payroll_to_accounting,
    reverse_payroll_run,
)


def _resolve_school(request):
    return resolve_active_school(request)


class PayrollRunListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PayrollRunListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            self.request, school, FINANCIAL_ROLES | HR_ROLES, "payroll.view_payrollrun",
        )
        qs = PayrollRun.objects.filter(school=school, is_archived=False).select_related("journal_entry")
        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(year=year)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-year", "-month")


class PayrollRunDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PayrollRunDetailSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            self.request, school, FINANCIAL_ROLES | HR_ROLES, "payroll.view_payrollrun",
        )
        return PayrollRun.objects.filter(
            school=school, is_archived=False,
        ).select_related("journal_entry").prefetch_related(
            "payslips__employee_contract__teacher__user",
            "payslips__employee_contract__staff_member__user",
        )


class PayrollRunGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, FINANCIAL_ROLES | HR_ROLES, "payroll.add_payrollrun")
        serializer = GeneratePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data["year"]
        month = serializer.validated_data["month"]

        payroll_run = generate_monthly_payroll(
            school=school,
            month=month,
            year=year,
            created_by=request.user,
        )
        out_serializer = PayrollRunDetailSerializer(payroll_run)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class PayrollRunApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, {"school-director", "school_director"}, "payroll.change_payrollrun")
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)
        if run.status != PayrollRun.Status.DRAFT:
            raise ValidationError(f"لا يمكن اعتماد مسير بحالة {run.get_status_display()}.")

        run.status = PayrollRun.Status.APPROVED
        run.approved_by = request.user
        run.save(update_fields=["status", "approved_by", "updated_at"])

        return Response({
            "message": f"تم اعتماد مسير الرواتب {run.name} بنجاح.",
            "status": run.status,
        }, status=status.HTTP_200_OK)


class PayrollRunPostAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "payroll.change_payrollrun")
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)

        journal_entry = post_payroll_to_accounting(payroll_run=run, user=request.user)
        return Response({
            "message": f"تم ترحيل مسير الرواتب محاسبياً بنجاح برقم قيد {journal_entry.entry_number}.",
            "journal_entry": journal_entry.entry_number,
            "status": run.status,
        }, status=status.HTTP_200_OK)


class PayrollRunDisburseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "payroll.change_payrollrun")
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)
        serializer = DisbursePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account = get_object_or_404(Account, pk=data["payment_account_id"], school=school)
        disb_entry = disburse_payroll_run(
            payroll_run=run,
            payment_account=account,
            payment_method=data.get("payment_method", "bank_transfer"),
            reference_number=data.get("reference_number", ""),
            user=request.user,
        )
        from apps.accounting.models import PaymentVoucher
        voucher = PaymentVoucher.objects.filter(
            school=school, journal_entry=disb_entry
        ).first()
        if voucher is None:
            raise ValidationError("تم إنشاء قيد الصرف ولكن لم يتم العثور على سند الصرف المرتبط؛ راجع سجل المحاسبة.")
        run.refresh_from_db()

        return Response({
            "message": f"تم صرف مسير الرواتب بنجاح برقم سند {voucher.voucher_number} وقيد صرف {disb_entry.entry_number}.",
            "voucher_number": voucher.voucher_number,
            "disbursement_entry": disb_entry.entry_number,
            "status": run.status,
        }, status=status.HTTP_200_OK)


class PayrollRunReverseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, FINANCIAL_ROLES, "payroll.delete_payrollrun")
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)
        serializer = ReversePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        reverse_payroll_run(payroll_run=run, reason=reason, reversed_by=request.user)

        return Response({
            "message": "تم عكس مسير الرواتب وإعادة السلف والقيود السابقة بنجاح.",
            "status": run.status,
        }, status=status.HTTP_200_OK)
