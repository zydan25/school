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
from apps.assets.models import AssetDepreciationEntry
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


def post_credit_settlement_to_journal(credit_tx) -> JournalEntry | None:
    """
    قيد تسوية استخدام الرصيد الدائن للطالب لسداد فاتورة:
    مدين: أرصدة وأمانات الطلاب الدائنة (2102)
    دائن: ذمم ورسوم الطلاب (1104)
    """
    if credit_tx.amount <= Decimal("0.00"):
        return None
    school = credit_tx.school
    tx_date = credit_tx.created_at.date()
    period = _get_active_fiscal_period(school, tx_date)

    acc_liability = _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
    acc_receivable = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")

    entry_num = f"JV-SETTLE-{credit_tx.id.hex[:8].upper()}"
    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="student_fees_credit",
            source_reference=str(credit_tx.id),
            is_archived=False,
        ).first()
        if existing:
            return existing

        entry = JournalEntry.objects.create(
            school=school,
            branch=credit_tx.branch,
            fiscal_period=period,
            entry_number=entry_num,
            date=tx_date,
            status=JournalEntry.Status.DRAFT,
            source_module="student_fees_credit",
            source_reference=str(credit_tx.id),
            description=f"تسوية سداد من الرصيد الدائن للطالب {credit_tx.student}",
        )

        # Debit: 2102 (Reduce liability)
        JournalEntryLine.objects.create(
            school=school,
            branch=credit_tx.branch,
            journal_entry=entry,
            account=acc_liability,
            debit=credit_tx.amount,
            credit=Decimal("0.00"),
            description=f"تسوية رصيد دائن للطالب {credit_tx.student}",
        )

        # Credit: 1104 (Reduce student receivable)
        JournalEntryLine.objects.create(
            school=school,
            branch=credit_tx.branch,
            journal_entry=entry,
            account=acc_receivable,
            debit=Decimal("0.00"),
            credit=credit_tx.amount,
            description=f"إثبات سداد الفاتورة #{credit_tx.invoice.invoice_number if credit_tx.invoice else ''}",
        )

        entry.post(user=credit_tx.created_by)
        return entry


def post_student_credit_refund_to_journal(credit_tx) -> JournalEntry:
    """قيد استرداد رصيد الطالب: مدين الأرصدة الدائنة ودائن وسيلة الصرف."""
    from apps.student_fees.models import StudentCreditTransaction

    if credit_tx.transaction_type != StudentCreditTransaction.TransactionType.REFUND:
        raise ValidationError("الحركة المحددة ليست استرداد رصيد دائن.")
    if credit_tx.amount <= Decimal("0.00"):
        raise ValidationError("قيمة استرداد الرصيد يجب أن تكون أكبر من الصفر.")
    school = credit_tx.school
    tx_date = credit_tx.created_at.date()
    period = _get_active_fiscal_period(school, tx_date)
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_fees_credit_refund",
        source_reference=str(credit_tx.pk),
        is_archived=False,
    ).first()
    if existing:
        return existing

    payment_accounts = {
        PaymentReceipt.PaymentMethod.CASH: ("1101", "الصندوق / الخزينة"),
        PaymentReceipt.PaymentMethod.BANK_TRANSFER: ("1102", "البنك"),
        PaymentReceipt.PaymentMethod.POS: ("1103", "نقاط البيع - شبكة"),
        PaymentReceipt.PaymentMethod.ONLINE: ("1102", "البنك"),
    }
    account_code, account_name = payment_accounts.get(
        credit_tx.refund_payment_method, (None, None),
    )
    if not account_code:
        raise ValidationError("طريقة صرف استرداد الرصيد غير معتمدة.")
    liability = _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
    payment_account = _get_account_or_seed(school, account_code, account_name)
    entry = JournalEntry.objects.create(
        school=school,
        branch=credit_tx.branch,
        fiscal_period=period,
        entry_number=f"JV-REFUND-{credit_tx.pk.hex[:8].upper()}",
        date=tx_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_fees_credit_refund",
        source_reference=str(credit_tx.pk),
        description=f"استرداد رصيد دائن للطالب {credit_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school, branch=credit_tx.branch, journal_entry=entry, account=liability,
        debit=credit_tx.amount, credit=Decimal("0.00"),
        description=f"تخفيض الرصيد الدائن المستحق للطالب {credit_tx.student}",
    )
    JournalEntryLine.objects.create(
        school=school, branch=credit_tx.branch, journal_entry=entry, account=payment_account,
        debit=Decimal("0.00"), credit=credit_tx.amount,
        description=f"صرف استرداد رصيد الطالب {credit_tx.student}",
    )
    entry.post(user=credit_tx.created_by)
    return entry


