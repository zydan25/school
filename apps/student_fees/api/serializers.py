from decimal import Decimal

from rest_framework import serializers

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
    StudentInvoiceItem,
)


class FeeCategorySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        school = self.context.get("school")
        branch = (
            (attrs.get("branch") or self.context.get("branch"))
            if self.instance is None
            else getattr(self.instance, "branch", None)
        )
        if school and branch and branch.school_id != school.pk:
            raise serializers.ValidationError({"branch": "الفرع لا يتبع المدرسة المحددة."})
        return attrs

    class Meta:
        model = FeeCategory
        fields = ["id", "branch", "name", "code", "description", "is_mandatory"]
        read_only_fields = ["id"]


class FeeStructureSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        school = self.context.get("school")
        academic_year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        grade_level = attrs.get("grade_level", getattr(self.instance, "grade_level", None))
        fee_category = attrs.get("fee_category", getattr(self.instance, "fee_category", None))
        branch = (
            (attrs.get("branch") or self.context.get("branch"))
            if self.instance is None
            else getattr(self.instance, "branch", None)
        )
        if school:
            for field, obj in (
                ("academic_year", academic_year),
                ("grade_level", grade_level),
                ("fee_category", fee_category),
            ):
                if obj and obj.school_id != school.pk:
                    raise serializers.ValidationError({field: "السجل المرتبط لا يتبع المدرسة المحددة."})
            if branch and branch.school_id != school.pk:
                raise serializers.ValidationError({"branch": "الفرع لا يتبع المدرسة المحددة."})
            for field, obj in (
                ("academic_year", academic_year),
                ("grade_level", grade_level),
                ("fee_category", fee_category),
            ):
                related_branch_id = getattr(obj, "branch_id", None) if obj else None
                if related_branch_id and related_branch_id != getattr(branch, "pk", None):
                    raise serializers.ValidationError({field: "السجل المرتبط يتبع فرعاً مختلفاً عن هيكل الرسوم."})
        return attrs

    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    fee_category_name = serializers.CharField(source="fee_category.name", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id", "branch", "academic_year", "academic_year_name",
            "grade_level", "grade_level_name",
            "fee_category", "fee_category_name", "amount", "due_date",
        ]
        read_only_fields = ["id"]


class StudentInvoiceItemSerializer(serializers.ModelSerializer):
    fee_category_name = serializers.CharField(source="fee_category.name", read_only=True)

    class Meta:
        model = StudentInvoiceItem
        fields = [
            "id", "fee_category", "fee_category_name", "description",
            "amount", "discount_amount",
        ]
        read_only_fields = ["id"]


class FeeInstallmentSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )

    class Meta:
        model = FeeInstallment
        fields = [
            "id", "installment_number", "title", "due_date",
            "amount", "paid_amount", "remaining_amount", "status", "paid_date",
        ]


class FeeInstallmentPlanSerializer(serializers.ModelSerializer):
    installments = FeeInstallmentSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = FeeInstallmentPlan
        fields = [
            "id", "student", "student_name", "invoice", "invoice_number",
            "plan_name", "total_amount", "number_of_installments",
            "notes", "installments", "created_at",
        ]
        read_only_fields = fields


class CreateInstallmentInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    due_date = serializers.DateField()


class CreateInstallmentPlanSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    plan_name = serializers.CharField(max_length=150)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    installments = CreateInstallmentInputSerializer(many=True, allow_empty=False)


class StudentInvoiceListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    remaining_balance = serializers.DecimalField(
        source="remaining_amount", max_digits=12, decimal_places=2, read_only=True,
    )

    class Meta:
        model = StudentInvoice
        fields = [
            "id", "invoice_number", "student", "student_name", "student_id_number",
            "academic_year", "academic_year_name", "issue_date", "due_date",
            "total_amount", "discount_amount", "paid_amount", "remaining_balance",
            "status", "created_at",
        ]


