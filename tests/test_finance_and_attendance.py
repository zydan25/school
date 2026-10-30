from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section, Subject
from apps.attendance.models import DailyAttendance
from apps.student_fees.models import FeeCategory, FeeStructure, PaymentReceipt, StudentInvoice, StudentInvoiceItem
from apps.accounting.models import Account, FiscalYear, JournalEntry, JournalEntryLine
from apps.students.models import Student
from apps.tenants.models import School


class FinanceAndAttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            phone="+967777222001", password="StrongPassword123!",
            first_name="محمد", last_name="المدير",
        )
        cls.school = School.objects.create(owner=cls.user, code="SCH_FIN_1", name="مدرسة الرواد الأهلية", status=School.Status.ACTIVE)
        cls.academic_year = AcademicYear.objects.create(school=cls.school, code="2026-2027", name="2026-2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30))
        cls.stage = EducationalStage.objects.create(school=cls.school, code="PRI", name="المرحلة الابتدائية", sequence=1)
        cls.grade = GradeLevel.objects.create(school=cls.school, stage=cls.stage, code="G1", name="الصف الأول", sequence=1)
        cls.section = Section.objects.create(school=cls.school, academic_year=cls.academic_year, grade=cls.grade, code="1-A", name="أول / أ")

        cls.student = Student.objects.create(
            school=cls.school,
            student_id_number="STD-FIN-1",
            first_name="يوسف",
            last_name="المتفوق",
            grade_level=cls.grade,
            section=cls.section,
            academic_year=cls.academic_year,
        )

    def test_daily_attendance_creation_and_unique(self):
        """التحقق من إنشاء سجل الحضور اليومي ومنع تكرار نفس الطالب في نفس اليوم."""
        DailyAttendance.objects.create(
            school=self.school,
            student=self.student,
            date=date(2026, 10, 30),
            status=DailyAttendance.Status.PRESENT,
        )
        # Attempting duplicate date for same student
        dup = DailyAttendance(
            school=self.school,
            student=self.student,
            date=date(2026, 10, 30),
            status=DailyAttendance.Status.LATE,
            late_minutes=15,
        )
        with self.assertRaises(Exception):
            dup.save()

    def test_student_invoice_and_receipt_flow(self):
        """التحقق من دورة فوترة رسوم الطالب وسند القبض."""
        fee_cat = FeeCategory.objects.create(school=self.school, code="TUITION", name="رسوم دراسية سنوية")
        FeeStructure.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            grade_level=self.grade,
            fee_category=fee_cat,
            amount=Decimal("150000.00"),
        )

        invoice = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-2026-001",
            total_amount=Decimal("150000.00"),
            discount_amount=Decimal("10000.00"),
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 12, 31),
        )

        StudentInvoiceItem.objects.create(
            school=self.school,
            invoice=invoice,
            fee_category=fee_cat,
            description="القسط الدراسي الأول",
            amount=Decimal("150000.00"),
            discount_amount=Decimal("10000.00"),
        )

        # Net payable is 140,000
        self.assertEqual(invoice.remaining_amount, Decimal("140000.00"))

        # Pay 50,000
        receipt = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=invoice,
            receipt_number="RCP-2026-001",
            amount=Decimal("50000.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("50000.00"))
        self.assertEqual(invoice.status, StudentInvoice.Status.PARTIAL)
        self.assertEqual(invoice.remaining_amount, Decimal("90000.00"))

    def test_double_entry_accounting_lines(self):
        """التحقق من إنشاء حسابات مالية وخطوط القيد اليومي."""
        fy = FiscalYear.objects.create(school=self.school, name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        
        # Accounts: Cash and Tuition Revenue
        cash_account = Account.objects.create(school=self.school, code="1101", name="الصندوق الرئيسي", account_type=Account.AccountType.ASSET, is_leaf=True)
        revenue_account = Account.objects.create(school=self.school, code="4101", name="إيرادات الرسوم الدراسية", account_type=Account.AccountType.REVENUE, is_leaf=True)

        entry = JournalEntry.objects.create(
            school=self.school,
            entry_number="JE-2026-001",
            date=date(2026, 10, 30),
            description="إثبات تحصيل قسط دراسي نقداً",
            status=JournalEntry.Status.POSTED,
            source_module="student_fees",
        )

        # Debit cash
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=cash_account,
            debit=Decimal("50000.00"),
            credit=Decimal("0.00"),
            description="تحصيل من الطالب يوسف",
        )
        # Credit revenue
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=revenue_account,
            debit=Decimal("0.00"),
            credit=Decimal("50000.00"),
            description="إيراد رسوم",
        )

        total_debit = sum(line.debit for line in entry.lines.all())
        total_credit = sum(line.credit for line in entry.lines.all())
        self.assertEqual(total_debit, total_credit)