def post_student_invoice_discount_to_journal(discount_request) -> JournalEntry:
    """قيد الخصم المعتمد: تخفيض إيراد الرسوم والذمم بالقيمة نفسها."""
    if discount_request.amount <= Decimal("0.00"):
        raise ValidationError("قيمة الخصم يجب أن تكون أكبر من الصفر.")
    invoice = discount_request.invoice
    if not invoice.journal_entry_id:
        raise ValidationError("لا يمكن اعتماد خصم محاسبي قبل ترحيل قيد استحقاق الفاتورة.")
    school = discount_request.school
    tx_date = discount_request.decided_at.date() if discount_request.decided_at else timezone.localdate()
    period = _get_active_fiscal_period(school, tx_date)
    existing = JournalEntry.objects.filter(
        school=school,
        source_module="student_invoice_discount",
        source_reference=str(discount_request.pk),
        is_archived=False,
    ).first()
    if existing:
        return existing
    old_net_amount = max(
        Decimal("0.00"), invoice.total_amount
        - (invoice.discount_amount - discount_request.amount),
    )
    new_net_amount = max(
        Decimal("0.00"), invoice.total_amount - invoice.discount_amount,
    )
    old_overpayment = max(Decimal("0.00"), invoice.paid_amount - old_net_amount)
    new_overpayment = max(Decimal("0.00"), invoice.paid_amount - new_net_amount)
    credit_delta = max(Decimal("0.00"), new_overpayment - old_overpayment)

    revenue = _get_account_or_seed(school, "4101", "إيرادات الرسوم الدراسية")
    receivable = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")
    liability = (
        _get_account_or_seed(school, "2102", "أرصدة وأمانات الطلاب الدائنة")
        if credit_delta > Decimal("0.00") else None
    )
    receivable_credit = discount_request.amount - credit_delta
    entry = JournalEntry.objects.create(
        school=school,
        branch=discount_request.branch,
        fiscal_period=period,
        entry_number=f"JV-DISC-{discount_request.pk.hex[:8].upper()}",
        date=tx_date,
        status=JournalEntry.Status.DRAFT,
        source_module="student_invoice_discount",
        source_reference=str(discount_request.pk),
        description=f"اعتماد خصم للفاتورة #{invoice.invoice_number}: {discount_request.reason[:150]}",
    )
    JournalEntryLine.objects.create(
        school=school, branch=discount_request.branch, journal_entry=entry, account=revenue,
        debit=discount_request.amount, credit=Decimal("0.00"),
        description=f"تخفيض إيراد الرسوم للفاتورة #{invoice.invoice_number}",
    )
    if receivable_credit > Decimal("0.00"):
        JournalEntryLine.objects.create(
            school=school, branch=discount_request.branch,
            journal_entry=entry, account=receivable,
            debit=Decimal("0.00"), credit=receivable_credit,
            description=f"تخفيض ذمم الطالب عن الفاتورة #{invoice.invoice_number}",
        )
    if credit_delta > Decimal("0.00"):
        JournalEntryLine.objects.create(
            school=school, branch=discount_request.branch,
            journal_entry=entry, account=liability,
            debit=Decimal("0.00"), credit=credit_delta,
            description=f"تحويل الخصم الزائد إلى رصيد دائن للطالب {invoice.student}",
        )
    entry.post(user=discount_request.approved_by)
    return entry


