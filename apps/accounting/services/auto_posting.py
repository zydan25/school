"""
apps/accounting/services/auto_posting.py
خدمة الترحيل المحاسبي الآلي المزدوج لكافة التعاملات المالية (Onyx Pro Integration).
تربط كافة السندات، الإيرادات، المصروفات، الرسوم، الرواتب، وإهلاك الأصول
بقيود اليومية المتوازنة والمستقلة لكل مدرسة مع منع الترحيل على الحسابات التجميعية.
"""
from __future__ import annotations

import datetime
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.accounting.models import (
    Account,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
    PaymentVoucher,
    ReceiptVoucher,
)
from apps.assets.models import AssetDepreciationEntry, FixedAsset
from apps.student_fees.models import PaymentReceipt


def _get_account_or_seed(school, code: str, name: str = "") -> Account:
    """استرجاع الحساب المالي من الدليل مع تهيئة الدليل الافتراضي تلقائياً إن لم تكن حسابات المدرسة مهيأة."""
    acc = Account.objects.filter(school=school, code=code, is_leaf=True).first()
    if not acc:
        from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
        seed_default_chart_of_accounts(school)
        acc = Account.objects.filter(school=school, code=code, is_leaf=True).first()
    if not acc:
        raise ValidationError(f"الحساب المالي المطلوب ({code} - {name}) غير مهيأ في دليل الحسابات للمدرسة.")
    return acc


def _get_active_fiscal_period(school, target_date=None) -> FiscalPeriod:
    """إرجاع الفترة الوحيدة المطابقة للتاريخ، مع رفض أي فترة/سنة مغلقة."""
    if target_date is None:
        target_date = timezone.localdate()
    elif isinstance(target_date, datetime.datetime):
        target_date = target_date.date()

    with transaction.atomic():
        years = list(
            FiscalYear.objects.select_for_update().filter(
                school=school,
                is_archived=False,
                start_date__lte=target_date,
                end_date__gte=target_date,
            )
        )
        if len(years) > 1:
            raise ValidationError("يوجد تداخل بين السنوات المالية لهذا التاريخ؛ يجب معالجة التداخل قبل الترحيل.")
        if years and years[0].is_closed:
            raise ValidationError("التاريخ المحدد يقع داخل سنة مالية مقفلة.")
        if not years:
            f_year, _ = FiscalYear.objects.get_or_create(
                school=school,
                start_date=date(target_date.year, 1, 1),
                end_date=date(target_date.year, 12, 31),
                defaults={
                    "name": f"السنة المالية {target_date.year}",
                    "is_closed": False,
                },
            )
            if f_year.is_closed or not (f_year.start_date <= target_date <= f_year.end_date):
                raise ValidationError("لا توجد سنة مالية مفتوحة تغطي تاريخ المعاملة.")
        else:
            f_year = years[0]

        periods = list(
            FiscalPeriod.objects.select_for_update().filter(
                school=school,
                fiscal_year=f_year,
                is_archived=False,
                start_date__lte=target_date,
                end_date__gte=target_date,
            )
        )
        if len(periods) > 1:
            raise ValidationError("يوجد تداخل بين الفترات المالية التي تغطي تاريخ المعاملة.")
        if periods:
            period = periods[0]
            if period.is_closed or period.fiscal_year.is_closed:
                raise ValidationError("لا يمكن تسجيل حركة بتاريخ يقع داخل فترة مالية مقفلة.")
            return period

        import calendar
        last_day_num = calendar.monthrange(target_date.year, target_date.month)[1]
        first_day = max(f_year.start_date, date(target_date.year, target_date.month, 1))
        last_day = min(f_year.end_date, date(target_date.year, target_date.month, last_day_num))
        if first_day > last_day:
            raise ValidationError("لا توجد فترة مالية صالحة للتاريخ المحدد.")

        period, _ = FiscalPeriod.objects.get_or_create(
            school=school,
            fiscal_year=f_year,
            period_number=target_date.month,
            defaults={
                "name": f"فترة {target_date.strftime('%m/%Y')}",
                "start_date": first_day,
                "end_date": last_day,
                "is_closed": False,
            },
        )
        if period.is_closed or not (period.start_date <= target_date <= period.end_date):
            raise ValidationError("الفترة الموجودة لهذا الشهر مغلقة أو لا تغطي تاريخ المعاملة.")
        return period


def post_student_receipt_to_journal(receipt: PaymentReceipt) -> JournalEntry:
    """ترحيل سند قبض الطالب بعد قفل المصدر وإعادة القيد نفسه عند إعادة الطلب."""
    with transaction.atomic():
        locked_receipt = PaymentReceipt.objects.select_for_update(of=("self",)).get(
            pk=receipt.pk,
        )
        if locked_receipt.is_cancelled:
            raise ValidationError("لا يمكن ترحيل سند قبض ملغى أو مسترد.")
        if locked_receipt.journal_entry_id:
            existing = locked_receipt.journal_entry
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("سند القبض مرتبط بقيد غير مرحّل؛ يجب مراجعته.")
            receipt.journal_entry = existing
            return existing

        entry = _post_student_receipt_to_journal_locked(locked_receipt)
        if entry.status != JournalEntry.Status.POSTED:
            raise ValidationError("قيد سند القبض السابق غير مرحّل؛ لا يمكن ربطه بالسند.")
        locked_receipt.journal_entry = entry
        locked_receipt.save(update_fields=["journal_entry", "updated_at"])
        receipt.journal_entry = entry
        return entry


