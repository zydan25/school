"""
apps/accounting/services/auto_posting.py
خدمة الترحيل المحاسبي الآلي المزدوج لكافة التعاملات المالية (Onyx Pro Integration).
تربط كافة السندات، الإيرادات، المصروفات، الرسوم، الرواتب، وإهلاك الأصول
بقيود اليومية المتوازنة والمستقلة لكل مدرسة مع منع الترحيل على الحسابات التجميعية.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Account, FiscalPeriod, FiscalYear, JournalEntry, JournalEntryLine, PaymentVoucher, ReceiptVoucher
from apps.student_fees.models import PaymentReceipt
from apps.assets.models import AssetDepreciationEntry


def _get_active_fiscal_period(school, target_date=None) -> FiscalPeriod:
    """البحث عن الفترة المالية المفتوحة للمدرسة الموافقة للتاريخ، مع تهيئة السنة والفترة تلقائياً عند عدم وجودهما."""
    if target_date is None:
        target_date = timezone.localdate()
    elif isinstance(target_date, datetime.datetime):
        target_date = target_date.date()

    period = FiscalPeriod.objects.filter(
        school=school,
        fiscal_year__is_closed=False,
        is_closed=False,
        start_date__lte=target_date,
        end_date__gte=target_date,
        is_archived=False,
    ).first()

    if not period:
        f_year = FiscalYear.objects.filter(
            school=school,
            is_closed=False,
            start_date__lte=target_date,
            end_date__gte=target_date,
            is_archived=False,
        ).first()

        if not f_year:
            # Fallback to any open fiscal year for the school
            f_year = FiscalYear.objects.filter(
                school=school,
                is_closed=False,
                is_archived=False,
            ).first()

        if not f_year:
            # Auto-initialize standard calendar fiscal year for this school
            f_year = FiscalYear.objects.create(
                school=school,
                name=f"السنة المالية {target_date.year}",
                start_date=date(target_date.year, 1, 1),
                end_date=date(target_date.year, 12, 31),
                is_closed=False,
            )

        period_num = f_year.periods.count() + 1
        first_day = target_date.replace(day=1)
        if first_day.month == 12:
            last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timezone.timedelta(days=1)
        else:
            last_day = first_day.replace(month=first_day.month + 1, day=1) - timezone.timedelta(days=1)

        period = FiscalPeriod.objects.create(
            school=school,
            fiscal_year=f_year,
            period_number=period_num,
            name=f"فترة {target_date.strftime('%m/%Y')}",
            start_date=max(f_year.start_date, first_day),
            end_date=min(f_year.end_date, last_day),
        )

    return period


def post_student_receipt_to_journal(receipt: PaymentReceipt) -> JournalEntry:
    """
    الترحيل الآلي لسند قبض رسوم الطالب إلى قيد يومية محاسبي مزدوج متوازن.
    الجانب المدين: الصندوق (1101) أو البنك (1102) حسب طريقة الدفع.
    الجانب الدائن: ذمم ورسوم الطلاب (1104) أو إيرادات الرسوم الدراسية (4101).
    """
    if receipt.amount <= Decimal("0.00"):
        raise ValueError("لا يمكن ترحيل سند قبض بمبلغ صفر أو سالب.")

    school = receipt.school
    tx_date = receipt.paid_at
    if isinstance(tx_date, datetime.datetime):
        tx_date = tx_date.date()
    period = _get_active_fiscal_period(school, tx_date)

    with transaction.atomic():
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="student_fees",
            source_reference=receipt.receipt_number,
            is_archived=False,
        ).first()
        if existing:
            return existing

        if receipt.payment_method == PaymentReceipt.PaymentMethod.BANK_TRANSFER:
            debit_acc = Account.objects.filter(school=school, code="1102", is_leaf=True).first()
        elif receipt.payment_method == PaymentReceipt.PaymentMethod.POS:
            debit_acc = Account.objects.filter(school=school, code="1103", is_leaf=True).first()
        else:
            debit_acc = Account.objects.filter(school=school, code="1101", is_leaf=True).first()

        credit_acc = Account.objects.filter(school=school, code="1104", is_leaf=True).first()
        if not credit_acc:
            credit_acc = Account.objects.filter(school=school, code="4101", is_leaf=True).first()

        if not debit_acc or not credit_acc:
            raise ValueError("شجرة الحسابات للمدرسة غير مهيأة. يرجى تهيئة دليل الحسابات أولاً.")

        entry_number = f"JV-REC-{receipt.receipt_number}"
        entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=entry_number,
            date=receipt.paid_at.date(),
            status=JournalEntry.Status.POSTED,
            source_module="student_fees",
            source_reference=receipt.receipt_number,
            description=f"تحصيل رسوم دراسية بسند قبض #{receipt.receipt_number} - الطالب: {receipt.student}",
            posted_at=receipt.paid_at,
            posted_by=receipt.received_by,
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=debit_acc,
            description=f"إيداع نقدي/بنكي لقاء سند قبض #{receipt.receipt_number}",
            debit=receipt.amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=credit_acc,
            description=f"سداد رسوم الطالب: {receipt.student.first_name} {receipt.student.last_name}",
            debit=Decimal("0.00"),
            credit=receipt.amount,
        )

        validate_and_balance_journal_entry(entry)
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
            fiscal_period=period,
            entry_number=entry_number,
            date=voucher.date,
            status=JournalEntry.Status.POSTED,
            source_module="accounting_payment",
            source_reference=voucher.voucher_number,
            description=f"صرف مالي بسند #{voucher.voucher_number} إلى: {voucher.paid_to} - {voucher.description}",
            posted_at=timezone.now(),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.debit_account,
            cost_center=voucher.cost_center,
            description=voucher.description or f"صرف إلى {voucher.paid_to}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.credit_account,
            description=f"خروج نقدية لصالح {voucher.paid_to}",
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

        validate_and_balance_journal_entry(entry)
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
            fiscal_period=period,
            entry_number=entry_number,
            date=voucher.date,
            status=JournalEntry.Status.POSTED,
            source_module="accounting_receipt",
            source_reference=voucher.voucher_number,
            description=f"قبض إيراد عام بسند #{voucher.voucher_number} من: {voucher.received_from} - {voucher.description}",
            posted_at=timezone.now(),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.debit_account,
            description=f"قبض نقدية من {voucher.received_from}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.credit_account,
            cost_center=voucher.cost_center,
            description=voucher.description,
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

        validate_and_balance_journal_entry(entry)
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

        depreciation_expense = Account.objects.filter(school=school, code="5209", is_leaf=True).first()
        accumulated_depreciation = Account.objects.filter(school=school, code="1209", is_leaf=True).first()

        if not depreciation_expense or not accumulated_depreciation:
            raise ValueError("حسابات إهلاك الأصول (5209 أو 1209) غير موجودة في دليل حسابات المدرسة.")

        journal_entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=f"JV-DEP-{entry.asset.code}-{entry.fiscal_year.name}",
            date=entry.date,
            status=JournalEntry.Status.POSTED,
            source_module="assets_depreciation",
            source_reference=f"{entry.asset.code}-{entry.fiscal_year.id}",
            description=f"قيد إهلاك أصل ثابت: {entry.asset.name} عن السنة المالية {entry.fiscal_year.name}",
            posted_at=timezone.now(),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=journal_entry,
            account=depreciation_expense,
            description=f"مصروف إهلاك أصل [{entry.asset.code}] {entry.asset.name}",
            debit=entry.depreciation_amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=journal_entry,
            account=accumulated_depreciation,
            description=f"مجمع إهلاك الأصل [{entry.asset.code}]",
            debit=Decimal("0.00"),
            credit=entry.depreciation_amount,
        )

        validate_and_balance_journal_entry(journal_entry)
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
    post_date = getattr(invoice, "due_date", None) or getattr(invoice, "issue_date", None) or timezone.localdate()
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

        debit_acc = Account.objects.filter(school=school, code="1104", is_leaf=True).first()
        credit_acc = Account.objects.filter(school=school, code="4101", is_leaf=True).first()

        if not debit_acc or not credit_acc:
            raise ValueError("شجرة الحسابات للمدرسة غير مهيأة (حساب ذمم الطلاب 1104 أو إيرادات الرسوم 4101 غير موجود).")

        entry_number = f"JV-INV-{invoice.invoice_number}"
        entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=entry_number,
            date=post_date,
            status=JournalEntry.Status.POSTED,
            source_module="student_invoice",
            source_reference=invoice.invoice_number,
            description=f"إثبات استحقاق فاتورة رسوم #{invoice.invoice_number} للطالب {invoice.student}",
            posted_at=timezone.now(),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=debit_acc,
            description=f"ذمة الطالب: {invoice.student} - فاتورة #{invoice.invoice_number}",
            debit=net_amount,
            credit=Decimal("0.00"),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=credit_acc,
            description=f"إيراد رسوم دراسية - فاتورة #{invoice.invoice_number}",
            debit=Decimal("0.00"),
            credit=net_amount,
        )

        validate_and_balance_journal_entry(entry)
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
    """
    إنشاء قيد عكسي محاسبي متكامل لقيد سابق لإلغاء أثره المالي دون حذف السجل التاريخي.
    الأطراف المدينة تصبح دائنة، والأطراف الدائنة تصبح مدينة.
    كلا القيدين يظلان في دفتر الأستاذ كـ POSTED ليتلاشى أثرهما الرياضي معاً إلى الصفر،
    ويتم توثيق الارتباط التبادلي وسبب العكس.
    """
    if original_entry.is_reversed:
        raise ValueError("لا يمكن عكس قيد محاسبي تم عكسه مسبقاً.")
    if original_entry.status != JournalEntry.Status.POSTED:
        raise ValueError("لا يمكن عكس قيد غير مرحل.")

    school = original_entry.school
    period = _get_active_fiscal_period(school, timezone.localdate())

    with transaction.atomic():
        reversal_num = f"REV-{original_entry.entry_number}"
        rev_entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=reversal_num,
            date=timezone.localdate(),
            status=JournalEntry.Status.POSTED,
            source_module="reversal",
            source_reference=original_entry.entry_number,
            description=f"قيد عكسي للقيد #{original_entry.entry_number} - السبب: {reason}",
            posted_at=timezone.now(),
            posted_by=reversed_by,
        )

        for line in original_entry.lines.all():
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=rev_entry,
                account=line.account,
                cost_center=line.cost_center,
                description=f"عكس: {line.description}",
                debit=line.credit,  # swap
                credit=line.debit,  # swap
            )

        validate_and_balance_journal_entry(rev_entry)
        original_entry.is_reversed = True
        original_entry.reversed_by_entry = rev_entry
        original_entry.reversal_reason = reason
        original_entry.save(update_fields=["is_reversed", "reversed_by_entry", "reversal_reason", "updated_at"])

        return rev_entry