def post_payment_voucher_to_journal(voucher: PaymentVoucher) -> JournalEntry:
    """
    الترحيل الآلي لسند الصرف المالي إلى قيد يومية محاسبي.
    الجانب المدين: حساب المصروف أو المورد (voucher.debit_account).
    الجانب الدائن: حساب الصندوق أو البنك (voucher.credit_account).
    """
    if voucher.amount <= Decimal("0.00"):
        raise ValueError("لا يمكن ترحيل سند صرف مالي بمبلغ صفر أو سالب.")
    if voucher.status == PaymentVoucher.Status.CANCELLED:
        raise ValueError("لا يمكن ترحيل سند صرف ملغى.")

    school = voucher.school
    if voucher.debit_account.school_id != school.id or voucher.credit_account.school_id != school.id:
        raise ValueError("حسابات سند الصرف لا تنتمي إلى نفس مدرسة السند.")

    period = _get_active_fiscal_period(school, voucher.date)
    debit_branch = voucher.branch_id or voucher.debit_account.branch_id or (voucher.cost_center.branch_id if voucher.cost_center_id else None)
    credit_branch = voucher.branch_id or voucher.credit_account.branch_id
    entry_branch_id = debit_branch if debit_branch == credit_branch else None

    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="accounting_payment",
            source_reference=voucher.voucher_number,
            is_archived=False,
        ).first()
        if existing:
            if not voucher.journal_entry_id:
                voucher.journal_entry = existing
                voucher.status = PaymentVoucher.Status.POSTED
                voucher.save(update_fields=["journal_entry", "status", "updated_at"])
            return existing

        entry_number = f"JV-PAY-{voucher.voucher_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch_id=entry_branch_id,
            fiscal_period=period,
            entry_number=entry_number,
            date=voucher.date,
            status=JournalEntry.Status.DRAFT,
            source_module="accounting_payment",
            source_reference=voucher.voucher_number,
            description=f"صرف مالي بسند #{voucher.voucher_number} إلى: {voucher.paid_to} - {voucher.description}",
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=debit_branch,
            journal_entry=entry,
            account=voucher.debit_account,
            cost_center=voucher.cost_center,
            description=voucher.description or f"صرف إلى {voucher.paid_to}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=credit_branch,
            journal_entry=entry,
            account=voucher.credit_account,
            description=f"خروج نقدية لصالح {voucher.paid_to}",
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

        entry.post(user=voucher.created_by if hasattr(voucher, "created_by") else None)
        voucher.status = PaymentVoucher.Status.POSTED
        voucher.journal_entry = entry
        voucher.save(update_fields=["status", "journal_entry", "updated_at"])

        return entry


def post_receipt_voucher_to_journal(voucher: ReceiptVoucher) -> JournalEntry:
    """
    الترحيل الآلي لسند القبض العام إلى قيد يومية محاسبي.
    الجانب المدين: حساب الصندوق أو البنك (voucher.debit_account).
    الجانب الدائن: حساب الإيراد (voucher.credit_account).
    """
    if voucher.amount <= Decimal("0.00"):
        raise ValueError("لا يمكن ترحيل سند قبض عام بمبلغ صفر أو سالب.")
    if voucher.status == ReceiptVoucher.Status.CANCELLED:
        raise ValueError("لا يمكن ترحيل سند قبض ملغى.")

    school = voucher.school
    if voucher.debit_account.school_id != school.id or voucher.credit_account.school_id != school.id:
        raise ValueError("حسابات سند القبض لا تنتمي إلى نفس مدرسة السند.")

    period = _get_active_fiscal_period(school, voucher.date)
    debit_branch = voucher.branch_id or voucher.debit_account.branch_id
    credit_branch = voucher.branch_id or voucher.credit_account.branch_id or (voucher.cost_center.branch_id if voucher.cost_center_id else None)
    entry_branch_id = debit_branch if debit_branch == credit_branch else None

    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="accounting_receipt",
            source_reference=voucher.voucher_number,
            is_archived=False,
        ).first()
        if existing:
            if not voucher.journal_entry_id:
                voucher.journal_entry = existing
                voucher.status = ReceiptVoucher.Status.POSTED
                voucher.save(update_fields=["journal_entry", "status", "updated_at"])
            return existing

        entry_number = f"JV-REC-GEN-{voucher.voucher_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch_id=entry_branch_id,
            fiscal_period=period,
            entry_number=entry_number,
            date=voucher.date,
            status=JournalEntry.Status.DRAFT,
            source_module="accounting_receipt",
            source_reference=voucher.voucher_number,
            description=f"قبض إيراد عام بسند #{voucher.voucher_number} من: {voucher.received_from} - {voucher.description}",
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=debit_branch,
            journal_entry=entry,
            account=voucher.debit_account,
            description=f"قبض نقدية من {voucher.received_from}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=credit_branch,
            journal_entry=entry,
            account=voucher.credit_account,
            cost_center=voucher.cost_center,
            description=voucher.description,
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

        entry.post(user=voucher.created_by if hasattr(voucher, "created_by") else None)
        voucher.status = ReceiptVoucher.Status.POSTED
        voucher.journal_entry = entry
        voucher.save(update_fields=["status", "journal_entry", "updated_at"])

        return entry


