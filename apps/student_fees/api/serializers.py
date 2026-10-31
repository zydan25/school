from decimal import Decimal

from rest_framework import serializers

from apps.student_fees.models import (
    FeeInstallment,
    PaymentReceipt,
    StudentInvoice,
    StudentInvoiceItem,
)


class StudentInvoiceItemSerializer(serializers.ModelSerializer):
    fee_category_name = serializers.CharField(source="fee_category.name", read_only=True)

    class Meta:
        model = StudentInvoiceItem
        fields = [
            "id",
            "fee_category",
            "fee_category_name",
            "description",
            "amount",
        ]


class FeeInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInstallment
        fields = [
            "id",
            "installment_number",
            "due_date",
            "amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "paid_date",
        ]


class StudentInvoiceListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = StudentInvoice
        fields = [
            "id",
            "invoice_number",
            "student",
            "student_name",
            "student_id_number",
            "academic_year",
            "academic_year_name",
            "issue_date",
            "due_date",
            "total_amount",
            "discount_amount",
            "paid_amount",
            "remaining_balance",
            "status",
            "created_at",
        ]


class StudentInvoiceDetailSerializer(StudentInvoiceListSerializer):
    items = StudentInvoiceItemSerializer(many=True, read_only=True)

    class Meta(StudentInvoiceListSerializer.Meta):
        fields = StudentInvoiceListSerializer.Meta.fields + [
            "notes",
            "items",
        ]


class CreateInvoiceItemInputSerializer(serializers.Serializer):
    fee_category_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    description = serializers.CharField(required=False, allow_blank=True, default="")


class CreateStudentInvoiceSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)
    due_date = serializers.DateField(required=True)
    issue_date = serializers.DateField(required=False)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=Decimal("0.00"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = CreateInvoiceItemInputSerializer(many=True, required=True)


class PaymentReceiptListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_id_number = serializers.CharField(source="student.student_id_number", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)

    class Meta:
        model = PaymentReceipt
        fields = [
            "id",
            "receipt_number",
            "student",
            "student_name",
            "student_id_number",
            "invoice",
            "invoice_number",
            "amount",
            "payment_method",
            "payment_method_display",
            "reference_number",
            "paid_at",
            "is_cancelled",
            "created_at",
        ]


class CreatePaymentReceiptSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(required=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=PaymentReceipt.PaymentMethod.choices, default=PaymentReceipt.PaymentMethod.CASH)
    reference_number = serializers.CharField(required=False, allow_blank=True, default="")
    paid_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ReverseReceiptSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, min_length=3)
