from rest_framework import serializers

from apps.payroll.models import PayrollRun, Payslip


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            "id",
            "employee_contract",
            "employee_name",
            "basic_salary",
            "housing_allowance",
            "transport_allowance",
            "other_allowances",
            "gross_salary",
            "absence_deduction",
            "loan_deduction",
            "insurance_deduction",
            "other_deductions",
            "total_deductions",
            "net_salary",
            "status",
        ]

    def get_employee_name(self, obj):
        c = obj.employee_contract
        if c.teacher:
            return c.teacher.user.get_full_name() or c.teacher.user.phone
        if c.staff_member:
            return c.staff_member.user.get_full_name() or c.staff_member.user.phone
        return ""


class PayrollRunListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    journal_entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True, default=None)

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "name",
            "year",
            "month",
            "total_basic",
            "total_allowances",
            "total_deductions",
            "total_net",
            "status",
            "status_display",
            "journal_entry",
            "journal_entry_number",
            "created_at",
        ]


class PayrollRunDetailSerializer(PayrollRunListSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta(PayrollRunListSerializer.Meta):
        fields = PayrollRunListSerializer.Meta.fields + [
            "payslips",
        ]


class GeneratePayrollSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=True, min_value=2020, max_value=2100)
    month = serializers.IntegerField(required=True, min_value=1, max_value=12)


class DisbursePayrollSerializer(serializers.Serializer):
    payment_account_id = serializers.UUIDField(required=True)
    reference_number = serializers.CharField(required=False, allow_blank=True, default="")
    payment_method = serializers.CharField(required=False, default="bank_transfer")


class ReversePayrollSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, min_length=3)