def _post_student_receipt_to_journal_locked(receipt: PaymentReceipt) -> JournalEntry:
    """
    الترحيل الآلي لسند قبض رسوم الطالب إلى قيد يومية محاسبي مزدوج متوازن.
    الجانب المدين: الصندوق (1101) أو البنك (1102) أو الشبكة (1103) حسب طريقة الدفع.
    الجانب الدائن:
    - ذمم ورسوم الطلاب (1104) للمبالغ المخصصة على الفواتير.
    - أرصدة وأمانات الطلاب الدائنة (2102) لمبالغ الفائض المودعة كرصيد دائن.
    """
    if receipt.amount <= Decimal("0.00"):
        raise ValueError("لا يمكن ترحيل سند قبض بمبلغ صفر أو سالب.")

    school = receipt.school
    if getattr(receipt, "journal_entry_id", None):
        return receipt.journal_entry

    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_fees",
        source_reference=receipt.receipt_number,
        is_archived=False,
    ).first()
    if existing:
        if not getattr(receipt, "journal_entry_id", None):
            receipt.journal_entry = existing
            receipt.save(update_fields=["journal_entry", "updated_at"])
        return existing

    tx_date = receipt.paid_at
    if isinstance(tx_date, datetime.datetime):
        tx_date = tx_date.date()
    period = _get_active_fiscal_period(school, tx_date)

    with transaction.atomic():
        if receipt.payment_method == PaymentReceipt.PaymentMethod.BANK_TRANSFER:
            debit_acc = _get_account_or_seed(school, "1102", "البنك")
        elif receipt.payment_method == PaymentReceipt.PaymentMethod.POS:
            debit_acc = _get_account_or_seed(school, "1103", "نقاط البيع - شبكة")
        else:
            debit_acc = _get_account_or_seed(school, "1101", "الصندوق / الخزينة")

        from apps.student_fees.models import PaymentAllocation
        alloc_agg = receipt.allocations.filter(
            status=PaymentAllocation.Status.ACTIVE
        ).aggregate(total=models.Sum("allocated_amount"))
        allocated_amount = alloc_agg["total"] or Decimal("0.00")

        if allocated_amount == Decimal("0.00") and receipt.invoice_id:
            inv = receipt.invoice
            net = max(Decimal("0.00"), inv.total_amount - inv.discount_amount)
            needed = max(Decimal("0.00"), net - inv.paid_amount)
            allocated_amount = min(receipt.amount, needed)

        excess_amount = max(Decimal("0.00"), receipt.amount - allocated_amount)

        acc_receivable = None
        if allocated_amount > Decimal("0.00"):
            acc_receivable = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")

        acc_advance = None
        if excess_amount > Decimal("0.00") or allocated_amount == Decimal("0.00"):
            acc_advance = _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")

        entry_number = f"JV-REC-{receipt.receipt_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch=receipt.branch,
            fiscal_period=period,
            entry_number=entry_number,
            date=receipt.paid_at.date(),
            status=JournalEntry.Status.DRAFT,
            source_module="student_fees",
            source_reference=receipt.receipt_number,
            description=f"تحصيل رسوم دراسية بسند قبض #{receipt.receipt_number} - الطالب: {receipt.student}",
        )

        # 1. Debit: Cash/Bank/POS
        JournalEntryLine.objects.create(
            school=school,
            branch=receipt.branch,
            journal_entry=entry,
            account=debit_acc,
            description=f"إيداع نقدي/بنكي لقاء سند قبض #{receipt.receipt_number}",
            debit=receipt.amount,
            credit=Decimal("0.00"),
        )

        # 2. Credit: Accounts Receivable (1104)
        if allocated_amount > Decimal("0.00") and acc_receivable:
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=acc_receivable,
                description=f"سداد رسوم الطالب: {receipt.student.first_name} {receipt.student.last_name}",
                debit=Decimal("0.00"),
                credit=allocated_amount,
            )

        # 3. Credit: Customer Advance Deposits (2102)
        if excess_amount > Decimal("0.00") and acc_advance:
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=acc_advance,
                description=f"فائض رصيد دائن للطالب: {receipt.student.first_name} {receipt.student.last_name}",
                debit=Decimal("0.00"),
                credit=excess_amount,
            )
        elif allocated_amount == Decimal("0.00") and acc_advance:
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=acc_advance,
                description=f"دفعة مقدمة ورصيد دائن للطالب: {receipt.student.first_name} {receipt.student.last_name}",
                debit=Decimal("0.00"),
                credit=receipt.amount,
            )

        entry.post(user=receipt.received_by)
        return entry


@transaction.atomic
def post_credit_settlement_to_journal(credit_tx) -> JournalEntry | None:
    """ترحيل استخدام رصيد الطالب بعد قفل حركة الرصيد ومنع تكرار القيد."""
    from apps.student_fees.models import StudentCreditTransaction

    locked_tx = StudentCreditTransaction.objects.select_for_update(of=("self",)).get(
        pk=credit_tx.pk,
    )
    if locked_tx.amount <= Decimal("0.00"):
        return None
    school = locked_tx.school
    source_reference = str(locked_tx.pk)
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_fees_credit",
        source_reference=source_reference,
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد تسوية رصيد سابق غير مرحّل؛ يجب مراجعته.")
        return existing
    if locked_tx.is_reversed:
        raise ValidationError("لا يمكن إنشاء قيد تسوية جديد لحركة رصيد معكوسة.")

    tx_date = locked_tx.created_at.date()
    period = _get_active_fiscal_period(school, tx_date)
    acc_liability = _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
    acc_receivable = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")
    entry = JournalEntry.objects.create(
        school=school,
        branch=locked_tx.branch,
        fiscal_period=period,
        entry_number=f"JV-SETTLE-{locked_tx.pk.hex[:8].upper()}",
        date=tx_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_fees_credit",
        source_reference=source_reference,
        description=f"تسوية سداد من الرصيد الدائن للطالب {locked_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school,
        branch=locked_tx.branch,
        journal_entry=entry,
        account=acc_liability,
        debit=locked_tx.amount,
        credit=Decimal("0.00"),
        description=f"تسوية رصيد دائن للطالب {locked_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school,
        branch=locked_tx.branch,
        journal_entry=entry,
        account=acc_receivable,
        debit=Decimal("0.00"),
        credit=locked_tx.amount,
        description=f"إثبات سداد الفاتورة #{locked_tx.invoice.invoice_number if locked_tx.invoice else ''}",
    )
    entry.post(user=locked_tx.created_by)
    return entry

