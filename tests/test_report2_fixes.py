"""
tests/test_report2_fixes.py
Comprehensive verification tests for all phases of chatgptreport2.txt:
1. Student Credit Ledger & Payment Excess Allocation
2. Journal Entry & Line Immutability Guards
3. HRMS & Payroll Accrual & Disbursement Lifecycle
4. Student Historical Enrollment & Section Year Enforcement
5. School Services Book Distribution Inventory Sync
6. Mobile Token Authentication & SchoolContextMiddleware Header Resolution
7. User In-App Notifications API
8. Strict Multi-Tenant Isolation in Reports (No arbitrary platform fallback)
"""
from datetime import date, time
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from apps.accounts.models import User, SchoolRole, SchoolMembership
from apps.academics.models import AcademicYear, AcademicTerm, EducationalStage, GradeLevel, Section, Subject
from apps.staff.models import Teacher, StaffMember, Department, WorkShift, LeaveType, LeaveRequest, StaffAttendance
from apps.students.models import Student, StudentEnrollment
from apps.tenants.models import School
from apps.tenants.services import provision_school

from apps.accounting.models import Account, FiscalYear, FiscalPeriod, JournalEntry, JournalEntryLine, PaymentVoucher
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounting.services.auto_posting import (
    post_student_invoice_to_journal,
    post_student_receipt_to_journal,
)
from apps.student_fees.models import (
    FeeCategory,
    StudentInvoice,
    StudentInvoiceItem,
    PaymentReceipt,
    PaymentAllocation,
    StudentCreditTransaction,
    apply_credit_balance_to_invoice,
)
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun, Payslip
from apps.payroll.services import (
    generate_monthly_payroll,
    post_payroll_to_accounting,
    disburse_payroll_run,
)
from apps.inventory.models import Warehouse, InventoryItem
from apps.school_services.models import StudentBookDistribution
from apps.notifications.models import Notification


