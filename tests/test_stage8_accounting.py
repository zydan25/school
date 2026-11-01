from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import (
    Account, BankReconciliation, BankStatementLine, FiscalPeriod,
    FiscalYear, JournalEntry, JournalEntryLine, TreasuryAccount,
    TreasuryTransfer,
)
from apps.accounting.services.auto_posting import (
    _get_active_fiscal_period,
    reverse_journal_entry,
)
from apps.accounting.services.period_closing import (
    close_fiscal_period, close_fiscal_year, open_fiscal_year,
)
from apps.accounting.services.treasury import (
    complete_bank_reconciliation, create_treasury_transfer, reverse_treasury_transfer,
)
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import User
from apps.tenants.models import School
from apps.tenants.services import provision_school


class Stage8AccountingIntegrityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770008001",
            password="StrongPassword123!",
            first_name="مالك",
            last_name="المحاسبة",
        )
        self.school = School.objects.create(
            owner=self.owner,
            name="مدرسة المرحلة الثامنة",
            code="STAGE8",
            status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        seed_default_chart_of_accounts(self.school)
        today = timezone.localdate()
        self.year = FiscalYear.objects.create(
            school=self.school,
            name=f"السنة المالية {today.year}",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
        )
        self.period = self.make_current_period()

    def make_current_period(self, closed=False):
        today = timezone.localdate()
        first = date(today.year, today.month, 1)
        if today.month == 12:
            last = date(today.year, 12, 31)
        else:
            last = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return FiscalPeriod.objects.create(
            school=self.school,
            fiscal_year=self.year,
            period_number=today.month,
            name=f"فترة {today.month:02d}/{today.year}",
            start_date=first,
            end_date=last,
            is_closed=closed,
            closed_at=timezone.now() if closed else None,
        )

    def make_balanced_entry(self, *, period=None, entry_number="ST8-001", date_value=None):
        today = timezone.localdate()
        entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=period,
            entry_number=entry_number,
            date=date_value or today,
            description="قيد اختبار سلامة الدفتر العام",
            source_module="stage8_test",
            source_reference=entry_number,
        )
        cash = Account.objects.get(school=self.school, code="1101")
        revenue = Account.objects.get(school=self.school, code="4101")
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=cash,
            debit=Decimal("125.00"),
            credit=Decimal("0.00"),
            description="مدين",
        )
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=revenue,
            debit=Decimal("0.00"),
            credit=Decimal("125.00"),
            description="دائن",
        )
        return entry

    def test_fiscal_year_rejects_overlapping_years(self):
        duplicate = FiscalYear(
            school=self.school,
            name="سنة مالية متداخلة",
            start_date=date(self.year.start_date.year, 7, 1),
            end_date=date(self.year.end_date.year, 12, 31),
        )
        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_fiscal_period_rejects_overlapping_ranges(self):
        overlapping = FiscalPeriod(
            school=self.school,
            fiscal_year=self.year,
            period_number=12 if self.period.period_number != 12 else 11,
            name="فترة متداخلة",
            start_date=self.period.start_date - timedelta(days=1),
            end_date=self.period.end_date,
        )
        with self.assertRaises(ValidationError):
            overlapping.save()

    def test_active_period_helper_rejects_closed_period(self):
        close_fiscal_period(self.period, self.owner)
        with self.assertRaises(ValidationError):
            _get_active_fiscal_period(self.school, timezone.localdate())

    def test_posting_requires_a_fiscal_period(self):
        entry = self.make_balanced_entry(period=None, entry_number="ST8-NO-PERIOD")
        with self.assertRaises(ValidationError):
            entry.post(user=self.owner)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.DRAFT)

    def test_direct_status_change_cannot_bypass_posting_service(self):
        entry = self.make_balanced_entry(
            period=self.period,
            entry_number="ST8-DIRECT-POST",
        )
        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).update(
                status=JournalEntry.Status.POSTED,
            )
        entry.status = JournalEntry.Status.POSTED
        with self.assertRaises(ValidationError):
            entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.DRAFT)
        entry.post(user=self.owner)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

    def test_posting_rejects_closed_period(self):
        # Model a pre-existing draft that references a period subsequently closed.
        entry = self.make_balanced_entry(
            period=None,
            entry_number="ST8-CLOSED",
        )
        close_fiscal_period(self.period, self.owner)
        JournalEntry.objects.filter(pk=entry.pk).update(fiscal_period=self.period)
        entry.refresh_from_db()
        with self.assertRaises(ValidationError):
            entry.post(user=self.owner)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.DRAFT)

    def test_posting_rejects_duplicate_source_reference(self):
        self.make_balanced_entry(period=self.period, entry_number="ST8-SOURCE-1")
        duplicate = self.make_balanced_entry(period=self.period, entry_number="ST8-SOURCE-2")
        duplicate.source_reference = "ST8-SOURCE-1"
        duplicate.save(update_fields=["source_reference", "updated_at"])
        with self.assertRaises(ValidationError):
            duplicate.post(user=self.owner)

    def test_reversing_twice_returns_the_same_reversal_entry(self):
        original = self.make_balanced_entry(
            period=self.period,
            entry_number="ST8-REVERSAL",
        )
        original.post(user=self.owner)
        reversal = reverse_journal_entry(
            original,
            reason="اختبار عكس القيد",
            reversed_by=self.owner,
        )
        repeated = reverse_journal_entry(
            original,
            reason="إعادة إرسال طلب العكس",
            reversed_by=self.owner,
        )
        self.assertEqual(reversal.pk, repeated.pk)
        self.assertEqual(
            JournalEntry.objects.filter(
                school=self.school,
                source_module="reversal",
                source_reference=original.entry_number,
            ).count(),
            1,
        )
        original.refresh_from_db()
        self.assertTrue(original.is_reversed)
        self.assertEqual(original.reversed_by_entry_id, reversal.pk)

    def test_posted_entry_balances_and_is_immutable(self):
        entry = self.make_balanced_entry(
            period=self.period,
            entry_number="ST8-IMMUTABLE",
        )
        entry.post(user=self.owner)
        total_debit = sum(entry.lines.values_list("debit", flat=True), Decimal("0.00"))
        total_credit = sum(entry.lines.values_list("credit", flat=True), Decimal("0.00"))
        self.assertEqual(total_debit, total_credit)
        line = entry.lines.first()
        line.debit = Decimal("100.00")
        with self.assertRaises(ValidationError):
            line.save()

    def test_cash_to_bank_transfer_is_idempotent_and_reversible(self):
        cash = TreasuryAccount.objects.create(
            school=self.school, code="CASH-MAIN", name="الصندوق الرئيسي",
            kind=TreasuryAccount.Kind.CASH,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-MAIN", name="الحساب البنكي الرئيسي",
            kind=TreasuryAccount.Kind.BANK, bank_name="البنك التجريبي",
            bank_account_number="123456",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        transfer = create_treasury_transfer(
            source_account=cash, destination_account=bank,
            amount=Decimal("75.00"), transfer_number="TR-ST8-001",
            idempotency_key="stage8-transfer-001",
            description="إيداع نقدي في البنك", user=self.owner,
        )
        duplicate = create_treasury_transfer(
            source_account=cash, destination_account=bank,
            amount=Decimal("75.00"), transfer_number="TR-ST8-001",
            idempotency_key="stage8-transfer-001",
            description="إعادة إرسال الطلب", user=self.owner,
        )
        self.assertEqual(transfer.pk, duplicate.pk)
        self.assertEqual(transfer.status, TreasuryTransfer.Status.POSTED)
        self.assertEqual(transfer.journal_entry.status, JournalEntry.Status.POSTED)
        self.assertEqual(
            sum(transfer.journal_entry.lines.values_list("debit", flat=True)),
            Decimal("75.00"),
        )
        reverse_treasury_transfer(
            transfer, reason="اختبار عكس تحويل الخزينة", reversed_by=self.owner,
        )
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, TreasuryTransfer.Status.REVERSED)
        self.assertIsNotNone(transfer.reversed_by_entry_id)

    def test_treasury_account_identity_is_immutable_after_posted_transfer(self):
        cash = TreasuryAccount.objects.create(
            school=self.school, code="CASH-LOCKED", name="صندوق ثابت",
            kind=TreasuryAccount.Kind.CASH,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-LOCKED", name="بنك ثابت",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        create_treasury_transfer(
            source_account=cash, destination_account=bank,
            amount=Decimal("10.00"), transfer_number="TR-LOCKED-001",
            idempotency_key="transfer-locked-001",
            description="اختبار تثبيت هوية الخزينة", user=self.owner,
        )
        cash.refresh_from_db()
        cash.code = "CASH-RENAMED"
        with self.assertRaises(ValidationError):
            cash.save()
        cash.refresh_from_db()
        self.assertEqual(cash.code, "CASH-LOCKED")

    def test_only_one_default_treasury_account_per_kind(self):
        TreasuryAccount.objects.create(
            school=self.school, code="CASH-DEFAULT-1", name="الصندوق الافتراضي",
            kind=TreasuryAccount.Kind.CASH, is_default=True,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        duplicate = TreasuryAccount(
            school=self.school, code="CASH-DEFAULT-2", name="صندوق افتراضي ثان",
            kind=TreasuryAccount.Kind.CASH, is_default=True,
            account=Account.objects.get(school=self.school, code="1102"),
        )
        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_treasury_transfer_cannot_be_posted_or_reversed_directly(self):
        cash = TreasuryAccount.objects.create(
            school=self.school, code="CASH-DIRECT-STATE", name="صندوق حالات مباشرة",
            kind=TreasuryAccount.Kind.CASH,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-DIRECT-STATE", name="بنك حالات مباشرة",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        transfer = TreasuryTransfer.objects.create(
            school=self.school,
            transfer_number="TR-DIRECT-STATE",
            source_account=cash,
            destination_account=bank,
            amount=Decimal("20.00"),
            description="اختبار منع تغيير الحالة المباشر",
            idempotency_key="direct-state-transfer-001",
        )
        transfer.status = TreasuryTransfer.Status.POSTED
        with self.assertRaises(ValidationError):
            transfer.save()
        transfer.status = TreasuryTransfer.Status.REVERSED
        with self.assertRaises(ValidationError):
            transfer.save()
        with self.assertRaises(ValidationError):
            TreasuryTransfer.objects.filter(pk=transfer.pk).update(
                status=TreasuryTransfer.Status.POSTED,
            )

    def test_treasury_transfer_reversal_is_idempotent(self):
        cash = TreasuryAccount.objects.create(
            school=self.school, code="CASH-REVERSE", name="صندوق العكس",
            kind=TreasuryAccount.Kind.CASH,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-REVERSE", name="بنك العكس",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        transfer = create_treasury_transfer(
            source_account=cash, destination_account=bank,
            amount=Decimal("30.00"), transfer_number="TR-REVERSE-001",
            idempotency_key="transfer-reverse-001",
            description="تحويل لاختبار العكس", user=self.owner,
        )
        reversed_transfer = reverse_treasury_transfer(
            transfer, reason="اختبار عكس التحويل", reversed_by=self.owner,
        )
        repeated = reverse_treasury_transfer(
            transfer, reason="إعادة طلب العكس", reversed_by=self.owner,
        )
        self.assertEqual(reversed_transfer.status, TreasuryTransfer.Status.REVERSED)
        self.assertEqual(repeated.pk, reversed_transfer.pk)
        self.assertEqual(repeated.reversed_by_entry_id, reversed_transfer.reversed_by_entry_id)

    def test_transfer_idempotency_key_rejects_different_amount(self):
        cash = TreasuryAccount.objects.create(
            school=self.school, code="CASH-2", name="صندوق 2",
            kind=TreasuryAccount.Kind.CASH,
            account=Account.objects.get(school=self.school, code="1101"),
        )
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-2", name="بنك 2",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك تجريبي",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        create_treasury_transfer(
            source_account=cash, destination_account=bank,
            amount=Decimal("50.00"), transfer_number="TR-ST8-002",
            idempotency_key="stage8-transfer-002",
            description="تحويل تجريبي", user=self.owner,
        )
        with self.assertRaises(ValidationError):
            create_treasury_transfer(
                source_account=cash, destination_account=bank,
                amount=Decimal("55.00"), transfer_number="TR-ST8-002",
                idempotency_key="stage8-transfer-002",
                description="بيانات مختلفة", user=self.owner,
            )

    def test_bank_statement_reconciles_to_general_ledger(self):
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-RECON", name="بنك المطابقة",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        entry = JournalEntry.objects.create(
            school=self.school, fiscal_period=self.period,
            entry_number="ST8-BANK-001", date=timezone.localdate(),
            description="إيداع بنكي للاختبار",
            source_module="stage8_bank", source_reference="bank-deposit-001",
        )
        bank_line = JournalEntryLine.objects.create(
            school=self.school, journal_entry=entry, account=bank.account,
            debit=Decimal("200.00"), credit=Decimal("0.00"),
            description="إيداع في البنك",
        )
        JournalEntryLine.objects.create(
            school=self.school, journal_entry=entry,
            account=Account.objects.get(school=self.school, code="4101"),
            debit=Decimal("0.00"), credit=Decimal("200.00"),
            description="إيراد",
        )
        entry.post(user=self.owner)
        reconciliation = BankReconciliation.objects.create(
            school=self.school, treasury_account=bank,
            start_date=timezone.localdate(), end_date=timezone.localdate(),
            statement_opening_balance=Decimal("0.00"),
            statement_closing_balance=Decimal("200.00"),
        )
        BankStatementLine.objects.create(
            school=self.school, reconciliation=reconciliation,
            transaction_date=timezone.localdate(),
            external_reference="BANK-EXT-001",
            amount=Decimal("200.00"), journal_line=bank_line,
        )
        completed = complete_bank_reconciliation(
            reconciliation, reconciled_by=self.owner,
        )
        self.assertEqual(completed.status, BankReconciliation.Status.RECONCILED)
        self.assertEqual(completed.difference, Decimal("0.00"))
        self.assertEqual(completed.book_closing_balance, Decimal("200.00"))

        statement_line = BankStatementLine.objects.get(pk=BankStatementLine.objects.get(
            reconciliation=reconciliation,
        ).pk)
        statement_line.amount = Decimal("250.00")
        with self.assertRaises(ValidationError):
            statement_line.save()
        with self.assertRaises(ValidationError):
            BankStatementLine.objects.filter(pk=statement_line.pk).update(
                amount=Decimal("250.00"),
            )
        with self.assertRaises(ValidationError):
            BankStatementLine.objects.filter(pk=statement_line.pk).delete()

    def test_bank_reconciliation_rejects_direct_approval(self):
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-DIRECT-APPROVAL",
            name="بنك اختبار الاعتماد المباشر",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        reconciliation = BankReconciliation.objects.create(
            school=self.school, treasury_account=bank,
            start_date=timezone.localdate(), end_date=timezone.localdate(),
            statement_opening_balance=Decimal("0.00"),
            statement_closing_balance=Decimal("0.00"),
        )
        reconciliation.status = BankReconciliation.Status.RECONCILED
        reconciliation.reconciled_at = timezone.now()
        reconciliation.reconciled_by = self.owner
        with self.assertRaises(ValidationError):
            reconciliation.save()
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, BankReconciliation.Status.DRAFT)

    def test_bank_reconciliation_rejects_unmatched_statement_line(self):
        bank = TreasuryAccount.objects.create(
            school=self.school, code="BANK-UNMATCHED", name="بنك غير مطابق",
            kind=TreasuryAccount.Kind.BANK, bank_name="بنك الاختبار",
            account=Account.objects.get(school=self.school, code="1102"),
        )
        reconciliation = BankReconciliation.objects.create(
            school=self.school, treasury_account=bank,
            start_date=timezone.localdate(), end_date=timezone.localdate(),
            statement_opening_balance=Decimal("0.00"),
            statement_closing_balance=Decimal("25.00"),
        )
        BankStatementLine.objects.create(
            school=self.school, reconciliation=reconciliation,
            transaction_date=timezone.localdate(),
            external_reference="BANK-UNMATCHED-001",
            amount=Decimal("25.00"),
        )
        with self.assertRaises(ValidationError):
            complete_bank_reconciliation(
                reconciliation, reconciled_by=self.owner,
            )

    def test_direct_fiscal_closure_cannot_bypass_services(self):
        period = FiscalPeriod.objects.get(pk=self.period.pk)
        period.is_closed = True
        period.closed_at = timezone.now()
        period.closed_by = self.owner
        with self.assertRaises(ValidationError):
            period.save()
        period.refresh_from_db()
        self.assertFalse(period.is_closed)

        year = FiscalYear.objects.get(pk=self.year.pk)
        year.is_closed = True
        year.closed_at = timezone.now()
        year.closed_by = self.owner
        with self.assertRaises(ValidationError):
            year.save()
        year.refresh_from_db()
        self.assertFalse(year.is_closed)

    def test_period_and_year_closure_record_audit_data(self):
        close_fiscal_period(self.period, self.owner)
        self.period.refresh_from_db()
        self.assertTrue(self.period.is_closed)
        self.assertEqual(self.period.closed_by_id, self.owner.pk)
        self.assertIsNotNone(self.period.closed_at)
        with self.assertRaises(ValidationError):
            FiscalPeriod.objects.filter(pk=self.period.pk).update(is_closed=False)

    def test_year_closure_requires_full_period_coverage_and_records_closing(self):
        import calendar

        for month in range(1, 13):
            if month == self.period.period_number:
                continue
            last_day = calendar.monthrange(self.year.start_date.year, month)[1]
            FiscalPeriod.objects.create(
                school=self.school, fiscal_year=self.year,
                period_number=month, name=f"فترة {month}",
                start_date=date(self.year.start_date.year, month, 1),
                end_date=date(self.year.start_date.year, month, last_day),
            )
        for period in self.year.periods.order_by("period_number"):
            close_fiscal_period(period, self.owner)
        closed_year = close_fiscal_year(self.year, self.owner)
        self.assertTrue(closed_year.is_closed)
        self.assertEqual(closed_year.closed_by_id, self.owner.pk)
        self.assertIsNotNone(closed_year.closed_at)
        with self.assertRaises(ValidationError):
            FiscalYear.objects.filter(pk=self.year.pk).update(is_closed=False)

    def test_opening_entry_carries_forward_balance_sheet_accounts(self):
        import calendar

        previous = FiscalYear.objects.create(
            school=self.school, name="السنة السابقة",
            start_date=date(self.year.start_date.year - 1, 1, 1),
            end_date=date(self.year.start_date.year - 1, 12, 31),
        )
        previous_periods = []
        for month in range(1, 13):
            last_day = calendar.monthrange(previous.start_date.year, month)[1]
            previous_periods.append(FiscalPeriod.objects.create(
                school=self.school, fiscal_year=previous,
                period_number=month, name=f"سنة سابقة - {month}",
                start_date=date(previous.start_date.year, month, 1),
                end_date=date(previous.start_date.year, month, last_day),
            ))
        prior_entry = JournalEntry.objects.create(
            school=self.school, fiscal_period=previous_periods[-1],
            entry_number="ST8-PRIOR-BALANCE", date=previous.end_date,
            description="رصيد افتتاحي للاختبار",
            source_module="stage8_opening_test", source_reference="prior-balance-1",
        )
        JournalEntryLine.objects.create(
            school=self.school, journal_entry=prior_entry,
            account=Account.objects.get(school=self.school, code="1102"),
            debit=Decimal("300.00"), credit=Decimal("0.00"),
        )
        JournalEntryLine.objects.create(
            school=self.school, journal_entry=prior_entry,
            account=Account.objects.get(school=self.school, code="3101"),
            debit=Decimal("0.00"), credit=Decimal("300.00"),
        )
        prior_entry.post(user=self.owner)
        for period in previous_periods:
            close_fiscal_period(period, self.owner)
        close_fiscal_year(previous, self.owner)

        first_day = self.year.start_date
        if not self.year.periods.filter(
            start_date__lte=first_day, end_date__gte=first_day,
        ).exists():
            FiscalPeriod.objects.create(
                school=self.school, fiscal_year=self.year,
                period_number=1, name="الفترة الافتتاحية",
                start_date=first_day, end_date=date(first_day.year, 1, 31),
            )
        opening = open_fiscal_year(self.year, previous, user=self.owner)
        self.assertIsNotNone(opening)
        self.assertEqual(opening.status, JournalEntry.Status.POSTED)
        self.assertEqual(
            sum(opening.lines.values_list("debit", flat=True)),
            sum(opening.lines.values_list("credit", flat=True)),
        )
        repeated = open_fiscal_year(self.year, previous, user=self.owner)
        self.assertEqual(opening.pk, repeated.pk)