@transaction.atomic
def post_student_credit_refund_to_journal(credit_tx) -> JournalEntry:
    """ترحيل استرداد رصيد الطالب مرة واحدة ضمن معاملة ذرية."""
    from apps.student_fees.models import StudentCreditTransaction

    locked_tx = StudentCreditTransaction.objects.select_for_update(of=("self",)).get(
        pk=credit_tx.pk,
    )
    if locked_tx.transaction_type != StudentCreditTransaction.TransactionType.REFUND:
        raise ValidationError("الحركة المحددة ليست استرداد رصيد دائن.")
    if locked_tx.amount <= Decimal("0.00"):
        raise ValidationError("قيمة استرداد الرصيد يجب أن تكون أكبر من الصفر.")

    school = locked_tx.school
    source_reference = str(locked_tx.pk)
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_fees_credit_refund",
        source_reference=source_reference,
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد استرداد سابق غير مرحّل؛ يجب مراجعته.")
        return existing
    if locked_tx.is_reversed:
        raise ValidationError("لا يمكن ترحيل استرداد سبق عكسه.")

    tx_date = locked_tx.created_at.date()
    period = _get_active_fiscal_period(school, tx_date)
    payment_accounts = {
        PaymentReceipt.PaymentMethod.CASH: ("1101", "الصندوق / الخزينة"),
        PaymentReceipt.PaymentMethod.BANK_TRANSFER: ("1102", "البنك"),
        PaymentReceipt.PaymentMethod.POS: ("1103", "نقاط البيع - شبكة"),
        PaymentReceipt.PaymentMethod.ONLINE: ("1102", "البنك"),
    }
    account_code, account_name = payment_accounts.get(
        locked_tx.refund_payment_method, (None, None),
    )
    if not account_code:
        raise ValidationError("طريقة صرف استرداد الرصيد غير معتمدة.")
    liability = _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
    payment_account = _get_account_or_seed(school, account_code, account_name)
    entry = JournalEntry.objects.create(
        school=school,
        branch=locked_tx.branch,
        fiscal_period=period,
        entry_number=f"JV-REFUND-{locked_tx.pk.hex[:8].upper()}",
        date=tx_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_fees_credit_refund",
        source_reference=source_reference,
        description=f"استرداد رصيد دائن للطالب {locked_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school, branch=locked_tx.branch, journal_entry=entry, account=liability,
        debit=locked_tx.amount, credit=Decimal("0.00"),
        description=f"تخفيض الرصيد الدائن المستحق للطالب {locked_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school, branch=locked_tx.branch, journal_entry=entry, account=payment_account,
        debit=Decimal("0.00"), credit=locked_tx.amount,
        description=f"صرف استرداد رصيد الطالب {locked_tx.student}",
    )
    entry.post(user=locked_tx.created_by)
    return entry

@transaction.atomic
def post_student_invoice_discount_to_journal(discount_request) -> JournalEntry:
    """ترحيل الخصم المعتمد بعد قفل الطلب والفاتورة ومنع تكرار القيد."""
    from apps.student_fees.models import FeeDiscountRequest, StudentInvoice

    locked_request = FeeDiscountRequest.objects.select_for_update(of=("self",)).get(
        pk=discount_request.pk,
    )
    if locked_request.status != FeeDiscountRequest.Status.APPROVED:
        raise ValidationError("لا يمكن ترحيل طلب خصم غير معتمد.")
    if locked_request.amount <= Decimal("0.00"):
        raise ValidationError("قيمة الخصم يجب أن تكون أكبر من الصفر.")

    invoice = StudentInvoice.objects.select_for_update(of=("self",)).get(
        pk=locked_request.invoice_id,
    )
    school = locked_request.school
    source_reference = str(locked_request.pk)
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_invoice_discount",
        source_reference=source_reference,
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد خصم سابق غير مرحّل؛ يجب مراجعته.")
        return existing
    if not invoice.journal_entry_id:
        raise ValidationError("لا يمكن اعتماد خصم محاسبي قبل ترحيل قيد استحقاق الفاتورة.")
    if invoice.journal_entry.status != JournalEntry.Status.POSTED:
        raise ValidationError("قيد استحقاق الفاتورة المرتبط غير مرحّل.")

    tx_date = (
        locked_request.decided_at.date()
        if locked_request.decided_at else timezone.localdate()
    )
    period = _get_active_fiscal_period(school, tx_date)
    old_net_amount = max(
        Decimal("0.00"),
        invoice.total_amount - (invoice.discount_amount - locked_request.amount),
    )
    new_net_amount = max(
        Decimal("0.00"),
        invoice.total_amount - invoice.discount_amount,
    )
    old_overpayment = max(
        Decimal("0.00"), invoice.paid_amount - old_net_amount,
    )
    new_overpayment = max(
        Decimal("0.00"), invoice.paid_amount - new_net_amount,
    )
    credit_delta = max(
        Decimal("0.00"), new_overpayment - old_overpayment,
    )
    revenue = _get_account_or_seed(school, "4101", "إيرادات الرسوم الدراسية")
    receivable = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")
    liability = (
        _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
        if credit_delta > Decimal("0.00") else None
    )
    receivable_credit = locked_request.amount - credit_delta
    if receivable_credit < Decimal("0.00"):
        raise ValidationError("قيمة الخصم غير متسقة مع رصيد الفاتورة والرصيد الدائن؛ راجع التسوية.")

    entry = JournalEntry.objects.create(
        school=school,
        branch=locked_request.branch,
        fiscal_period=period,
        entry_number=f"JV-DISC-{locked_request.pk.hex[:8].upper()}",
        date=tx_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_invoice_discount",
        source_reference=source_reference,
        description=(
            f"اعتماد خصم للفاتورة #{invoice.invoice_number}: "
            f"{locked_request.reason[:150]}"
        ),
    )
    JournalEntryLine.objects.create(
        school=school, branch=locked_request.branch, journal_entry=entry, account=revenue,
        debit=locked_request.amount, credit=Decimal("0.00"),
        description=f"تخفيض إيراد الرسوم للفاتورة #{invoice.invoice_number}",
    )
    if receivable_credit > Decimal("0.00"):
        JournalEntryLine.objects.create(
            school=school, branch=locked_request.branch,
            journal_entry=entry, account=receivable,
            debit=Decimal("0.00"), credit=receivable_credit,
            description=f"تخفيض ذمم الطالب عن الفاتورة #{invoice.invoice_number}",
        )
    if credit_delta > Decimal("0.00"):
        JournalEntryLine.objects.create(
            school=school, branch=locked_request.branch,
            journal_entry=entry, account=liability,
            debit=Decimal("0.00"), credit=credit_delta,
            description=f"تحويل الخصم الزائد إلى رصيد دائن للطالب {invoice.student}",
        )
    entry.post(user=locked_request.approved_by)
    return entry

