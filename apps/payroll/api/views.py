from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    if getattr(request, "school", None):
        return request.school
    from apps.accounts.services import is_platform_operator
    from apps.tenants.models import School
    school_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    school_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")
    if is_platform_operator(request.user):
        if school_id:
            return School.objects.filter(pk=school_id, status=School.Status.ACTIVE).first()
        if school_code:
            return School.objects.filter(code=school_code.upper(), status=School.Status.ACTIVE).first()
        return School.objects.filter(status=School.Status.ACTIVE).first()
    memberships = request.user.school_memberships.filter(status="active", school__status=School.Status.ACTIVE)
    if school_id:
        m = memberships.filter(school_id=school_id).first()
        return m.school if m else None
    if school_code:
        m = memberships.filter(school__code=school_code.upper()).first()
        return m.school if m else None
    first_m = memberships.first()
    return first_m.school if first_m else None


class PayrollRunListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PayrollRunListSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
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
        return PayrollRun.objects.filter(school=school, is_archived=False).select_related("journal_entry").prefetch_related(
            "payslips__employee_contract__teacher__user",
            "payslips__employee_contract__staff_member__user",
        )


class PayrollRunGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
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
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)
        serializer = DisbursePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account = get_object_or_404(Account, pk=data["payment_account_id"], school=school)
        disb_entry, voucher = disburse_payroll_run(
            payroll_run=run,
            payment_account=account,
            payment_method=data.get("payment_method", "bank_transfer"),
            reference_number=data.get("reference_number", ""),
            user=request.user,
        )

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
        run = get_object_or_404(PayrollRun, pk=pk, school=school, is_archived=False)
        serializer = ReversePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        reverse_payroll_run(payroll_run=run, reason=reason, reversed_by=request.user)

        return Response({
            "message": "تم عكس مسير الرواتب وإعادة السلف والقيود السابقة بنجاح.",
            "status": run.status,
        }, status=status.HTTP_200_OK)
