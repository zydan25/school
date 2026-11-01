"""Serializers for HR contracts, employee loans, and repayments."""
from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from apps.accounting.models import Account, PaymentVoucher, ReceiptVoucher
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, EmployeeLoanRepayment
from apps.staff.models import StaffMember, Teacher


class EmployeeContractSerializer(serializers.ModelSerializer):
    gross_salary = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_salary = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeContract
        fields = [
            "id", "branch", "teacher", "staff_member", "employee_name",
            "contract_number", "contract_type", "start_date", "end_date",
            "basic_salary", "housing_allowance", "transport_allowance",
            "other_allowances", "insurance_deduction", "gross_salary",
            "net_salary", "bank_name", "iban", "is_active", "created_at",
        ]
        read_only_fields = ["id", "gross_salary", "net_salary", "employee_name", "created_at"]

    def get_employee_name(self, obj):
        user = obj.teacher.user if obj.teacher_id else obj.staff_member.user
        return user.get_full_name() or user.phone

    def validate(self, attrs):
        instance = self.instance
        protected = {
            "teacher", "staff_member", "contract_number", "contract_type",
            "start_date", "basic_salary", "housing_allowance",
            "transport_allowance", "other_allowances", "insurance_deduction",
            "bank_name", "iban",
        }
        if instance and protected.intersection(attrs):
            raise serializers.ValidationError(
                "بيانات العقد والراتب الأساسية تاريخية ولا تعدل بعد إنشائه؛ أنهِ العقد وأنشئ عقداً جديداً لأي تغيير."
            )

        school = self.context["school"]
        teacher = attrs.get("teacher", instance.teacher if instance else None)
        staff_member = attrs.get("staff_member", instance.staff_member if instance else None)
        if bool(teacher) == bool(staff_member):
            raise serializers.ValidationError("يجب ربط العقد بمعلم أو موظف إداري واحد فقط.")
        employee = teacher or staff_member
        if employee.school_id != school.pk or employee.is_archived:
            raise serializers.ValidationError("ملف الموظف المحدد لا يتبع المدرسة النشطة أو أنه مؤرشف.")
        if teacher and not teacher.is_active_teaching:
            raise serializers.ValidationError({"teacher": "المعلم غير نشط تدريسياً."})
        if staff_member and not staff_member.is_active:
            raise serializers.ValidationError({"staff_member": "الموظف غير نشط."})

        start_date = attrs.get("start_date", instance.start_date if instance else None)
        end_date = attrs.get("end_date", instance.end_date if instance else None)
        is_active = attrs.get("is_active", instance.is_active if instance else True)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "نهاية العقد تسبق بدايته."})
        for field in (
            "basic_salary", "housing_allowance", "transport_allowance",
            "other_allowances", "insurance_deduction",
        ):
            value = attrs.get(field, getattr(instance, field, Decimal("0.00")) if instance else Decimal("0.00"))
            if value < Decimal("0.00"):
                raise serializers.ValidationError({field: "لا يمكن أن تكون القيمة سالبة."})

        branch = attrs.get("branch", instance.branch if instance else None)
        if branch and branch.school_id != school.pk:
            raise serializers.ValidationError({"branch": "الفرع لا يتبع المدرسة النشطة."})
        if is_active and start_date:
            overlaps = EmployeeContract.objects.filter(
                school=school, is_active=True, is_archived=False,
            ).exclude(pk=instance.pk if instance else None)
            if teacher:
                overlaps = overlaps.filter(teacher=teacher, staff_member__isnull=True)
            else:
                overlaps = overlaps.filter(staff_member=staff_member, teacher__isnull=True)
            overlaps = overlaps.filter(Q(end_date__isnull=True) | Q(end_date__gte=start_date))
            if end_date:
                overlaps = overlaps.filter(start_date__lte=end_date)
            if overlaps.exists():
                raise serializers.ValidationError("يوجد عقد نشط متداخل زمنياً لهذا الموظف.")
        return attrs


class EmployeeLoanAdvanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    disbursement_voucher_number = serializers.CharField(
        source="disbursement_voucher.voucher_number", read_only=True, default=None,
    )

    class Meta:
        model = EmployeeLoanAdvance
        fields = [
            "id", "teacher", "staff_member", "employee_name", "loan_number",
            "amount", "monthly_installment", "repaid_amount", "remaining_amount",
            "start_date", "status", "notes", "requested_by", "approved_by",
            "approved_at", "disbursed_by", "disbursed_at",
            "disbursement_voucher_number", "created_at",
        ]
        read_only_fields = [
            "id", "repaid_amount", "status", "requested_by", "approved_by",
            "approved_at", "disbursed_by", "disbursed_at",
            "disbursement_voucher_number", "created_at",
        ]

    def get_employee_name(self, obj):
        user = obj.teacher.user if obj.teacher_id else obj.staff_member.user
        return user.get_full_name() or user.phone


class CreateEmployeeLoanAdvanceSerializer(serializers.Serializer):
    teacher_id = serializers.UUIDField(required=False, allow_null=True)
    staff_member_id = serializers.UUIDField(required=False, allow_null=True)
    loan_number = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    monthly_installment = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    start_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    branch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if bool(attrs.get("teacher_id")) == bool(attrs.get("staff_member_id")):
            raise serializers.ValidationError("يجب تحديد المعلم أو الموظف الإداري فقط.")
        if attrs["monthly_installment"] <= 0 or attrs["amount"] <= 0:
            raise serializers.ValidationError("مبلغ السلفة والقسط الشهري يجب أن يكونا أكبر من الصفر.")
        return attrs


class ApproveEmployeeLoanSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class DisburseEmployeeLoanSerializer(serializers.Serializer):
    payment_account_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(
        choices=PaymentVoucher.PaymentMethod.choices,
        default=PaymentVoucher.PaymentMethod.BANK_TRANSFER,
    )
    reference_number = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")


class CreateLoanRepaymentSerializer(serializers.Serializer):
    loan_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    payment_account_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(
        choices=ReceiptVoucher.PaymentMethod.choices,
        default=ReceiptVoucher.PaymentMethod.BANK_TRANSFER,
    )
    reference_number = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    idempotency_key = serializers.CharField(min_length=8, max_length=70)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
