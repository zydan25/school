"""Procurement and inventory management domain models."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class Supplier(TenantOwnedModel):
    """سجل الموردين المعتمدين للمدرسة (مستلزمات، كتب، صيانة، أجهزة)."""
    name = models.CharField("اسم المورد / الشركة", max_length=150)
    code = models.CharField("رمز المورد", max_length=50, db_index=True)
    contact_person = models.CharField("مسؤول التواصل", max_length=120, blank=True)
    phone = models.CharField("رقم الهاتف", max_length=30)
    email = models.EmailField("البريد الإلكتروني", blank=True)
    tax_number = models.CharField("الرقم الضريبي", max_length=50, blank=True)
    address = models.TextField("العنوان والمقر", blank=True)
    is_active = models.BooleanField("مورد نشط معتمد", default=True)

    class Meta:
        verbose_name = "مورد معتمد"
        verbose_name_plural = "الموردون المعتمدون"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="inventory_supplier_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Warehouse(TenantOwnedModel):
    """المستودعات والمخازن التابعة للمدرسة أو فروعها."""
    name = models.CharField("اسم المستودع", max_length=150)
    code = models.CharField("رمز المستودع", max_length=50, db_index=True)
    branch = models.ForeignKey(
        "tenants.Branch",
        verbose_name="الفرع التابع له",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warehouses",
    )
    location = models.CharField("موقع المستودع داخل المدرسة", max_length=200, blank=True)
    manager = models.ForeignKey(
        "staff.Teacher",
        verbose_name="أمين المستودع",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_warehouses",
    )

    class Meta:
        verbose_name = "مستودع مدرسي"
        verbose_name_plural = "المستودعات والمخازن"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="inventory_warehouse_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class InventoryItem(TenantOwnedModel):
    """الأصناف المخزنية، المواد، والكتب المدرسية والزي."""
    class Unit(models.TextChoices):
        PIECE = "piece", "قطعة / حبة"
        BOX = "box", "كرتون / صندوق"
        PACK = "pack", "رزمة / باقة"
        SET = "set", "طقم / مجموعة"
        BOOK = "book", "نسخة كتاب"

    code = models.CharField("رمز الصنف / الباركود", max_length=50, db_index=True)
    name = models.CharField("اسم الصنف والمواصفات", max_length=200)
    warehouse = models.ForeignKey(
        Warehouse,
        verbose_name="المستودع الرئيسي",
        on_delete=models.PROTECT,
        related_name="items",
    )
    category = models.CharField("تصنيف المادة (كتب، زي، قرطاسية، حواسيب)", max_length=100, blank=True)
    unit = models.CharField("وحدة القياس", max_length=20, choices=Unit.choices, default=Unit.PIECE)
    current_stock = models.DecimalField("الرصيد المخزني الحالي", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField("تكلفة الوحدة التقديرية", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reorder_level = models.DecimalField("حد إعادة الطلب (تنبيه النقص)", max_digits=12, decimal_places=2, default=Decimal("5.00"))

    class Meta:
        verbose_name = "صنف مخزني"
        verbose_name_plural = "دليل الأصناف والمواد"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="inventory_item_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"[{self.code}] {self.name} (المتوفر: {self.current_stock})"

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.reorder_level


class StockMovement(TenantOwnedModel):
    """سجل حركات المخزون (وارد، صرف، تسوية، تحويل)."""
    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "توريد وارد (مشتريات)"
        ISSUE = "issue", "صرف ونفقة (لقسم أو طالب)"
        ADJUSTMENT_ADD = "adj_add", "تسوية جردية بالزيادة"
        ADJUSTMENT_SUB = "adj_sub", "تسوية جردية بالعجز أو التلف"

    item = models.ForeignKey(
        InventoryItem,
        verbose_name="الصنف",
        on_delete=models.PROTECT,
        related_name="movements",
    )
    movement_type = models.CharField("نوع الحركة", max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField("الكمية", max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField("سعر / تكلفة الوحدة", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    date = models.DateField("تاريخ الحركة", default=timezone.localdate)
    reference = models.CharField("رقم المستند المرجعي (سند صرف / فاتورة توريد)", max_length=100, blank=True)
    recipient_name = models.CharField("المستلم / القسم المستفيد", max_length=150, blank=True)
    notes = models.TextField("ملاحظات الحركة", blank=True)

    class Meta:
        verbose_name = "حركة مخزنية"
        verbose_name_plural = "سجل حركات المخزون"

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} - {self.item.name}: {self.quantity}"

    def clean(self):
        super().clean()
        if self.quantity <= Decimal("0.00"):
            raise ValidationError({"quantity": "يجب أن تكون كمية الحركة أكبر من الصفر."})
        if self.movement_type in [self.MovementType.ISSUE, self.MovementType.ADJUSTMENT_SUB]:
            if self._state.adding and self.item.current_stock < self.quantity:
                raise ValidationError({
                    "quantity": f"الكمية المطلوبة للصرف ({self.quantity}) تتجاوز الرصيد المتاح بالمستودع ({self.item.current_stock})."
                })

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        from django.db import transaction
        with transaction.atomic():
            locked_item = InventoryItem.objects.select_for_update().get(pk=self.item_id)
            if not is_new and self.pk:
                old = StockMovement.objects.filter(pk=self.pk).first()
                if old:
                    # Unwind previous movement from item stock
                    if old.movement_type in [self.MovementType.RECEIPT, self.MovementType.ADJUSTMENT_ADD]:
                        locked_item.current_stock -= old.quantity
                    else:
                        locked_item.current_stock += old.quantity

            # Apply current movement
            if self.movement_type in [self.MovementType.RECEIPT, self.MovementType.ADJUSTMENT_ADD]:
                locked_item.current_stock += self.quantity
            else:
                if locked_item.current_stock < self.quantity:
                    raise ValidationError(f"الكمية المطلوبة ({self.quantity}) تتجاوز الرصيد المتاح بالمستودع ({locked_item.current_stock}).")
                locked_item.current_stock -= self.quantity

            locked_item.save(update_fields=["current_stock"])
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            locked_item = InventoryItem.objects.select_for_update().get(pk=self.item_id)
            if self.movement_type in [self.MovementType.RECEIPT, self.MovementType.ADJUSTMENT_ADD]:
                locked_item.current_stock = max(Decimal("0.00"), locked_item.current_stock - self.quantity)
            else:
                locked_item.current_stock += self.quantity
            locked_item.save(update_fields=["current_stock"])
            return super().delete(*args, **kwargs)


class PurchaseOrder(TenantOwnedModel):
    """أوامر الشراء والتوريد المعتمدة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة طلب"
        APPROVED = "approved", "أمر شراء معتمد"
        RECEIVED = "received", "مستلم بالكامل في المخزن"
        CANCELLED = "cancelled", "ملغى"

    order_number = models.CharField("رقم أمر الشراء", max_length=50, db_index=True)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="المورد",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        verbose_name="مستودع الاستلام المعتمد",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    order_date = models.DateField("تاريخ الأمر", default=timezone.localdate)
    total_amount = models.DecimalField("إجمالي قيمة الطلب", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الطلب", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_purchase_orders",
    )
    notes = models.TextField("شروط التوريد والملاحظات", blank=True)

    class Meta:
        verbose_name = "أمر شراء"
        verbose_name_plural = "أوامر الشراء والتوريد"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "order_number"],
                condition=models.Q(is_archived=False),
                name="inventory_purchase_order_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"أمر شراء #{self.order_number} - {self.supplier.name} ({self.total_amount})"

    def receive_into_warehouse(self, user=None):
        """تحويل أمر الشراء إلى حركات توريد مخزنية فعلية وتحديث رصيد المستودع."""
        if self.status == self.Status.RECEIVED:
            return []
        if self.status != self.Status.APPROVED:
            raise ValidationError("لا يمكن استلام أمر الشراء في المخزن إلا بعد اعتماده رسمياً (APPROVED).")
        from django.db import transaction
        created_movements = []
        with transaction.atomic():
            for po_item in self.items.all():
                movement = StockMovement.objects.create(
                    school=self.school,
                    item=po_item.item,
                    movement_type=StockMovement.MovementType.RECEIPT,
                    quantity=po_item.quantity,
                    unit_cost=po_item.unit_price,
                    reference=f"استلام أمر شراء #{self.order_number}",
                    recipient_name=self.supplier.name,
                )
                created_movements.append(movement)
            self.status = self.Status.RECEIVED
            if user and not self.approved_by:
                self.approved_by = user
            self.save(update_fields=["status", "approved_by", "updated_at"])
        return created_movements


