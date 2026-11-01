"""API endpoints for HR contracts, employee advances, and repayments."""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    FINANCIAL_ROLES,
    HR_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
from apps.accounting.models import Account
from apps.payroll.api.hr_serializers import (
    ApproveEmployeeLoanSerializer,
    CreateEmployeeLoanAdvanceSerializer,
    CreateLoanRepaymentSerializer,
    DisburseEmployeeLoanSerializer,
    EmployeeContractSerializer,
    EmployeeLoanAdvanceSerializer,
)
from apps.payroll.hr_services import (
    approve_employee_loan,
    disburse_employee_loan,
    record_employee_loan_repayment,
)
from apps.payroll.models import (
    EmployeeContract,
    EmployeeLoanAdvance,
    EmployeeLoanRepayment,
)
from apps.staff.models import StaffMember, Teacher


def _school(request):
    school = resolve_active_school(request)
    if not school:
        raise PermissionDenied("لم يتم تحديد مدرسة نشطة أو عضوية سارية.")
    return school


class EmployeeContractListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeContractSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = _school(request)
        permission = "payroll.view_employeecontract" if request.method == "GET" else "payroll.add_employeecontract"
        require_school_role_or_permission(request, school, HR_ROLES, permission)

    def get_queryset(self):
        school = _school(self.request)
        return EmployeeContract.objects.filter(
            school=school, is_archived=False,
        ).select_related("teacher__user", "staff_member__user", "branch").order_by(
            "-start_date", "contract_number",
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_create(self, serializer):
        school = _school(self.request)
        serializer.save(school=school)


class EmployeeContractDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeContractSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        school = _school(request)
        permissions = {
            "GET": "payroll.view_employeecontract",
            "PUT": "payroll.change_employeecontract",
            "PATCH": "payroll.change_employeecontract",
            "DELETE": "payroll.delete_employeecontract",
        }
        require_school_role_or_permission(
            request, school, HR_ROLES, permissions.get(request.method, "payroll.view_employeecontract"),
        )

    def get_queryset(self):
        return EmployeeContract.objects.filter(
            school=_school(self.request), is_archived=False,
        ).select_related("teacher__user", "staff_member__user", "branch")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["school"] = _school(self.request)
        return context

    def perform_destroy(self, instance):
        instance.archive(actor=self.request.user, reason="أرشفة عقد الموظف عبر API")


class EmployeeLoanAdvanceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _school(request)
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES | FINANCIAL_ROLES)
            or is_platform_operator(request.user)
        )
        qs = EmployeeLoanAdvance.objects.filter(
            school=school, is_archived=False,
        ).select_related(
            "teacher__user", "staff_member__user", "requested_by", "approved_by",
            "disbursed_by", "disbursement_voucher",
        )
        if not can_manage:
            own_teacher_ids = Teacher.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).values_list("pk", flat=True)
            own_staff_ids = StaffMember.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).values_list("pk", flat=True)
            if not own_teacher_ids and not own_staff_ids:
                raise PermissionDenied("لا تملك ملفاً وظيفياً في المدرسة النشطة.")
            qs = qs.filter(Q(teacher_id__in=own_teacher_ids) | Q(staff_member_id__in=own_staff_ids))
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(EmployeeLoanAdvanceSerializer(qs.order_by("-created_at")[:100], many=True).data)

    def post(self, request, *args, **kwargs):
        school = _school(request)
        serializer = CreateEmployeeLoanAdvanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES)
            or is_platform_operator(request.user)
        )
        teacher = None
        staff_member = None
        if data.get("teacher_id"):
            teacher = get_object_or_404(
                Teacher, pk=data["teacher_id"], school=school, is_archived=False,
            )
        if data.get("staff_member_id"):
            staff_member = get_object_or_404(
                StaffMember, pk=data["staff_member_id"], school=school, is_archived=False,
            )
        if not can_manage:
            owns_teacher = bool(teacher and teacher.user_id == request.user.pk)
            owns_staff = bool(staff_member and staff_member.user_id == request.user.pk)
            if not (owns_teacher or owns_staff):
                raise PermissionDenied("يمكنك تقديم طلب سلفة لملفك الوظيفي فقط.")
        branch = None
        if data.get("branch_id"):
            from apps.tenants.models import Branch
            branch = get_object_or_404(Branch, pk=data["branch_id"], school=school, is_archived=False)
        loan = EmployeeLoanAdvance.objects.create(
            school=school,
            branch=branch,
            teacher=teacher,
            staff_member=staff_member,
            loan_number=data["loan_number"],
            amount=data["amount"],
            monthly_installment=data["monthly_installment"],
            start_date=data["start_date"],
            notes=data.get("notes", ""),
            status=EmployeeLoanAdvance.Status.PENDING,
            requested_by=request.user,
        )
        return Response(
            EmployeeLoanAdvanceSerializer(loan).data,
            status=status.HTTP_201_CREATED,
        )


class EmployeeLoanApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _school(request)
        require_school_role_or_permission(
            request, school, HR_ROLES, "payroll.change_employeeloanadvance",
        )
        loan = get_object_or_404(
            EmployeeLoanAdvance, pk=pk, school=school, is_archived=False,
        )
        serializer = ApproveEmployeeLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approved = approve_employee_loan(loan=loan, approved_by=request.user)
        except DjangoValidationError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(exc.messages) from exc
        return Response(EmployeeLoanAdvanceSerializer(approved).data)


class EmployeeLoanDisburseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _school(request)
        require_school_role_or_permission(
            request, school, FINANCIAL_ROLES, "payroll.change_employeeloanadvance",
        )
        loan = get_object_or_404(
            EmployeeLoanAdvance, pk=pk, school=school, is_archived=False,
        )
        serializer = DisburseEmployeeLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = get_object_or_404(
            Account, pk=data["payment_account_id"], school=school, is_archived=False,
        )
        try:
            voucher = disburse_employee_loan(
                loan=loan,
                payment_account=account,
                payment_method=data["payment_method"],
                reference_number=data["reference_number"],
                disbursed_by=request.user,
            )
        except DjangoValidationError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(exc.messages) from exc
        return Response({
            "loan": EmployeeLoanAdvanceSerializer(
                EmployeeLoanAdvance.objects.select_related(
                    "teacher__user", "staff_member__user", "disbursement_voucher",
                ).get(pk=loan.pk)
            ).data,
            "voucher_number": voucher.voucher_number,
            "journal_entry": voucher.journal_entry.entry_number if voucher.journal_entry_id else None,
        })


class EmployeeLoanRepaymentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        school = _school(request)
        can_manage = (
            has_school_roles(request.user, school, HR_ROLES | FINANCIAL_ROLES)
            or is_platform_operator(request.user)
        )
        qs = EmployeeLoanRepayment.objects.filter(
            school=school, is_archived=False,
        ).select_related(
            "loan__teacher__user", "loan__staff_member__user", "receipt_voucher", "recorded_by",
        )
        if not can_manage:
            own_teacher_ids = Teacher.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).values_list("pk", flat=True)
            own_staff_ids = StaffMember.objects.filter(
                school=school, user=request.user, is_archived=False,
            ).values_list("pk", flat=True)
            if not own_teacher_ids and not own_staff_ids:
                raise PermissionDenied("لا تملك ملفاً وظيفياً في المدرسة النشطة.")
            qs = qs.filter(
                Q(loan__teacher_id__in=own_teacher_ids)
                | Q(loan__staff_member_id__in=own_staff_ids)
            )
        return Response(LoanRepaymentReadSerializer(qs.order_by("-repaid_at")[:100], many=True).data)

    def post(self, request, *args, **kwargs):
        school = _school(request)
        require_school_role_or_permission(
            request, school, FINANCIAL_ROLES, "payroll.add_employeeloanrepayment",
        )
        serializer = CreateLoanRepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        loan = get_object_or_404(
            EmployeeLoanAdvance, pk=data["loan_id"], school=school, is_archived=False,
        )
        account = get_object_or_404(
            Account, pk=data["payment_account_id"], school=school, is_archived=False,
        )
        try:
            repayment = record_employee_loan_repayment(
                loan=loan,
                amount=data["amount"],
                payment_account=account,
                idempotency_key=data["idempotency_key"],
                payment_method=data["payment_method"],
                reference_number=data["reference_number"],
                notes=data["notes"],
                recorded_by=request.user,
            )
        except DjangoValidationError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(exc.messages) from exc
        return Response(
            LoanRepaymentReadSerializer(repayment).data,
            status=status.HTTP_201_CREATED,
        )


class LoanRepaymentReadSerializer:
    """Small read-only adapter kept local to avoid widening the write serializer."""
    def __init__(self, instance, many=False):
        self.data = (
            [self._serialize(obj) for obj in instance]
            if many else self._serialize(instance)
        )

    @staticmethod
    def _serialize(obj):
        user = obj.loan.teacher.user if obj.loan.teacher_id else obj.loan.staff_member.user
        return {
            "id": str(obj.pk),
            "loan_id": str(obj.loan_id),
            "loan_number": obj.loan.loan_number,
            "employee_name": user.get_full_name() or user.phone,
            "amount": str(obj.amount),
            "balance_before": str(obj.balance_before),
            "balance_after": str(obj.balance_after),
            "repaid_at": obj.repaid_at.isoformat(),
            "is_reversed": obj.is_reversed,
            "receipt_voucher_number": obj.receipt_voucher.voucher_number if obj.receipt_voucher_id else None,
            "notes": obj.notes,
        }
