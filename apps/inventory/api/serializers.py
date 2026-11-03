"""School-scoped serializers for procurement and inventory."""
from decimal import Decimal

from rest_framework import serializers

from apps.accounting.models import Account, CostCenter
from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
    VendorInvoice,
    Warehouse,
    WarehouseStock,
    WarehouseTransfer,
)
from apps.tenants.models import Branch


class ScopedModelSerializer(serializers.ModelSerializer):
    def scoped_queryset(self, model, *, active=True):
        school = self.context.get("school")
        queryset = model.objects.filter(school=school) if school else model.objects.none()
        if active and hasattr(model, "is_archived"):
            queryset = queryset.filter(is_archived=False)
        return queryset


class SupplierSerializer(ScopedModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.none(), required=False, allow_null=True,
    )

    class Meta:
        model = Supplier
        fields = [
            "id", "branch", "code", "name", "contact_person", "phone",
            "email", "tax_number", "address", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()

    def validate(self, attrs):
        if not attrs.get("name", getattr(self.instance, "name", "")).strip():
            raise serializers.ValidationError({"name": "اسم المورد مطلوب."})
        return attrs


class WarehouseSerializer(ScopedModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.none(), required=False, allow_null=True,
    )

    class Meta:
        model = Warehouse
        fields = ["id", "branch", "code", "name", "location", "manager", "created_at"]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.staff.models import Teacher

        school = self.context.get("school")
        self.fields["branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()
        self.fields["manager"].queryset = Teacher.objects.filter(
            school=school, is_archived=False,
        ) if school else Teacher.objects.none()

    def validate(self, attrs):
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        manager = attrs.get("manager", getattr(self.instance, "manager", None))
        school = self.context["school"]
        if branch and branch.school_id != school.pk:
            raise serializers.ValidationError({"branch": "الفرع لا يتبع المدرسة الحالية."})
        if manager and manager.school_id != school.pk:
            raise serializers.ValidationError({"manager": "أمين المستودع لا يتبع المدرسة الحالية."})
        return attrs


class InventoryItemSerializer(ScopedModelSerializer):
    current_stock = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id", "branch", "code", "name", "warehouse", "category", "unit",
            "current_stock", "unit_cost", "reorder_level", "is_low_stock",
            "created_at",
        ]
        read_only_fields = ["id", "branch", "current_stock", "unit_cost", "is_low_stock", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["warehouse"].queryset = Warehouse.objects.filter(
            school=school, is_archived=False,
        ) if school else Warehouse.objects.none()

    def validate(self, attrs):
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        if warehouse and warehouse.school_id != self.context["school"].pk:
            raise serializers.ValidationError({"warehouse": "المستودع لا يتبع المدرسة الحالية."})
        if "reorder_level" in attrs and attrs["reorder_level"] < 0:
            raise serializers.ValidationError({"reorder_level": "حد إعادة الطلب لا يمكن أن يكون سالباً."})
        return attrs


class WarehouseStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.code", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = WarehouseStock
        fields = [
            "id", "item", "item_code", "item_name", "warehouse",
            "warehouse_name", "quantity", "average_unit_cost", "updated_at",
        ]
        read_only_fields = fields


class StockMovementCreateSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.none())
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.none(), required=False, allow_null=True,
    )
    movement_type = serializers.ChoiceField(choices=[
        (StockMovement.MovementType.RECEIPT, "توريد"),
        (StockMovement.MovementType.ISSUE, "صرف"),
        (StockMovement.MovementType.ADJUSTMENT_ADD, "تسوية بالزيادة"),
        (StockMovement.MovementType.ADJUSTMENT_SUB, "تسوية بالنقص"),
    ])
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0.00"), default=Decimal("0.0000"),
    )
    idempotency_key = serializers.CharField(min_length=8, max_length=100)
    date = serializers.DateField(required=False)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    recipient_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["item"].queryset = InventoryItem.objects.filter(
            school=school, is_archived=False,
        ) if school else InventoryItem.objects.none()
        self.fields["warehouse"].queryset = Warehouse.objects.filter(
            school=school, is_archived=False,
        ) if school else Warehouse.objects.none()

    def validate(self, attrs):
        item = attrs["item"]
        warehouse = attrs.get("warehouse") or item.warehouse
        if warehouse.school_id != self.context["school"].pk:
            raise serializers.ValidationError({"warehouse": "المستودع لا يتبع المدرسة الحالية."})
        attrs["warehouse"] = warehouse
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id", "item", "item_name", "warehouse", "warehouse_name",
            "movement_type", "quantity", "unit_cost", "date", "reference",
            "recipient_name", "notes", "idempotency_key", "created_by",
            "created_at", "reversal_of",
        ]
        read_only_fields = fields


class PurchaseOrderItemInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.none())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ["id", "item", "item_name", "quantity", "received_quantity", "unit_price", "total_price"]
        read_only_fields = fields