def post_asset_depreciation_to_journal(entry: AssetDepreciationEntry) -> JournalEntry:
    """
    الترحيل الآلي لإهلاك الأصل الثابت إلى قيد يومية محاسبي.
    الجانب المدين: مصروف إهلاك الأصول السنوي (5209).
    الجانب الدائن: مجمع الإهلاك المتراكم للأصل (1209).
    """
    if entry.depreciation_amount <= Decimal("0.00"):
        raise ValueError("مبلغ إهلاك الأصل يجب أن يكون أكبر من الصفر.")

    school = entry.school
    period = _get_active_fiscal_period(school, entry.date)

    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="assets_depreciation",
            source_reference=f"{entry.asset.code}-{entry.fiscal_year.id}",
            is_archived=False,
        ).first()
        if existing:
            return existing

        depreciation_expense = _get_account_or_seed(school, "5209", "مصروف إهلاك الأصول")
        accumulated_depreciation = _get_account_or_seed(school, "1209", "مجمع إهلاك الأصول المتراكم")

        asset_branch_id = entry.branch_id or entry.asset.branch_id
        journal_entry = JournalEntry.objects.create(
            school=school,
            branch_id=asset_branch_id,
            fiscal_period=period,
            entry_number=f"JV-DEP-{entry.asset.code}-{entry.fiscal_year.name}",
            date=entry.date,
            status=JournalEntry.Status.DRAFT,
            source_module="assets_depreciation",
            source_reference=f"{entry.asset.code}-{entry.fiscal_year.id}",
            description=f"قيد إهلاك أصل ثابت: {entry.asset.name} عن السنة المالية {entry.fiscal_year.name}",
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=asset_branch_id,
            journal_entry=journal_entry,
            account=depreciation_expense,
            description=f"مصروف إهلاك أصل [{entry.asset.code}] {entry.asset.name}",
            debit=entry.depreciation_amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            branch_id=asset_branch_id,
            journal_entry=journal_entry,
            account=accumulated_depreciation,
            description=f"مجمع إهلاك الأصل [{entry.asset.code}]",
            debit=Decimal("0.00"),
            credit=entry.depreciation_amount,
        )

        journal_entry.post()
        entry.asset.accumulated_depreciation += entry.depreciation_amount
        entry.asset.save(update_fields=["accumulated_depreciation"])

        return journal_entry


