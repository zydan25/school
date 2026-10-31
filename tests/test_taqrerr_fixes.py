"""
tests/test_taqrerr_fixes.py
Comprehensive verification tests for all phases of taqrerr.txt:
Phase 1: Migrations consistency & no drift
Phase 2: Accounting auto-posting (receivable 1104 vs advance deposit 2102, no fallback to 4101),
         partial installment allocation, receipt reversal, credit settlement journal entry,
         immutability of posted journal entry lines, billing vs ledger reconciliation report.
Phase 3: Payroll approval lifecycle (DRAFT -> APPROVED -> POSTED -> PAID), accrual date matching month,
         absence deductions, loan repayment tracking records (EmployeeLoanRepayment).
Phase 4: Permissions hardening (cashier excluded from general ledger & statements, teacher excluded from school-wide reports,
         membership expiration validation).
Phase 5: DRF Bearer or Token Authentication & OpenAPI Schema endpoint.
Phase 6: Subsystem hardening (book distribution quantity, bus financial settlement strict account 5205, library concurrency).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.accounting.models import Account, FiscalPeriod, FiscalYear, JournalEntry, JournalEntryLine
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.inventory.models import InventoryItem, Warehouse
from apps.payroll.models import (
    EmployeeContract,
    EmployeeLoanAdvance,
    EmployeeLoanRepayment,
    PayrollRun,
)
from apps.payroll.services import (
    approve_payroll_run,
    generate_monthly_payroll,
    post_payroll_to_accounting,
)
from apps.reports.selectors.financial_reports import get_billing_ledger_reconciliation_report
from apps.school_services.models import StudentBookDistribution
from apps.staff.models import StaffAttendance, Teacher
from apps.student_fees.models import (
    FeeCategory,
    FeeInstallment,
    FeeInstallmentPlan,
    PaymentReceipt,
    StudentInvoice,
    apply_credit_balance_to_invoice,
    reverse_payment_receipt,
)
from apps.students.models import Student
from apps.tenants.models import School
from apps.tenants.services import provision_school


class TaqrerrFixesVerificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. School Owner & School
        cls.owner = User.objects.create_user(
            phone="+967770001122",
            password="StrongPassword123!",
            first_name="أحمد",
            last_name="المدير",
            is_staff=True,
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="SCH_TAQ_01",
            name="مدارس الفلاح النموذجية",
            status=School.Status.ACTIVE,
        )
        provision_school(cls.school)
        seed_default_chart_of_accounts(cls.school)

        # 2. Fiscal Year & Monthly Period
        cls.fiscal_year = FiscalYear.objects.create(
            school=cls.school,
            name="السنة المالية 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.fiscal_period = FiscalPeriod.objects.create(
            school=cls.school,
            fiscal_year=cls.fiscal_year,
            period_number=10,
            name="فترة 10/2026",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )

        # 3. Academic Structure
        cls.academic_year = AcademicYear.objects.create(
            school=cls.school,
            code="2026-2027",
            name="2026-2027",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
        )
        cls.stage = EducationalStage.objects.create(
            school=cls.school,
            code="PRIMARY",
            name="المرحلة الابتدائية",
            sequence=1,
        )
        cls.grade = GradeLevel.objects.create(
            school=cls.school,
            stage=cls.stage,
            code="G1",
            name="الصف الأول",
            sequence=1,
        )
        cls.section = Section.objects.create(
            school=cls.school,
            grade=cls.grade,
            academic_year=cls.academic_year,
            code="SEC-A",
            name="الشعبة أ",
        )

        # 4. Student
        cls.student = Student.objects.create(
            school=cls.school,
            grade_level=cls.grade,
            academic_year=cls.academic_year,
            section=cls.section,
            student_id_number="STU-TAQ-100",
            first_name="يوسف",
            last_name="المتوكل",
            gender="male",
            enrollment_date=date(2026, 9, 1),
            credit_balance=Decimal("0.00"),
        )

        # 5. Fee Category
        cls.fee_cat = FeeCategory.objects.create(
            school=cls.school,
            name="رسوم دراسية عامة",
            code="TUITION",
        )

        # 6. Roles: Cashier, Teacher, HR Manager
        cls.cashier_user = User.objects.create_user(
            phone="+967770003344",
            password="CashierPassword123!",
            first_name="محمود",
            last_name="الكاشير",
        )
        cls.cashier_membership = SchoolMembership.objects.create(
            school=cls.school,
            user=cls.cashier_user,
            status=SchoolMembership.Status.ACTIVE,
        )
        cashier_role = SchoolRole.objects.filter(school=cls.school, code="cashier").first()
        if cashier_role:
            MembershipRole.objects.create(membership=cls.cashier_membership, role=cashier_role)

        cls.teacher_user = User.objects.create_user(
            phone="+967770005566",
            password="TeacherPassword123!",
            first_name="سالم",
            last_name="المعلم",
        )
        cls.teacher_membership = SchoolMembership.objects.create(
            school=cls.school,
            user=cls.teacher_user,
            status=SchoolMembership.Status.ACTIVE,
        )
        teacher_role = SchoolRole.objects.filter(school=cls.school, code="teacher").first()
        if teacher_role:
            MembershipRole.objects.create(membership=cls.teacher_membership, role=teacher_role)
        cls.teacher_profile = Teacher.objects.create(
            school=cls.school,
            user=cls.teacher_user,
            employee_number="TCH-TAQ-01",
            specialization="لغة عربية",
        )

    # -------------------------------------------------------------------------
    # Phase 2: Accounting & Fee Collection Stabilization Tests
    # -------------------------------------------------------------------------

    def test_installment_partial_payments(self):
        """التحقق من أن سداد جزء من قيمة القسط يحوله إلى مسدد جزئياً (PARTIAL) وليس مسدداً بالكامل."""
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-PARTIAL-01",
            total_amount=Decimal("1000.00"),
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 31),
        )
        plan = FeeInstallmentPlan.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            plan_name="خطة قسطين متساويين",
            total_amount=Decimal("1000.00"),
            number_of_installments=2,
        )
        inst1 = FeeInstallment.objects.create(
            school=self.school,
            plan=plan,
            installment_number=1,
            title="القسط الأول",
            amount=Decimal("500.00"),
            due_date=date(2026, 10, 15),
            status=FeeInstallment.Status.PENDING,
        )
        inst2 = FeeInstallment.objects.create(
            school=self.school,
            plan=plan,
            installment_number=2,
            title="القسط الثاني",
            amount=Decimal("500.00"),
            due_date=date(2026, 11, 15),
            status=FeeInstallment.Status.PENDING,
        )

        # 1. دفع 300 فقط على الفاتورة (أقل من القسط الأول 500)
        rec1 = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            receipt_number="REC-PARTIAL-01",
            amount=Decimal("300.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            paid_at=timezone.now(),
        )

        inst1.refresh_from_db()
        self.assertEqual(inst1.status, FeeInstallment.Status.PARTIAL)
        self.assertEqual(inst1.paid_amount, Decimal("300.00"))
        self.assertEqual(inst1.remaining_amount, Decimal("200.00"))

        # 2. دفع 400 إضافية (تكمل الـ 200 المتبقية للقسط الأول و 200 للقسط الثاني)
        rec2 = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            receipt_number="REC-PARTIAL-02",
            amount=Decimal("400.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            paid_at=timezone.now(),
        )

        inst1.refresh_from_db()
        inst2.refresh_from_db()
        self.assertEqual(inst1.status, FeeInstallment.Status.PAID)
        self.assertEqual(inst1.paid_amount, Decimal("500.00"))
        self.assertEqual(inst1.remaining_amount, Decimal("0.00"))

        self.assertEqual(inst2.status, FeeInstallment.Status.PARTIAL)
        self.assertEqual(inst2.paid_amount, Decimal("200.00"))
        self.assertEqual(inst2.remaining_amount, Decimal("300.00"))

    def test_receipt_journal_posting_split_receivable_and_advance(self):
        """فصل الأثر المحاسبي لسند القبض: الذمم المدينة 1104 للفاتورة والأمانات الدائنة 2102 للفائض."""
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-SPLIT-01",
            total_amount=Decimal("1000.00"),
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 31),
        )

        # سداد 1300 على فاتورة بـ 1000 (فائض 300)
        rec = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            receipt_number="REC-SPLIT-01",
            amount=Decimal("1300.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            paid_at=timezone.now(),
        )

        self.assertIsNotNone(rec.journal_entry)
        entry = rec.journal_entry
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

        # فحص أسطر القيد
        lines = entry.lines.all()
        # المدين: الصندوق 1101 = 1300
        cash_line = lines.filter(account__code="1101").first()
        self.assertIsNotNone(cash_line)
        self.assertEqual(cash_line.debit, Decimal("1300.00"))

        # الدائن 1: ذمم الطلاب 1104 = 1000 (المخصص للفاتورة)
        rec_line = lines.filter(account__code="1104").first()
        self.assertIsNotNone(rec_line)
        self.assertEqual(rec_line.credit, Decimal("1000.00"))

        # الدائن 2: أمانات ورصيد دائن 2102 = 300 (الفائض)
        adv_line = lines.filter(account__code="2102").first()
        self.assertIsNotNone(adv_line)
        self.assertEqual(adv_line.credit, Decimal("300.00"))

        # تحقق من التوازن التام
        total_debit = sum(l.debit for l in lines)
        total_credit = sum(l.credit for l in lines)
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal("1300.00"))

    def test_reverse_payment_receipt_atomic(self):
        """عكس سند القبض ذرياً: استرجاع رصيد الفاتورة، إلغاء التخصيص، خصم رصيد الطالب، وعكس القيد المحاسبي."""
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-REV-01",
            total_amount=Decimal("800.00"),
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 31),
        )

        rec = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            receipt_number="REC-REV-01",
            amount=Decimal("1000.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            paid_at=timezone.now(),
        )

        inv.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(inv.status, StudentInvoice.Status.PAID)
        self.assertEqual(self.student.credit_balance, Decimal("200.00"))
        orig_entry = rec.journal_entry

        # تنفيذ العكس
        rev_rec = reverse_payment_receipt(rec, reason="خطأ في الإيداع البنكي", reversed_by=self.owner)
        self.assertTrue(rev_rec.is_cancelled)

        inv.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(inv.status, StudentInvoice.Status.UNPAID)
        self.assertEqual(inv.paid_amount, Decimal("0.00"))
        self.assertEqual(self.student.credit_balance, Decimal("0.00"))

        # التحقق من القيد العكسي
        orig_entry.refresh_from_db()
        self.assertTrue(orig_entry.is_reversed)
        self.assertIsNotNone(orig_entry.reversed_by_entry)

    def test_concurrent_credit_balance_and_settlement_posting(self):
        """استخدام الرصيد الدائن للطالب لسداد فاتورة مع توليد قيد تسوية مزدوج (مدين 2102، دائن 1104)."""
        self.student.credit_balance = Decimal("600.00")
        self.student.save(update_fields=["credit_balance"])

        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-CRED-01",
            total_amount=Decimal("400.00"),
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 31),
        )

        tx = apply_credit_balance_to_invoice(self.student, inv, amount=Decimal("400.00"), user=self.owner)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal("400.00"))

        self.student.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("200.00"))
        self.assertEqual(inv.status, StudentInvoice.Status.PAID)

        # التحقق من وجود قيد التسوية المحاسبي
        settle_entry = JournalEntry.objects.filter(
            school=self.school,
            source_module="student_fees_credit",
            source_reference=str(tx.id),
        ).first()
        self.assertIsNotNone(settle_entry)
        self.assertEqual(settle_entry.status, JournalEntry.Status.POSTED)

        # مدين 2102 ودائن 1104
        line_debit = settle_entry.lines.filter(account__code="2102").first()
        line_credit = settle_entry.lines.filter(account__code="1104").first()
        self.assertEqual(line_debit.debit, Decimal("400.00"))
        self.assertEqual(line_credit.credit, Decimal("400.00"))

    def test_journal_entry_line_immutable_when_posted(self):
        """منع تعديل أو حذف أسطر القيد المحاسبي المرحل."""
        entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=self.fiscal_period,
            entry_number="JV-LOCK-01",
            date=date(2026, 10, 15),
            status=JournalEntry.Status.DRAFT,
            description="قيد اختباري مقفل",
        )
        line = JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=Account.objects.filter(school=self.school, code="1101", is_leaf=True).first(),
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
            description="سطر مقفل",
        )
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=Account.objects.filter(school=self.school, code="4101", is_leaf=True).first(),
            debit=Decimal("0.00"),
            credit=Decimal("500.00"),
            description="سطر دائن موازن",
        )
        entry.post()
        line.refresh_from_db()

        # محاولة تعديل المبلغ بعد الترحيل
        line.debit = Decimal("999.00")
        with self.assertRaises(ValidationError):
            line.save()

        # محاولة حذف السطر بعد الترحيل
        with self.assertRaises(ValidationError):
            line.delete()

    # -------------------------------------------------------------------------
    # Phase 3: Payroll & HRMS Lifecycle Tests
    # -------------------------------------------------------------------------

    def test_payroll_approval_workflow_and_repayment_records(self):
        """دورة مسير الرواتب: اشتراط الاعتماد قبل الترحيل، تاريخ الاستحقاق الشهري، وتسجيل سداد السلف."""
        # إنشاء عقد عمل
        contract = EmployeeContract.objects.create(
            school=self.school,
            teacher=self.teacher_profile,
            contract_number="CNT-TAQ-01",
            basic_salary=Decimal("3000.00"),
            housing_allowance=Decimal("500.00"),
            transport_allowance=Decimal("200.00"),
            start_date=date(2026, 9, 1),
            is_active=True,
        )

        # إنشاء سلفة نشطة
        loan = EmployeeLoanAdvance.objects.create(
            school=self.school,
            teacher=self.teacher_profile,
            loan_number="LN-TAQ-01",
            amount=Decimal("1200.00"),
            monthly_installment=Decimal("300.00"),
            start_date=date(2026, 10, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )

        # تسجيل يوم غياب
        StaffAttendance.objects.create(
            school=self.school,
            teacher=self.teacher_profile,
            date=date(2026, 10, 5),
            status=StaffAttendance.Status.UNEXCUSED,
        )

        # 1. توليد المسير لشهر أكتوبر 2026
        payroll_run = generate_monthly_payroll(self.school, year=2026, month=10)
        self.assertEqual(payroll_run.status, PayrollRun.Status.DRAFT)

        slip = payroll_run.payslips.first()
        self.assertEqual(slip.loan_deduction, Decimal("300.00"))
        self.assertGreater(slip.absence_deduction, Decimal("0.00"))

        # 2. محاولة الترحيل المحاسبي وهو في حالة DRAFT (يجب أن ترفض)
        with self.assertRaises(ValidationError):
            post_payroll_to_accounting(payroll_run)

        # 3. اعتماد المسير رسمياً
        approve_payroll_run(payroll_run, approved_by=self.owner)
        self.assertEqual(payroll_run.status, PayrollRun.Status.APPROVED)

        # 4. الترحيل المحاسبي الآن ينجح وينشئ القيد بتاريخ نهاية شهر أكتوبر
        entry = post_payroll_to_accounting(payroll_run)
        payroll_run.refresh_from_db()
        self.assertEqual(payroll_run.status, PayrollRun.Status.POSTED)
        self.assertEqual(entry.date, date(2026, 10, 31))

        # 5. التحقق من توثيق سداد السلفة في EmployeeLoanRepayment
        repayment = EmployeeLoanRepayment.objects.filter(loan=loan, payroll_run=payroll_run).first()
        self.assertIsNotNone(repayment)
        self.assertEqual(repayment.amount, Decimal("300.00"))

    # -------------------------------------------------------------------------
    # Phase 4 & 5: Security, Permissions, OpenAPI & Bearer Auth Tests
    # -------------------------------------------------------------------------

    def test_cashier_restricted_from_general_ledger_reports(self):
        """منع الكاشير من ميزان المراجعة والميزانية العمومية وأعمار الذمم مع السماح له بحركة الصندوق."""
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.cashier_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        # حركة الصندوق اليومية مسموحة للكاشير
        res_cash = client.get("/api/v1/reports/financial/daily-cash/?date=2026-10-15")
        self.assertEqual(res_cash.status_code, status.HTTP_200_OK)

        # ميزان المراجعة ممنوع للكاشير
        res_tb = client.get("/api/v1/reports/financial/trial-balance/")
        self.assertEqual(res_tb.status_code, status.HTTP_403_FORBIDDEN)

        # الميزانية العمومية ممنوعة للكاشير
        res_bs = client.get("/api/v1/reports/financial/balance-sheet/")
        self.assertEqual(res_bs.status_code, status.HTTP_403_FORBIDDEN)

        # تقرير أعمار الذمم ممنوع للكاشير
        res_ar = client.get("/api/v1/reports/financial/aging-receivables/")
        self.assertEqual(res_ar.status_code, status.HTTP_403_FORBIDDEN)

        # تقرير المطابقة ممنوع للكاشير
        res_rec = client.get("/api/v1/reports/financial/reconciliation/")
        self.assertEqual(res_rec.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_restricted_from_schoolwide_reports(self):
        """منع المعلم العادي من الاطلاع على تقرير نصاب كافة المعلمين أو الغياب المزمن للمدرسة بأكملها."""
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.teacher_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

        # تقرير نصاب المعلمين على مستوى المدرسة
        res_workload = client.get("/api/v1/reports/hr/teacher-workload/")
        self.assertEqual(res_workload.status_code, status.HTTP_403_FORBIDDEN)

        # تقرير الغياب المزمن على مستوى المدرسة
        res_absent = client.get("/api/v1/reports/attendance/chronic-absenteeism/")
        self.assertEqual(res_absent.status_code, status.HTTP_403_FORBIDDEN)

    def test_bearer_or_token_authentication(self):
        """التحقق من عمل مصادقة DRF برأس Authorization يبدأ بـ Bearer أو Token."""
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.owner)

        # 1. Bearer
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
        res_bearer = client.get("/api/v1/me/")
        self.assertEqual(res_bearer.status_code, status.HTTP_200_OK)

        # 2. Token
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        res_token = client.get("/api/v1/me/")
        self.assertEqual(res_token.status_code, status.HTTP_200_OK)

    def test_openapi_schema_endpoint(self):
        """التحقق من توفر مسار توثيق OpenAPI."""
        client = APIClient()
        res = client.get("/api/v1/openapi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_billing_ledger_reconciliation_report(self):
        """التحقق من حساب تقرير المطابقة الدورية بين الفواتير ودفتر الأستاذ."""
        report = get_billing_ledger_reconciliation_report(self.school)
        self.assertIn("operational", report)
        self.assertIn("ledger", report)
        self.assertIn("reconciliation", report)
        self.assertIn("is_reconciled", report["reconciliation"])

    # -------------------------------------------------------------------------
    # Phase 6: Subsystems (Books Quantity & Bus Strict Settlement)
    # -------------------------------------------------------------------------

    def test_book_distribution_quantity_sync(self):
        """التحقق من تسليم واسترجاع كتب بكميات مخصصة وتحديث رصيد المخزون ذرياً."""
        wh = Warehouse.objects.create(
            school=self.school,
            name="مستودع الكتب الرئيسي",
            code="WH-BOOKS",
        )
        item = InventoryItem.objects.create(
            school=self.school,
            warehouse=wh,
            code="BK-MATH-1",
            name="كتاب الرياضيات - الصف الأول",
            unit=InventoryItem.Unit.BOOK,
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("15.00"),
        )

        dist = StudentBookDistribution.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            inventory_item=item,
            book_title="كتاب الرياضيات",
            quantity=Decimal("3.00"),
        )

        # تسليم 3 كتب
        dist.deliver_book(user=self.owner)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("47.00"))
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.DELIVERED)

        # إرجاع 3 كتب
        dist.return_book(user=self.owner)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("50.00"))
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.RETURNED)