class PurchaseOrderSerializer(ScopedModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.none(), required=False, allow_null=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "branch", "order_number", "supplier", "warehouse", "order_date",
            "total_amount", "status", "approved_by", "approved_at", "received_at",
            "notes", "items", "created_at",
        ]
        read_only_fields = [
            "id", "total_amount", "status", "approved_by", "approved_at",
            "received_at", "items", "created_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["supplier"].queryset = Supplier.objects.filter(
            school=school, is_archived=False, is_active=True,
        ) if school else Supplier.objects.none()
        self.fields["warehouse"].queryset = Warehouse.objects.filter(
            school=school, is_archived=False,
        ) if school else Warehouse.objects.none()
        self.fields["branch"].queryset = Branch.objects.filter(
            school=school, is_archived=False,
        ) if school else Branch.objects.none()

    def validate(self, attrs):
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        if supplier and warehouse and supplier.school_id != warehouse.school_id:
            raise serializers.ValidationError("المورد والمستودع يجب أن يتبعا المدرسة نفسها.")
        if self.instance and self.instance.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError("لا يمكن تعديل أمر شراء بعد اعتماده.")
        return attrs


class PurchaseOrderCreateSerializer(PurchaseOrderSerializer):
    items = PurchaseOrderItemInputSerializer(many=True, write_only=True, min_length=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["items"].child.fields["item"].queryset = InventoryItem.objects.filter(
            school=school, is_archived=False,
        ) if school else InventoryItem.objects.none()

    def create(self, validated_data):
        from django.db import transaction

        items = validated_data.pop("items")
        school = self.context["school"]
        with transaction.atomic():
            order = PurchaseOrder.objects.create(school=school, **validated_data)
            for row in items:
                item = row["item"]
                if item.school_id != school.pk:
                    raise serializers.ValidationError("صنف أمر الشراء لا يتبع المدرسة الحالية.")
                PurchaseOrderItem.objects.create(
                    school=school,
                    branch=order.branch,
                    purchase_order=order,
                    item=item,
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                    total_price=row["quantity"] * row["unit_price"],
                )
            return order


class PurchaseReceiptInputSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(min_length=8, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    received_items = serializers.ListField(
        child=serializers.DictField(), allow_empty=False,
    )


class VendorInvoiceSerializer(ScopedModelSerializer):
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = VendorInvoice
        fields = [
            "id", "branch", "invoice_number", "supplier", "purchase_order",
            "invoice_date", "due_date", "total_amount", "paid_amount",
            "remaining_amount", "accounting_treatment", "expense_account",
            "cost_center", "status", "approved_by", "approved_at",
            "journal_entry", "notes", "created_at",
        ]
        read_only_fields = [
            "id", "paid_amount", "remaining_amount", "status", "approved_by",
            "approved_at", "journal_entry", "created_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["supplier"].queryset = Supplier.objects.filter(
            school=school, is_archived=False, is_active=True,
        ) if school else Supplier.objects.none()
        self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
            school=school, is_archived=False,
        ) if school else PurchaseOrder.objects.none()
        self.fields["expense_account"].queryset = Account.objects.filter(
            school=school, is_archived=False, is_leaf=True,
        ) if school else Account.objects.none()
        self.fields["cost_center"].queryset = CostCenter.objects.filter(
            school=school, is_archived=False,
        ) if school else CostCenter.objects.none()

    def validate(self, attrs):
        school = self.context["school"]
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        po = attrs.get("purchase_order", getattr(self.instance, "purchase_order", None))
        if supplier and supplier.school_id != school.pk:
            raise serializers.ValidationError({"supplier": "المورد لا يتبع المدرسة الحالية."})
        if po and (po.school_id != school.pk or (supplier and po.supplier_id != supplier.pk)):
            raise serializers.ValidationError({"purchase_order": "أمر الشراء غير مطابق للمورد أو المدرسة."})
        amount = attrs.get("total_amount", getattr(self.instance, "total_amount", None))
        paid = attrs.get("paid_amount", getattr(self.instance, "paid_amount", Decimal("0.00")))
        if amount is not None and paid > amount:
            raise serializers.ValidationError({"total_amount": "إجمالي الفاتورة أقل من المبلغ المسدد."})
        if self.instance and (
            self.instance.journal_entry_id
            or self.instance.paid_amount > 0
            or self.instance.status != VendorInvoice.Status.DRAFT
        ):
            raise serializers.ValidationError("فاتورة المورد المعتمدة أو المرتبطة بقيد لا تعدل؛ أنشئ مستند تسوية.")
        return attrs


class VendorPaymentInputSerializer(serializers.Serializer):
    payment_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    idempotency_key = serializers.CharField(min_length=8, max_length=100)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "cheque", "card"],
        default="bank_transfer",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = self.context.get("school")
        self.fields["payment_account"].queryset = Account.objects.filter(
            school=school, is_archived=False, is_leaf=True,
            account_type=Account.AccountType.ASSET,
        ) if school else Account.objects.none()
