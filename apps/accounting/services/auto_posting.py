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


def _get_active_fiscal_period(school, target_date=None) -> Optional[FiscalPeriod]:
    """البحث عن الفترة المالية المفتوحة للمدرسة الموافقة للتاريخ."""
    if target_date is None:
        target_date = timezone.localdate()

    period = FiscalPeriod.objects.filter(
        school=school,
        fiscal_year__is_closed=False,
        is_closed=False,
        start_date__lte=target_date,
        end_date__gte=target_date,
        is_archived=False,
    ).first()

    if not period:
        # Fallback to any open year's first period or create default
        f_year = FiscalYear.objects.filter(school=school, is_closed=False, is_archived=False).first()
        if f_year:
            period = f_year.periods.filter(is_closed=False, is_archived=False).first()
            if not period:
                period = FiscalPeriod.objects.create(
                    school=school,
                    fiscal_year=f_year,
                    period_number=1,
                    name=f"فترة {f_year.name}",
                    start_date=f_year.start_date,
                    end_date=f_year.end_date,
                )

    return period


def post_student_receipt_to_journal(receipt: PaymentReceipt) -> JournalEntry:
    """
    الترحيل الآلي لسند قبض رسوم الطالب إلى قيد يومية محاسبي مزدوج متوازن.
    الجانب المدين: الصندوق (1101) أو البنك (1102) حسب طريقة الدفع.
    الجانب الدائن: ذمم ورسوم الطلاب (1104) أو إيرادات الرسوم الدراسية (4101).
    """
    school = receipt.school
    period = _get_active_fiscal_period(school, receipt.paid_at.date())

    with transaction.atomic():
        # Prevent duplicate posting
        existing = JournalEntry.objects.filter(
            school=school,
            source_module="student_fees",
            source_reference=receipt.receipt_number,
            is_archived=False,
        ).first()
        if existing:
            return existing

        # Identify Debit Account (Cash / Bank)
        if receipt.payment_method == PaymentReceipt.PaymentMethod.BANK_TRANSFER:
            debit_acc = Account.objects.filter(school=school, code="1102", is_leaf=True).first()
        elif receipt.payment_method == PaymentReceipt.PaymentMethod.POS:
            debit_acc = Account.objects.filter(school=school, code="1103", is_leaf=True).first()
        else:
            debit_acc = Account.objects.filter(school=school, code="1101", is_leaf=True).first()

        # Identify Credit Account (Student Receivables 1104 or Tuition Revenue 4101)
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

        # 1. Debit Line (الطرف المدين: الصندوق أو البنك)
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=debit_acc,
            description=f"إيداع نقدي/بنكي لقاء سند قبض #{receipt.receipt_number}",
            debit=receipt.amount,
            credit=Decimal("0.00"),
        )

        # 2. Credit Line (الطرف الدائن: حساب ذمم الطلاب)
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=credit_acc,
            description=f"سداد رسوم الطالب: {receipt.student.first_name} {receipt.student.last_name}",
            debit=Decimal("0.00"),
            credit=receipt.amount,
        )

        return entry


def post_payment_voucher_to_journal(voucher: PaymentVoucher) -> JournalEntry:
    """
    الترحيل الآلي لسند الصرف المالي إلى قيد يومية محاسبي.
    الجانب المدين: حساب المصروف أو المورد (voucher.debit_account).
    الجانب الدائن: حساب الصندوق أو البنك (voucher.credit_account).
    """
    school = voucher.school
    period = _get_active_fiscal_period(school, voucher.date)

    with transaction.atomic():
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

        # Debit: Expense Account
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.debit_account,
            cost_center=voucher.cost_center,
            description=voucher.description or f"صرف إلى {voucher.paid_to}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        # Credit: Cash/Bank Account
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.credit_account,
            description=f"خروج نقدية لصالح {voucher.paid_to}",
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

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
    school = voucher.school
    period = _get_active_fiscal_period(school, voucher.date)

    with transaction.atomic():
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

        # Debit: Cash/Bank Account
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.debit_account,
            description=f"قبض نقدية من {voucher.received_from}",
            debit=voucher.amount,
            credit=Decimal("0.00"),
        )

        # Credit: Revenue Account
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=voucher.credit_account,
            cost_center=voucher.cost_center,
            description=voucher.description,
            debit=Decimal("0.00"),
            credit=voucher.amount,
        )

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
    school = entry.school
    period = _get_active_fiscal_period(school, entry.date)

    with transaction.atomic():
        depreciation_expense = Account.objects.filter(school=school, code="5209", is_leaf=True).first()
        accumulated_depreciation = Account.objects.filter(school=school, code="1209", is_leaf=True).first()

        if not depreciation_expense or not accumulated_depreciation:
            raise ValueError("حسابات إهلاك الأصول غير موجودة في دليل حسابات المدرسة.")

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

        # Debit: Depreciation Expense
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=journal_entry,
            account=depreciation_expense,
            description=f"مصروف إهلاك أصل [{entry.asset.code}] {entry.asset.name}",
            debit=entry.depreciation_amount,
            credit=Decimal("0.00"),
        )

        # Credit: Accumulated Depreciation
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=journal_entry,
            account=accumulated_depreciation,
            description=f"مجمع إهلاك الأصل [{entry.asset.code}]",
            debit=Decimal("0.00"),
            credit=entry.depreciation_amount,
        )

        # Update accumulated depreciation on the asset
        entry.asset.accumulated_depreciation += entry.depreciation_amount
        entry.asset.save(update_fields=["accumulated_depreciation"])

        return journal_entry


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
    """
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
        original_entry.status = JournalEntry.Status.CANCELLED
        original_entry.save(update_fields=["status", "updated_at"])

        return rev_entry