def post_payment_voucher_to_journal(voucher: PaymentVoucher) -> JournalEntry:
    """ترحيل سند الصرف بقيد مزدوج، بقفل السند وإعادة القيد نفسه عند تكرار الطلب."""
    with transaction.atomic():
        locked = PaymentVoucher.objects.select_for_update(of=("self",)).get(pk=voucher.pk)
        if locked.amount <= Decimal("0.00"):
            raise ValidationError("لا يمكن ترحيل سند صرف مالي بمبلغ صفر أو سالب.")
        if locked.status == PaymentVoucher.Status.CANCELLED:
            raise ValidationError("لا يمكن ترحيل سند صرف ملغى.")

        school = locked.school
        if (
            locked.debit_account.school_id != school.pk
            or locked.credit_account.school_id != school.pk
        ):
            raise ValidationError("حسابات سند الصرف لا تنتمي إلى نفس مدرسة السند.")

        existing = JournalEntry.objects.filter(
            school=school,
            source_module="accounting_payment",
            source_reference=locked.voucher_number,
            is_archived=False,
        ).first()
        if existing:
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد سند صرف سابق غير مرحّل؛ يجب مراجعته قبل المتابعة.")
            locked.journal_entry = existing
            locked.status = PaymentVoucher.Status.POSTED
            locked.save(update_fields=["journal_entry", "status", "updated_at"])
            return existing

        if locked.status == PaymentVoucher.Status.POSTED:
            raise ValidationError("سند الصرف معلّم كمرحل دون وجود قيد محاسبي مرتبط.")

        period = _get_active_fiscal_period(school, locked.date)
        debit_branch = (
            locked.branch_id or locked.debit_account.branch_id
            or (locked.cost_center.branch_id if locked.cost_center_id else None)
        )
        credit_branch = locked.branch_id or locked.credit_account.branch_id
        entry_branch_id = debit_branch if debit_branch == credit_branch else None

        entry = JournalEntry.objects.create(
            school=school,
            branch_id=entry_branch_id,
            fiscal_period=period,
            entry_number=f"JV-PAY-{locked.voucher_number}",
            date=locked.date,
            status=JournalEntry.Status.DRAFT,
            source_module="accounting_payment",
            source_reference=locked.voucher_number,
            description=(
                f"صرف مالي بسند #{locked.voucher_number} إلى: "
                f"{locked.paid_to} - {locked.description}"
            ),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=debit_branch,
            journal_entry=entry,
            account=locked.debit_account,
            cost_center=locked.cost_center,
            description=locked.description or f"صرف إلى {locked.paid_to}",
            debit=locked.amount,
            credit=Decimal("0.00"),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=credit_branch,
            journal_entry=entry,
            account=locked.credit_account,
            description=f"خروج نقدية لصالح {locked.paid_to}",
            debit=Decimal("0.00"),
            credit=locked.amount,
        )
        entry.post(user=getattr(locked, "created_by", None))
        locked.status = PaymentVoucher.Status.POSTED
        locked.journal_entry = entry
        locked.save(update_fields=["status", "journal_entry", "updated_at"])
        return entry

def post_receipt_voucher_to_journal(voucher: ReceiptVoucher) -> JournalEntry:
    """ترحيل سند القبض العام بقفل السند ومنع تكرار الأثر المحاسبي."""
    with transaction.atomic():
        locked = ReceiptVoucher.objects.select_for_update(of=("self",)).get(pk=voucher.pk)
        if locked.amount <= Decimal("0.00"):
            raise ValidationError("لا يمكن ترحيل سند قبض عام بمبلغ صفر أو سالب.")
        if locked.status == ReceiptVoucher.Status.CANCELLED:
            raise ValidationError("لا يمكن ترحيل سند قبض ملغى.")

        school = locked.school
        if (
            locked.debit_account.school_id != school.pk
            or locked.credit_account.school_id != school.pk
        ):
            raise ValidationError("حسابات سند القبض لا تنتمي إلى نفس مدرسة السند.")

        existing = JournalEntry.objects.filter(
            school=school,
            source_module="accounting_receipt",
            source_reference=locked.voucher_number,
            is_archived=False,
        ).first()
        if existing:
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد سند قبض سابق غير مرحّل؛ يجب مراجعته قبل المتابعة.")
            locked.journal_entry = existing
            locked.status = ReceiptVoucher.Status.POSTED
            locked.save(update_fields=["journal_entry", "status", "updated_at"])
            return existing

        if locked.status == ReceiptVoucher.Status.POSTED:
            raise ValidationError("سند القبض معلّم كمرحل دون وجود قيد محاسبي مرتبط.")

        period = _get_active_fiscal_period(school, locked.date)
        debit_branch = locked.branch_id or locked.debit_account.branch_id
        credit_branch = (
            locked.branch_id or locked.credit_account.branch_id
            or (locked.cost_center.branch_id if locked.cost_center_id else None)
        )
        entry_branch_id = debit_branch if debit_branch == credit_branch else None

        entry = JournalEntry.objects.create(
            school=school,
            branch_id=entry_branch_id,
            fiscal_period=period,
            entry_number=f"JV-REC-GEN-{locked.voucher_number}",
            date=locked.date,
            status=JournalEntry.Status.DRAFT,
            source_module="accounting_receipt",
            source_reference=locked.voucher_number,
            description=(
                f"قبض إيراد عام بسند #{locked.voucher_number} من: "
                f"{locked.received_from} - {locked.description}"
            ),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=debit_branch,
            journal_entry=entry,
            account=locked.debit_account,
            description=f"قبض نقدية من {locked.received_from}",
            debit=locked.amount,
            credit=Decimal("0.00"),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=credit_branch,
            journal_entry=entry,
            account=locked.credit_account,
            cost_center=locked.cost_center,
            description=locked.description,
            debit=Decimal("0.00"),
            credit=locked.amount,
        )
        entry.post(user=getattr(locked, "created_by", None))
        locked.status = ReceiptVoucher.Status.POSTED
        locked.journal_entry = entry
        locked.save(update_fields=["status", "journal_entry", "updated_at"])
        return entry

