"""Transactional workflows for optional school services.

All service operations are tenant-scoped and idempotent where they create
financial or stock effects.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.auditlog.services import record_event
from apps.platform.services import school_has_feature
from apps.tenants.models import SchoolSettings

SCHOOL_SERVICE_FEATURES = {
    "school-transport": {"name": "النقل المدرسي", "module": "transport"},
    "school-library": {"name": "المكتبة المدرسية", "module": "library"},
    "school-book-distribution": {"name": "توزيع الكتب وأوامر الصرف", "module": "book_distribution"},
}


def school_service_feature_state(school) -> list[dict]:
    settings = SchoolSettings.objects.filter(school=school).only("feature_overrides").first()
    raw = settings.feature_overrides if settings and isinstance(settings.feature_overrides, dict) else {}
    local = raw.get("school_services", {})
    local = local if isinstance(local, dict) else {}
    result = []
    for code, metadata in SCHOOL_SERVICE_FEATURES.items():
        entitled = school_has_feature(school, code)
        locally_enabled = local.get(code) is not False
        result.append({
            "code": code,
            "name": metadata["name"],
            "entitled": entitled,
            "enabled": entitled and locally_enabled,
            "school_disabled": not locally_enabled,
        })
    return result


def school_service_is_enabled(school, feature_code: str) -> bool:
    if feature_code not in SCHOOL_SERVICE_FEATURES:
        return False
    settings = SchoolSettings.objects.filter(school=school).only("feature_overrides").first()
    raw = settings.feature_overrides if settings and isinstance(settings.feature_overrides, dict) else {}
    local = raw.get("school_services", {})
    if isinstance(local, dict) and local.get(feature_code) is False:
        return False
    return school_has_feature(school, feature_code)


@transaction.atomic
def set_school_service_enabled(*, school, feature_code: str, enabled: bool, actor):
    if feature_code not in SCHOOL_SERVICE_FEATURES:
        raise ValidationError({"code": "رمز خدمة غير معروف."})
    if not isinstance(enabled, bool):
        raise ValidationError({"enabled": "يجب أن تكون القيمة true أو false."})
    entitled = school_has_feature(school, feature_code)
    if enabled and not entitled:
        raise ValidationError({
            "enabled": "لا يمكن تفعيل خدمة غير مشمولة في باقة المدرسة أو غير ممنوحة من إدارة المنصة."
        })
    settings, _ = SchoolSettings.objects.select_for_update().get_or_create(school=school)
    overrides = settings.feature_overrides if isinstance(settings.feature_overrides, dict) else {}
    overrides = dict(overrides)
    service_overrides = overrides.get("school_services", {})
    service_overrides = dict(service_overrides) if isinstance(service_overrides, dict) else {}
    if enabled:
        service_overrides.pop(feature_code, None)
    else:
        service_overrides[feature_code] = False
    overrides["school_services"] = service_overrides
    settings.feature_overrides = overrides
    settings.save(update_fields=["feature_overrides", "updated_at"])
    record_event(
        action="school_service.feature.enabled" if enabled else "school_service.feature.disabled",
        description=f"{SCHOOL_SERVICE_FEATURES[feature_code]['name']} {'تفعيل' if enabled else 'تعطيل'} على مستوى المدرسة",
        actor=actor,
        school=school,
        obj=settings,
        metadata={"feature": feature_code, "enabled": enabled},
    )
    return next(item for item in school_service_feature_state(school) if item["code"] == feature_code)


@transaction.atomic
def update_library_policy(*, school, values: dict, actor=None):
    allowed = {
        "library_default_loan_days": (int, 1, 365),
        "library_max_renewals": (int, 0, 20),
        "library_overdue_fine_per_day": (Decimal, Decimal("0.00"), Decimal("1000000000.00")),
        "library_max_overdue_fine": (Decimal, Decimal("0.00"), Decimal("1000000000.00")),
        "library_lost_book_fine": (Decimal, Decimal("0.00"), Decimal("1000000000.00")),
    }
    if not isinstance(values, dict) or not values:
        raise ValidationError({"detail": "أرسل إعداداً واحداً على الأقل."})
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValidationError({"fields": f"حقول غير مسموح بتعديلها: {', '.join(sorted(unknown))}"})
    settings, _ = SchoolSettings.objects.select_for_update().get_or_create(school=school)
    changed = []
    for field, value in values.items():
        expected_type, minimum, maximum = allowed[field]
        try:
            if expected_type is Decimal:
                normalized = Decimal(str(value))
            else:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError
                normalized = value
        except Exception as exc:
            raise ValidationError({field: "قيمة الإعداد غير صالحة."}) from exc
        if normalized < minimum or normalized > maximum:
            raise ValidationError({field: "قيمة الإعداد خارج الحدود المسموح بها."})
        setattr(settings, field, normalized)
        changed.append(field)
    settings.save(update_fields=[*changed, "updated_at"])
    record_event(
        action="school_library.policy.updated",
        description="تحديث سياسة المكتبة المدرسية",
        actor=actor, school=school, obj=settings,
        metadata={field: str(getattr(settings, field)) for field in changed},
    )
    return settings


@transaction.atomic
def issue_bus_subscription_monthly_invoice(*, school, subscription_id, year: int, month: int, actor=None):
    """Issue one student invoice for one subscription and billing month."""
    from apps.school_services.models import BusSubscriptionCharge, StudentBusSubscription
    from apps.student_fees.models import FeeCategory, StudentInvoice, StudentInvoiceItem

    if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 9999:
        raise ValidationError({"year": "السنة المالية غير صالحة."})
    if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12:
        raise ValidationError({"month": "يجب أن يكون الشهر بين 1 و12."})
    subscription = StudentBusSubscription.objects.select_for_update(of=("self",)).select_related(
        "student", "student__branch", "academic_year", "bus_route", "branch"
    ).get(pk=subscription_id, school=school, is_archived=False)
    existing_charge = BusSubscriptionCharge.objects.select_for_update().filter(
        school=school, subscription=subscription, billing_year=year, billing_month=month
    ).first()
    if existing_charge:
        return existing_charge, False
    if subscription.status != StudentBusSubscription.Status.ACTIVE:
        raise ValidationError("لا تصدر فاتورة نقل لاشتراك غير نشط.")
    if not subscription.bus_route.is_active or subscription.bus_route.is_archived:
        raise ValidationError("خط النقل غير نشط ولا يقبل فوترة جديدة.")
    amount = subscription.bus_route.monthly_fee
    if amount <= Decimal("0.00"):
        raise ValidationError("حدد رسوم النقل الشهرية لخط السير قبل إصدار الفواتير.")

    fee_category, _ = FeeCategory.objects.get_or_create(
        school=school,
        code="BUS-TRANSPORT",
        defaults={"name": "رسوم النقل المدرسي", "is_mandatory": False},
    )
    period_code = f"{year:04d}{month:02d}"
    invoice_key = f"bus-subscription:{subscription.pk}:{period_code}"
    invoice_number = f"BUS-{subscription.pk.hex[:20]}-{period_code}"
    invoice, invoice_created = StudentInvoice.objects.get_or_create(
        school=school,
        idempotency_key=invoice_key,
        defaults={
            "branch": subscription.student.branch,
            "student": subscription.student,
            "academic_year": subscription.academic_year,
            "invoice_number": invoice_number,
            "issue_date": timezone.localdate(),
            "due_date": date(year, month, calendar.monthrange(year, month)[1]),
            "total_amount": amount,
            "notes": f"رسوم النقل المدرسي عن شهر {month:02d}/{year} - {subscription.bus_route.route_name}",
        },
    )
    if (
        invoice.student_id != subscription.student_id
        or invoice.total_amount != amount
        or invoice.academic_year_id != subscription.academic_year_id
        or invoice.status == StudentInvoice.Status.CANCELLED
    ):
        raise ValidationError("مفتاح فاتورة النقل مرتبط ببيانات مختلفة أو فاتورة ملغاة؛ يلزم فحص السجل المالي.")
    if invoice_created:
        StudentInvoiceItem.objects.create(
            school=school,
            branch=invoice.branch,
            invoice=invoice,
            fee_category=fee_category,
            description=f"اشتراك النقل المدرسي - {subscription.bus_route.route_name} - {period_code}",
            amount=amount,
        )
    elif not invoice.items.exists():
        raise ValidationError("فاتورة النقل السابقة لا تحتوي بنوداً؛ لا يمكن متابعة الفوترة تلقائياً.")
    if not invoice.journal_entry_id:
        invoice.post_to_journal()
    invoice.refresh_from_db()
    if (
        not invoice.journal_entry_id
        or invoice.journal_entry.status != invoice.journal_entry.Status.POSTED
    ):
        raise ValidationError("فاتورة النقل غير مرتبطة بقيد محاسبي مرحّل؛ لا يمكن اعتماد فوترة الاشتراك.")

    charge = BusSubscriptionCharge.objects.create(
        school=school,
        branch=subscription.branch or subscription.student.branch,
        subscription=subscription,
        invoice=invoice,
        billing_year=year,
        billing_month=month,
        amount=amount,
        issued_by=actor,
    )
    record_event(
        action="school_transport.subscription.monthly_billed",
        description=f"إصدار فاتورة نقل للطالب عن {period_code}",
        actor=actor,
        school=school,
        obj=charge,
        metadata={
            "subscription_id": str(subscription.pk),
            "invoice_number": invoice.invoice_number,
            "amount": str(amount),
            "billing_year": year,
            "billing_month": month,
        },
    )
    return charge, True


@transaction.atomic
def issue_bus_route_monthly_invoices(*, school, route_id, year: int, month: int, actor=None):
    from apps.school_services.models import BusRoute, StudentBusSubscription

    route = BusRoute.objects.select_for_update().get(
        pk=route_id, school=school, is_archived=False
    )
    if not route.is_active:
        raise ValidationError("لا يمكن فوترة خط نقل غير نشط.")
    subscriptions = StudentBusSubscription.objects.select_for_update(of=("self",)).filter(
        school=school,
        bus_route=route,
        academic_year__school=school,
        status=StudentBusSubscription.Status.ACTIVE,
        is_archived=False,
    ).select_related("student", "student__branch", "academic_year", "branch").order_by("pk")
    issued = []
    skipped = 0
    for subscription in subscriptions:
        charge, created = issue_bus_subscription_monthly_invoice(
            school=school,
            subscription_id=subscription.pk,
            year=year,
            month=month,
            actor=actor,
        )
        issued.append(charge)
        if not created:
            skipped += 1
    return {"charges": issued, "created": len(issued) - skipped, "already_issued": skipped}


def _library_policy(school):
    settings = SchoolSettings.objects.filter(school=school).first()
    if settings is None:
        settings = SchoolSettings.objects.create(school=school)
    return settings


def _create_library_fine_invoice(*, loan, amount: Decimal, reason: str):
    from apps.student_fees.models import FeeCategory, StudentInvoice, StudentInvoiceItem

    if not loan.student_id or amount <= Decimal("0.00"):
        return None
    if loan.fine_invoice_id:
        return loan.fine_invoice
    category, _ = FeeCategory.objects.get_or_create(
        school=loan.school,
        code="LIBRARY-FINE",
        defaults={"name": "غرامات المكتبة", "is_mandatory": False},
    )
    invoice, created = StudentInvoice.objects.get_or_create(
        school=loan.school,
        idempotency_key=f"library-loan-fine:{loan.pk}",
        defaults={
            "branch": loan.student.branch,
            "student": loan.student,
            "academic_year": loan.student.academic_year,
            "invoice_number": f"LIB-{loan.pk.hex[:24]}",
            "issue_date": timezone.localdate(),
            "due_date": timezone.localdate(),
            "total_amount": amount,
            "notes": f"غرامة مكتبة: {reason}",
        },
    )
    if invoice.student_id != loan.student_id or invoice.total_amount != amount:
        raise ValidationError("فاتورة غرامة الإعارة السابقة لا تطابق قيمة الغرامة الحالية.")
    if created:
        StudentInvoiceItem.objects.create(
            school=loan.school,
            branch=invoice.branch,
            invoice=invoice,
            fee_category=category,
            description=f"غرامة مكتبة - {loan.book.title} - {reason}",
            amount=amount,
        )
        invoice.post_to_journal()
    elif not invoice.items.exists():
        raise ValidationError("فاتورة غرامة المكتبة السابقة لا تحتوي بنوداً.")
    loan.fine_invoice = invoice
    loan._allow_library_service_update = True
    loan.save(update_fields=["fine_invoice", "updated_at"])
    return invoice


@transaction.atomic
def renew_book_loan(*, school, loan_id, actor=None):
    from apps.school_services.models import BookLoan

    loan = BookLoan.objects.select_for_update(of=("self",)).select_related("book", "student", "teacher").get(
        pk=loan_id, school=school, is_archived=False
    )
    if loan.status != BookLoan.Status.BORROWED:
        raise ValidationError("لا يمكن تجديد إعارة ليست في حالة معار حالياً.")
    today = timezone.localdate()
    if loan.due_date < today:
        raise ValidationError("لا يمكن تجديد إعارة متأخرة؛ سجل إرجاع الكتاب أولاً.")
    policy = _library_policy(school)
    if loan.renewal_count >= policy.library_max_renewals:
        raise ValidationError("وصلت الإعارة إلى الحد الأقصى لمرات التجديد.")
    previous_due_date = loan.due_date
    loan.due_date = max(today, loan.due_date) + timedelta(days=policy.library_default_loan_days)
    loan.renewal_count += 1
    loan._allow_library_service_update = True
    loan.save(update_fields=["due_date", "renewal_count", "updated_at"])
    record_event(
        action="school_library.loan.renewed",
        description=f"تجديد إعارة الكتاب {loan.book.title}",
        actor=actor, school=school, obj=loan,
        metadata={"previous_due_date": previous_due_date.isoformat(), "new_due_date": loan.due_date.isoformat()},
    )
    return loan


@transaction.atomic
def return_book_loan(*, school, loan_id, actor=None):
    from apps.school_services.models import BookLoan

    loan = BookLoan.objects.select_for_update().select_related("book", "student", "teacher").get(
        pk=loan_id, school=school, is_archived=False
    )
    if loan.status == BookLoan.Status.RETURNED:
        return loan
    if loan.status not in {BookLoan.Status.BORROWED, BookLoan.Status.OVERDUE}:
        raise ValidationError("لا يمكن إرجاع هذا السجل بحالته الحالية.")
    policy = _library_policy(school)
    today = timezone.localdate()
    overdue_days = max(0, (today - loan.due_date).days)
    fine = Decimal(overdue_days) * policy.library_overdue_fine_per_day
    if policy.library_max_overdue_fine > Decimal("0.00"):
        fine = min(fine, policy.library_max_overdue_fine)
    loan.status = BookLoan.Status.RETURNED
    loan.return_date = today
    loan.fine_amount = fine
    loan._allow_library_service_update = True
    loan.save(update_fields=["status", "return_date", "fine_amount", "updated_at"])
    _create_library_fine_invoice(
        loan=loan, amount=fine, reason=f"تأخير {overdue_days} يوم"
    )
    record_event(
        action="school_library.loan.returned",
        description=f"إرجاع كتاب {loan.book.title}",
        actor=actor, school=school, obj=loan,
        metadata={"overdue_days": overdue_days, "fine_amount": str(fine)},
    )
    return loan


@transaction.atomic
def mark_book_loan_lost(*, school, loan_id, actor=None):
    from apps.school_services.models import BookLoan

    loan = BookLoan.objects.select_for_update().select_related("book", "student", "teacher").get(
        pk=loan_id, school=school, is_archived=False
    )
    if loan.status == BookLoan.Status.LOST:
        return loan
    if loan.status not in {BookLoan.Status.BORROWED, BookLoan.Status.OVERDUE}:
        raise ValidationError("لا يمكن تسجيل هذا السجل كمفقود بحالته الحالية.")
    policy = _library_policy(school)
    fine = policy.library_lost_book_fine
    loan.status = BookLoan.Status.LOST
    loan.fine_amount = fine
    loan._allow_library_service_update = True
    loan.save(update_fields=["status", "fine_amount", "updated_at"])
    _create_library_fine_invoice(loan=loan, amount=fine, reason="كتاب مفقود")
    record_event(
        action="school_library.loan.marked_lost",
        description=f"تسجيل كتاب مفقود: {loan.book.title}",
        actor=actor, school=school, obj=loan,
        metadata={"fine_amount": str(fine)},
    )
    return loan


@transaction.atomic
def fulfill_book_requisition(*, school, order_id, allocations, idempotency_key: str, actor=None):
    """Fulfil a requisition exactly once per request key and canonical payload."""
    from apps.inventory.models import InventoryItem, StockMovement
    from apps.inventory.services import record_stock_movement
    from apps.school_services.models import (
        BookRequisitionFulfillment,
        BookRequisitionOrder,
    )

    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 80:
        raise ValidationError("أرسل مفتاح Idempotency-Key بطول 8 إلى 80 حرفاً.")
    if not isinstance(allocations, list) or not allocations:
        raise ValidationError({"items": "أرسل قائمة بنود صرف غير فارغة."})

    order = BookRequisitionOrder.objects.select_for_update().get(
        pk=order_id, school=school, is_archived=False
    )
    normalized = []
    used_item_ids = set()
    for allocation in allocations:
        if not isinstance(allocation, dict):
            raise ValidationError("كل بند صرف يجب أن يكون كائناً منظماً.")
        requisition_item_id = str(allocation.get("requisition_item_id", "")).strip()
        inventory_item_id = str(allocation.get("inventory_item_id", "")).strip()
        if not requisition_item_id or not inventory_item_id:
            raise ValidationError("حدد بند أمر الصرف والصنف المخزني لكل عملية صرف.")
        if requisition_item_id in used_item_ids:
            raise ValidationError("لا تكرر بنداً في طلب الصرف.")
        used_item_ids.add(requisition_item_id)
        try:
            quantity = Decimal(str(allocation.get("quantity", "0")))
        except Exception as exc:
            raise ValidationError("كمية الصرف غير صالحة.") from exc
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise ValidationError("كمية الصرف يجب أن تكون عدداً صحيحاً موجباً.")
        normalized.append({
            "requisition_item_id": requisition_item_id,
            "inventory_item_id": inventory_item_id,
            "quantity": str(quantity.quantize(Decimal("1"))),
        })

    normalized.sort(key=lambda row: (row["requisition_item_id"], row["inventory_item_id"]))
    payload_hash = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    previous_batch = BookRequisitionFulfillment.objects.filter(
        school=school, idempotency_key=key, is_archived=False
    ).first()
    if previous_batch:
        if previous_batch.requisition_id != order.pk or previous_batch.payload_hash != payload_hash:
            raise ValidationError("مفتاح Idempotency-Key مستخدم من قبل لطلب صرف أو بيانات مختلفة.")
        return order

    if order.status != BookRequisitionOrder.Status.APPROVED:
        raise ValidationError("لا يصرف إلا أمر الصرف المعتمد الذي لم يكتمل صرفه.")

    requisition_items = {
        str(item.pk): item
        for item in order.items.select_for_update().all()
    }
    prepared = []
    for allocation in normalized:
        req_item = requisition_items.get(allocation["requisition_item_id"])
        if req_item is None:
            raise ValidationError("أحد البنود لا يتبع أمر الصرف الحالي.")
        quantity = Decimal(allocation["quantity"])
        remaining = req_item.quantity_approved - req_item.quantity_dispatched
        if quantity > remaining:
            raise ValidationError("كمية الصرف تتجاوز الكمية المعتمدة المتبقية.")
        inventory_item = InventoryItem.objects.select_for_update().filter(
            pk=allocation["inventory_item_id"], school=school, is_archived=False,
        ).first()
        if inventory_item is None:
            raise ValidationError("الصنف المخزني غير موجود في المدرسة النشطة.")
        prepared.append((req_item, inventory_item, quantity))

    batch = BookRequisitionFulfillment.objects.create(
        school=school,
        branch=order.branch,
        requisition=order,
        idempotency_key=key,
        payload_hash=payload_hash,
        line_count=len(prepared),
        created_by=actor,
    )
    record_event(
        action="school_book_requisition.fulfillment_created",
        description=f"تنفيذ دفعة صرف لأمر الكتب {order.order_number}",
        actor=actor,
        school=school,
        obj=batch,
        metadata={
            "order_number": order.order_number,
            "line_count": len(prepared),
            "idempotency_key": key,
        },
    )
    for req_item, inventory_item, quantity in prepared:
        movement_key = f"bookreq:{batch.pk.hex[:12]}:{req_item.pk.hex[:12]}"
        _, created = record_stock_movement(
            school=school,
            item=inventory_item,
            warehouse=inventory_item.warehouse,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=quantity,
            unit_cost=inventory_item.unit_cost,
            idempotency_key=movement_key,
            notes=f"{req_item.book_title} - صرف لصالح الطلب {order.order_number}",
            reference=order.order_number,
            recipient_name=f"أمر صرف الكتب {order.order_number}",
            created_by=actor,
        )
        if created:
            req_item.quantity_dispatched += int(quantity)
            req_item._allow_requisition_fulfilment_update = True
            req_item.save(update_fields=["quantity_dispatched", "updated_at"])

    if all(
        item.quantity_dispatched >= item.quantity_approved
        for item in requisition_items.values()
    ):
        order.status = BookRequisitionOrder.Status.FULFILLED
        order.fulfilled_by = actor
        order.fulfilled_at = timezone.now()
        order._allow_requisition_workflow_update = True
        order.save(update_fields=["status", "fulfilled_by", "fulfilled_at", "updated_at"])
    order.refresh_from_db()
    return order