class Report2AuditFixesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Platform & Primary School
        cls.user = User.objects.create_user(
            phone="+967771234567",
            password="StrongPassword123!",
            first_name="فهد",
            last_name="المهندس",
            is_staff=True,
        )
        cls.school = School.objects.create(
            owner=cls.user,
            code="SCH_REP2_01",
            name="مدارس النور الحديثة",
            status=School.Status.ACTIVE,
        )
        provision_school(cls.school)
        seed_default_chart_of_accounts(cls.school)

        # 2. Fiscal Year & Period
        cls.fiscal_year = FiscalYear.objects.create(
            school=cls.school,
            name="السنة المالية 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.fiscal_period = FiscalPeriod.objects.create(
            school=cls.school,
            fiscal_year=cls.fiscal_year,
            period_number=1,
            name="الفترة الأولى 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

        # 3. Academic Structure
        cls.academic_year = AcademicYear.objects.create(
            school=cls.school,
            code="2026-2027",
            name="2026-2027",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
        )
        cls.term = AcademicTerm.objects.create(
            school=cls.school,
            academic_year=cls.academic_year,
            name="الفصل الأول",
            number=1,
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 1, 15),
            is_current=True,
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
            name="شعبة أ",
            code="G1-A",
        )

        # Student
        cls.student = Student.objects.create(
            school=cls.school,
            academic_year=cls.academic_year,
            grade_level=cls.grade,
            section=cls.section,
            student_id_number="STU-REP2-001",
            first_name="سالم",
            last_name="المتوكل",
            enrollment_date=date(2026, 9, 1),
        )

        # Fee Category
        cls.fee_category = FeeCategory.objects.create(
            school=cls.school,
            name="رسوم دراسية سنوية",
            code="TUITION_REP2",
            is_mandatory=True,
        )

    def test_student_credit_balance_excess_and_usage(self):
        """Phase 1: التحقق من تسجيل فائض السداد في سجل الرصيد الدائن واستخدامه لاحقاً."""
        # 1. Create Invoice of 1000
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-REP2-100",
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 15),
            total_amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),
        )
        StudentInvoiceItem.objects.create(
            school=self.school,
            invoice=inv,
            description="رسوم دراسية",
            fee_category=self.fee_category,
            amount=Decimal("1000.00"),
        )

        # 2. Pay 1300 (300 excess)
        receipt = PaymentReceipt(
            school=self.school,
            receipt_number="REC-REP2-100",
            student=self.student,
            invoice=inv,
            amount=Decimal("1300.00"),
            paid_at=date(2026, 9, 2),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            received_by=self.user,
        )
        receipt.save()

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("1000.00"))
        self.assertEqual(inv.remaining_amount, Decimal("0.00"))
        self.assertEqual(inv.status, StudentInvoice.Status.PAID)

        # 3. Check StudentCreditTransaction deposit
        credit_tx = StudentCreditTransaction.objects.filter(
            student=self.student,
            transaction_type=StudentCreditTransaction.TransactionType.DEPOSIT,
        ).first()
        self.assertIsNotNone(credit_tx)
        self.assertEqual(credit_tx.amount, Decimal("300.00"))

        # 4. Create new Invoice of 500 and apply credit balance
        inv2 = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-REP2-101",
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 15),
            total_amount=Decimal("500.00"),
            paid_amount=Decimal("0.00"),
        )
        applied = apply_credit_balance_to_invoice(self.student, inv2)
        self.assertEqual(applied, Decimal("300.00"))

        inv2.refresh_from_db()
        self.assertEqual(inv2.paid_amount, Decimal("300.00"))
        self.assertEqual(inv2.remaining_amount, Decimal("200.00"))
        self.assertEqual(inv2.status, StudentInvoice.Status.PARTIALLY_PAID)

        usage_tx = StudentCreditTransaction.objects.filter(
            student=self.student,
            transaction_type=StudentCreditTransaction.TransactionType.USAGE,
        ).first()
        self.assertIsNotNone(usage_tx)
        self.assertEqual(usage_tx.amount, Decimal("300.00"))

    def test_posted_journal_entry_and_line_immutability(self):
        """Phase 1: التحقق من قفل القيود المرحلة وعدم جواز تعديلها أو حذف سطورها مباشرة."""
        ar_acc = Account.objects.get(school=self.school, code="1104")
        rev_acc = Account.objects.get(school=self.school, code="4101")

        entry = JournalEntry.objects.create(
            school=self.school,
            entry_number="JE-TEST-IMMUTABLE-01",
            date=date(2026, 9, 1),
            status=JournalEntry.Status.DRAFT,
            description="قيد اختبار الحماية",
        )
        line1 = JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=ar_acc,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
        )
        line2 = JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=rev_acc,
            debit=Decimal("0.00"),
            credit=Decimal("500.00"),
        )

        # Post the entry
        entry.status = JournalEntry.Status.POSTED
        entry.save()

        # Attempt to delete a line from a posted entry -> must raise ValidationError
        with self.assertRaises(ValidationError):
            line1.delete()

        # Attempt to delete the posted journal entry -> must raise ValidationError
        with self.assertRaises(ValidationError):
            entry.delete()

        # Attempt to alter financial content of a posted entry -> must raise ValidationError
        with self.assertRaises(ValidationError):
            entry.description = "تعديل غير مسموح"
            entry.save()

    def test_payroll_accrual_and_disbursement_lifecycle(self):
        """Phase 2: دورة الرواتب: الاستحقاق، استقطاع أقساط السلف، وصرف المستحقات."""
        emp_user = User.objects.create_user(
            phone="+967779988771",
            password="StrongPassword123!",
            first_name="سمير",
            last_name="المحاسب",
        )
        staff = StaffMember.objects.create(
            school=self.school,
            user=emp_user,
            job_title="محاسب",
            employee_number="EMP-STAFF-02",
            hire_date=date(2026, 1, 1),
        )
        contract = EmployeeContract.objects.create(
            school=self.school,
            staff_member=staff,
            contract_number="CNT-REP2-01",
            contract_type=EmployeeContract.ContractType.FULL_TIME,
            basic_salary=Decimal("100000.00"),
            housing_allowance=Decimal("20000.00"),
            transport_allowance=Decimal("10000.00"),
            insurance_deduction=Decimal("5000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        # Advance loan: 30000, monthly installment 15000
        loan = EmployeeLoanAdvance.objects.create(
            school=self.school,
            staff_member=staff,
            loan_number="LN-REP2-01",
            amount=Decimal("30000.00"),
            monthly_installment=Decimal("15000.00"),
            repaid_amount=Decimal("0.00"),
            date_granted=date(2026, 1, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )

        # 1. Generate Payroll
        run = generate_monthly_payroll(
            school=self.school,
            year=2026,
            month=9,
            created_by=self.user,
        )
        payslip = run.payslips.filter(staff_member=staff).first()
        self.assertIsNotNone(payslip)
        self.assertEqual(payslip.loan_deductions, Decimal("15000.00"))
        # Gross = 130000; Deductions = 5000 (insurance) + 15000 (loan) = 20000; Net = 110000
        self.assertEqual(payslip.net_salary, Decimal("110000.00"))

        # 2. Post Payroll to Accounting (Accrual)
        post_payroll_to_accounting(run)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.POSTED)
        self.assertIsNotNone(run.journal_entry)

        loan.refresh_from_db()
        self.assertEqual(loan.repaid_amount, Decimal("15000.00"))
        self.assertEqual(loan.remaining_amount, Decimal("15000.00"))

        # 3. Disburse Payroll (Payment Voucher & Cash Outflow)
        cash_acc = Account.objects.get(school=self.school, code="1101")
        pv = disburse_payroll_run(
            payroll_run=run,
            payment_method="cash",
            credit_account=cash_acc,
            disbursed_by=self.user,
        )
        self.assertIsNotNone(pv)
        self.assertEqual(pv.status, PaymentVoucher.Status.POSTED)

        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.PAID)
        payslip.refresh_from_db()
        self.assertTrue(payslip.is_paid)

    def test_student_enrollment_and_section_year_validation(self):
        """Phase 3: التحقق من التزامن مع سجل القيد التاريخي وتطابق العام الدراسي للشعبة."""
        # Check automatic StudentEnrollment creation
        enrollment = StudentEnrollment.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
        ).first()
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.status, StudentEnrollment.Status.ENROLLED)

        # Create another year and section
        other_year = AcademicYear.objects.create(
            school=self.school,
            code="2027-2028",
            name="2027-2028",
            starts_on=date(2027, 9, 1),
            ends_on=date(2028, 6, 30),
        )
        other_section = Section.objects.create(
            school=self.school,
            grade=self.grade,
            academic_year=other_year,
            name="شعبة ب سنة أخرى",
            code="G1-B-OTHER",
        )

        # Assigning section with mismatching academic year must raise ValidationError
        self.student.section = other_section
        with self.assertRaises(ValidationError):
            self.student.full_clean()

    def test_book_distribution_inventory_integration(self):
        """Phase 3: ربط تسليم واسترجاع الكتب المدرسية بالمخزون والمستودعات آلياً."""
        wh = Warehouse.objects.create(
            school=self.school,
            code="WH-BOOKS-01",
            name="مخزن الكتب الرئيسي",
        )
        item = InventoryItem.objects.create(
            school=self.school,
            warehouse=wh,
            code="BK-MATH-G1",
            name="كتاب الرياضيات للصف الأول",
            unit=InventoryItem.Unit.BOOK,
            current_stock=Decimal("50.00"),
        )
        dist = StudentBookDistribution.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            book_title="كتاب الرياضيات للصف الأول",
            inventory_item=item,
        )

        # 1. Deliver Book -> Stock decreases to 49
        dist.deliver_book(user=self.user)
        dist.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.DELIVERED)
        self.assertEqual(item.current_stock, Decimal("49.00"))

        # 2. Return Book -> Stock restored to 50
        dist.return_book(user=self.user)
        dist.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.RETURNED)
        self.assertEqual(item.current_stock, Decimal("50.00"))

    def test_user_in_app_notifications_api(self):
        """Phase 4: التحقق من واجهات إشعارات المستخدم والتحديد كمقروء."""
        notif = Notification.objects.create(
            school=self.school,
            recipient=self.user,
            title="تنبيه بموعد الاختبار",
            body="تبدأ اختبارات الفصل الأول الأسبوع القادم",
            category="exams",
        )
        token, _ = Token.objects.get_or_create(user=self.user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # GET notifications
        res = client.get("/api/v1/notifications/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["unread_count"], 1)
        self.assertEqual(len(res.data["notifications"]), 1)

        # Mark single as read
        res_read = client.post(f"/api/v1/notifications/{notif.id}/read/")
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # Check unread count is now 0
        res_after = client.get("/api/v1/notifications/?unread_only=true")
        self.assertEqual(res_after.status_code, status.HTTP_200_OK)
        self.assertEqual(res_after.data["unread_count"], 0)
        self.assertEqual(len(res_after.data["notifications"]), 0)

    def test_reports_school_isolation_without_fallback(self):
        """Phase 4: التحقق من عدم تسريب بيانات مدرسة عشوائية عند طلب تقرير دون تحديد المدرسة."""
        platform_user = User.objects.create_user(
            phone="+967778899000",
            password="StrongPassword123!",
            first_name="مدير",
            last_name="عام",
            is_platform_admin=True,
        )
        token, _ = Token.objects.get_or_create(user=platform_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # Request report without school_code or X-School-ID header
        res = client.get("/api/v1/reports/financial/daily-cash/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("المدرسة غير محددة", res.data.get("error", ""))