def post_asset_depreciation_to_journal(entry: AssetDepreciationEntry, user=None) -> JournalEntry:
    """ترحيل إهلاك الأصل مرة واحدة مع قفل سجل الإهلاك والأصل لتفادي التكرار."""
    with transaction.atomic():
        locked_entry = AssetDepreciationEntry.objects.select_for_update(of=("self",)).get(
            pk=entry.pk,
        )
        if locked_entry.depreciation_amount <= Decimal("0.00"):
            raise ValidationError("مبلغ إهلاك الأصل يجب أن يكون أكبر من الصفر.")

        locked_asset = FixedAsset.objects.select_for_update(of=("self",)).get(
            pk=locked_entry.asset_id,
        )
        locked_entry.asset = locked_asset
        school = locked_entry.school
        source_reference = f"{locked_asset.code}-{locked_entry.fiscal_year_id}"
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="assets_depreciation",
            source_reference=source_reference,
            is_archived=False,
        ).first()
        if existing:
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد إهلاك سابق غير مرحّل؛ يجب مراجعته قبل المتابعة.")
            if locked_entry.journal_entry_id and locked_entry.journal_entry_id != existing.pk:
                raise ValidationError("سجل الإهلاك مرتبط بقيد مختلف عن قيد مصدره.")
            if not locked_entry.journal_entry_id:
                locked_entry.journal_entry = existing
                locked_entry.posted_at = existing.posted_at or timezone.now()
                locked_entry.posted_by = user
                locked_entry.save(update_fields=[
                    "journal_entry", "posted_at", "posted_by", "updated_at",
                ])
            return existing
        if locked_entry.journal_entry_id:
            linked = locked_entry.journal_entry
            if linked.status != JournalEntry.Status.POSTED:
                raise ValidationError("سجل الإهلاك مرتبط بقيد غير مرحّل؛ يجب مراجعته.")
            return linked

        locked_entry.full_clean()
        if locked_entry.date < locked_entry.fiscal_year.start_date or (
            locked_entry.date > locked_entry.fiscal_year.end_date
        ):
            raise ValidationError("تاريخ الإهلاك يقع خارج حدود السنة المالية المحددة.")
        if locked_entry.depreciation_amount > locked_asset.current_book_value - locked_asset.salvage_value:
            raise ValidationError("مبلغ الإهلاك يتجاوز القيمة القابلة للإهلاك المتبقية للأصل.")
        if locked_asset.status == FixedAsset.Status.DISPOSED:
            raise ValidationError("لا يمكن إهلاك أصل مستبعد.")
        period = _get_active_fiscal_period(school, locked_entry.date)
        if period.fiscal_year_id != locked_entry.fiscal_year_id:
            raise ValidationError("الفترة المحاسبية لا تتبع السنة المالية لسجل الإهلاك.")

        category = locked_asset.category
        depreciation_expense = category.depreciation_expense_account or _get_account_or_seed(
            school, "5209", "مصروف إهلاك الأصول",
        )
        accumulated_depreciation = category.accumulated_depreciation_account or _get_account_or_seed(
            school, "1209", "مجمع إهلاك الأصول المتراكم",
        )
        if (
            depreciation_expense.school_id != school.pk
            or depreciation_expense.account_type != Account.AccountType.EXPENSE
            or not depreciation_expense.is_leaf
            or depreciation_expense.is_archived
        ):
            raise ValidationError("حساب مصروف الإهلاك غير صالح.")
        if (
            accumulated_depreciation.school_id != school.pk
            or accumulated_depreciation.account_type != Account.AccountType.ASSET
            or not accumulated_depreciation.is_leaf
            or accumulated_depreciation.is_archived
        ):
            raise ValidationError("حساب مجمع الإهلاك غير صالح.")
        asset_branch_id = locked_entry.branch_id or locked_asset.branch_id
        journal_entry = JournalEntry.objects.create(
            school=school,
            branch_id=asset_branch_id,
            fiscal_period=period,
            entry_number=(
                f"JV-DEP-{locked_asset.code}-{locked_entry.fiscal_year.name}"
            ),
            date=locked_entry.date,
            status=JournalEntry.Status.DRAFT,
            source_module="assets_depreciation",
            source_reference=source_reference,
            description=(
                f"قيد إهلاك أصل ثابت: {locked_asset.name} "
                f"عن السنة المالية {locked_entry.fiscal_year.name}"
            ),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=asset_branch_id,
            journal_entry=journal_entry,
            account=depreciation_expense,
            description=f"مصروف إهلاك أصل [{locked_asset.code}] {locked_asset.name}",
            debit=locked_entry.depreciation_amount,
            credit=Decimal("0.00"),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch_id=asset_branch_id,
            journal_entry=journal_entry,
            account=accumulated_depreciation,
            description=f"مجمع إهلاك الأصل [{locked_asset.code}]",
            debit=Decimal("0.00"),
            credit=locked_entry.depreciation_amount,
        )

        journal_entry.post(user=user)
        from django.db import models
        models.QuerySet.update(
            FixedAsset.objects.filter(pk=locked_asset.pk),
            accumulated_depreciation=locked_asset.accumulated_depreciation + locked_entry.depreciation_amount,
            updated_at=timezone.now(),
        )
        locked_entry.journal_entry = journal_entry
        locked_entry.posted_at = timezone.now()
        locked_entry.posted_by = user
        locked_entry.save(update_fields=[
            "journal_entry", "posted_at", "posted_by", "updated_at",
        ])
        return journal_entry

