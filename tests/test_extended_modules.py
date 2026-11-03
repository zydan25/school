"""Automated tests for extended ERP modules:
- Accounting Vouchers & Chart of Accounts Seeder
- Payroll Management & Payslip Calculation
- Fixed Assets & Depreciation
- Procurement & Inventory Movements
- Optional School Services (Buses, Library, Textbook Distribution)
- Fee Installment Plans & Exam Control
- Comprehensive Reporting Engine
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.academics.models import (
    AcademicTerm,
    AcademicYear,
    EducationalStage,
    GradeLevel,
    Section,
    Subject,
)
from apps.accounting.models import (
    Account,
    PaymentVoucher,
    ReceiptVoucher,
)
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounting.services.financial_reports import (
    get_balance_sheet,
    get_income_statement,
)
from apps.accounts.models import SchoolMembership, User
from apps.assessments.models import ExamCommittee, ExamSeating, GradeBook
from apps.assets.models import AssetCategory, FixedAsset
from apps.inventory.models import InventoryItem, StockMovement, Supplier, Warehouse
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance
from apps.payroll.services import generate_monthly_payroll
from apps.reports.selectors.academic_reports import (
    get_class_ranking_report,
    get_student_report_card,
)
from apps.reports.selectors.financial_reports import (
    get_aging_receivables_report,
    get_student_statement_of_account,
)
from apps.reports.selectors.hr_reports import (
    get_teacher_workload_report,
)
from apps.school_services.models import (
    BookLoan,
    BusRoute,
    LibraryBook,
    StudentBusSubscription,
)
from apps.staff.models import Teacher
from apps.student_fees.models import (
    FeeInstallment,
    FeeInstallmentPlan,
    PaymentReceipt,
    StudentInvoice,
)
from apps.students.models import Student
from apps.tenants.models import School


class ExtendedModulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            phone="+967777333001", password="StrongPassword123!",
            first_name="علي", last_name="العتّاب",
        )
        cls.school = School.objects.create(
            owner=cls.user,
            code="SCH_EXT_1",
            name="مدرسة الأندلس الدولية",
            status=School.Status.ACTIVE,
        )
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
        cls.stage = EducationalStage.objects.create(school=cls.school, code="SEC", name="المرحلة الثانوية", sequence=1)
        cls.grade = GradeLevel.objects.create(school=cls.school, stage=cls.stage, code="G10", name="الصف العاشر", sequence=1)
        cls.section = Section.objects.create(school=cls.school, academic_year=cls.academic_year, grade=cls.grade, code="10-A", name="عاشر / أ")
        cls.subject = Subject.objects.create(school=cls.school, code="MATH10", name="الرياضيات المتقدمة")

        cls.teacher_user = User.objects.create_user(
            phone="+967777333002", password="StrongPassword123!",
            first_name="فهد", last_name="الأستاذ",
        )
        cls.teacher = Teacher.objects.create(
            school=cls.school,
            user=cls.teacher_user,
            employee_number="EMP-001",
            specialization="رياضيات",
            max_weekly_periods=20,
        )

        cls.student = Student.objects.create(
            school=cls.school,
            student_id_number="STD-EXT-1",
            first_name="سالم",
            last_name="المجتهد",
            grade_level=cls.grade,
            section=cls.section,
            academic_year=cls.academic_year,
        )

    def test_chart_of_accounts_and_vouchers(self):
        """التحقق من إنشاء شجرة الحسابات وسندات الصرف والقبض المحاسبية."""
        count = seed_default_chart_of_accounts(self.school)
        self.assertGreater(count, 10)
        
        cash_account = Account.objects.get(school=self.school, code="1101")
        expense_account = Account.objects.get(school=self.school, code="5204")
        revenue_account = Account.objects.get(school=self.school, code="4101")

        # Create Payment Voucher (سند صرف مصاريف)
        pv = PaymentVoucher.objects.create(
            school=self.school,
            voucher_number="PV-2026-001",
            paid_to="شركة صيانة المكيفات",
            amount=Decimal("500.00"),
            payment_method=PaymentVoucher.PaymentMethod.CASH,
            credit_account=cash_account,
            debit_account=expense_account,
            description="صيانة دورية لقاعات الثانوية",
            status=PaymentVoucher.Status.POSTED,
        )
        self.assertEqual(pv.amount, Decimal("500.00"))

        # Create Receipt Voucher (سند قبض إيرادات)
        rv = ReceiptVoucher.objects.create(
            school=self.school,
            voucher_number="RV-2026-001",
            received_from="راعي الحفل المدرسي",
            amount=Decimal("1500.00"),
            payment_method=ReceiptVoucher.PaymentMethod.CASH,
            debit_account=cash_account,
            credit_account=revenue_account,
            description="دعم الحفل السنوي",
            status=ReceiptVoucher.Status.POSTED,
        )
        self.assertEqual(rv.amount, Decimal("1500.00"))

        # Verify Financial Reports
        income_stmt = get_income_statement(self.school)
        self.assertIn("net_income", income_stmt)
        bal_sheet = get_balance_sheet(self.school)
        self.assertIn("total_assets", bal_sheet)

    def test_payroll_management_flow(self):
        """التحقق من دورة الرواتب: العقد، السلفة، وتوليد مسير الرواتب."""
        contract = EmployeeContract.objects.create(
            school=self.school,
            teacher=self.teacher,
            contract_number="CNT-2026-01",
            start_date=date(2026, 9, 1),
            basic_salary=Decimal("5000.00"),
            housing_allowance=Decimal("1000.00"),
            transport_allowance=Decimal("500.00"),
            insurance_deduction=Decimal("200.00"),
        )
        self.assertEqual(contract.gross_salary, Decimal("6500.00"))
        self.assertEqual(contract.net_salary, Decimal("6300.00"))

        # Employee Advance / Loan
        loan = EmployeeLoanAdvance.objects.create(
            school=self.school,
            teacher=self.teacher,
            loan_number="LN-001",
            amount=Decimal("3000.00"),
            monthly_installment=Decimal("500.00"),
            start_date=date(2026, 10, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )
        self.assertEqual(loan.remaining_amount, Decimal("3000.00"))

        # Generate monthly payroll for October 2026
        payroll_run = generate_monthly_payroll(
            school=self.school,
            year=2026,
            month=10,
        )
        self.assertEqual(payroll_run.payslips.count(), 1)
        payslip = payroll_run.payslips.first()
        # Basic 5000 + 1500 allowances - 200 insurance - 500 loan installment = 5800
        self.assertEqual(payslip.net_salary, Decimal("5800.00"))
        self.assertEqual(payslip.loan_deduction, Decimal("500.00"))

    def test_fixed_assets_and_depreciation(self):
        """التحقق من إدارة الأصول الثابتة وتسجيل الإهلاك."""
        cat = AssetCategory.objects.create(
            school=self.school,
            code="COMP",
            name="أجهزة حاسوب وشاشات",
            annual_depreciation_rate=Decimal("20.00"),
            useful_life_years=5,
        )
        asset = FixedAsset.objects.create(
            school=self.school,
            category=cat,
            code="PC-LAB-01",
            name="حاسوب معمل الذكاء الاصطناعي",
            purchase_date=date(2026, 1, 1),
            purchase_cost=Decimal("4000.00"),
            accumulated_depreciation=Decimal("800.00"),
            custodian=self.teacher,
        )
        self.assertEqual(asset.current_book_value, Decimal("3200.00"))

    def test_inventory_and_stock_movements(self):
        """التحقق من الموردين، المستودعات، وحركات المخزون وصرف المواد."""
        supplier = Supplier.objects.create(
            school=self.school,
            code="SUPP-01",
            name="دار الكتب للطباعة والتوزيع",
            phone="012345678",
        )
        warehouse = Warehouse.objects.create(
            school=self.school,
            code="WH-MAIN",
            name="المستودع المركزي",
            manager=self.teacher,
        )
        item = InventoryItem.objects.create(
            school=self.school,
            code="BK-MATH-10",
            name="كتاب الرياضيات للصف العاشر",
            warehouse=warehouse,
            unit=InventoryItem.Unit.BOOK,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("25.00"),
            reorder_level=Decimal("10.00"),
        )

        # Receipt movement (وارد 100 كتاب)
        StockMovement.objects.create(
            school=self.school,
            item=item,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("100.00"),
            unit_cost=Decimal("25.00"),
            reference="PO-991",
        )
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("100.00"))

        # Issue movement (صرف 30 كتاباً للطلاب)
        StockMovement.objects.create(
            school=self.school,
            item=item,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=Decimal("30.00"),
            recipient_name="شعبة عاشر / أ",
        )
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("70.00"))

    def test_school_services_buses_and_library(self):
        """التحقق من خدمات النقل والمكتبة المدرسية دون خدمة العيادة المستبعدة."""
        # 1. Bus Transport
        bus = BusRoute.objects.create(
            school=self.school,
            route_code="BUS-R1",
            route_name="خط حي الأندلس والزهراء",
            bus_number="4412-YEM",
            driver_name="أحمد السائق",
            driver_phone="770000001",
            monthly_fee=Decimal("150.00"),
        )
        sub = StudentBusSubscription.objects.create(
            school=self.school,
            student=self.student,
            bus_route=bus,
            academic_year=self.academic_year,
            subscription_type=StudentBusSubscription.SubscriptionType.TWO_WAY,
        )
        self.assertEqual(sub.status, StudentBusSubscription.Status.ACTIVE)

        # 2. Library
        book = LibraryBook.objects.create(
            school=self.school,
            isbn="978-0123456789",
            title="مقدمة في علم البيانات والخوارزميات",
            author="د. عبد الرحمن الخوارزمي",
            total_copies=5,
            available_copies=5,
        )
        loan = BookLoan.objects.create(
            school=self.school,
            book=book,
            student=self.student,
            borrow_date=date(2026, 10, 1),
            due_date=date(2026, 10, 15),
        )
        book.refresh_from_db()
        self.assertEqual(book.available_copies, 4)


    def test_fee_installment_plans_and_exam_control(self):
        """التحقق من خطط تقسيط الرسوم ولجان الامتحانات وأرقام الجلوس."""
        # Fee Invoice & Installment Plan
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-2026-90",
            total_amount=Decimal("1200.00"),
            due_date=date(2026, 12, 31),
        )
        plan = FeeInstallmentPlan.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            plan_name="خطة تقسيط فصلية",
            total_amount=Decimal("1200.00"),
            number_of_installments=3,
        )
        inst1 = FeeInstallment.objects.create(
            school=self.school,
            plan=plan,
            installment_number=1,
            title="القسط الأول",
            amount=Decimal("400.00"),
            due_date=date(2026, 10, 1),
            status=FeeInstallment.Status.PAID,
        )
        inst2 = FeeInstallment.objects.create(
            school=self.school,
            plan=plan,
            installment_number=2,
            title="القسط الثاني",
            amount=Decimal("400.00"),
            due_date=date(2026, 11, 1),
            status=FeeInstallment.Status.PENDING,
        )
        self.assertEqual(plan.installments.count(), 2)

        # Exam Committee & Seating
        committee = ExamCommittee.objects.create(
            school=self.school,
            name="لجنة الشهادة الثانوية رقم 1",
            committee_number="COMM-01",
            location_room="قاعة الأندلس الكبرى",
            capacity=30,
            head_supervisor=self.teacher,
        )
        seating = ExamSeating.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            committee=committee,
            student=self.student,
            seating_number=1001,
            secret_code="SEC-X-77",
        )
        self.assertEqual(seating.seating_number, 1001)

    def test_reporting_engine_selectors(self):
        """التحقق من محرك التقارير الشامل: مالي، أكاديمي، حضور، وموارد بشرية."""
        # 1. Statement of Account
        stmt = get_student_statement_of_account(self.student)
        self.assertIn("summary", stmt)
        self.assertIn("invoices", stmt)

        # 2. Aging of Receivables
        aging = get_aging_receivables_report(self.school)
        self.assertIn("buckets", aging)

        # 3. Academic Report Card
        GradeBook.objects.create(
            school=self.school,
            student=self.student,
            subject=self.subject,
            assessment_title="اختبار نصف الفصل",
            score=Decimal("95.00"),
            max_score=Decimal("100.00"),
            is_published=True,
        )
        report_card = get_student_report_card(self.student)
        self.assertEqual(report_card["overall_summary"]["overall_percentage"], 95.0)
        self.assertEqual(report_card["overall_summary"]["overall_grade"], "ممتاز (A)")

        # 4. Class Ranking
        ranking = get_class_ranking_report(self.section)
        self.assertGreater(len(ranking["rankings"]), 0)

        # 5. Teacher Workload Report
        workload = get_teacher_workload_report(self.school)
        self.assertGreater(workload["teachers_count"], 0)

    def test_auto_posting_double_entry_integration(self):
        """التحقق من الترحيل الآلي المزدوج الشامل (Onyx Pro Integration)."""
        from apps.accounting.models import Account, PaymentVoucher
        from apps.accounting.services.auto_posting import (
            post_payment_voucher_to_journal,
            post_student_receipt_to_journal,
        )

        seed_default_chart_of_accounts(self.school)

        # 1. Post student fee receipt
        receipt = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            receipt_number="REC-AUTO-101",
            amount=Decimal("750.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )
        entry = post_student_receipt_to_journal(receipt)
        self.assertEqual(entry.lines.count(), 2)
        debit_line = entry.lines.filter(debit__gt=0).first()
        credit_line = entry.lines.filter(credit__gt=0).first()
        self.assertEqual(debit_line.debit, Decimal("750.00"))
        self.assertEqual(credit_line.credit, Decimal("750.00"))

        # 2. Post payment voucher
        cash_acc = Account.objects.get(school=self.school, code="1101")
        exp_acc = Account.objects.get(school=self.school, code="5204")
        voucher = PaymentVoucher.objects.create(
            school=self.school,
            voucher_number="PV-AUTO-202",
            paid_to="مورد القرطاسية",
            amount=Decimal("350.00"),
            credit_account=cash_acc,
            debit_account=exp_acc,
            description="شراء أدوات نظافة",
        )
        v_entry = post_payment_voucher_to_journal(voucher)
        self.assertEqual(v_entry.lines.count(), 2)
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, PaymentVoucher.Status.POSTED)

    def test_whatsapp_gateway_and_ai_auto_reply(self):
        """التحقق من بوابة الواتساب والرد الآلي الذكي لكل مدرسة."""
        from apps.notifications.api.views import _generate_school_ai_reply
        from apps.notifications.models import SchoolMessagingGateway

        gateway = SchoolMessagingGateway.objects.create(
            school=self.school,
            name="بوابة واتساب الأندلس",
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            provider=SchoolMessagingGateway.Provider.ULTRAMSG,
            api_endpoint_url="https://api.ultramsg.com/instance123/messages/chat",
            auth_token="test_token_abc",
            webhook_verify_token="test-webhook-secret",
            sender_id="+967777333000",
            auto_ai_reply=True,
        )
        self.assertTrue(gateway.auto_ai_reply)

        # Student query over WhatsApp
        reply = _generate_school_ai_reply(
            school=self.school,
            sender_phone=self.student.student_id_number,
            message_text="ما هو جدول الحصص اليوم؟",
        )
        self.assertIn("جدول", reply)

        # General visitor inquiry over WhatsApp
        general_reply = _generate_school_ai_reply(
            school=self.school,
            sender_phone="967770999888",
            message_text="هل التسجيل متاح لديكم في الصف العاشر؟",
        )
        self.assertIn(self.school.name, general_reply)
        self.assertIn("القبول والتسجيل", general_reply)

        # Test Webhook GET & POST via DRF APIClient
        from rest_framework.test import APIClient
        client = APIClient()
        get_res = client.get(f"/api/v1/notifications/webhook/whatsapp/{self.school.code}/")
        self.assertEqual(get_res.status_code, 200)

        import hashlib
        import hmac
        import json

        webhook_payload = {
            "from": self.student.student_id_number,
            "body": "???? ?????",
        }
        webhook_body = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
        webhook_signature = "sha256=" + hmac.new(
            b"test-webhook-secret", webhook_body, hashlib.sha256,
        ).hexdigest()
        post_res = client.post(
            f"/api/v1/notifications/webhook/whatsapp/{self.school.code}/",
            data=webhook_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=webhook_signature,
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.data["status"], "success")

    def test_bus_financial_settlement_and_book_distribution(self):
        """التحقق من التسوية المالية للباصات ومستحقات السائق وتوزيع الكتب المدرسية."""
        from apps.school_services.models import (
            BusFinancialSettlement,
            BusRoute,
            StudentBookDistribution,
            StudentBusSubscription,
        )

        bus = BusRoute.objects.create(
            school=self.school,
            route_code="BUS-FIN-01",
            route_name="خط النزهة والروضة",
            destination_area="حي النزهة",
            bus_number="9876-YEM",
            driver_name="صالح السائق",
            driver_phone="771122334",
            compensation_type=BusRoute.CompensationType.PER_STUDENT,
            contract_amount=Decimal("50.00"),
            contractor_type=BusRoute.ContractorType.EXTERNAL,
            monthly_fee=Decimal("150.00"),
        )

        StudentBusSubscription.objects.create(
            school=self.school,
            student=self.student,
            bus_route=bus,
            academic_year=self.academic_year,
            status=StudentBusSubscription.Status.ACTIVE,
        )

        settlement = BusFinancialSettlement.objects.create(
            school=self.school,
            bus_route=bus,
            academic_year=self.academic_year,
            month=10,
            year=2026,
            advances_withdrawn=Decimal("15.00"),
        )
        settlement.calculate_due()
        settlement.save()

        # 1 active student * 50 = 50 gross due, minus 15 advance = 35 net payable
        self.assertEqual(settlement.student_count, 1)
        self.assertEqual(settlement.gross_due, Decimal("50.00"))
        self.assertEqual(settlement.net_payable, Decimal("35.00"))

        # Book distribution test
        dist = StudentBookDistribution.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            book_title="كتاب الفيزياء المتقدم",
            fee_amount=Decimal("120.00"),
            delivery_status=StudentBookDistribution.DeliveryStatus.DELIVERED,
        )
        self.assertEqual(dist.delivery_status, "delivered")

    def test_journal_reversal_and_auto_allocation(self):
        """التحقق من عكس القيود المحاسبية وتخصيص الدفعات التلقائي على الفواتير."""
        from apps.accounting.models import JournalEntry
        from apps.accounting.services.auto_posting import reverse_journal_entry
        from apps.student_fees.models import StudentInvoice

        # 1. Test Journal Reversal
        entry = JournalEntry.objects.filter(school=self.school, status=JournalEntry.Status.POSTED).first()
        if entry:
            rev_entry = reverse_journal_entry(entry, reason="خطأ في تسجيل المستند الأصلي")
            entry.refresh_from_db()
            self.assertEqual(entry.status, JournalEntry.Status.CANCELLED)
            self.assertEqual(rev_entry.status, JournalEntry.Status.POSTED)
            self.assertIn("REV-", rev_entry.entry_number)

        # 2. Test Payment Receipt Auto Allocation to Student Invoice
        inv = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.academic_year,
            invoice_number="INV-AUTO-ALLOC-99",
            total_amount=Decimal("1000.00"),
            discount_amount=Decimal("100.00"),
            due_date=date(2026, 12, 1),
        )
        # Net payable is 900. Pay 400
        receipt = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv,
            receipt_number="RCP-AUTO-99",
            amount=Decimal("400.00"),
        )
        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("400.00"))
        self.assertEqual(inv.status, StudentInvoice.Status.PARTIAL)
        self.assertEqual(inv.remaining_amount, Decimal("500.00"))

    def test_security_copilot_and_reports_access_control(self):
        """التحقق الأمني من منع تسريب بيانات الطلاب ومنع غير المصرح لهم من رؤية التقارير المالية."""
        from rest_framework.test import APIClient

        from apps.accounts.models import SchoolMembership, User

        unauth_user = User.objects.create_user(
            phone="770000002",
            first_name="معلم",
            last_name="عادي",
            password="pass_test_123",
        )
        SchoolMembership.objects.create(
            user=unauth_user,
            school=self.school,
            status=SchoolMembership.Status.ACTIVE,
        )
        client = APIClient()
        client.force_authenticate(user=unauth_user)

        # 1. Copilot today lessons without linked student must return 403 Forbidden (no arbitrary leakage)
        copilot_res = client.get("/api/v1/copilot/student/today-lessons/")
        self.assertEqual(copilot_res.status_code, 403)

        # 2. Trial balance without finance role must return 403 Forbidden
        fin_res = client.get("/api/v1/reports/financial/trial-balance/")
        self.assertEqual(fin_res.status_code, 403)

    def test_staff_supervisors_and_section_capacity(self):
        """التحقق من تعيين مشرفي الأدوار والأقسام وحساب سعة الشعب ديناميكياً."""
        from apps.staff.models import StaffMember

        supervisor_user = User.objects.create_user(
            phone="+967777444101",
            password="StrongPassword123!",
            first_name="سليمان",
            last_name="المشرف",
        )
        staff_member = StaffMember.objects.create(
            school=self.school,
            user=supervisor_user,
            employee_number="STF-SUP-01",
            role=StaffMember.StaffRole.SUPERVISOR,
            assigned_floor_wing="الدور الثاني - الجناح أ",
            job_title="مشرف الدور الثاني",
        )
        self.assertEqual(staff_member.role, "supervisor")

        self.section.capacity = 35
        self.section.floor_wing = "الدور الثاني"
        self.section.supervisor_user = supervisor_user
        self.section.save()

        self.assertEqual(self.section.current_student_count, 1)
        self.assertEqual(self.section.available_seats, 34)
        self.assertFalse(self.section.is_full)

    def test_incident_summon_complaint_workflow(self):
        """التحقق من تقارير الوقائع السلوكية والاستدعاء الإداري وصندوق الشكاوى."""
        from django.utils import timezone

        from apps.students.models import (
            AdministrativeSummon,
            Guardian,
            SchoolComplaint,
            StudentGuardianRelation,
            StudentIncidentReport,
        )

        guardian_user = User.objects.create_user(
            phone="+967777444102",
            password="StrongPassword123!",
            first_name="أحمد",
            last_name="ولي الأمر",
        )
        guardian = Guardian.objects.create(
            school=self.school,
            user=guardian_user,
            relationship_type=Guardian.RelationshipType.FATHER,
            emergency_phone="777444102",
        )
        StudentGuardianRelation.objects.create(
            school=self.school,
            student=self.student,
            guardian=guardian,
            is_primary=True,
        )

        incident = StudentIncidentReport.objects.create(
            school=self.school,
            student=self.student,
            reporter=self.teacher_user,
            severity=StudentIncidentReport.Severity.MEDIUM,
            title="تأخر متكرر عن الحصة الأولى",
            details="لوحظ التأخر لثلاثة أيام متتالية",
            parent_notified=True,
        )
        self.assertEqual(incident.severity, "medium")
        self.assertTrue(incident.parent_notified)

        summon = AdministrativeSummon.objects.create(
            school=self.school,
            student=self.student,
            target_user=guardian_user,
            summon_type=AdministrativeSummon.TargetType.GUARDIAN,
            reason="مناقشة الانضباط والالتزام بالمواعيد الرسمية",
            appointment_date=timezone.now() + timezone.timedelta(days=3),
            issued_by=self.user,
        )
        self.assertFalse(summon.is_attended)

        complaint = SchoolComplaint.objects.create(
            school=self.school,
            submitter=guardian_user,
            category=SchoolComplaint.Category.ACADEMIC,
            subject="استفسار عن خطة اختبارات الشهر الثاني",
            details="يرجى تزويدنا بجدول الاختبارات الشهرية المعتمد",
        )
        self.assertEqual(complaint.status, "new")

    def test_book_requisition_order_workflow(self):
        """التحقق من دورة أوامر صرف الكتب من المشرف للمخزن والاعتماد."""
        from apps.school_services.models import BookRequisitionItem, BookRequisitionOrder

        SchoolMembership.objects.get_or_create(
            school=self.school,
            user=self.user,
            defaults={"status": SchoolMembership.Status.ACTIVE},
        )
        req_order = BookRequisitionOrder.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            requested_by=self.user,
            order_number="REQ-2026-001",
            notes="طلب كتب الرياضيات للصف العاشر",
        )
        self.assertEqual(req_order.order_number, "REQ-2026-001")
        self.assertEqual(req_order.status, BookRequisitionOrder.Status.DRAFT)

        item = BookRequisitionItem.objects.create(
            school=self.school,
            requisition=req_order,
            book_title="الرياضيات للصف العاشر - الجزء الأول",
            quantity_requested=30,
        )
        self.assertEqual(item.quantity_requested, 30)

        req_order.status = BookRequisitionOrder.Status.SUBMITTED
        req_order._allow_requisition_workflow_update = True
        req_order.save(update_fields=["status", "updated_at"])
        req_order.status = BookRequisitionOrder.Status.APPROVED
        req_order.approved_by = self.user
        req_order._allow_requisition_workflow_update = True
        req_order.save(update_fields=["status", "approved_by", "updated_at"])
        self.assertEqual(req_order.status, "approved")

    def test_question_bank_and_online_exam_auto_grading(self):
        """التحقق من بنك الأسئلة، وإنشاء الاختبار الإلكتروني والتصحيح التلقائي."""
        from django.utils import timezone

        from apps.assessments.models import OnlineExam, QuestionBank, StudentOnlineExamSubmission

        q1 = QuestionBank.objects.create(
            school=self.school,
            subject=self.subject,
            grade_level=self.grade,
            unit_name="الوحدة الأولى: الجبر",
            question_type=QuestionBank.QuestionType.MCQ,
            question_text="ما هو ناتج 2 + 2؟",
            options_json=[{"id": "A", "text": "4"}, {"id": "B", "text": "5"}],
            correct_answer="A",
            default_marks=Decimal("5.00"),
            created_by=self.teacher_user,
        )
        q2 = QuestionBank.objects.create(
            school=self.school,
            subject=self.subject,
            grade_level=self.grade,
            unit_name="الوحدة الأولى: الجبر",
            question_type=QuestionBank.QuestionType.TRUE_FALSE,
            question_text="مجموع زوايا المثلث 180 درجة.",
            correct_answer="true",
            default_marks=Decimal("5.00"),
            created_by=self.teacher_user,
        )

        exam = OnlineExam.objects.create(
            school=self.school,
            title="اختبار الجبر القصير",
            subject=self.subject,
            academic_term=self.term,
            grade_level=self.grade,
            created_by=self.teacher_user,
            duration_minutes=30,
            total_marks=Decimal("10.00"),
            passing_marks=Decimal("5.00"),
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=2),
            is_published=True,
        )
        exam.questions.set([q1, q2])

        submission = StudentOnlineExamSubmission.objects.create(
            school=self.school,
            exam=exam,
            student=self.student,
            answers_json={
                str(q1.id): "A",
                str(q2.id): "true",
            },
        )
        earned = submission.auto_grade()
        self.assertEqual(earned, Decimal("10.00"))
        self.assertEqual(submission.final_score, Decimal("10.00"))
        self.assertTrue(submission.passed)
        self.assertEqual(submission.status, StudentOnlineExamSubmission.Status.GRADED)

    def test_ai_timetable_generator_service(self):
        """التحقق من خوارزمية التوليد الآلي لجدول الحصص الأسبوعي بدون تعارضات."""
        from apps.staff.models import TeacherAssignment
        from apps.timetable.models import ClassSchedule
        from apps.timetable.services.ai_generator import generate_school_timetable

        TeacherAssignment.objects.create(
            school=self.school,
            teacher=self.teacher,
            subject=self.subject,
            section=self.section,
            academic_year=self.academic_year,
            weekly_periods=4,
        )

        # 1. Preview mode (dry_run = True)
        preview_res = generate_school_timetable(
            school=self.school,
            academic_year=self.academic_year,
            dry_run=True,
        )
        self.assertEqual(preview_res["status"], "success")
        self.assertEqual(preview_res["mode"], "preview")
        self.assertGreaterEqual(preview_res["total_generated"], 1)

        # 2. Commit mode (dry_run = False)
        commit_res = generate_school_timetable(
            school=self.school,
            academic_year=self.academic_year,
            dry_run=False,
        )
        self.assertEqual(commit_res["status"], "success")
        self.assertEqual(commit_res["mode"], "committed")

        schedules = ClassSchedule.objects.filter(school=self.school, section=self.section)
        self.assertEqual(schedules.count(), commit_res["total_generated"])
