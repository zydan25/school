"""Fiscal period closing, fiscal year closing, and opening balance services."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import (
    Account,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
)


ZERO = Decimal("0.00")


def _entry_totals(entry: JournalEntry) -> tuple[Decimal, Decimal]:
    totals = entry.lines.filter(is_archived=False).aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )
    return totals["debit"] or ZERO, totals["credit"] or ZERO


def _validate_period_entries(period: FiscalPeriod) -> None:
    entries = JournalEntry.objects.filter(
        school=period.school,
        fiscal_period=period,
        is_archived=False,
    )
    if entries.filter(status=JournalEntry.Status.DRAFT).exists():
        raise ValidationError("لا يمكن إقفال الفترة قبل ترحيل أو حذف جميع القيود المسودة.")
    for entry in entries.filter(status=JournalEntry.Status.POSTED).iterator():
        debit, credit = _entry_totals(entry)
        if debit <= ZERO or debit != credit:
            raise ValidationError(
                f"القيد {entry.entry_number} غير متوازن؛ لا يمكن إقفال الفترة."
            )


@transaction.atomic
def close_fiscal_period(period: FiscalPeriod, user) -> FiscalPeriod:
    """إقفال فترة بعد فحص جميع القيود، مع جعل العملية آمنة عند تكرار الطلب."""
    locked = FiscalPeriod.objects.select_for_update().select_related(
        "fiscal_year", "school",
    ).get(pk=period.pk)
    if locked.is_closed:
        return locked
    if locked.fiscal_year.is_closed:
        raise ValidationError("السنة المالية مقفلة بالفعل.")
    _validate_period_entries(locked)

    locked.is_closed = True
    locked.closed_at = timezone.now()
    locked.closed_by = user
    locked.save(update_fields=["is_closed", "closed_at", "closed_by", "updated_at"])
    return locked


def _assert_year_period_coverage(year: FiscalYear) -> list[FiscalPeriod]:
    periods = list(
        FiscalPeriod.objects.filter(
            school=year.school,
            fiscal_year=year,
            is_archived=False,
        ).order_by("start_date", "period_number")
    )
    if not periods:
        raise ValidationError("لا يمكن إقفال سنة مالية بلا فترات محاسبية.")
    expected_start = year.start_date
    for period in periods:
        if period.start_date != expected_start:
            raise ValidationError(
                f"يوجد انقطاع في التغطية المحاسبية قبل الفترة {period.name}."
            )
        expected_start = period.end_date + timedelta(days=1)
    if expected_start != year.end_date + timedelta(days=1):
        raise ValidationError("الفترات المحاسبية لا تغطي السنة المالية كاملة حتى تاريخ انتهائها.")
    if any(not period.is_closed for period in periods):
        raise ValidationError("يجب إقفال جميع الفترات المحاسبية قبل إقفال السنة.")
    return periods


def _year_profit_and_loss_lines(year: FiscalYear) -> list[dict]:
    rows = JournalEntryLine.objects.filter(
        school=year.school,
        journal_entry__school=year.school,
        journal_entry__fiscal_period__fiscal_year=year,
        journal_entry__status=JournalEntry.Status.POSTED,
        journal_entry__date__range=(year.start_date, year.end_date),
        is_archived=False,
        account__is_leaf=True,
        account__is_archived=False,
        account__account_type__in=[
            Account.AccountType.REVENUE,
            Account.AccountType.EXPENSE,
        ],
    ).values(
        "account_id", "branch_id", "account__account_type",
    ).annotate(
        debit_total=Sum("debit"),
        credit_total=Sum("credit"),
    ).order_by("account_id")

    lines = []
    net_income_by_branch: dict[object, Decimal] = {}
    for row in rows:
        debit = row["debit_total"] or ZERO
        credit = row["credit_total"] or ZERO
        account_type = row["account__account_type"]
        branch_id = row["branch_id"]
        if account_type == Account.AccountType.REVENUE:
            balance = credit - debit
            net_income_by_branch[branch_id] = (
                net_income_by_branch.get(branch_id, ZERO) + balance
            )
            if balance > ZERO:
                lines.append({
                    "account_id": row["account_id"],
                    "branch_id": branch_id,
                    "debit": balance,
                    "credit": ZERO,
                    "description": "إقفال رصيد الإيراد في نهاية السنة المالية",
                })
            elif balance < ZERO:
                lines.append({
                    "account_id": row["account_id"],
                    "branch_id": branch_id,
                    "debit": ZERO,
                    "credit": abs(balance),
                    "description": "إقفال الرصيد المدين لحساب الإيراد",
                })
        else:
            balance = debit - credit
            net_income_by_branch[branch_id] = (
                net_income_by_branch.get(branch_id, ZERO) - balance
            )
            if balance > ZERO:
                lines.append({
                    "account_id": row["account_id"],
                    "branch_id": branch_id,
                    "debit": ZERO,
                    "credit": balance,
                    "description": "إقفال رصيد المصروف في نهاية السنة المالية",
                })
            elif balance < ZERO:
                lines.append({
                    "account_id": row["account_id"],
                    "branch_id": branch_id,
                    "debit": abs(balance),
                    "credit": ZERO,
                    "description": "إقفال الرصيد الدائن لحساب المصروف",
                })

    non_zero_branches = {
        branch_id: balance
        for branch_id, balance in net_income_by_branch.items()
        if balance != ZERO
    }
    if non_zero_branches:
        retained = Account.objects.filter(
            school=year.school,
            code="3102",
            is_leaf=True,
            is_archived=False,
        ).first()
        if not retained:
            raise ValidationError("حساب الأرباح والخسائر المرحلة 3102 غير موجود في دليل الحسابات.")
        for branch_id, net_income in non_zero_branches.items():
            if retained.branch_id and retained.branch_id != branch_id:
                raise ValidationError(
                    "حساب الأرباح المرحلة 3102 مربوط بفرع مختلف عن فرع نتائج السنة؛ راجع دليل الحسابات."
                )
            lines.append({
                "account_id": retained.pk,
                "branch_id": branch_id if retained.branch_id is None else retained.branch_id,
                "debit": abs(net_income) if net_income < ZERO else ZERO,
                "credit": net_income if net_income > ZERO else ZERO,
                "description": (
                    "ترحيل صافي ربح السنة إلى الأرباح المرحلة"
                    if net_income > ZERO else "ترحيل صافي خسارة السنة إلى الأرباح المرحلة"
                ),
            })
    return lines


@transaction.atomic
def close_fiscal_year(year: FiscalYear, user) -> FiscalYear:
    """إقفال السنة بعد إقفال فتراتها وتصفير حسابات الدخل والمصروف إلى الأرباح المرحلة."""
    locked = FiscalYear.objects.select_for_update().select_related("school").get(pk=year.pk)
    if locked.is_closed:
        return locked

    periods = _assert_year_period_coverage(locked)
    for period in periods:
        _validate_period_entries(period)

    unassigned = JournalEntry.objects.filter(
        school=locked.school,
        date__range=(locked.start_date, locked.end_date),
        status=JournalEntry.Status.POSTED,
        fiscal_period__isnull=True,
        is_archived=False,
    ).exists()
    if unassigned:
        raise ValidationError("توجد قيود مرحلة داخل السنة دون ربط بفترة مالية؛ يجب تسويتها قبل الإقفال.")

    last_period = periods[-1]
    source_reference = str(locked.pk)
    existing = JournalEntry.objects.filter(
        school=locked.school,
        source_module="fiscal_year_close",
        source_reference=source_reference,
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد إقفال سابق غير مرحل؛ يجب مراجعته قبل المتابعة.")
        closing_entry = existing
    else:
        closing_lines = _year_profit_and_loss_lines(locked)
        if closing_lines:
            closing_entry = JournalEntry.objects.create(
                school=locked.school,
                fiscal_period=last_period,
                entry_number=f"YE-CLOSE-{locked.start_date.year}-{locked.pk.hex[:8].upper()}",
                date=locked.end_date,
                description=f"قيد إقفال حسابات الإيرادات والمصروفات للسنة {locked.name}",
                status=JournalEntry.Status.DRAFT,
                source_module="fiscal_year_close",
                source_reference=source_reference,
            )
            for item in closing_lines:
                JournalEntryLine.objects.create(
                    school=locked.school,
                    branch_id=item["branch_id"],
                    journal_entry=closing_entry,
                    account_id=item["account_id"],
                    debit=item["debit"],
                    credit=item["credit"],
                    description=item["description"],
                )
            closing_entry.post(user=user)
        else:
            closing_entry = None

    locked.closing_entry = closing_entry
    locked.is_closed = True
    locked.closed_at = timezone.now()
    locked.closed_by = user
    locked.save(update_fields=[
        "closing_entry", "is_closed", "closed_at", "closed_by", "updated_at",
    ])
    return locked


@transaction.atomic
def open_fiscal_year(
    year: FiscalYear,
    previous_year: FiscalYear,
    user=None,
) -> JournalEntry | None:
    """ترحيل أرصدة الأصول والالتزامات وحقوق الملكية إلى أول فترة في السنة الجديدة."""
    locked_year = FiscalYear.objects.select_for_update().select_related("school").get(pk=year.pk)
    previous = FiscalYear.objects.select_for_update().get(pk=previous_year.pk)
    if locked_year.school_id != previous.school_id:
        raise ValidationError("السنتان الماليتان يجب أن تتبعا المدرسة نفسها.")
    if previous.end_date + timezone.timedelta(days=1) != locked_year.start_date:
        raise ValidationError("يجب أن تبدأ السنة الجديدة في اليوم التالي مباشرة لنهاية السنة السابقة.")
    if not previous.is_closed:
        raise ValidationError("يجب إقفال السنة السابقة قبل ترحيل الأرصدة الافتتاحية.")
    if locked_year.is_closed:
        raise ValidationError("لا يمكن فتح سنة مالية مقفلة.")
    if locked_year.opening_entry_id:
        return locked_year.opening_entry

    first_period = FiscalPeriod.objects.select_for_update().filter(
        school=locked_year.school,
        fiscal_year=locked_year,
        is_archived=False,
        start_date__lte=locked_year.start_date,
        end_date__gte=locked_year.start_date,
        is_closed=False,
    ).first()
    if not first_period:
        raise ValidationError("يجب إنشاء أول فترة مالية مفتوحة تغطي تاريخ بداية السنة الجديدة.")

    existing = JournalEntry.objects.filter(
        school=locked_year.school,
        source_module="fiscal_year_opening",
        source_reference=str(locked_year.pk),
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد افتتاح سابق غير مرحل؛ يجب مراجعته قبل المتابعة.")
        locked_year.opening_entry = existing
        locked_year.save(update_fields=["opening_entry", "updated_at"])
        return existing

    trial = JournalEntryLine.objects.filter(
        school=previous.school,
        journal_entry__school=previous.school,
        journal_entry__status=JournalEntry.Status.POSTED,
        journal_entry__date__lte=previous.end_date,
        is_archived=False,
    ).values("account_id", "branch_id", "account__account_type").annotate(
        debit_total=Sum("debit"),
        credit_total=Sum("credit"),
    ).order_by("account_id")
    opening_lines = []
    total_debit = ZERO
    total_credit = ZERO
    for row in trial:
        account_type = row["account__account_type"]
        if account_type not in (
            Account.AccountType.ASSET,
            Account.AccountType.LIABILITY,
            Account.AccountType.EQUITY,
        ):
            continue
        debit_balance = (row["debit_total"] or ZERO) - (row["credit_total"] or ZERO)
        if debit_balance == ZERO:
            continue
        if account_type == Account.AccountType.ASSET:
            debit, credit = (debit_balance, ZERO) if debit_balance > ZERO else (ZERO, abs(debit_balance))
        else:
            credit_balance = -debit_balance
            debit, credit = (ZERO, credit_balance) if credit_balance > ZERO else (abs(credit_balance), ZERO)
        opening_lines.append((row["account_id"], row["branch_id"], debit, credit))
        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise ValidationError(
            f"الأرصدة الافتتاحية غير متوازنة ({total_debit} مدين مقابل {total_credit} دائن)."
        )
    if not opening_lines:
        return None

    entry = JournalEntry.objects.create(
        school=locked_year.school,
        fiscal_period=first_period,
        entry_number=f"YE-OPEN-{locked_year.start_date.year}-{locked_year.pk.hex[:8].upper()}",
        date=locked_year.start_date,
        description=f"الأرصدة الافتتاحية للسنة المالية {locked_year.name}",
        status=JournalEntry.Status.DRAFT,
        source_module="fiscal_year_opening",
        source_reference=str(locked_year.pk),
    )
    for account_id, branch_id, debit, credit in opening_lines:
        JournalEntryLine.objects.create(
            school=locked_year.school,
            branch_id=branch_id,
            journal_entry=entry,
            account_id=account_id,
            debit=debit,
            credit=credit,
            description="ترحيل رصيد افتتاحي من السنة المالية السابقة",
        )
    entry.post(user=user)
    locked_year.opening_entry = entry
    locked_year.save(update_fields=["opening_entry", "updated_at"])
    return entry