@transaction.atomic
def post_student_invoice_to_journal(invoice) -> JournalEntry:
    """ترحيل استحقاق فاتورة الطالب بعد قفلها ومنع إنشاء قيد مكرر."""
    from apps.student_fees.models import StudentInvoice

    locked_invoice = StudentInvoice.objects.select_for_update(of=("self",)).get(
        pk=invoice.pk,
    )
    if locked_invoice.status == StudentInvoice.Status.CANCELLED:
        raise ValidationError("لا يمكن ترحيل فاتورة طالب ملغاة.")
    school = locked_invoice.school
    source_reference = locked_invoice.invoice_number
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_invoice",
        source_reference=source_reference,
        is_archived=False,
    ).first()
    if existing:
        if existing.status != JournalEntry.Status.POSTED:
            raise ValidationError("يوجد قيد فاتورة سابق غير مرحّل؛ يجب مراجعته.")
        if locked_invoice.journal_entry_id and locked_invoice.journal_entry_id != existing.pk:
            raise ValidationError("الفاتورة مرتبطة بقيد مختلف عن قيد مصدرها.")
        if not locked_invoice.journal_entry_id:
            locked_invoice.journal_entry = existing
            locked_invoice.save(update_fields=["journal_entry", "updated_at"])
        invoice.journal_entry = existing
        return existing
    if locked_invoice.journal_entry_id:
        raise ValidationError("الفاتورة مرتبطة بقيد لا يطابق مرجع مصدرها.")

    post_date = locked_invoice.issue_date or locked_invoice.due_date or timezone.localdate()
    period = _get_active_fiscal_period(school, post_date)
    net_amount = max(
        Decimal("0.00"),
        locked_invoice.total_amount - locked_invoice.discount_amount,
    )
    if net_amount <= Decimal("0.00"):
        raise ValidationError(
            f"صافي قيمة الفاتورة ({net_amount}) يجب أن يكون أكبر من الصفر لترحيلها."
        )
    debit_acc = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")
    credit_acc = _get_account_or_seed(school, "4101", "إيرادات الرسوم الدراسية")
    entry = JournalEntry.objects.create(
        school=school,
        branch=locked_invoice.branch,
        fiscal_period=period,
        entry_number=f"JV-INV-{locked_invoice.invoice_number}",
        date=post_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_invoice",
        source_reference=source_reference,
        description=(
            f"إثبات استحقاق فاتورة رسوم #{locked_invoice.invoice_number} "
            f"للطالب {locked_invoice.student}"
        ),
    )
    JournalEntryLine.objects.create(
        school=school,
        branch=locked_invoice.branch,
        journal_entry=entry,
        account=debit_acc,
        description=f"ذمة الطالب: {locked_invoice.student} - فاتورة #{locked_invoice.invoice_number}",
        debit=net_amount,
        credit=Decimal("0.00"),
    )
    JournalEntryLine.objects.create(
        school=school,
        branch=locked_invoice.branch,
        journal_entry=entry,
        account=credit_acc,
        description=f"إيراد رسوم دراسية - فاتورة #{locked_invoice.invoice_number}",
        debit=Decimal("0.00"),
        credit=net_amount,
    )
    entry.post(user=getattr(locked_invoice, "created_by", None))
    locked_invoice.journal_entry = entry
    locked_invoice.save(update_fields=["journal_entry", "updated_at"])
    invoice.journal_entry = entry
    return entry

def validate_and_balance_journal_entry(entry: JournalEntry) -> bool:
    """التحقق الصارم من توازن القيد اليومي (تطابق إجمالي المدين والدائن)."""
    lines = entry.lines.all()
    if not lines.exists():
        raise ValueError("لا يمكن ترحيل قيد محاسبي بدون أسطر.")
    total_debit = sum(line.debit for line in lines)
    total_credit = sum(line.credit for line in lines)
    if total_debit != total_credit:
        raise ValueError(f"القيد المحاسبي غير متوازن! إجمالي المدين ({total_debit}) لا يساوي إجمالي الدائن ({total_credit}).")
    return True


def reverse_journal_entry(original_entry: JournalEntry, reason: str, reversed_by=None) -> JournalEntry:
    """عكس القيد داخل معاملة واحدة؛ إعادة الطلب تعيد القيد العكسي نفسه."""
    if not reason or not reason.strip():
        raise ValidationError("سبب عكس القيد مطلوب.")

    with transaction.atomic():
        original = JournalEntry.objects.select_for_update(of=("self",)).select_related(
            "fiscal_period__fiscal_year",
        ).get(pk=original_entry.pk)
        if original.is_reversed:
            if original.reversed_by_entry_id:
                return original.reversed_by_entry
            raise ValidationError("القيد معلّم كمعكوس دون ربط القيد العكسي.")
        if original.status != JournalEntry.Status.POSTED:
            raise ValidationError("لا يمكن عكس قيد غير مرحل.")

        school = original.school
        period = _get_active_fiscal_period(school, timezone.localdate())
        reversal_num = f"REV-{original.entry_number}"
        existing = JournalEntry.objects.filter(
            school=school,
            entry_number=reversal_num,
            is_archived=False,
        ).first()
        if existing:
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد عكسي سابق غير مرحل؛ يجب مراجعته قبل إعادة المحاولة.")
            original.is_reversed = True
            original.reversed_by_entry = existing
            original.reversal_reason = reason.strip()
            original.save(update_fields=[
                "is_reversed", "reversed_by_entry", "reversal_reason", "updated_at",
            ])
            return existing

        rev_entry = JournalEntry.objects.create(
            school=school,
            branch=original.branch,
            fiscal_period=period,
            entry_number=reversal_num,
            date=timezone.localdate(),
            status=JournalEntry.Status.DRAFT,
            source_module="reversal",
            source_reference=original.entry_number,
            description=f"قيد عكسي للقيد #{original.entry_number} - السبب: {reason.strip()}",
        )

        for line in original.lines.filter(is_archived=False).select_related("account", "cost_center"):
            JournalEntryLine.objects.create(
                school=school,
                branch=line.branch,
                journal_entry=rev_entry,
                account=line.account,
                cost_center=line.cost_center,
                description=f"عكس: {line.description}",
                debit=line.credit,
                credit=line.debit,
            )

        rev_entry.post(user=reversed_by)
        original.is_reversed = True
        original.reversed_by_entry = rev_entry
        original.reversal_reason = reason.strip()
        original.save(update_fields=[
            "is_reversed", "reversed_by_entry", "reversal_reason", "updated_at",
        ])
        return rev_entry


