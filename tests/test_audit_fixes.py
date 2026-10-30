"""
tests/test_audit_fixes.py
اختبارات شاملة للتحقق من تنفيذ كافة متطلبات تقرير المراجعة والتدقيق (chatgptreport1.txt):
1. إثبات استحقاق الفواتير المحاسبي (Accrual Posting).
2. دفتر تخصيص الدفعات وسجل الفائض الدائن للطلاب (Payment Allocations & Credit Balance).
3. القيد العكسي الرياضي غير التدميري (Non-destructive Journal Reversal).
4. مسير الرواتب الموحد للكادر الإداري والتدريسي مع تجميع استقطاعات السلف المتعددة.
5. التحقق الصارم من تطابق شعبة الطالب مع شعبة الحصة المجدولة في الحضور.
6. تحويل أوامر الشراء المعتمدة إلى حركات توريد مخزنية فعلية وتحديث الأرصدة.
7. اعتماد التسويات المالية للباصات وإنشاء سندات الصرف المحاسبية المرتبطة.
8. استبعاد المسودات والملغيات من تقرير حركة الصناديق واليومية.
9. عزل صلاحيات العيادة والملفات الطبية الحساسة وإنشاء دور مسؤول العيادة.
10. مصادقة الرموز (Token Authentication) لتطبيقات الموبايل وواجهات API.
"""
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.academics.models import AcademicYear, AcademicTerm, EducationalStage, GradeLevel, Section, Subject
from apps.staff.models import Teacher, StaffMember
from apps.students.models import Student
from apps.tenants.models import School, SchoolRole
from apps.tenants.services import ensure_default_roles

from apps.accounting.models import Account, FiscalYear, FiscalPeriod, JournalEntry, JournalEntryLine, PaymentVoucher, ReceiptVoucher
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounting.services.auto_posting import (
    post_student_invoice_to_journal,
    reverse_journal_entry,
)
from apps.student_fees.models import FeeCategory, StudentInvoice, PaymentReceipt, PaymentAllocation
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun, Payslip
from apps.payroll.services import generate_monthly_payroll

from apps.timetable.models import ClassSchedule
from apps.attendance.models import PeriodAttendance
from apps.inventory.models import Warehouse, InventoryItem, PurchaseOrder, PurchaseOrderItem, StockMovement
from apps.school_services.models import BusRoute, BusFinancialSettlement
from apps.reports.selectors.financial_reports import get_daily_cash_register_report


class AuditFixesVerificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Platform & School
        cls.user = User.objects.create_user(
            phone="+967770001122",
            password="StrongPassword123!",
            first_name="أحمد",
            last_name="المختبر",
        )
        cls.school = School.objects.create(
            owner=cls.user,
            code="SCH_AUDIT_01",
            name="مدرسة الرواد النموذجية",
            status=School.Status.ACTIVE,
        )
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
            code="T1",
            name="الفصل الأول",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 1, 15),
        )
        cls.stage = EducationalStage.objects.create(
            school=cls.school,
            code="PRIMARY",
            name="المرحلة الابتدائية",
        )
        cls.grade = GradeLevel.objects.create(
            school=cls.school,
            stage=cls.stage,
            code="G1",
            name="الصف الأول",
        )
        cls.section_a = Section.objects.create(
            school=cls.school,
            grade_level=cls.grade,
            code="A",
            name="شعبة أ",
        )
        cls.section_b = Section.objects.create(
            school=cls.school,
            grade_level=cls.grade,
            code="B",
            name="شعبة ب",
        )
        cls.subject = Subject.objects.create(
            school=cls.school,
            code="MATH1",
            name="الرياضيات",
        )

        # 4. Student & Staff
        cls.student_user = User.objects.create_user(
            phone="+967770001133",
            password="StrongPassword123!",
            first_name="سامي",
            last_name="خالد",
        )
        cls.student = Student.objects.create(
            school=cls.school,
            user=cls.student_user,
            student_id_number="STD-00101",
            first_name="سامي",
            last_name="خالد",
            grade_level=cls.grade,
            section=cls.section_a,
        )

        cls.staff_user = User.objects.create_user(
            phone="+967770001144",
            password="StrongPassword123!",
            first_name="طارق",
            last_name="النجار",
        )
        cls.staff_member = StaffMember.objects.create(
            school=cls.school,
            user=cls.staff_user,
            employee_number="EMP-055",
            job_title="مشرف الدور الأول",
            role=StaffMember.StaffRole.SUPERVISOR,
        )

    def test_post_student_invoice_accrual_to_journal(self):
        """1. التحقق من قيد استحقاق فاتورة الرسوم الدراسية (المدين: ذمم الطلاب 1104، الدائن: إيرادات الرسوم 4101)."""
        fee_cat = FeeCategory.objects.create(
            school=self.school,
            code="TUITION",
            name="رسوم دراسية سنوية",
        )
        invoice = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            fee_category=fee_cat,
            invoice_number="INV-2026-TEST-001",
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 15),
            total_amount=Decimal("5000.00"),
            discount_amount=Decimal("500.00"),
        )
        entry = post_student_invoice_to_journal(invoice)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

        lines = list(entry.lines.all())
        self.assertEqual(len(lines), 2)
        debit_line = next(l for l in lines if l.debit > 0)
        credit_line = next(l for l in lines if l.credit > 0)

        # 5000 - 500 = 4500 net
        self.assertEqual(debit_line.debit, Decimal("4500.00"))
        self.assertEqual(debit_line.account.code, "1104")  # ذمم ورسوم الطلاب
        self.assertEqual(credit_line.credit, Decimal("4500.00"))
        self.assertEqual(credit_line.account.code, "4101")  # إيرادات الرسوم الدراسية

    def test_payment_allocation_and_student_credit_balance(self):
        """2. التحقق من دفتر تخصيص الدفعات وحفظ الرصيد الفائض في حساب الطالب الدائن."""
        fee_cat = FeeCategory.objects.create(
            school=self.school,
            code="ACTIVITY",
            name="رسوم أنشطة ومختبرات",
        )
        invoice = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            fee_category=fee_cat,
            invoice_number="INV-2026-TEST-002",
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 15),
            total_amount=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
        )
        # سداد مبلغ 1400 (سداد الفاتورة 1000 + فائض 400 في رصيد الطالب)
        receipt = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            receipt_number="REC-2026-TEST-001",
            amount=Decimal("1400.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            received_by=self.user,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, StudentInvoice.Status.PAID)
        self.assertEqual(invoice.paid_amount, Decimal("1000.00"))

        allocations = PaymentAllocation.objects.filter(receipt=receipt)
        self.assertEqual(allocations.count(), 1)
        alloc = allocations.first()
        self.assertEqual(alloc.invoice, invoice)
        self.assertEqual(alloc.allocated_amount, Decimal("1000.00"))

        self.student.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("400.00"))

    def test_non_destructive_journal_entry_reversal(self):
        """3. التحقق من القيد العكسي الرياضي غير التدميري وبقاء القيدين مرحلين ليتلاشى الأثر لـ 0.00."""
        cash_acc = Account.objects.get(school=self.school, code="1101")
        revenue_acc = Account.objects.get(school=self.school, code="4101")

        orig_entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=self.fiscal_period,
            entry_number="JV-TEST-REV-01",
            date=date(2026, 10, 1),
            status=JournalEntry.Status.POSTED,
            description="قيد أصلي للتجربة",
        )
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=orig_entry,
            account=cash_acc,
            debit=Decimal("1500.00"),
            credit=Decimal("0.00"),
            description="قبض نقدي",
        )
        JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=orig_entry,
            account=revenue_acc,
            debit=Decimal("0.00"),
            credit=Decimal("1500.00"),
            description="إيراد",
        )

        rev_entry = reverse_journal_entry(orig_entry, reason="خطأ في تسجيل الإيراد", reversed_by=self.user)
        self.assertIsNotNone(rev_entry)

        orig_entry.refresh_from_db()
        self.assertTrue(orig_entry.is_reversed)
        self.assertEqual(orig_entry.reversed_by_entry, rev_entry)
        self.assertEqual(orig_entry.status, JournalEntry.Status.POSTED)  # Non-destructive
        self.assertEqual(rev_entry.status, JournalEntry.Status.POSTED)

        # Lines swapped
        rev_lines = list(rev_entry.lines.all())
        rev_debit = next(l for l in rev_lines if l.debit > 0)
        rev_credit = next(l for l in rev_lines if l.credit > 0)
        self.assertEqual(rev_debit.account, revenue_acc)
        self.assertEqual(rev_debit.debit, Decimal("1500.00"))
        self.assertEqual(rev_credit.account, cash_acc)
        self.assertEqual(rev_credit.credit, Decimal("1500.00"))

        # Re-reversal should be strictly rejected
        with self.assertRaises(ValueError):
            reverse_journal_entry(orig_entry, reason="محاولة عكس ثانية")

    def test_staff_payroll_and_multi_loan_deduction(self):
        """4. التحقق من مسير الرواتب الموحد للكادر الإداري وتجميع استقطاعات السلف المتعددة."""
        contract = EmployeeContract.objects.create(
            school=self.school,
            staff_member=self.staff_member,
            contract_type=EmployeeContract.ContractType.FULL_TIME,
            basic_salary=Decimal("4000.00"),
            housing_allowance=Decimal("500.00"),
            transport_allowance=Decimal("300.00"),
            insurance_deduction=Decimal("200.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        # سلفة 1: قسطها الشهري 150
        EmployeeLoanAdvance.objects.create(
            school=self.school,
            staff_member=self.staff_member,
            loan_number="LN-STAFF-01",
            total_amount=Decimal("1500.00"),
            remaining_amount=Decimal("1500.00"),
            monthly_installment=Decimal("150.00"),
            disbursement_date=date(2026, 1, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )
        # سلفة 2: قسطها الشهري 100
        EmployeeLoanAdvance.objects.create(
            school=self.school,
            staff_member=self.staff_member,
            loan_number="LN-STAFF-02",
            total_amount=Decimal("1000.00"),
            remaining_amount=Decimal("1000.00"),
            monthly_installment=Decimal("100.00"),
            disbursement_date=date(2026, 1, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )

        run = generate_monthly_payroll(school=self.school, year=2026, month=10)
        self.assertIsNotNone(run)

        payslip = run.payslips.filter(staff_member=self.staff_member).first()
        self.assertIsNotNone(payslip)
        # Total loan deductions = 150 + 100 = 250
        self.assertEqual(payslip.loan_deduction, Decimal("250.00"))
        self.assertEqual(payslip.insurance_deduction, Decimal("200.00"))
        # Total earnings = 4000 + 500 + 300 = 4800
        # Net = 4800 - (200 + 250) = 4350
        self.assertEqual(payslip.net_salary, Decimal("4350.00"))

    def test_period_attendance_cross_section_enforcement(self):
        """5. التحقق الصارم من رفض تسجيل حضور الطالب في حصة دراسية لشعبة لا ينتمي إليها."""
        schedule_section_b = ClassSchedule.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            section=self.section_b,  # شعبة ب
            subject=self.subject,
            day_of_week=0,
            period_number=1,
        )
        # الطالب سامي مسجل في شعبة أ
        attendance = PeriodAttendance(
            school=self.school,
            schedule=schedule_section_b,
            student=self.student,
            date=date(2026, 10, 15),
            status=PeriodAttendance.Status.PRESENT,
        )
        with self.assertRaises(ValidationError) as ctx:
            attendance.clean()
        self.assertIn("student", ctx.exception.message_dict)

    def test_purchase_order_warehouse_receipt(self):
        """6. التحقق من تحويل أمر الشراء إلى حركات توريد مخزنية وتحديث رصيد المستودع."""
        wh = Warehouse.objects.create(
            school=self.school,
            code="WH-MAIN",
            name="المستودع المركزي للكتب والمستلزمات",
        )
        from apps.inventory.models import Supplier
        supplier = Supplier.objects.create(
            school=self.school,
            name="دار النشر والتوزيع المدرسية",
            contact_person="المدير التجاري",
            phone="+967771234567",
        )
        item1 = InventoryItem.objects.create(
            school=self.school,
            code="BK-MATH-01",
            name="كتاب الرياضيات - الصف الأول",
            warehouse=wh,
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("20.00"),
        )
        po = PurchaseOrder.objects.create(
            school=self.school,
            order_number="PO-2026-001",
            supplier=supplier,
            warehouse=wh,
            total_amount=Decimal("1000.00"),
        )
        PurchaseOrderItem.objects.create(
            school=self.school,
            purchase_order=po,
            item=item1,
            quantity=Decimal("50.00"),
            unit_price=Decimal("20.00"),
            total_price=Decimal("1000.00"),
        )

        movements = po.receive_into_warehouse(user=self.user)
        self.assertEqual(len(movements), 1)
        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.Status.RECEIVED)

        item1.refresh_from_db()
        # Original 10 + 50 received = 60
        self.assertEqual(item1.current_stock, Decimal("60.00"))

    def test_bus_financial_settlement_approval_and_voucher(self):
        """7. التحقق من اعتماد التسوية المالية للباص وتوليد سند الصرف المرتبط آلياً."""
        bus = BusRoute.objects.create(
            school=self.school,
            route_name="خط الأصبحي - حده",
            route_code="BUS-01",
            bus_number="44123",
            driver_name="فؤاد السائق",
            driver_phone="+967770009988",
            compensation_type=BusRoute.CompensationType.MONTHLY_FLAT,
            contract_amount=Decimal("120000.00"),
        )
        settlement = BusFinancialSettlement.objects.create(
            school=self.school,
            bus_route=bus,
            academic_year=self.academic_year,
            month=10,
            year=2026,
            advances_withdrawn=Decimal("20000.00"),
        )
        pv = settlement.approve_and_create_payment_voucher(approved_by_user=self.user)
        self.assertIsNotNone(pv)
        self.assertEqual(settlement.status, BusFinancialSettlement.Status.APPROVED)
        self.assertEqual(settlement.payment_voucher, pv)
        # 120000 - 20000 = 100000 net payable
        self.assertEqual(pv.amount, Decimal("100000.00"))
        self.assertEqual(pv.status, PaymentVoucher.Status.APPROVED)

    def test_cash_register_report_excludes_draft_and_cancelled(self):
        """8. التحقق من استبعاد السندات المسودة والملغاة من تقرير حركة الصناديق واليومية."""
        today = date(2026, 10, 20)
        cash_acc = Account.objects.get(school=self.school, code="1101")
        exp_acc = Account.objects.get(school=self.school, code="5204")

        # 1. Approved/Posted Payment Voucher (100)
        PaymentVoucher.objects.create(
            school=self.school,
            voucher_number="PV-TEST-POSTED",
            date=today,
            amount=Decimal("100.00"),
            debit_account=exp_acc,
            credit_account=cash_acc,
            status=PaymentVoucher.Status.APPROVED,
        )
        # 2. Draft Payment Voucher (250) - should be excluded
        PaymentVoucher.objects.create(
            school=self.school,
            voucher_number="PV-TEST-DRAFT",
            date=today,
            amount=Decimal("250.00"),
            debit_account=exp_acc,
            credit_account=cash_acc,
            status=PaymentVoucher.Status.DRAFT,
        )
        # 3. Cancelled Payment Voucher (300) - should be excluded
        PaymentVoucher.objects.create(
            school=self.school,
            voucher_number="PV-TEST-CANCELLED",
            date=today,
            amount=Decimal("300.00"),
            debit_account=exp_acc,
            credit_account=cash_acc,
            status=PaymentVoucher.Status.CANCELLED,
        )

        rep = get_daily_cash_register_report(school=self.school, target_date=today)
        self.assertEqual(rep["summary"]["total_outflow"], 100.0)

    def test_clinic_role_isolation_and_permissions(self):
        """9. التحقق من عزل صلاحيات السجلات الصحية والعيادة عن أمين المخزن والمراجع وتخصيص دور مسؤول العيادة."""
        ensure_default_roles(self.school)

        clinic_role = SchoolRole.objects.get(school=self.school, code="clinic-officer")
        store_role = SchoolRole.objects.get(school=self.school, code="store-keeper")
        auditor_role = SchoolRole.objects.get(school=self.school, code="school-auditor")

        clinic_codenames = [p.codename for p in clinic_role.permissions.all()]
        store_codenames = [p.codename for p in store_role.permissions.all()]
        auditor_codenames = [p.codename for p in auditor_role.permissions.all()]

        # Clinic role has health and clinic permissions
        self.assertTrue(any("studenthealthprofile" in cn for cn in clinic_codenames))
        self.assertTrue(any("clinicvisit" in cn for cn in clinic_codenames))

        # Store keeper and auditor must NOT have health or clinic permissions
        self.assertFalse(any("studenthealthprofile" in cn for cn in store_codenames))
        self.assertFalse(any("clinicvisit" in cn for cn in store_codenames))
        self.assertFalse(any("studenthealthprofile" in cn for cn in auditor_codenames))
        self.assertFalse(any("clinicvisit" in cn for cn in auditor_codenames))

    def test_api_token_login_and_logout(self):
        """10. التحقق من مسارات مصادقة الرموز (Token Auth) لتطبيقات الموبايل وإبطالها عند الخروج."""
        client = APIClient()

        # Login failure with bad password
        res_fail = client.post("/api/v1/auth/login/", {"phone": "+967770001122", "password": "wrong"})
        self.assertEqual(res_fail.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login success
        res_ok = client.post("/api/v1/auth/login/", {"phone": "+967770001122", "password": "StrongPassword123!"})
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertIn("token", res_ok.data)
        token_str = res_ok.data["token"]

        # Authenticated Logout
        client.credentials(HTTP_AUTHORIZATION=f"Token {token_str}")
        res_logout = client.post("/api/v1/auth/logout/")
        self.assertEqual(res_logout.status_code, status.HTTP_200_OK)

        # Token should now be invalidated
        from rest_framework.authtoken.models import Token
        self.assertFalse(Token.objects.filter(key=token_str).exists())
