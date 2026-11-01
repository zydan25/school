from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import (
    Account,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
)
from apps.accounting.services.auto_posting import (
    _get_active_fiscal_period,
    reverse_journal_entry,
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
        self.period.is_closed = True
        self.period.closed_at = timezone.now()
        self.period.save(update_fields=["is_closed", "closed_at", "updated_at"])
        with self.assertRaises(ValidationError):
            _get_active_fiscal_period(self.school, timezone.localdate())

    def test_posting_requires_a_fiscal_period(self):
        entry = self.make_balanced_entry(period=None, entry_number="ST8-NO-PERIOD")
        with self.assertRaises(ValidationError):
            entry.post(user=self.owner)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.DRAFT)

    def test_posting_rejects_closed_period(self):
        self.period.is_closed = True
        self.period.closed_at = timezone.now()
        self.period.save(update_fields=["is_closed", "closed_at", "updated_at"])
        entry = self.make_balanced_entry(
            period=self.period,
            entry_number="ST8-CLOSED",
        )
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