def post_student_invoice_to_journal(invoice) -> JournalEntry:
    """
    الترحيل الآلي لإصدار فاتورة رسوم الطالب إلى قيد استحقاق محاسبي.
    الجانب المدين: ذمم الطلاب وأولياء الأمور (1104).
    الجانب الدائن: إيرادات الرسوم الدراسية (4101).
    """
    school = invoice.school
    post_date = getattr(invoice, "issue_date", None) or getattr(invoice, "due_date", None) or timezone.localdate()
    period = _get_active_fiscal_period(school, post_date)

    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="student_invoice",
            source_reference=invoice.invoice_number,
            is_archived=False,
        ).first()
        if existing:
            if not getattr(invoice, "journal_entry_id", None):
                invoice.journal_entry = existing
                invoice.save(update_fields=["journal_entry", "updated_at"])
            return existing

        net_amount = max(Decimal("0.00"), invoice.total_amount - invoice.discount_amount)
        if net_amount <= Decimal("0.00"):
            raise ValueError(f"صافي قيمة الفاتورة ({net_amount}) يجب أن يكون أكبر من الصفر لترحيلها.")

        debit_acc = _get_account_or_seed(school, "1104", "ذمم ورسوم الطلاب")
        credit_acc = _get_account_or_seed(school, "4101", "إيرادات الرسوم الدراسية")

        entry_number = f"JV-INV-{invoice.invoice_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch=invoice.branch,
            fiscal_period=period,
            entry_number=entry_number,
            date=post_date,
            status=JournalEntry.Status.DRAFT,
            source_module="student_invoice",
            source_reference=invoice.invoice_number,
            description=f"إثبات استحقاق فاتورة رسوم #{invoice.invoice_number} للطالب {invoice.student}",
        )

        JournalEntryLine.objects.create(
            school=school,
            branch=invoice.branch,
            journal_entry=entry,
            account=debit_acc,
            description=f"ذمة الطالب: {invoice.student} - فاتورة #{invoice.invoice_number}",
            debit=net_amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            branch=invoice.branch,
            journal_entry=entry,
            account=credit_acc,
            description=f"إيراد رسوم دراسية - فاتورة #{invoice.invoice_number}",
            debit=Decimal("0.00"),
            credit=net_amount,
        )

        entry.post(user=getattr(invoice, "created_by", None))
        if hasattr(invoice, "journal_entry"):
            invoice.journal_entry = entry
            invoice.save(update_fields=["journal_entry", "updated_at"])
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
        original = JournalEntry.objects.select_for_update().select_related(
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
    """
    الترحيل الآلي لفاتورة المشتريات والموردين لإثبات استحقاق الذمم الدائنة والمخزون.
    الطرف المدين: مخزون الكتب والقرطاسية والزي (1106).
    الطرف الدائن: ذمم الموردين والشركات الدائنة (2101).
    """
    school = vendor_invoice.school
    post_date = getattr(vendor_invoice, "invoice_date", None) or timezone.localdate()
    period = _get_active_fiscal_period(school, post_date)

    with transaction.atomic():
        if vendor_invoice.journal_entry:
            return vendor_invoice.journal_entry

        if vendor_invoice.total_amount <= Decimal("0.00"):
            raise ValidationError(f"إجمالي فاتورة المورد ({vendor_invoice.total_amount}) يجب أن يكون أكبر من الصفر.")

        debit_acc = _get_account_or_seed(school, "1106", "مخزون الكتب والقرطاسية والزي")
        credit_acc = _get_account_or_seed(school, "2101", "ذمم الموردين والشركات الدائنة")

        entry_number = f"JV-VINV-{vendor_invoice.invoice_number}"
        entry = JournalEntry.objects.create(
            school=school,
            branch=vendor_invoice.branch,
            fiscal_period=period,
            entry_number=entry_number,
            date=post_date,
            status=JournalEntry.Status.DRAFT,
            source_module="vendor_invoice",
            source_reference=str(vendor_invoice.invoice_number),
            description=f"إثبات فاتورة مورد #{vendor_invoice.invoice_number} - {vendor_invoice.supplier.name}",
        )

        JournalEntryLine.objects.create(
            school=school,
            branch=vendor_invoice.branch,
            journal_entry=entry,
            account=debit_acc,
            description=f"إثبات بضاعة / مخزون مورد: {vendor_invoice.supplier.name}",
            debit=vendor_invoice.total_amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            branch=vendor_invoice.branch,
            journal_entry=entry,
            account=credit_acc,
            description=f"استحقاق ذمة المورد: {vendor_invoice.supplier.name} - فاتورة #{vendor_invoice.invoice_number}",
            debit=Decimal("0.00"),
            credit=vendor_invoice.total_amount,
        )

        entry.post(user=user)
        vendor_invoice.journal_entry = entry
        if vendor_invoice.status == vendor_invoice.Status.DRAFT:
            vendor_invoice.status = vendor_invoice.Status.APPROVED
        vendor_invoice.save(update_fields=["journal_entry", "status", "updated_at"])
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
    from apps.inventory.models import VendorInvoice
    from apps.tenants.models import School

    if amount <= Decimal("0.00"):
        raise ValidationError("مبلغ السداد يجب أن يكون أكبر من الصفر.")
    if idempotency_key and len(idempotency_key.strip()) < 8:
        raise ValidationError("مفتاح منع التكرار يجب ألا يقل عن 8 أحرف.")
    school = vendor_invoice.school
    if payment_account.school_id != school.pk:
        raise ValidationError("حساب السداد لا يتبع نفس المدرسة الخاصة بالفاتورة.")
    if payment_account.account_type != Account.AccountType.ASSET or not payment_account.is_leaf:
        raise ValidationError("حساب السداد يجب أن يكون حساب أصول تفصيلياً (صندوق أو بنك).")

    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        locked_invoice = VendorInvoice.objects.select_for_update().get(pk=vendor_invoice.pk)
        vendor_payable_acc = _get_account_or_seed(
            school, "2101", "ذمم الموردين والشركات الدائنة",
        )

        if idempotency_key:
            existing = PaymentVoucher.objects.select_for_update().filter(
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
                )
                if not same_data:
                    raise ValidationError("مفتاح منع التكرار مستخدم لسداد ببيانات مختلفة.")
                if existing.status == PaymentVoucher.Status.POSTED and existing.journal_entry_id:
                    return existing.journal_entry, existing
                if existing.status != PaymentVoucher.Status.DRAFT:
                    raise ValidationError("سند السداد السابق ليس مسودة قابلة للاستكمال.")
                payment_voucher = existing
            else:
                payment_voucher = None
        else:
            payment_voucher = None

        if payment_voucher is None:
            if amount > locked_invoice.remaining_amount:
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

        locked_invoice.paid_amount += amount
        if locked_invoice.paid_amount >= locked_invoice.total_amount:
            locked_invoice.status = VendorInvoice.Status.PAID
        else:
            locked_invoice.status = VendorInvoice.Status.PARTIAL
        locked_invoice.save(update_fields=["paid_amount", "status", "updated_at"])
        return entry, payment_voucher
