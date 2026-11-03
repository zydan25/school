"""Transactional fixed-asset lifecycle services."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Account, FiscalYear, JournalEntry, JournalEntryLine
from apps.accounting.services.auto_posting import (
    _get_account_or_seed,
    _get_active_fiscal_period,
    post_asset_depreciation_to_journal,
)
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationEntry,
    AssetDisposal,
    AssetMovement,
    FixedAsset,
)
from apps.inventory.models import VendorInvoice


CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _ensure_account(*, account, school, account_type, label: str):
    if (
        account is None
        or account.school_id != school.pk
        or account.account_type != account_type
        or not account.is_leaf
        or account.is_archived
    ):
        raise ValidationError(f"{label} غير صالح أو لا يتبع المدرسة نفسها.")
    return account


@transaction.atomic
def register_asset_from_vendor_invoice(
    *,
    invoice: VendorInvoice,
    category: AssetCategory,
    code: str,
    name: str,
    purchase_date: date,
    salvage_value: Decimal = Decimal("0.00"),
    location_room: str = "",
    custodian=None,
    registered_by=None,
) -> FixedAsset:
    """Capitalize one identifiable asset from a posted fixed-asset supplier invoice."""
    locked_invoice = VendorInvoice.objects.select_for_update().get(pk=invoice.pk)
    if locked_invoice.accounting_treatment != VendorInvoice.AccountingTreatment.FIXED_ASSET:
        raise ValidationError("فاتورة المورد غير مصنفة كاقتناء أصل ثابت.")
    if locked_invoice.status not in {VendorInvoice.Status.APPROVED, VendorInvoice.Status.PARTIAL, VendorInvoice.Status.PAID}:
        raise ValidationError("يجب اعتماد فاتورة المورد وترحيلها قبل تسجيل الأصل.")
    if not locked_invoice.journal_entry_id or locked_invoice.journal_entry.status != JournalEntry.Status.POSTED:
        raise ValidationError("فاتورة المورد لا تملك قيد اقتناء مرحّلاً.")
    if category.school_id != locked_invoice.school_id or category.is_archived:
        raise ValidationError("تصنيف الأصل غير نشط أو لا يتبع مدرسة الفاتورة.")
    if custodian and (custodian.school_id != locked_invoice.school_id or custodian.is_archived):
        raise ValidationError("مسؤول العهدة لا يتبع المدرسة نفسها أو ملفه مؤرشف.")
    if not code.strip() or not name.strip():
        raise ValidationError("رمز الأصل واسمه مطلوبان.")
    if purchase_date < locked_invoice.invoice_date:
        raise ValidationError("تاريخ اقتناء الأصل لا يمكن أن يسبق تاريخ فاتورة المورد.")

    existing = FixedAsset.objects.filter(
        school=locked_invoice.school, code=code.strip(), is_archived=False,
    ).first()
    if existing:
        if existing.source_vendor_invoice_id == locked_invoice.pk:
            return existing
        raise ValidationError("رمز الأصل مستخدم مسبقاً في المدرسة.")

    current_assets_total = sum(
        FixedAsset.objects.filter(
            school=locked_invoice.school,
            source_vendor_invoice=locked_invoice,
            is_archived=False,
        ).values_list("purchase_cost", flat=True),
        Decimal("0.00"),
    )
    if current_assets_total + locked_invoice.total_amount > locked_invoice.total_amount and current_assets_total > 0:
        raise ValidationError("لا يمكن تجاوز قيمة فاتورة المورد عند رسملة عدة أصول منها.")

    asset_account = category.asset_account or locked_invoice.expense_account
    _ensure_account(
        account=asset_account,
        school=locked_invoice.school,
        account_type=Account.AccountType.ASSET,
        label="حساب تكلفة الأصل",
    )
    if locked_invoice.expense_account_id and locked_invoice.expense_account_id != asset_account.pk:
        raise ValidationError("حساب الأصل في التصنيف لا يطابق الحساب المستخدم في قيد فاتورة المورد.")
    amount = _money(locked_invoice.total_amount)
    salvage = _money(Decimal(salvage_value))
    if salvage < 0 or salvage > amount:
        raise ValidationError("القيمة التخريدية يجب أن تكون بين صفر وتكلفة الاقتناء.")

    return FixedAsset.objects.create(
        school=locked_invoice.school,
        branch=locked_invoice.branch,
        category=category,
        code=code.strip(),
        name=name.strip(),
        purchase_date=purchase_date,
        purchase_cost=amount,
        salvage_value=salvage,
        location_room=location_room.strip(),
        custodian=custodian,
        source_vendor_invoice=locked_invoice,
        acquisition_journal_entry=locked_invoice.journal_entry,
    )


@transaction.atomic
def move_asset(
    *,
    asset: FixedAsset,
    idempotency_key: str,
    reason: str,
    movement_date: date | None = None,
    to_branch=None,
    to_location: str | None = None,
    to_custodian=None,
    movement_type: str | None = None,
    recorded_by=None,
) -> AssetMovement:
    """Transfer a tagged asset or custody assignment while preserving history."""
    locked = FixedAsset.objects.select_for_update().get(pk=asset.pk)
    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع تكرار حركة الأصل يجب أن يكون بين 8 و100 حرف.")
    if not reason.strip():
        raise ValidationError("سبب نقل الأصل أو تغيير العهدة مطلوب.")
    if locked.status == FixedAsset.Status.DISPOSED:
        raise ValidationError("لا يمكن نقل أصل مستبعد.")
    existing = AssetMovement.objects.filter(
        school=locked.school, idempotency_key=key, is_archived=False,
    ).first()
    if existing:
        if existing.asset_id != locked.pk:
            raise ValidationError("مفتاح منع التكرار مرتبط بأصل آخر.")
        return existing

    new_branch = locked.branch if to_branch is None else to_branch
    new_location = locked.location_room if to_location is None else to_location.strip()
    new_custodian = locked.custodian if to_custodian is None else to_custodian
    for label, value in (("الفرع", new_branch), ("أمين العهدة", new_custodian)):
        if value and value.school_id != locked.school_id:
            raise ValidationError(f"{label} لا يتبع المدرسة نفسها.")
    if new_branch and locked.branch_id != getattr(new_branch, "pk", None):
        resolved_type = movement_type or AssetMovement.MovementType.TRANSFER
    else:
        resolved_type = movement_type or AssetMovement.MovementType.CUSTODY

    movement = AssetMovement.objects.create(
        school=locked.school,
        branch=new_branch,
        asset=locked,
        movement_type=resolved_type,
        from_branch=locked.branch,
        to_branch=new_branch,
        from_location=locked.location_room,
        to_location=new_location,
        from_custodian=locked.custodian,
        to_custodian=new_custodian,
        movement_date=movement_date or timezone.localdate(),
        idempotency_key=key,
        reason=reason.strip(),
        recorded_by=recorded_by,
    )
    from django.db import models
    models.QuerySet.update(
        FixedAsset.objects.filter(pk=locked.pk),
        branch=new_branch,
        location_room=new_location,
        custodian=new_custodian,
        updated_at=timezone.now(),
    )
    return movement


@transaction.atomic
def generate_asset_depreciation(
    *,
    asset: FixedAsset,
    fiscal_year: FiscalYear,
    posted_by=None,
    post: bool = True,
) -> AssetDepreciationEntry:
    """Generate straight-line, time-prorated depreciation for one financial year."""
    locked = FixedAsset.objects.select_for_update().get(pk=asset.pk)
    year = FiscalYear.objects.select_for_update().get(pk=fiscal_year.pk)
    if year.school_id != locked.school_id:
        raise ValidationError("السنة المالية لا تتبع مدرسة الأصل.")
    if year.is_closed or year.is_archived:
        raise ValidationError("لا يمكن إنشاء إهلاك على سنة مالية مقفلة أو مؤرشفة.")
    if locked.status == FixedAsset.Status.DISPOSED:
        raise ValidationError("لا يمكن إهلاك أصل مستبعد.")
    existing = AssetDepreciationEntry.objects.filter(
        school=locked.school,
        asset=locked,
        fiscal_year=year,
        is_archived=False,
    ).first()
    if existing:
        if post and not existing.journal_entry_id:
            post_asset_depreciation_to_journal(existing, user=posted_by)
            existing.refresh_from_db()
        return existing

    first_day = max(locked.purchase_date, year.start_date)
    last_day = year.end_date
    if first_day > last_day:
        raise ValidationError("تاريخ اقتناء الأصل يقع بعد نهاية السنة المالية.")
    total_days = (year.end_date - year.start_date).days + 1
    eligible_days = (last_day - first_day).days + 1
    depreciable_base = max(Decimal("0.00"), locked.purchase_cost - locked.salvage_value)
    if depreciable_base <= locked.accumulated_depreciation:
        raise ValidationError("الأصل استنفد كامل قيمته القابلة للإهلاك.")
    category = locked.category
    annual_rate = category.annual_depreciation_rate
    annual_amount = (
        locked.purchase_cost * annual_rate / Decimal("100.00")
        if annual_rate > 0
        else depreciable_base / Decimal(category.useful_life_years)
    )
    amount = _money(annual_amount * Decimal(eligible_days) / Decimal(total_days))
    remaining = _money(depreciable_base - locked.accumulated_depreciation)
    amount = min(amount, remaining)
    if amount <= 0:
        raise ValidationError("نتج قسط إهلاك صفري؛ راجع تاريخ الاقتناء ونسبة الإهلاك.")
    entry = AssetDepreciationEntry.objects.create(
        school=locked.school,
        branch=locked.branch,
        asset=locked,
        fiscal_year=year,
        depreciation_amount=amount,
        date=last_day,
    )
    if post:
        post_asset_depreciation_to_journal(entry, user=posted_by)
        entry.refresh_from_db()
    return entry


@transaction.atomic
def dispose_asset(
    *,
    asset: FixedAsset,
    idempotency_key: str,
    reason: str,
    disposal_date: date | None = None,
    proceeds: Decimal = Decimal("0.00"),
    payment_account: Account | None = None,
    disposed_by=None,
) -> AssetDisposal:
    """Dispose an asset using a balanced, linked journal entry and immutable document."""
    locked = FixedAsset.objects.select_for_update().get(pk=asset.pk)
    key = (idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 100:
        raise ValidationError("مفتاح منع تكرار الاستبعاد يجب أن يكون بين 8 و100 حرف.")
    if not reason.strip():
        raise ValidationError("سبب استبعاد الأصل مطلوب.")
    proceeds = _money(Decimal(proceeds))
    if proceeds < 0:
        raise ValidationError("متحصلات البيع لا يمكن أن تكون سالبة.")
    existing = AssetDisposal.objects.select_related("journal_entry").filter(
        school=locked.school, idempotency_key=key, is_archived=False,
    ).first()
    if existing:
        if existing.asset_id != locked.pk or existing.proceeds != proceeds:
            raise ValidationError("مفتاح منع التكرار مستخدم لاستبعاد أصل أو قيمة مختلفة.")
        return existing
    if locked.status == FixedAsset.Status.DISPOSED:
        raise ValidationError("الأصل مستبعد مسبقاً.")
    if AssetDepreciationEntry.objects.filter(
        asset=locked, is_archived=False, journal_entry__isnull=True,
    ).exists():
        raise ValidationError("يوجد إهلاك غير مرحّل لهذا الأصل؛ رحّله أو ألغِه قبل الاستبعاد.")

    school = locked.school
    category = locked.category
    asset_account = category.asset_account or _get_account_or_seed(
        school, "1201", "الأصول الثابتة",
    )
    accumulated_account = category.accumulated_depreciation_account or _get_account_or_seed(
        school, "1209", "مجمع الإهلاك المتراكم",
    )
    _ensure_account(
        account=asset_account, school=school,
        account_type=Account.AccountType.ASSET, label="حساب تكلفة الأصل",
    )
    _ensure_account(
        account=accumulated_account, school=school,
        account_type=Account.AccountType.ASSET, label="حساب مجمع الإهلاك",
    )
    if proceeds > 0:
        _ensure_account(
            account=payment_account, school=school,
            account_type=Account.AccountType.ASSET, label="حساب تحصيل متحصل الاستبعاد",
        )
    elif payment_account:
        _ensure_account(
            account=payment_account, school=school,
            account_type=Account.AccountType.ASSET, label="حساب التحصيل",
        )

    event_date = disposal_date or timezone.localdate()
    period = _get_active_fiscal_period(school, event_date)
    book_value = _money(locked.purchase_cost - locked.accumulated_depreciation)
    gain = _money(max(Decimal("0.00"), proceeds - book_value))
    loss = _money(max(Decimal("0.00"), book_value - proceeds))
    expense_loss = _get_account_or_seed(school, "5210", "خسائر استبعاد الأصول الثابتة")
    income_gain = _get_account_or_seed(school, "4202", "أرباح استبعاد الأصول الثابتة")
    reference = str(locked.pk)
    entry = JournalEntry.objects.create(
        school=school,
        branch=locked.branch,
        fiscal_period=period,
        entry_number=f"JV-ASSET-DISPOSAL-{locked.code}",
        date=event_date,
        status=JournalEntry.Status.DRAFT,
        source_module="asset_disposal",
        source_reference=reference,
        description=f"استبعاد الأصل [{locked.code}] {locked.name}: {reason.strip()}",
    )
    if proceeds > 0:
        JournalEntryLine.objects.create(
            school=school, branch=locked.branch, journal_entry=entry,
            account=payment_account, description="متحصلات بيع أو استبعاد أصل",
            debit=proceeds, credit=Decimal("0.00"),
        )
    if locked.accumulated_depreciation > 0:
        JournalEntryLine.objects.create(
            school=school, branch=locked.branch, journal_entry=entry,
            account=accumulated_account, description="إقفال مجمع إهلاك الأصل المستبعد",
            debit=locked.accumulated_depreciation, credit=Decimal("0.00"),
        )
    if loss > 0:
        JournalEntryLine.objects.create(
            school=school, branch=locked.branch, journal_entry=entry,
            account=expense_loss, description="خسارة استبعاد الأصل",
            debit=loss, credit=Decimal("0.00"),
        )
    JournalEntryLine.objects.create(
        school=school, branch=locked.branch, journal_entry=entry,
        account=asset_account, description="إقفال تكلفة الأصل المستبعد",
        debit=Decimal("0.00"), credit=locked.purchase_cost,
    )
    if gain > 0:
        JournalEntryLine.objects.create(
            school=school, branch=locked.branch, journal_entry=entry,
            account=income_gain, description="ربح استبعاد الأصل",
            debit=Decimal("0.00"), credit=gain,
        )
    entry.post(user=disposed_by)

    disposal = AssetDisposal.objects.create(
        school=school,
        branch=locked.branch,
        asset=locked,
        disposal_date=event_date,
        proceeds=proceeds,
        payment_account=payment_account,
        journal_entry=entry,
        idempotency_key=key,
        reason=reason.strip(),
        disposed_by=disposed_by,
    )
    from django.db import models
    models.QuerySet.update(
        FixedAsset.objects.filter(pk=locked.pk),
        status=FixedAsset.Status.DISPOSED,
        disposal_journal_entry=entry,
        disposed_at=timezone.now(),
        updated_at=timezone.now(),
    )
    return disposal