class StudentInvoiceDetailSerializer(StudentInvoiceListSerializer):
    items = StudentInvoiceItemSerializer(many=True, read_only=True)

    class Meta(StudentInvoiceListSerializer.Meta):
        fields = StudentInvoiceListSerializer.Meta.fields + ["notes", "items"]


class CreateInvoiceItemInputSerializer(serializers.Serializer):
    fee_category_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"),
        required=False, default=Decimal("0.00"),
    )
    description = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["discount_amount"] > attrs["amount"]:
            raise serializers.ValidationError({"discount_amount": "خصم البند لا يتجاوز قيمة البند."})
        return attrs


class CreateStudentInvoiceSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(min_length=8, max_length=128, allow_blank=False)
    student_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)
    due_date = serializers.DateField(required=True)
    issue_date = serializers.DateField(required=False)
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = CreateInvoiceItemInputSerializer(many=True, required=True, allow_empty=False)


class PaymentReceiptListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)

    class Meta:
        model = PaymentReceipt
        fields = [
            "id", "receipt_number", "student", "student_name", "student_id_number",
            "invoice", "invoice_number", "amount", "payment_method",
            "payment_method_display", "reference_number", "paid_at",
            "is_cancelled", "notes", "created_at",
        ]
        read_only_fields = fields


class CreatePaymentReceiptSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentReceipt.PaymentMethod.choices,
        default=PaymentReceipt.PaymentMethod.CASH,
    )
    reference_number = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(
        required=True, allow_blank=False, min_length=8, max_length=128,
    )
    paid_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ReverseReceiptSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, min_length=3, max_length=500)


class PaymentAllocationSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source="receipt.receipt_number", read_only=True, default=None)
    credit_transaction_type = serializers.CharField(
        source="credit_transaction.transaction_type", read_only=True, default=None,
    )
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    installment_number = serializers.IntegerField(
        source="installment.installment_number", read_only=True, default=None,
    )

    class Meta:
        model = PaymentAllocation
        fields = [
            "id", "receipt", "receipt_number", "credit_transaction",
            "credit_transaction_type", "invoice", "invoice_number",
            "installment", "installment_number", "allocated_amount",
            "allocated_at", "status", "notes",
        ]
        read_only_fields = fields


class StudentCreditTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)
    receipt_number = serializers.CharField(source="receipt.receipt_number", read_only=True, default=None)
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True,
    )

    class Meta:
        model = StudentCreditTransaction
        fields = [
            "id", "student", "student_name", "transaction_type",
            "transaction_type_display", "amount", "balance_before",
            "balance_after", "invoice", "invoice_number", "receipt",
            "receipt_number", "source_receipt", "refund_payment_method",
            "refund_reference", "is_reversed", "reversed_by_transaction",
            "created_at", "notes",
        ]
        read_only_fields = fields


class ApplyCreditBalanceSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        required=True,
    )
    idempotency_key = serializers.CharField(
        min_length=8, max_length=128, allow_blank=False,
    )


class RefundStudentCreditSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
    )
    payment_method = serializers.ChoiceField(choices=PaymentReceipt.PaymentMethod.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    idempotency_key = serializers.CharField(required=True, allow_blank=False, min_length=8, max_length=128)


class FeeDiscountPolicySerializer(serializers.ModelSerializer):
    max_discount_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
    )
    auto_approval_limit = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"),
    )

    class Meta:
        model = FeeDiscountPolicy
        fields = ["max_discount_percent", "auto_approval_limit", "allow_full_exemption"]


class FeeDiscountRequestSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    student_name = serializers.CharField(source="invoice.student.get_full_name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True, default=None)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = FeeDiscountRequest
        fields = [
            "id", "invoice", "invoice_number", "student_name", "amount",
            "reason", "status", "requested_by", "requested_by_name",
            "approved_by", "approved_by_name", "decided_at", "decision_notes",
            "created_at",
        ]
        read_only_fields = fields


class CreateFeeDiscountRequestSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(min_length=8, max_length=128, allow_blank=False)
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
    )
    reason = serializers.CharField(min_length=3, max_length=2000)
