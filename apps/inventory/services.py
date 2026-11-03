"""Transactional procurement and inventory workflows.

All quantities change through this module and immutable StockMovement rows.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    StockMovement,
    VendorInvoice,
    Warehouse,
    WarehouseStock,
    WarehouseStocktake,
    WarehouseStocktakeLine,
    WarehouseTransfer,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stock_movement_key(prefix: str, key: str, row_id) -> str:
    return f"{prefix}:{_digest(f'{key}:{row_id}')[:48]}"


@transaction.atomic
def record_stock_movement(
    *,
    school,
    item: InventoryItem,
    warehouse: Warehouse | None,
    movement_type: str,
    quantity: Decimal,
    unit_cost: Decimal = Decimal("0.0000"),
    idempotency_key: str,
    notes: str,
    date_value=None,
    reference: str = "",
    recipient_name: str = "",
    created_by=None,
) -> tuple[StockMovement, bool]:
    """Create one stock ledger movement exactly once."""
    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع تكرار الحركة يجب أن يكون بين 8 و100 حرف.")
    quantity = Decimal(quantity)
    unit_cost = Decimal(unit_cost)
    if quantity <= 0:
        raise ValidationError("كمية الحركة يجب أن تكون أكبر من صفر.")
    if unit_cost < 0:
        raise ValidationError("تكلفة الوحدة لا يمكن أن تكون سالبة.")
    if item.school_id != school.pk:
        raise ValidationError("الصنف لا يتبع المدرسة النشطة.")
    warehouse = warehouse or item.warehouse
    if warehouse.school_id != school.pk or warehouse.is_archived:
        raise ValidationError("المستودع غير صالح أو لا يتبع المدرسة النشطة.")

    locked_item = InventoryItem.objects.select_for_update().get(
        pk=item.pk, school_id=school.pk, is_archived=False,
    )
    existing = StockMovement.objects.filter(
        school=school, idempotency_key=key, is_archived=False,
    ).first()
    if existing:
        same = (
            existing.item_id == locked_item.pk
            and existing.warehouse_id == warehouse.pk
            and existing.movement_type == movement_type
            and existing.quantity == quantity
            and existing.unit_cost == unit_cost
            and existing.reference == reference
            and existing.recipient_name == recipient_name
        )
        if not same:
            raise ValidationError("مفتاح منع التكرار مستخدم لحركة مخزنية ببيانات مختلفة.")
        return existing, False

    movement = StockMovement.objects.create(
        school=school,
        branch=warehouse.branch,
        item=locked_item,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        date=date_value or timezone.localdate(),
        reference=reference,
        recipient_name=recipient_name,
        notes=(notes or "").strip() or "حركة مخزنية موثقة.",
        idempotency_key=key,
        created_by=created_by,
    )
    return movement, True


@transaction.atomic
def reverse_stock_movement(
    *,
    movement: StockMovement,
    idempotency_key: str,
    reason: str,
    reversed_by=None,
) -> StockMovement:
    """Reverse a non-transfer movement without editing or deleting history."""
    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع التكرار يجب أن يكون بين 8 و100 حرف.")
    if not reason.strip():
        raise ValidationError("سبب عكس حركة المخزون مطلوب.")
    locked = StockMovement.objects.select_for_update().get(pk=movement.pk)
    if locked.movement_type in {
        StockMovement.MovementType.TRANSFER_IN,
        StockMovement.MovementType.TRANSFER_OUT,
    }:
        raise ValidationError("يجب عكس مستند التحويل كاملاً من مسار التحويلات.")
    existing = StockMovement.objects.filter(
        school=locked.school, idempotency_key=key, is_archived=False,
    ).first()
    if existing:
        if existing.reversal_of_id != locked.pk:
            raise ValidationError("مفتاح منع التكرار مرتبط بعكس حركة مختلفة.")
        return existing
    if hasattr(locked, "reversal"):
        raise ValidationError("تم عكس هذه الحركة مسبقاً.")
    reverse_type = {
        StockMovement.MovementType.RECEIPT: StockMovement.MovementType.ADJUSTMENT_SUB,
        StockMovement.MovementType.ISSUE: StockMovement.MovementType.ADJUSTMENT_ADD,
        StockMovement.MovementType.ADJUSTMENT_ADD: StockMovement.MovementType.ADJUSTMENT_SUB,
        StockMovement.MovementType.ADJUSTMENT_SUB: StockMovement.MovementType.ADJUSTMENT_ADD,
    }[locked.movement_type]
    return StockMovement.objects.create(
        school=locked.school,
        branch=locked.branch,
        item=locked.item,
        warehouse=locked.warehouse,
        movement_type=reverse_type,
        quantity=locked.quantity,
        unit_cost=locked.unit_cost,
        date=timezone.localdate(),
        reference=f"عكس الحركة {locked.pk}",
        notes=reason.strip(),
        idempotency_key=key,
        created_by=reversed_by,
        reversal_of=locked,
    )


@transaction.atomic
def approve_purchase_order(*, purchase_order: PurchaseOrder, approved_by) -> PurchaseOrder:
    """Approve a complete draft after locking the header and validating all lines."""
    locked = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    if locked.status != PurchaseOrder.Status.DRAFT:
        raise ValidationError("لا يمكن اعتماد أمر شراء إلا إذا كان مسودة.")
    lines = list(
        PurchaseOrderItem.objects.select_for_update().filter(
            purchase_order=locked, is_archived=False,
        ).select_related("item"),
    )
    if not lines:
        raise ValidationError("لا يمكن اعتماد أمر شراء بلا بنود.")
    for line in lines:
        line.full_clean()
        if line.item.school_id != locked.school_id:
            raise ValidationError("يوجد بند لصنف من مدرسة أخرى.")
    total = sum((line.total_price for line in lines), Decimal("0.00"))
    if total <= 0:
        raise ValidationError("إجمالي أمر الشراء يجب أن يكون أكبر من صفر.")
    locked.total_amount = total
    locked.status = PurchaseOrder.Status.APPROVED
    locked.approved_by = approved_by
    locked.approved_at = timezone.now()
    locked.save(update_fields=[
        "total_amount", "status", "approved_by", "approved_at", "updated_at",
    ])
    return locked


@transaction.atomic
def receive_purchase_order(
    *,
    purchase_order: PurchaseOrder,
    received_items: list[dict],
    idempotency_key: str,
    received_by=None,
    notes: str = "",
) -> tuple[PurchaseReceipt, bool]:
    """Receive any subset of a PO, allowing several partial receipts safely."""
    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع التكرار يجب أن يكون بين 8 و100 حرف.")
    if not received_items:
        raise ValidationError("حدد بنداً واحداً على الأقل للاستلام.")

    normalized = []
    for entry in received_items:
        item_id = str(entry.get("purchase_order_item_id") or "")
        qty = Decimal(str(entry.get("quantity", "0")))
        if not item_id or qty <= 0:
            raise ValidationError("كل بند استلام يتطلب معرف بند صحيحاً وكمية موجبة.")
        normalized.append((item_id, qty))
    normalized.sort(key=lambda value: value[0])
    if len({row[0] for row in normalized}) != len(normalized):
        raise ValidationError("لا تكرر البند في محضر الاستلام نفسه؛ اجمع الكمية في سطر واحد.")
    payload_hash = _digest(json.dumps(
        [(item_id, str(qty)) for item_id, qty in normalized],
        ensure_ascii=False, separators=(",", ":"),
    ))

    locked_order = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    existing = PurchaseReceipt.objects.select_for_update().filter(
        school=locked_order.school,
        idempotency_key=key,
        is_archived=False,
    ).first()
    if existing:
        if existing.purchase_order_id != locked_order.pk or existing.payload_hash != payload_hash:
            raise ValidationError("مفتاح الاستلام نفسه مستخدم لأمر شراء أو كميات مختلفة.")
        return existing, False
    if locked_order.status not in {
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    }:
        raise ValidationError("لا يمكن استلام أمر شراء غير معتمد أو مكتمل أو ملغى.")

    receipt_digest = _digest(f"{locked_order.pk}:{key}")[:20].upper()
    receipt = PurchaseReceipt.objects.create(
        school=locked_order.school,
        branch=locked_order.branch or locked_order.warehouse.branch,
        purchase_order=locked_order,
        receipt_number=f"GRN-{receipt_digest}",
        idempotency_key=key,
        payload_hash=payload_hash,
        received_by=received_by,
        notes=(notes or "").strip(),
    )

    line_ids = [row[0] for row in normalized]
    lines = {
        str(line.pk): line
        for line in PurchaseOrderItem.objects.select_for_update().filter(
            purchase_order=locked_order,
            pk__in=line_ids,
            is_archived=False,
        ).select_related("item")
    }
    if len(lines) != len(normalized):
        raise ValidationError("تحتوي بيانات الاستلام على بند لا يتبع أمر الشراء المحدد.")

    for item_id, qty in normalized:
        line = lines[item_id]
        outstanding = line.quantity - line.received_quantity
        if qty > outstanding:
            raise ValidationError(
                f"الكمية المستلمة للصنف {line.item.name} تتجاوز المتبقي في أمر الشراء ({outstanding})."
            )
        StockMovement.objects.create(
            school=locked_order.school,
            branch=locked_order.warehouse.branch or locked_order.branch,
            item=line.item,
            warehouse=locked_order.warehouse,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=qty,
            unit_cost=line.unit_price,
            date=timezone.localdate(),
            reference=f"محضر استلام {receipt.receipt_number}",
            notes=(notes or "").strip() or f"استلام بند أمر شراء {locked_order.order_number}.",
            idempotency_key=_stock_movement_key("grn", key, line.pk),
            created_by=received_by,
            purchase_order_item=line,
            purchase_receipt=receipt,
        )
        models.QuerySet.update(
            PurchaseOrderItem.objects.filter(pk=line.pk),
            received_quantity=line.received_quantity + qty,
            updated_at=timezone.now(),
        )

    pending = PurchaseOrderItem.objects.filter(
        purchase_order=locked_order, is_archived=False,
        received_quantity__lt=models.F("quantity"),
    ).exists()
    locked_order.status = (
        PurchaseOrder.Status.PARTIALLY_RECEIVED
        if pending else PurchaseOrder.Status.RECEIVED
    )
    if not pending:
        locked_order.received_at = timezone.now()
    locked_order.save(update_fields=["status", "received_at", "updated_at"])
    return receipt, True


@transaction.atomic
def cancel_purchase_order(*, purchase_order: PurchaseOrder, cancelled_by=None) -> PurchaseOrder:
    locked = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    if locked.status not in {PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.APPROVED}:
        raise ValidationError("لا يمكن إلغاء أمر شراء بدأ استلامه أو اكتمل استلامه.")
    if locked.status == PurchaseOrder.Status.APPROVED and locked.items.filter(
        received_quantity__gt=0, is_archived=False,
    ).exists():
        raise ValidationError("لا يمكن إلغاء أمر شراء له كميات مستلمة.")
    locked.status = PurchaseOrder.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    return locked


@transaction.atomic
def post_warehouse_transfer(*, transfer: WarehouseTransfer, posted_by=None) -> WarehouseTransfer:
    locked = WarehouseTransfer.objects.select_for_update().get(pk=transfer.pk)
    if locked.status == WarehouseTransfer.Status.POSTED:
        return locked
    if locked.status != WarehouseTransfer.Status.DRAFT:
        raise ValidationError("لا يمكن ترحيل تحويل ملغى أو معكوس.")
    source_balance = WarehouseStock.objects.filter(
        school=locked.school, item=locked.item,
        warehouse=locked.source_warehouse, is_archived=False,
    ).first()
    available = source_balance.quantity if source_balance else Decimal("0.00")
    if available < locked.quantity:
        raise ValidationError(f"الرصيد غير كافٍ للتحويل؛ المتاح {available}.")
    cost = (
        locked.unit_cost if locked.unit_cost > 0
        else source_balance.average_unit_cost
    )
    key = locked.idempotency_key
    StockMovement.objects.create(
        school=locked.school, branch=locked.source_warehouse.branch,
        item=locked.item, warehouse=locked.source_warehouse,
        movement_type=StockMovement.MovementType.TRANSFER_OUT,
        quantity=locked.quantity, unit_cost=cost,
        date=locked.transfer_date, reference=locked.transfer_number,
        notes=locked.notes, idempotency_key=_stock_movement_key("transfer-out", key, locked.pk),
        created_by=posted_by, transfer=locked,
    )
    StockMovement.objects.create(
        school=locked.school, branch=locked.destination_warehouse.branch,
        item=locked.item, warehouse=locked.destination_warehouse,
        movement_type=StockMovement.MovementType.TRANSFER_IN,
        quantity=locked.quantity, unit_cost=cost,
        date=locked.transfer_date, reference=locked.transfer_number,
        notes=locked.notes, idempotency_key=_stock_movement_key("transfer-in", key, locked.pk),
        created_by=posted_by, transfer=locked,
    )
    locked.unit_cost = cost
    locked.status = WarehouseTransfer.Status.POSTED
    locked.posted_by = posted_by
    locked.posted_at = timezone.now()
    locked.save(update_fields=["unit_cost", "status", "posted_by", "posted_at", "updated_at"])
    return locked


@transaction.atomic
def reverse_warehouse_transfer(
    *, transfer: WarehouseTransfer, reason: str, reversed_by=None,
) -> WarehouseTransfer:
    locked = WarehouseTransfer.objects.select_for_update().get(pk=transfer.pk)
    if locked.status == WarehouseTransfer.Status.REVERSED:
        return locked
    if locked.status != WarehouseTransfer.Status.POSTED:
        raise ValidationError("لا يمكن عكس تحويل غير مرحّل.")
    original = list(locked.movements.select_for_update().filter(is_archived=False))
    source_out = next(
        (row for row in original if row.movement_type == StockMovement.MovementType.TRANSFER_OUT),
        None,
    )
    destination_in = next(
        (row for row in original if row.movement_type == StockMovement.MovementType.TRANSFER_IN),
        None,
    )
    if not source_out or not destination_in:
        raise ValidationError("سجل التحويل غير مكتمل؛ يلزم التدقيق قبل العكس.")
    reverse_key = f"reverse-{_digest(locked.idempotency_key)[:48]}"
    StockMovement.objects.create(
        school=locked.school, branch=locked.destination_warehouse.branch,
        item=locked.item, warehouse=locked.destination_warehouse,
        movement_type=StockMovement.MovementType.TRANSFER_OUT,
        quantity=locked.quantity, unit_cost=locked.unit_cost,
        reference=f"عكس {locked.transfer_number}", notes=reason.strip(),
        idempotency_key=_stock_movement_key("transfer-reverse-out", reverse_key, locked.pk),
        created_by=reversed_by, transfer=locked, reversal_of=destination_in,
    )
    StockMovement.objects.create(
        school=locked.school, branch=locked.source_warehouse.branch,
        item=locked.item, warehouse=locked.source_warehouse,
        movement_type=StockMovement.MovementType.TRANSFER_IN,
        quantity=locked.quantity, unit_cost=locked.unit_cost,
        reference=f"عكس {locked.transfer_number}", notes=reason.strip(),
        idempotency_key=_stock_movement_key("transfer-reverse-in", reverse_key, locked.pk),
        created_by=reversed_by, transfer=locked, reversal_of=source_out,
    )
    locked.status = WarehouseTransfer.Status.REVERSED
    locked.reversed_at = timezone.now()
    locked.save(update_fields=["status", "reversed_at", "updated_at"])
    return locked


@transaction.atomic
def approve_vendor_invoice(*, invoice: VendorInvoice, approved_by=None):
    """Post the supplier payable entry only once after invoice validations."""
    from apps.accounting.services.auto_posting import post_vendor_invoice_to_journal

    locked = VendorInvoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status not in {VendorInvoice.Status.DRAFT, VendorInvoice.Status.APPROVED}:
        raise ValidationError("لا يمكن اعتماد فاتورة مورد مدفوعة أو ملغاة.")
    if locked.purchase_order_id:
        received_value = sum(
            (row.received_quantity * row.unit_price for row in locked.purchase_order.items.filter(is_archived=False)),
            Decimal("0.00"),
        )
        if received_value < locked.total_amount:
            raise ValidationError("قيمة فاتورة المورد تتجاوز قيمة البضائع المستلمة من أمر الشراء.")
    entry = post_vendor_invoice_to_journal(locked, user=approved_by)
    locked.refresh_from_db()
    if locked.status == VendorInvoice.Status.DRAFT:
        locked.status = VendorInvoice.Status.APPROVED
        locked.approved_by = approved_by
        locked.approved_at = timezone.now()
        locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return locked, entry


@transaction.atomic
def pay_vendor_invoice(
    *,
    invoice: VendorInvoice,
    payment_account,
    amount: Decimal,
    idempotency_key: str,
    reference_number: str = "",
    payment_method: str = "bank_transfer",
    user=None,
):
    from apps.accounting.services.auto_posting import disburse_vendor_payment

    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع تكرار السداد يجب أن يكون بين 8 و100 حرف.")
    locked = VendorInvoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status not in {VendorInvoice.Status.APPROVED, VendorInvoice.Status.PARTIAL}:
        raise ValidationError("يجب اعتماد فاتورة المورد وترحيلها قبل السداد.")
    if not locked.journal_entry_id or locked.journal_entry.status != "posted":
        raise ValidationError("فاتورة المورد لا تملك قيد استحقاق مرحّلاً.")
    if payment_account.school_id != locked.school_id or payment_account.is_archived:
        raise ValidationError("حساب السداد غير صالح أو لا يتبع المدرسة نفسها.")
    if payment_account.account_type != "asset" or not payment_account.is_leaf:
        raise ValidationError("حساب السداد يجب أن يكون حساب أصول تفصيلياً.")
    if locked.branch_id and payment_account.branch_id and locked.branch_id != payment_account.branch_id:
        raise ValidationError("حساب السداد لا يتبع فرع الفاتورة.")
    return disburse_vendor_payment(
        locked,
        payment_account=payment_account,
        amount=Decimal(amount),
        reference_number=reference_number,
        payment_method=payment_method,
        user=user,
        idempotency_key=key,
    )


@transaction.atomic
def start_stocktake(
    *,
    school,
    warehouse: Warehouse,
    stocktake_number: str,
    idempotency_key: str,
    count_date=None,
    notes: str = "",
    created_by=None,
) -> tuple[WarehouseStocktake, bool]:
    """Open one warehouse count, snapshot every relevant item and freeze movements."""
    key = (idempotency_key or "").strip()
    number = (stocktake_number or "").strip()
    if not 8 <= len(key) <= 100:
        raise ValidationError("مفتاح منع تكرار الجرد يجب أن يكون بين 8 و100 حرف.")
    if not number:
        raise ValidationError("رقم محضر الجرد مطلوب.")
    if warehouse.school_id != school.pk or warehouse.is_archived:
        raise ValidationError("المستودع غير نشط أو لا يتبع المدرسة المحددة.")

    locked_warehouse = Warehouse.objects.select_for_update().get(
        pk=warehouse.pk, school=school, is_archived=False,
    )
    existing = WarehouseStocktake.objects.filter(
        school=school, idempotency_key=key, is_archived=False,
    ).first()
    if existing:
        if existing.warehouse_id != locked_warehouse.pk or existing.stocktake_number != number:
            raise ValidationError("مفتاح منع التكرار مستخدم لمحضر جرد مختلف.")
        return existing, False
    if WarehouseStocktake.objects.filter(
        school=school, warehouse=locked_warehouse,
        status=WarehouseStocktake.Status.COUNTING, is_archived=False,
    ).exists():
        raise ValidationError("يوجد محضر جرد مفتوح لهذا المستودع؛ أكمله أو ألغِه أولاً.")

    stocktake = WarehouseStocktake.objects.create(
        school=school,
        branch=locked_warehouse.branch,
        warehouse=locked_warehouse,
        stocktake_number=number,
        count_date=count_date or timezone.localdate(),
        idempotency_key=key,
        notes=(notes or "").strip(),
        created_by=created_by,
    )
    items = InventoryItem.objects.filter(
        school=school,
        is_archived=False,
    ).filter(
        models.Q(warehouse=locked_warehouse)
        | models.Q(warehouse_balances__warehouse=locked_warehouse, warehouse_balances__is_archived=False)
    ).distinct().order_by("code")
    balances = {
        row.item_id: row
        for row in WarehouseStock.objects.filter(
            school=school, warehouse=locked_warehouse, is_archived=False,
        )
    }
    item_count = 0
    for item in items:
        balance = balances.get(item.pk)
        WarehouseStocktakeLine.objects.create(
            school=school,
            branch=locked_warehouse.branch,
            stocktake=stocktake,
            item=item,
            system_quantity=balance.quantity if balance else Decimal("0.00"),
            counted_quantity=None,
            unit_cost=balance.average_unit_cost if balance else item.unit_cost,
        )
        item_count += 1
    if item_count == 0:
        raise ValidationError("لا توجد أصناف مرتبطة بالمستودع لإنشاء محضر جرد.")
    return stocktake, True


@transaction.atomic
def record_stocktake_counts(
    *,
    stocktake: WarehouseStocktake,
    counts: list[dict],
) -> WarehouseStocktake:
    """Record physical quantities while the warehouse remains frozen."""
    locked = WarehouseStocktake.objects.select_for_update().get(pk=stocktake.pk)
    if locked.status != WarehouseStocktake.Status.COUNTING:
        raise ValidationError("لا يمكن تعديل العد بعد اعتماد محضر الجرد أو إلغائه.")
    if not counts:
        raise ValidationError("أرسل بنداً واحداً على الأقل لتسجيل نتيجة العد.")
    normalized = []
    for row in counts:
        line_id = str(row.get("line_id") or "").strip()
        quantity = Decimal(str(row.get("counted_quantity", "-1")))
        if not line_id or quantity < 0:
            raise ValidationError("كل بند يتطلب معرفاً صحيحاً وكمية معدودة غير سالبة.")
        normalized.append((line_id, quantity))
    if len({line_id for line_id, _ in normalized}) != len(normalized):
        raise ValidationError("لا تكرر بند الجرد نفسه في طلب واحد.")

    lines = {
        str(line.pk): line
        for line in WarehouseStocktakeLine.objects.select_for_update().filter(
            stocktake=locked, school=locked.school,
            pk__in=[line_id for line_id, _ in normalized],
            is_archived=False,
        )
    }
    if len(lines) != len(normalized):
        raise ValidationError("يوجد بند لا يتبع محضر الجرد المحدد.")
    for line_id, quantity in normalized:
        models.QuerySet.update(
            WarehouseStocktakeLine.objects.filter(pk=lines[line_id].pk),
            counted_quantity=quantity,
            updated_at=timezone.now(),
        )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def post_stocktake(
    *,
    stocktake: WarehouseStocktake,
    posted_by=None,
) -> WarehouseStocktake:
    """Post only fully counted rows as immutable adjustment movements, once."""
    locked = WarehouseStocktake.objects.select_for_update().get(pk=stocktake.pk)
    if locked.status == WarehouseStocktake.Status.POSTED:
        return locked
    if locked.status != WarehouseStocktake.Status.COUNTING:
        raise ValidationError("لا يمكن ترحيل محضر جرد ملغى أو غير مفتوح.")
    lines = list(
        WarehouseStocktakeLine.objects.select_for_update().filter(
            stocktake=locked, school=locked.school, is_archived=False,
        ).select_related("item").order_by("item_id")
    )
    if not lines:
        raise ValidationError("محضر الجرد لا يحتوي على أصناف.")
    missing = [line.item.code for line in lines if line.counted_quantity is None]
    if missing:
        raise ValidationError(
            "لا يمكن ترحيل الجرد قبل إدخال الكميات لكل الأصناف: " + ", ".join(missing[:20])
        )

    for line in lines:
        variance = line.counted_quantity - line.system_quantity
        if variance == 0:
            continue
        movement_type = (
            StockMovement.MovementType.ADJUSTMENT_ADD
            if variance > 0
            else StockMovement.MovementType.ADJUSTMENT_SUB
        )
        StockMovement.objects.create(
            school=locked.school,
            branch=locked.warehouse.branch,
            item=line.item,
            warehouse=locked.warehouse,
            movement_type=movement_type,
            quantity=abs(variance),
            unit_cost=line.unit_cost,
            date=locked.count_date,
            reference=f"جرد {locked.stocktake_number}",
            notes=f"تسوية فرق الجرد للصنف {line.item.code}: {variance:+.2f}. {locked.notes}".strip(),
            idempotency_key=_stock_movement_key("stocktake", locked.idempotency_key, line.pk),
            created_by=posted_by,
            stocktake_line=line,
        )

    models.QuerySet.update(
        WarehouseStocktake.objects.filter(pk=locked.pk),
        status=WarehouseStocktake.Status.POSTED,
        posted_by=posted_by,
        posted_at=timezone.now(),
        updated_at=timezone.now(),
    )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def cancel_stocktake(
    *,
    stocktake: WarehouseStocktake,
    cancelled_by=None,
    reason: str = "",
) -> WarehouseStocktake:
    locked = WarehouseStocktake.objects.select_for_update().get(pk=stocktake.pk)
    if locked.status == WarehouseStocktake.Status.CANCELLED:
        return locked
    if locked.status != WarehouseStocktake.Status.COUNTING:
        raise ValidationError("لا يمكن إلغاء محضر جرد مرحّل؛ يجب تصحيح أثره بحركات معاكسة.")
    note = (reason or "").strip()
    models.QuerySet.update(
        WarehouseStocktake.objects.filter(pk=locked.pk),
        status=WarehouseStocktake.Status.CANCELLED,
        cancelled_by=cancelled_by,
        cancelled_at=timezone.now(),
        notes=(f"{locked.notes}\nسبب الإلغاء: {note}").strip()[:5000],
        updated_at=timezone.now(),
    )
    locked.refresh_from_db()
    return locked