def post_vendor_invoice_to_journal(vendor_invoice, user=None) -> JournalEntry:
    """ترحيل فاتورة المورد مرة واحدة مع قفل المستند المصدر والتحقق من قيده السابق."""
    from apps.inventory.models import VendorInvoice

    with transaction.atomic():
        locked_invoice = VendorInvoice.objects.select_for_update(of=("self",)).get(
            pk=vendor_invoice.pk,
        )
        if locked_invoice.status == VendorInvoice.Status.CANCELLED:
            raise ValidationError("لا يمكن ترحيل فاتورة مورد ملغاة.")
        if locked_invoice.total_amount <= Decimal("0.00"):
            raise ValidationError(
                f"إجمالي فاتورة المورد ({locked_invoice.total_amount}) يجب أن يكون أكبر من الصفر."
            )

        school = locked_invoice.school
        source_reference = str(locked_invoice.invoice_number)
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="vendor_invoice",
            source_reference=source_reference,
            is_archived=False,
        ).first()
        if existing:
            if existing.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد فاتورة مورد سابق غير مرحّل؛ يجب مراجعته قبل المتابعة.")
            if locked_invoice.journal_entry_id and locked_invoice.journal_entry_id != existing.pk:
                raise ValidationError("فاتورة المورد مرتبطة بقيد مختلف عن قيد مصدرها.")
            if not locked_invoice.journal_entry_id:
                locked_invoice.journal_entry = existing
            if locked_invoice.status == VendorInvoice.Status.DRAFT:
                locked_invoice.status = VendorInvoice.Status.APPROVED
            locked_invoice.approved_by = locked_invoice.approved_by or user
            locked_invoice.approved_at = locked_invoice.approved_at or timezone.now()
            locked_invoice.save(update_fields=[
                "journal_entry", "status", "approved_by", "approved_at", "updated_at",
            ])
            return existing

        if locked_invoice.journal_entry_id:
            linked = locked_invoice.journal_entry
            if linked.status != JournalEntry.Status.POSTED:
                raise ValidationError("فاتورة المورد مرتبطة بقيد غير مرحّل؛ يجب مراجعته.")
            raise ValidationError("القيد المرتبط بفاتورة المورد لا يطابق مرجع مصدر الفاتورة.")

        post_date = locked_invoice.invoice_date or timezone.localdate()
        period = _get_active_fiscal_period(school, post_date)
        if locked_invoice.accounting_treatment == VendorInvoice.AccountingTreatment.FIXED_ASSET:
            debit_acc = locked_invoice.expense_account or _get_account_or_seed(
                school, "1201", "الأصول الثابتة",
            )
        elif locked_invoice.accounting_treatment == VendorInvoice.AccountingTreatment.EXPENSE:
            debit_acc = locked_invoice.expense_account
            if debit_acc is None:
                raise ValidationError("فاتورة المصروف تتطلب تحديد حساب مصروف تفصيلي.")
        else:
            debit_acc = _get_account_or_seed(
                school, "1106", "مخزون الكتب والقرطاسية والزي",
            )
        if (
            debit_acc.school_id != school.pk or not debit_acc.is_leaf
            or debit_acc.is_archived
        ):
            raise ValidationError("حساب مدين فاتورة المورد غير صالح أو لا يتبع المدرسة.")
        credit_acc = _get_account_or_seed(
            school, "2101", "ذمم الموردين والشركات الدائنة",
        )
        entry_number = f"JV-VINV-{locked_invoice.invoice_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch=locked_invoice.branch,
            fiscal_period=period,
            entry_number=entry_number,
            date=post_date,
            status=JournalEntry.Status.DRAFT,
            source_module="vendor_invoice",
            source_reference=source_reference,
            description=(
                f"إثبات فاتورة مورد #{locked_invoice.invoice_number} "
                f"- {locked_invoice.supplier.name}"
            ),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch=locked_invoice.branch,
            journal_entry=entry,
            account=debit_acc,
            cost_center=locked_invoice.cost_center,
            description=f"إثبات فاتورة المورد: {locked_invoice.supplier.name}",
            debit=locked_invoice.total_amount,
            credit=Decimal("0.00"),
        )
        JournalEntryLine.objects.create(
            school=school,
            branch=locked_invoice.branch,
            journal_entry=entry,
            account=credit_acc,
            cost_center=locked_invoice.cost_center,
            description=(
                f"استحقاق ذمة المورد: {locked_invoice.supplier.name} "
                f"- فاتورة #{locked_invoice.invoice_number}"
            ),
            debit=Decimal("0.00"),
            credit=locked_invoice.total_amount,
        )
        entry.post(user=user)
        locked_invoice.journal_entry = entry
        if locked_invoice.status == VendorInvoice.Status.DRAFT:
            locked_invoice.status = VendorInvoice.Status.APPROVED
        locked_invoice.approved_by = user
        locked_invoice.approved_at = locked_invoice.approved_at or timezone.now()
        locked_invoice.save(update_fields=[
            "journal_entry", "status", "approved_by", "approved_at", "updated_at",
        ])
        return entry

