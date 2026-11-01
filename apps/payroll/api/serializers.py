from rest_framework import serializers

from apps.payroll.models import PayrollRun, Payslip


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_number = serializers.SerializerMethodField()
    gross_salary = serializers.DecimalField(
        source="total_earnings", max_digits=14, decimal_places=2, read_only=True,
    )
    total_deductions = serializers.DecimalField(
        source="total_deductions", max_digits=14, decimal_places=2, read_only=True,
    )
    loan_repayments = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            "id", "teacher", "staff_member", "employee_name", "employee_number",
            "basic_salary", "housing_allowance", "transport_allowance",
            "other_allowances", "overtime_amount", "gross_salary",
            "loan_deduction", "absence_deduction", "insurance_deduction",
            "total_deductions", "net_salary", "payment_date", "is_paid",
            "loan_repayments",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        user = obj.teacher.user if obj.teacher_id else (
            obj.staff_member.user if obj.staff_member_id else None
        )
        return (user.get_full_name() or user.phone) if user else ""

    def get_employee_number(self, obj):
        return (
            obj.teacher.employee_number if obj.teacher_id
            else obj.staff_member.employee_number if obj.staff_member_id
            else ""
        )

    def get_loan_repayments(self, obj):
        return [
            {
                "id": str(item.pk),
                "amount": str(item.amount),
                "balance_before": str(item.balance_before),
                "balance_after": str(item.balance_after),
                "repaid_at": item.repaid_at.isoformat(),
                "is_reversed": item.is_reversed,
            }
            for item in obj.loan_repayments.filter(is_archived=False).order_by("repaid_at", "pk")
        ]


class PayrollRunListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    journal_entry_number = serializers.CharField(
        source="journal_entry.entry_number", read_only=True, default=None,
    )

    class Meta:
        model = PayrollRun
        fields = [
            "id", "name", "year", "month", "total_basic", "total_allowances",
            "total_deductions", "total_net", "status", "status_display",
            "journal_entry", "journal_entry_number", "approved_by", "created_at",
        ]
        read_only_fields = fields


class PayrollRunDetailSerializer(PayrollRunListSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta(PayrollRunListSerializer.Meta):
        fields = PayrollRunListSerializer.Meta.fields + ["payslips"]


class GeneratePayrollSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=True, min_value=2020, max_value=2100)
    month = serializers.IntegerField(required=True, min_value=1, max_value=12)


class DisbursePayrollSerializer(serializers.Serializer):
    payment_account_id = serializers.UUIDField(required=True)
    reference_number = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "cheque"],
        default="bank_transfer",
    )


class ReversePayrollSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, min_length=3, max_length=500)