class PurchaseOrderItem(TenantOwnedModel):
    """بنود وتفاصيل أمر الشراء."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="أمر الشراء",
        on_delete=models.CASCADE,
        related_name="items",
    )
    item = models.ForeignKey(
        InventoryItem,
        verbose_name="الصنف",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    quantity = models.DecimalField("الكمية المطلوبة", max_digits=12, decimal_places=2)
    unit_price = models.DecimalField("سعر الوحدة المتفق عليه", max_digits=12, decimal_places=2)
    total_price = models.DecimalField("إجمالي البند", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "بند أمر شراء"
        verbose_name_plural = "بنود أوامر الشراء"

    def __str__(self) -> str:
        return f"{self.item.name} x {self.quantity} = {self.total_price}"

    def clean(self):
        super().clean()
        self.total_price = self.quantity * self.unit_price


class VendorInvoice(TenantOwnedModel):
    """فاتورة مورد مستلزمات وكتب ومطابقتها مع أمر الشراء لإثبات الذمم الدائنة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        APPROVED = "approved", "معتمدة"
        PAID = "paid", "مسددة بالكامل"
        PARTIAL = "partial", "مسددة جزئياً"
        CANCELLED = "cancelled", "ملغاة"

    invoice_number = models.CharField("رقم فاتورة المورد", max_length=100)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="المورد",
        on_delete=models.PROTECT,
        related_name="vendor_invoices",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="أمر الشراء المرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendor_invoices",
    )
    invoice_date = models.DateField("تاريخ الفاتورة", default=timezone.localdate)
    due_date = models.DateField("تاريخ الاستحقاق", default=timezone.localdate)
    total_amount = models.DecimalField("إجمالي الفاتورة", max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField("المبلغ المسدد", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("حالة الفاتورة", max_length=20, choices=Status.choices, default=Status.DRAFT)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        verbose_name="قيد الاستحقاق اليومي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendor_invoices",
    )
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "فاتورة مورد"
        verbose_name_plural = "فواتير الموردين والذمم الدائنة"

    def __str__(self) -> str:
        return f"فاتورة مورد #{self.invoice_number} - {self.supplier.name} ({self.total_amount})"

    @property
    def remaining_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.total_amount - self.paid_amount)