def disburse_vendor_payment(
    vendor_invoice,
    payment_account: Account,
    amount: Decimal,
    reference_number: str = "",
    payment_method: str = "bank_transfer",
    user=None,
    idempotency_key: str = "",
) -> tuple[JournalEntry, PaymentVoucher]:
    """سداد المورد بقيد واحد مع مفتاح اختياري يمنع تكرار طلب السداد نفسه."""
    from apps.inventory.models import VendorInvoice, VendorInvoicePayment
    from apps.tenants.models import School

    normalized_key = (idempotency_key or "").strip()
    if len(normalized_key) < 8 or len(normalized_key) > 100:
        raise ValidationError("مفتاح منع تكرار سداد المورد يجب أن يكون بين 8 و100 حرف.")
    if amount <= Decimal("0.00"):
        raise ValidationError("مبلغ السداد يجب أن يكون أكبر من الصفر.")
    if idempotency_key and len(idempotency_key.strip()) < 8:
        raise ValidationError("مفتاح منع التكرار يجب ألا يقل عن 8 أحرف.")
    school = vendor_invoice.school
    if payment_account.school_id != school.pk or payment_account.is_archived:
        raise ValidationError("حساب السداد غير صالح أو لا يتبع المدرسة نفسها.")
    if payment_account.account_type != Account.AccountType.ASSET or not payment_account.is_leaf:
        raise ValidationError("حساب السداد يجب أن يكون حساب أصول تفصيلياً (صندوق أو بنك).")

    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        locked_invoice = VendorInvoice.objects.select_for_update().get(pk=vendor_invoice.pk)
        recorded_payment = VendorInvoicePayment.objects.select_for_update().filter(
            school=school, idempotency_key=normalized_key, is_archived=False,
        ).select_related("payment_voucher", "journal_entry").first()
        if recorded_payment:
            if recorded_payment.invoice_id != locked_invoice.pk or recorded_payment.amount != amount:
                raise ValidationError("مفتاح منع التكرار مستخدم لسداد فاتورة أخرى أو بمبلغ مختلف.")
            return recorded_payment.journal_entry, recorded_payment.payment_voucher
        vendor_payable_acc = _get_account_or_seed(
            school, "2101", "ذمم الموردين والشركات الدائنة",
        )
        already_posted = False

        if idempotency_key:
            existing = PaymentVoucher.objects.select_for_update(of=("self",)).filter(
                school=school,
                idempotency_key=idempotency_key,
                is_archived=False,
            ).select_related("journal_entry").first()
            if existing:
                same_data = (
                    existing.amount == amount
                    and existing.credit_account_id == payment_account.pk
                    and existing.debit_account_id == vendor_payable_acc.pk
                    and existing.paid_to == locked_invoice.supplier.name
                    and existing.reference_number == reference_number
                    and existing.description == f"سداد دفعة من فاتورة المورد #{locked_invoice.invoice_number}"
                )
                if not same_data:
                    raise ValidationError("مفتاح منع التكرار مستخدم لسداد ببيانات مختلفة.")
                if existing.status == PaymentVoucher.Status.POSTED and existing.journal_entry_id:
                    payment_voucher = existing
                    already_posted = True
                elif existing.status != PaymentVoucher.Status.DRAFT:
                    raise ValidationError("سند السداد السابق ليس مسودة قابلة للاستكمال.")
                payment_voucher = existing
            else:
                payment_voucher = None
        else:
            payment_voucher = None

        if payment_voucher is None:
            if not already_posted and amount > locked_invoice.remaining_amount:
                raise ValidationError(
                    f"المبلغ المراد سداده ({amount}) أكبر من المبلغ المتبقي على الفاتورة ({locked_invoice.remaining_amount})."
                )
            payment_date = timezone.localdate()
            invoice_branch_id = locked_invoice.branch_id
            payment_branch_id = payment_account.branch_id
            payable_branch_id = vendor_payable_acc.branch_id
            debit_branch_id = payable_branch_id or invoice_branch_id
            credit_branch_id = payment_branch_id or invoice_branch_id
            entry_branch_id = (
                debit_branch_id
                if debit_branch_id == credit_branch_id
                else None
            )
            voucher_number = f"PV-VINV-{locked_invoice.pk.hex[:8]}-{uuid.uuid4().hex[:10].upper()}"
            payment_voucher = PaymentVoucher.objects.create(
                school=school,
                branch_id=entry_branch_id,
                voucher_number=voucher_number,
                idempotency_key=idempotency_key,
                date=payment_date,
                paid_to=locked_invoice.supplier.name,
                amount=amount,
                credit_account=payment_account,
                debit_account=vendor_payable_acc,
                payment_method=payment_method,
                reference_number=reference_number,
                description=f"سداد دفعة من فاتورة المورد #{locked_invoice.invoice_number}",
                status=PaymentVoucher.Status.DRAFT,
            )
            debit_branch_id = payable_branch_id or invoice_branch_id
            credit_branch_id = payment_branch_id or invoice_branch_id
        else:
            payment_date = payment_voucher.date
            debit_branch_id = payment_voucher.debit_account.branch_id or payment_voucher.branch_id
            credit_branch_id = payment_voucher.credit_account.branch_id or payment_voucher.branch_id
            entry_branch_id = (
                debit_branch_id
                if debit_branch_id == credit_branch_id
                else None
            )
            if amount > locked_invoice.remaining_amount:
                raise ValidationError(
                    f"المبلغ المراد سداده ({amount}) أكبر من المبلغ المتبقي على الفاتورة ({locked_invoice.remaining_amount})."
                )

        period = _get_active_fiscal_period(school, payment_date)
        entry_number = f"JV-VPAY-{payment_voucher.voucher_number}"
        entry = JournalEntry.objects.filter(
            school=school,
            source_module="vendor_payment",
            source_reference=payment_voucher.voucher_number,
            is_archived=False,
        ).first()
        if entry:
            if entry.status != JournalEntry.Status.POSTED:
                raise ValidationError("يوجد قيد سداد مورد سابق غير مرحّل؛ يجب مراجعته.")
        else:
            entry = JournalEntry.objects.create(
                school=school,
                branch_id=entry_branch_id,
                fiscal_period=period,
                entry_number=entry_number,
                date=payment_date,
                status=JournalEntry.Status.DRAFT,
                source_module="vendor_payment",
                source_reference=payment_voucher.voucher_number,
                description=f"سند صرف سداد فاتورة المورد #{locked_invoice.invoice_number} ({locked_invoice.supplier.name})",
            )
            JournalEntryLine.objects.create(
                school=school,
                branch_id=debit_branch_id,
                journal_entry=entry,
                account=vendor_payable_acc,
                description=f"سداد ذمة المورد: {locked_invoice.supplier.name} - فاتورة #{locked_invoice.invoice_number}",
                debit=amount,
                credit=Decimal("0.00"),
            )
            JournalEntryLine.objects.create(
                school=school,
                branch_id=credit_branch_id,
                journal_entry=entry,
                account=payment_account,
                description=f"صرف سداد من حساب {payment_account.name} للمورد {locked_invoice.supplier.name}",
                debit=Decimal("0.00"),
                credit=amount,
            )
            entry.post(user=user)

        payment_voucher.journal_entry = entry
        payment_voucher.status = PaymentVoucher.Status.POSTED
        payment_voucher.save(update_fields=["journal_entry", "status", "updated_at"])

        if not already_posted:
            locked_invoice.paid_amount += amount
            if locked_invoice.paid_amount >= locked_invoice.total_amount:
                locked_invoice.status = VendorInvoice.Status.PAID
            else:
                locked_invoice.status = VendorInvoice.Status.PARTIAL
            locked_invoice.save(update_fields=["paid_amount", "status", "updated_at"])
        VendorInvoicePayment.objects.create(
            school=school,
            branch=locked_invoice.branch,
            invoice=locked_invoice,
            payment_voucher=payment_voucher,
            journal_entry=entry,
            amount=amount,
            idempotency_key=normalized_key,
            payment_date=payment_date,
            recorded_by=user,
        )
        return entry, payment_voucher
