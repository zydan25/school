"""Procurement and inventory management domain models."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TenantOwnedModel, TenantQuerySet


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


class InventoryItemQuerySet(TenantQuerySet):
    def update(self, **kwargs):
        if {"current_stock", "unit_cost"}.intersection(kwargs):
            raise ValidationError("رصيد الصنف ومتوسط تكلفته يستمدان من دفتر الحركات ولا يعدلان مباشرة.")
        return super().update(**kwargs)


class InventoryItem(TenantOwnedModel):
    """الأصناف المخزنية، المواد، والكتب المدرسية والزي."""
    objects = InventoryItemQuerySet.as_manager()
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
            ),
            models.CheckConstraint(condition=models.Q(current_stock__gte=0), name="inventory_item_stock_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="inventory_item_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(reorder_level__gte=0), name="inventory_item_reorder_nonnegative"),
        ]

    def clean(self):
        super().clean()
        if self.warehouse_id and self.warehouse.school_id != self.school_id:
            raise ValidationError({"warehouse": "المستودع لا يتبع المدرسة نفسها."})
        if self.current_stock < 0 or self.unit_cost < 0 or self.reorder_level < 0:
            raise ValidationError("الرصيد والتكلفة وحد إعادة الطلب لا يمكن أن تكون سالبة.")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        opening_quantity = self.current_stock if is_new else Decimal("0.00")
        opening_cost = self.unit_cost
        if not is_new:
            original = InventoryItem.objects.filter(pk=self.pk).first()
            if original and (
                original.current_stock != self.current_stock
                or original.unit_cost != self.unit_cost
            ):
                raise ValidationError("رصيد الصنف ومتوسط تكلفته لا يعدلان مباشرة؛ استخدم حركات المخزون.")
        if is_new and opening_quantity > 0:
            # Legacy callers may supply an opening count while creating a
            # stock card. Persist it as an immutable opening ledger movement.
            self.current_stock = Decimal("0.00")
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            if is_new and opening_quantity > 0:
                StockMovement.objects.create(
                    school=self.school,
                    branch=self.warehouse.branch or self.branch,
                    item=self,
                    warehouse=self.warehouse,
                    movement_type=StockMovement.MovementType.OPENING,
                    quantity=opening_quantity,
                    unit_cost=opening_cost,
                    date=timezone.localdate(),
                    reference=f"رصيد افتتاحي للصنف {self.code}",
                    notes="رصيد افتتاحي مرحّل من بطاقة الصنف إلى دفتر الحركات.",
                    idempotency_key=f"opening-{self.pk}",
                )
                self.refresh_from_db(fields=["current_stock", "unit_cost"])
            return result

    def __str__(self) -> str:
        return f"[{self.code}] {self.name} (المتوفر: {self.current_stock})"

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.reorder_level


class WarehouseStock(TenantOwnedModel):
    """الرصيد الحالي للصنف داخل مستودع واحد؛ دفتر الحركات هو مصدر الأثر."""
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="warehouse_balances",
        verbose_name="الصنف",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="stock_balances",
        verbose_name="المستودع",
    )
    quantity = models.DecimalField("الرصيد المتاح", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    average_unit_cost = models.DecimalField("متوسط تكلفة الوحدة", max_digits=14, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        verbose_name = "رصيد صنف في مستودع"
        verbose_name_plural = "أرصدة الأصناف بالمستودعات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "item", "warehouse"],
                condition=models.Q(is_archived=False),
                name="inventory_warehouse_stock_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventory_warehouse_stock_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(average_unit_cost__gte=0),
                name="inventory_warehouse_cost_nonnegative",
            ),
        ]
        indexes = [models.Index(fields=["school", "warehouse", "item"], name="inventory_whstock_scope_idx")]

    def clean(self):
        super().clean()
        if self.item_id and self.item.school_id != self.school_id:
            raise ValidationError({"item": "الصنف لا يتبع المدرسة نفسها."})
        if self.warehouse_id and self.warehouse.school_id != self.school_id:
            raise ValidationError({"warehouse": "المستودع لا يتبع المدرسة نفسها."})
        if self.warehouse_id and self.branch_id != self.warehouse.branch_id:
            raise ValidationError({"branch": "فرع الرصيد يجب أن يطابق فرع المستودع."})


class StockMovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("سجل حركة المخزون دفتر تاريخي غير قابل للتعديل؛ استخدم حركة عكسية موثقة.")

    def delete(self):
        raise ValidationError("لا يجوز حذف حركات المخزون؛ التصحيح يتم بحركة عكسية موثقة.")


class StockMovement(TenantOwnedModel):
    """دفتر حركات المخزون غير القابل للتعديل بعد الإنشاء."""
    objects = StockMovementQuerySet.as_manager()

    class MovementType(models.TextChoices):
        OPENING = "opening", "رصيد افتتاحي"
        RECEIPT = "receipt", "توريد وارد (مشتريات)"
        ISSUE = "issue", "صرف"
        ADJUSTMENT_ADD = "adj_add", "تسوية جردية بالزيادة"
        ADJUSTMENT_SUB = "adj_sub", "تسوية جردية بالنقص"
        TRANSFER_IN = "transfer_in", "استلام تحويل من مستودع"
        TRANSFER_OUT = "transfer_out", "إرسال تحويل إلى مستودع"

    item = models.ForeignKey(
        InventoryItem, verbose_name="الصنف", on_delete=models.PROTECT,
        related_name="movements",
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name="المستودع", on_delete=models.PROTECT,
        related_name="movements",
    )
    movement_type = models.CharField("نوع الحركة", max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField("الكمية", max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField("تكلفة الوحدة", max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    date = models.DateField("تاريخ الحركة", default=timezone.localdate)
    reference = models.CharField("رقم المستند المرجعي (سند صرف / فاتورة توريد)", max_length=100, blank=True)
    recipient_name = models.CharField("المستلم / القسم المستفيد", max_length=150, blank=True)
    notes = models.TextField("سبب الحركة وملاحظاتها", blank=True)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=100, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_stock_movements", verbose_name="منشئ الحركة",
    )
    purchase_order_item = models.ForeignKey(
        "inventory.PurchaseOrderItem", null=True, blank=True, on_delete=models.PROTECT,
        related_name="stock_movements", verbose_name="بند أمر الشراء",
    )
    purchase_receipt = models.ForeignKey(
        "inventory.PurchaseReceipt", null=True, blank=True, on_delete=models.PROTECT,
        related_name="movements", verbose_name="محضر الاستلام",
    )
    transfer = models.ForeignKey(
        "inventory.WarehouseTransfer", null=True, blank=True, on_delete=models.PROTECT,
        related_name="movements", verbose_name="مستند التحويل",
    )
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="reversal", verbose_name="الحركة الأصلية المعكوسة",
    )
    stocktake_line = models.OneToOneField(
        "inventory.WarehouseStocktakeLine", null=True, blank=True,
        on_delete=models.PROTECT, related_name="stock_movement",
        verbose_name="بند الجرد المصدر",
    )

    class Meta:
        verbose_name = "حركة مخزنية"
        verbose_name_plural = "دفتر حركات المخزون"
        permissions = [
            ("reverse_stockmovement", "Can reverse stock movements"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False, idempotency_key__gt=""),
                name="inventory_stock_movement_idem_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "warehouse", "date"], name="inventory_stock_wh_date_idx"),
            models.Index(fields=["school", "item", "date"], name="inventory_stock_item_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} - {self.item.name}: {self.quantity}"

    @property
    def is_inbound(self) -> bool:
        return self.movement_type in {
            self.MovementType.OPENING,
            self.MovementType.RECEIPT,
            self.MovementType.ADJUSTMENT_ADD,
            self.MovementType.TRANSFER_IN,
        }

    def clean(self):
        super().clean()
        if self.quantity <= Decimal("0.00"):
            raise ValidationError({"quantity": "يجب أن تكون كمية الحركة أكبر من الصفر."})
        if self.unit_cost < Decimal("0.00"):
            raise ValidationError({"unit_cost": "تكلفة الوحدة لا يمكن أن تكون سالبة."})
        if self.item_id and self.item.school_id != self.school_id:
            raise ValidationError({"item": "الصنف لا يتبع المدرسة نفسها."})
        if self.warehouse_id and self.warehouse.school_id != self.school_id:
            raise ValidationError({"warehouse": "المستودع لا يتبع المدرسة نفسها."})
        if self.warehouse_id and self.item_id and self.warehouse.is_archived:
            raise ValidationError({"warehouse": "لا يمكن استخدام مستودع مؤرشف."})
        if self.purchase_order_item_id:
            if self.purchase_order_item.school_id != self.school_id:
                raise ValidationError({"purchase_order_item": "بند أمر الشراء لا يتبع المدرسة نفسها."})
            if self.purchase_order_item.item_id != self.item_id:
                raise ValidationError({"purchase_order_item": "الصنف لا يطابق بند أمر الشراء."})
        if self.purchase_receipt_id and self.purchase_receipt.school_id != self.school_id:
            raise ValidationError({"purchase_receipt": "محضر الاستلام لا يتبع المدرسة نفسها."})
        if self.transfer_id and self.transfer.school_id != self.school_id:
            raise ValidationError({"transfer": "مستند التحويل لا يتبع المدرسة نفسها."})
        if self.reversal_of_id:
            if self.reversal_of.school_id != self.school_id or self.reversal_of.item_id != self.item_id:
                raise ValidationError({"reversal_of": "الحركة الأصلية لا تتطابق مع المدرسة والصنف."})
        if self.stocktake_line_id:
            line = self.stocktake_line
            if (
                line.school_id != self.school_id
                or line.item_id != self.item_id
                or line.stocktake.warehouse_id != self.warehouse_id
            ):
                raise ValidationError({"stocktake_line": "بند الجرد لا يطابق المدرسة والصنف والمستودع."})

    def save(self, *args, **kwargs):
        from django.db import transaction

        if not self._state.adding:
            raise ValidationError("حركة المخزون غير قابلة للتعديل بعد إنشائها؛ أنشئ حركة عكسية بدلاً من ذلك.")
        with transaction.atomic():
            if not self.notes.strip():
                self.notes = "حركة مخزنية مسجلة عبر مسار التوافق القديم."
            item = InventoryItem.objects.select_for_update().get(pk=self.item_id, school_id=self.school_id)
            if not self.warehouse_id:
                self.warehouse_id = item.warehouse_id
            warehouse = Warehouse.objects.select_for_update().get(
                pk=self.warehouse_id, school_id=self.school_id, is_archived=False,
            )
            if item.branch_id and warehouse.branch_id and item.branch_id != warehouse.branch_id:
                raise ValidationError("لا يمكن استخدام صنف مملوك لفرع في مستودع فرع آخر.")
            if warehouse.branch_id:
                self.branch_id = warehouse.branch_id
            elif self.branch_id and item.branch_id and self.branch_id != item.branch_id:
                raise ValidationError("فرع الحركة لا يطابق فرع الصنف.")

            active_stocktake = WarehouseStocktake.objects.select_for_update().filter(
                school_id=self.school_id,
                warehouse=warehouse,
                status=WarehouseStocktake.Status.COUNTING,
                is_archived=False,
            ).first()
            if active_stocktake and (
                not self.stocktake_line_id
                or self.stocktake_line.stocktake_id != active_stocktake.pk
            ):
                raise ValidationError(
                    "المستودع في حالة جرد فعّال؛ أوقف الحركات حتى اعتماد الجرد أو إلغائه."
                )

            balance, _ = WarehouseStock.objects.get_or_create(
                school_id=self.school_id,
                item=item,
                warehouse=warehouse,
                defaults={
                    "branch_id": warehouse.branch_id,
                    "quantity": Decimal("0.00"),
                    "average_unit_cost": item.unit_cost,
                },
            )
            balance = WarehouseStock.objects.select_for_update().get(pk=balance.pk)
            inbound = self.is_inbound
            if not inbound and balance.quantity < self.quantity:
                raise ValidationError(
                    f"الرصيد غير كافٍ في المستودع {warehouse.name}: المتاح {balance.quantity} والمطلوب {self.quantity}."
                )

            self.full_clean()
            previous_quantity = balance.quantity
            next_quantity = previous_quantity + self.quantity if inbound else previous_quantity - self.quantity
            if inbound and self.movement_type == self.MovementType.RECEIPT:
                old_value = previous_quantity * balance.average_unit_cost
                new_value = self.quantity * self.unit_cost
                average = (
                    (old_value + new_value) / next_quantity
                    if next_quantity > 0 else self.unit_cost
                )
                balance.average_unit_cost = average.quantize(Decimal("0.0001"))
                if self.unit_cost > 0:
                    current_total = item.current_stock
                    aggregate_value = current_total * item.unit_cost + new_value
                    aggregate_qty = current_total + self.quantity
                    if aggregate_qty > 0:
                        item.unit_cost = (aggregate_value / aggregate_qty).quantize(Decimal("0.0001"))
            elif inbound and self.movement_type == self.MovementType.TRANSFER_IN:
                if self.unit_cost > 0:
                    old_value = previous_quantity * balance.average_unit_cost
                    new_value = self.quantity * self.unit_cost
                    balance.average_unit_cost = (
                        (old_value + new_value) / next_quantity
                    ).quantize(Decimal("0.0001"))

            balance.quantity = next_quantity
            balance.save(update_fields=["quantity", "average_unit_cost", "updated_at"])
            aggregate_delta = self.quantity if inbound else -self.quantity
            models.QuerySet.update(
                InventoryItem.objects.filter(pk=item.pk),
                current_stock=item.current_stock + aggregate_delta,
                unit_cost=item.unit_cost,
                updated_at=timezone.now(),
            )
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يجوز حذف حركة مخزنية؛ التصحيح يتم بحركة عكسية مرتبطة بالحركة الأصلية.")


class PurchaseReceipt(TenantOwnedModel):
    """محضر استلام مستقل قابل للتكرار الآمن لأوامر الشراء الجزئية."""
    purchase_order = models.ForeignKey(
        "inventory.PurchaseOrder", on_delete=models.PROTECT,
        related_name="receipts", verbose_name="أمر الشراء",
    )
    receipt_number = models.CharField("رقم محضر الاستلام", max_length=60)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=100)
    received_at = models.DateTimeField("تاريخ الاستلام", default=timezone.now)
    payload_hash = models.CharField("بصمة بيانات طلب الاستلام", max_length=64)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="inventory_receipts", verbose_name="مستلم التوريد",
    )
    notes = models.TextField("ملاحظات الاستلام", blank=True)

    class Meta:
        verbose_name = "محضر استلام مشتريات"
        verbose_name_plural = "محاضر استلام المشتريات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="inventory_receipt_idem_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "receipt_number"],
                condition=models.Q(is_archived=False),
                name="inventory_receipt_number_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.purchase_order_id and self.purchase_order.school_id != self.school_id:
            raise ValidationError({"purchase_order": "أمر الشراء لا يتبع المدرسة نفسها."})
        if len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})


class PurchaseOrder(TenantOwnedModel):
    """أوامر الشراء والتوريد المعتمدة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة طلب"
        APPROVED = "approved", "أمر شراء معتمد"
        PARTIALLY_RECEIVED = "partially_received", "مستلم جزئياً"
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
    status = models.CharField("حالة الطلب", max_length=24, choices=Status.choices, default=Status.DRAFT)
    approved_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)
    received_at = models.DateTimeField("تاريخ اكتمال الاستلام", null=True, blank=True)
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
        permissions = [
            ("approve_purchaseorder", "Can approve purchase orders"),
            ("receive_purchaseorder", "Can receive purchase orders"),
            ("cancel_purchaseorder", "Can cancel purchase orders"),
        ]
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
        """التوافق مع المسار القديم؛ ينفذ استلاماً كاملاً بمفتاح ثابت وآمن."""
        from apps.inventory.services import receive_purchase_order

        items = list(
            self.items.filter(is_archived=False).values("id", "quantity", "quantity"),
        )
        payload = [
            {"purchase_order_item_id": str(row["id"]), "quantity": str(row["quantity"])}
            for row in items
        ]
        receipt, _created = receive_purchase_order(
            purchase_order=self,
            received_items=payload,
            idempotency_key=f"legacy-full-receipt-{self.pk}",
            received_by=user,
            notes="استلام كامل عبر مسار التوافق القديم",
        )
        return list(receipt.movements.all())



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
    received_quantity = models.DecimalField("الكمية المستلمة", max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "بند أمر شراء"
        verbose_name_plural = "بنود أوامر الشراء"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_po_item_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="inventory_po_item_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(received_quantity__gte=0) & models.Q(received_quantity__lte=models.F("quantity")),
                name="inventory_po_item_received_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item.name} x {self.quantity} = {self.total_price}"

    def clean(self):
        super().clean()
        if self.quantity <= 0:
            raise ValidationError({"quantity": "كمية أمر الشراء يجب أن تكون أكبر من صفر."})
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "سعر الوحدة لا يمكن أن يكون سالباً."})
        if self.received_quantity < 0 or self.received_quantity > self.quantity:
            raise ValidationError({"received_quantity": "الكمية المستلمة يجب أن تكون بين صفر والكمية المطلوبة."})
        if self.purchase_order_id and self.purchase_order.school_id != self.school_id:
            raise ValidationError({"purchase_order": "أمر الشراء لا يتبع المدرسة نفسها."})
        if self.item_id and self.item.school_id != self.school_id:
            raise ValidationError({"item": "الصنف لا يتبع المدرسة نفسها."})
        if self.purchase_order_id and self.purchase_order.status != PurchaseOrder.Status.DRAFT and self._state.adding:
            raise ValidationError("لا يمكن إضافة بنود إلى أمر شراء معتمد أو مستلم.")

    def save(self, *args, **kwargs):
        if self.purchase_order_id:
            order = PurchaseOrder.objects.get(pk=self.purchase_order_id)
            if order.status != PurchaseOrder.Status.DRAFT:
                raise ValidationError("لا يمكن تعديل بنود أمر شراء بعد اعتماده.")
        self.total_price = (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        super().save(*args, **kwargs)
        total = PurchaseOrderItem.objects.filter(
            purchase_order_id=self.purchase_order_id, is_archived=False,
        ).aggregate(total=models.Sum("total_price"))["total"] or Decimal("0.00")
        models.QuerySet.update(
            PurchaseOrder.objects.filter(pk=self.purchase_order_id),
            total_amount=total,
            updated_at=timezone.now(),
        )

    def delete(self, *args, **kwargs):
        order = PurchaseOrder.objects.get(pk=self.purchase_order_id)
        if order.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError("لا يمكن حذف بند من أمر شراء بعد اعتماده.")
        result = super().delete(*args, **kwargs)
        total = PurchaseOrderItem.objects.filter(
            purchase_order_id=self.purchase_order_id, is_archived=False,
        ).aggregate(total=models.Sum("total_price"))["total"] or Decimal("0.00")
        models.QuerySet.update(
            PurchaseOrder.objects.filter(pk=self.purchase_order_id),
            total_amount=total,
            updated_at=timezone.now(),
        )
        return result





class WarehouseTransfer(TenantOwnedModel):
    """مستند تحويل بين مستودعين ضمن المدرسة نفسها."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        POSTED = "posted", "مرحّل"
        REVERSED = "reversed", "معكوس"

    transfer_number = models.CharField("رقم التحويل", max_length=60)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="warehouse_transfers", verbose_name="الصنف")
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="outgoing_transfers", verbose_name="من مستودع")
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="incoming_transfers", verbose_name="إلى مستودع")
    quantity = models.DecimalField("الكمية المحولة", max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField("تكلفة الوحدة عند التحويل", max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    transfer_date = models.DateField("تاريخ التحويل", default=timezone.localdate)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=100)
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.DRAFT)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="posted_warehouse_transfers", verbose_name="مرحل التحويل")
    posted_at = models.DateTimeField("تاريخ الترحيل", null=True, blank=True)
    reversed_at = models.DateTimeField("تاريخ العكس", null=True, blank=True)
    notes = models.TextField("سبب التحويل وملاحظاته")

    class Meta:
        verbose_name = "تحويل مخزني"
        verbose_name_plural = "تحويلات المستودعات"
        permissions = [
            ("post_warehousetransfer", "Can post warehouse transfers"),
            ("reverse_warehousetransfer", "Can reverse warehouse transfers"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "transfer_number"],
                condition=models.Q(is_archived=False),
                name="inventory_transfer_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="inventory_transfer_idem_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_transfer_qty_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.quantity <= 0:
            raise ValidationError({"quantity": "كمية التحويل يجب أن تكون أكبر من صفر."})
        if len(self.idempotency_key.strip()) < 8:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب ألا يقل عن 8 أحرف."})
        if self.source_warehouse_id and self.destination_warehouse_id:
            if self.source_warehouse_id == self.destination_warehouse_id:
                raise ValidationError("لا يمكن التحويل من المستودع إلى نفسه.")
            if self.source_warehouse.school_id != self.school_id or self.destination_warehouse.school_id != self.school_id:
                raise ValidationError("يجب أن يتبع المستودعان المدرسة نفسها.")
        if self.item_id and self.item.school_id != self.school_id:
            raise ValidationError({"item": "الصنف لا يتبع المدرسة نفسها."})
        if self.source_warehouse_id and self.item_id and self.item.branch_id and self.source_warehouse.branch_id and self.item.branch_id != self.source_warehouse.branch_id:
            raise ValidationError({"source_warehouse": "المستودع المصدر لا يتوافق مع فرع الصنف."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("تعديل مستند التحويل بعد إنشائه يتم عبر خدمات التحويل فقط.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.DRAFT:
            raise ValidationError("لا يمكن حذف تحويل مرحّل أو معكوس.")
        return super().delete(*args, **kwargs)


class VendorInvoice(TenantOwnedModel):
    """فاتورة مورد مستلزمات وكتب ومطابقتها مع أمر الشراء لإثبات الذمم الدائنة."""
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        APPROVED = "approved", "معتمدة"
        PAID = "paid", "مسددة بالكامل"
        PARTIAL = "partial", "مسددة جزئياً"
        CANCELLED = "cancelled", "ملغاة"

    class AccountingTreatment(models.TextChoices):
        INVENTORY = "inventory", "مخزون"
        FIXED_ASSET = "fixed_asset", "أصل ثابت"
        EXPENSE = "expense", "مصروف مباشر"

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
    accounting_treatment = models.CharField("المعالجة المحاسبية", max_length=20, choices=AccountingTreatment.choices, default=AccountingTreatment.INVENTORY)
    expense_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="vendor_invoices", verbose_name="حساب المصروف أو الأصل",
    )
    cost_center = models.ForeignKey(
        "accounting.CostCenter", null=True, blank=True, on_delete=models.PROTECT,
        related_name="vendor_invoices", verbose_name="مركز التكلفة",
    )
    status = models.CharField("حالة الفاتورة", max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_vendor_invoices", verbose_name="معتمد الفاتورة",
    )
    approved_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)
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
        permissions = [
            ("approve_vendorinvoice", "Can approve vendor invoices"),
            ("pay_vendorinvoice", "Can pay vendor invoices"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "invoice_number"],
                condition=models.Q(is_archived=False),
                name="inventory_vendor_invoice_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"فاتورة مورد #{self.invoice_number} - {self.supplier.name} ({self.total_amount})"

    def clean(self):
        super().clean()
        if self.school_id and self.supplier_id and self.supplier.school_id != self.school_id:
            raise ValidationError({"supplier": "المورد المحدد لا يتبع نفس المدرسة."})
        if self.school_id and self.purchase_order_id:
            if self.purchase_order.school_id != self.school_id:
                raise ValidationError({"purchase_order": "أمر الشراء لا يتبع نفس المدرسة."})
            if self.purchase_order.supplier_id != self.supplier_id:
                raise ValidationError({"purchase_order": "أمر الشراء مرتبط بمورد مختلف عن مورد الفاتورة."})
        if self.total_amount <= Decimal("0.00"):
            raise ValidationError({"total_amount": "إجمالي الفاتورة يجب أن يكون أكبر من الصفر."})
        if self.paid_amount < 0 or self.paid_amount > self.total_amount:
            raise ValidationError({"paid_amount": "المبلغ المسدد يجب أن يكون بين صفر وإجمالي الفاتورة."})
        if self.cost_center_id and self.cost_center.school_id != self.school_id:
            raise ValidationError({"cost_center": "مركز التكلفة لا يتبع المدرسة نفسها."})
        if self.expense_account_id and self.expense_account.school_id != self.school_id:
            raise ValidationError({"expense_account": "حساب الفاتورة لا يتبع المدرسة نفسها."})
        if self.accounting_treatment == self.AccountingTreatment.EXPENSE:
            if not self.expense_account_id or self.expense_account.account_type != "expense" or not self.expense_account.is_leaf:
                raise ValidationError({"expense_account": "اختر حساب مصروف تفصيلياً صالحاً."})
        if self.accounting_treatment == self.AccountingTreatment.FIXED_ASSET:
            if self.expense_account_id and (self.expense_account.account_type != "asset" or not self.expense_account.is_leaf):
                raise ValidationError({"expense_account": "حساب الأصل يجب أن يكون حساب أصول تفصيلياً."})
        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            raise ValidationError({"due_date": "تاريخ استحقاق الفاتورة يجب ألا يسبق تاريخ إصدارها."})

    @property
    def remaining_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.total_amount - self.paid_amount)


class VendorInvoicePayment(TenantOwnedModel):
    """سجل ربط غير قابل للتكرار بين دفعة المورد والفاتورة وسند الصرف."""
    invoice = models.ForeignKey(
        VendorInvoice, on_delete=models.PROTECT, related_name="payments",
        verbose_name="فاتورة المورد",
    )
    payment_voucher = models.OneToOneField(
        "accounting.PaymentVoucher", on_delete=models.PROTECT,
        related_name="vendor_invoice_payment", verbose_name="سند الصرف",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.PROTECT,
        related_name="vendor_invoice_payments", verbose_name="القيد المحاسبي",
    )
    amount = models.DecimalField("مبلغ الدفعة", max_digits=14, decimal_places=2)
    idempotency_key = models.CharField("مفتاح منع تكرار الدفعة", max_length=100)
    payment_date = models.DateField("تاريخ السداد", default=timezone.localdate)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="vendor_invoice_payments", verbose_name="مسجل الدفعة",
    )

    class Meta:
        verbose_name = "دفعة فاتورة مورد"
        verbose_name_plural = "دفعات فواتير الموردين"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="inventory_vendor_payment_idem_uniq",
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="inventory_vendor_payment_positive"),
        ]

    def clean(self):
        super().clean()
        if self.invoice_id and self.invoice.school_id != self.school_id:
            raise ValidationError({"invoice": "الفاتورة لا تتبع المدرسة نفسها."})
        if self.payment_voucher_id and self.payment_voucher.school_id != self.school_id:
            raise ValidationError({"payment_voucher": "سند الصرف لا يتبع المدرسة نفسها."})
        if self.journal_entry_id and self.journal_entry.school_id != self.school_id:
            raise ValidationError({"journal_entry": "القيد المحاسبي لا يتبع المدرسة نفسها."})
        if self.amount <= 0 or len(self.idempotency_key.strip()) < 8:
            raise ValidationError("مبلغ الدفعة موجب ومفتاح منع التكرار بطول 8 أحرف على الأقل مطلوب.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سجل دفعة المورد تاريخي وغير قابل للتعديل.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يجوز حذف دفعة مورد؛ التصحيح عبر عكس سند الصرف والقيد المحاسبي.")


class WarehouseStocktake(TenantOwnedModel):
    """محضر جرد فعلي يقفل المستودع مؤقتاً حتى الاعتماد أو الإلغاء."""

    class Status(models.TextChoices):
        COUNTING = "counting", "قيد الجرد"
        POSTED = "posted", "معتمد ومرحّل"
        CANCELLED = "cancelled", "ملغى"

    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="stocktakes",
        verbose_name="المستودع",
    )
    stocktake_number = models.CharField("رقم محضر الجرد", max_length=60)
    count_date = models.DateField("تاريخ الجرد", default=timezone.localdate)
    idempotency_key = models.CharField("مفتاح منع تكرار الجرد", max_length=100)
    status = models.CharField("حالة الجرد", max_length=20, choices=Status.choices, default=Status.COUNTING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_inventory_stocktakes", verbose_name="منشئ الجرد",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posted_inventory_stocktakes", verbose_name="معتمد الجرد",
    )
    posted_at = models.DateTimeField("تاريخ اعتماد الجرد", null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cancelled_inventory_stocktakes", verbose_name="ملغي الجرد",
    )
    cancelled_at = models.DateTimeField("تاريخ إلغاء الجرد", null=True, blank=True)
    notes = models.TextField("ملاحظات الجرد", blank=True)

    class Meta:
        verbose_name = "محضر جرد مخزني"
        verbose_name_plural = "محاضر الجرد المخزني"
        permissions = [
            ("count_warehousestocktake", "Can record warehouse stock counts"),
            ("post_warehousestocktake", "Can post warehouse stocktakes"),
            ("cancel_warehousestocktake", "Can cancel warehouse stocktakes"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "stocktake_number"],
                condition=models.Q(is_archived=False),
                name="inventory_stocktake_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=models.Q(is_archived=False),
                name="inventory_stocktake_idem_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "warehouse"],
                condition=models.Q(is_archived=False, status="counting"),
                name="inventory_one_active_stocktake_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "warehouse", "status"], name="inventory_stocktake_scope_idx"),
        ]

    def clean(self):
        super().clean()
        if self.warehouse_id and self.warehouse.school_id != self.school_id:
            raise ValidationError({"warehouse": "المستودع لا يتبع المدرسة نفسها."})
        if self.warehouse_id and self.warehouse.is_archived:
            raise ValidationError({"warehouse": "لا يمكن جرد مستودع مؤرشف."})
        if not 8 <= len(self.idempotency_key.strip()) <= 100:
            raise ValidationError({"idempotency_key": "مفتاح منع التكرار يجب أن يكون بين 8 و100 حرف."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("محضر الجرد لا يعدل مباشرة؛ استخدم خدمات الجرد المعتمدة.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا تحذف محاضر الجرد؛ استخدم الإلغاء قبل الترحيل.")


class WarehouseStocktakeLine(TenantOwnedModel):
    """سطر جرد يحتفظ برصيد النظام ونتيجة العد الفعلي قبل التسوية."""

    stocktake = models.ForeignKey(
        WarehouseStocktake, on_delete=models.PROTECT, related_name="lines",
        verbose_name="محضر الجرد",
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="stocktake_lines",
        verbose_name="الصنف",
    )
    system_quantity = models.DecimalField("رصيد النظام عند بدء الجرد", max_digits=14, decimal_places=2)
    counted_quantity = models.DecimalField(
        "الكمية الفعلية المعدودة", max_digits=14, decimal_places=2,
        null=True, blank=True,
    )
    unit_cost = models.DecimalField("متوسط تكلفة الوحدة وقت الجرد", max_digits=14, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        verbose_name = "بند محضر جرد"
        verbose_name_plural = "بنود محاضر الجرد"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "stocktake", "item"],
                condition=models.Q(is_archived=False),
                name="inventory_stocktake_item_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(system_quantity__gte=0),
                name="inventory_stocktake_system_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(counted_quantity__isnull=True) | models.Q(counted_quantity__gte=0),
                name="inventory_stocktake_count_nonnegative",
            ),
        ]

    @property
    def variance(self):
        if self.counted_quantity is None:
            return None
        return self.counted_quantity - self.system_quantity

    def clean(self):
        super().clean()
        if self.stocktake_id and self.stocktake.school_id != self.school_id:
            raise ValidationError({"stocktake": "محضر الجرد لا يتبع المدرسة نفسها."})
        if self.item_id and self.item.school_id != self.school_id:
            raise ValidationError({"item": "الصنف لا يتبع المدرسة نفسها."})
        if self.stocktake_id and self.item_id:
            if self.stocktake.warehouse_id != self.item.warehouse_id and not self.item.warehouse_balances.filter(
                warehouse=self.stocktake.warehouse, is_archived=False,
            ).exists():
                raise ValidationError({"item": "الصنف لا يملك مستودعاً أو رصيداً في المستودع الجاري جرده."})
        if self.system_quantity < 0 or (self.counted_quantity is not None and self.counted_quantity < 0):
            raise ValidationError("كميات الجرد لا يمكن أن تكون سالبة.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سطر الجرد تاريخي؛ تسجل نتيجة العد عبر خدمة الجرد فقط.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("لا يجوز حذف سطر جرد؛ ألغِ المحضر قبل ترحيله.")
