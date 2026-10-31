"""
tests/test_report4_fixes.py
Comprehensive test suite verifying all fixes from chatgptreport4:
1. Strict immutability of POSTED journal entries and lines (save, add, delete, school isolation).
2. Advanced student credit unwinding upon receipt reversal (restoring invoice balance & reversing settlement JV).
3. Payroll advance date filtering, absence revenue account 4201, and full payroll reversal.
4. Security hardening: removing is_staff tenant bypass from reports.
5. Inbound webhook deduplication via InboundWebhookMessage.
6. Inventory StockMovement update and delete stock consistency.
7. StudentBookDistribution pessimistic locking and return tracking.
8. Academic student promotion and enrollment history services.
9. Vendor invoice auto-posting and disbursement.
10. REST API endpoints for students, fees, staff, and payroll.
"""
import hashlib
import hmac
import json
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.accounting.models import Account, FiscalPeriod, FiscalYear, JournalEntry, JournalEntryLine
from apps.accounting.services.auto_posting import (
    disburse_vendor_payment,
    post_vendor_invoice_to_journal,
)
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.inventory.models import InventoryItem, StockMovement, Supplier, VendorInvoice, Warehouse
from apps.notifications.models import InboundWebhookMessage, SchoolMessagingGateway
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun
from apps.payroll.services import (
    approve_payroll_run,
    generate_monthly_payroll,
    post_payroll_to_accounting,
    reverse_payroll_run,
)
from apps.school_services.models import StudentBookDistribution
from apps.staff.models import Teacher
from apps.student_fees.models import (
    FeeCategory,
    PaymentReceipt,
    StudentInvoice,
    apply_credit_balance_to_invoice,
    reverse_payment_receipt,
)
from apps.students.models import Student, StudentEnrollment
from apps.students.services import (
    promote_student,
)
from apps.tenants.models import School
from apps.tenants.services import provision_school


class Report4FixesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(phone="+966500000099", password="password123", first_name="مالك", last_name="المدرسة")
        self.owner2 = User.objects.create_user(phone="+966500000098", password="password123", first_name="مالك", last_name="الثاني")
        self.school = School.objects.create(owner=self.owner, name="مدرسة التميز النموذجية", code="TAMAYUZ", status=School.Status.ACTIVE)
        self.school2 = School.objects.create(owner=self.owner2, name="مدرسة أخرى", code="OTHER", status=School.Status.ACTIVE)
        provision_school(self.school)
        provision_school(self.school2)
        seed_default_chart_of_accounts(self.school)
        seed_default_chart_of_accounts(self.school2)

        # Fiscal year & period
        today = timezone.localdate()
        self.fy = FiscalYear.objects.create(
            school=self.school,
            name=f"السنة المالية {today.year}",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            is_closed=False,
        )
        self.fp = FiscalPeriod.objects.create(
            school=self.school,
            fiscal_year=self.fy,
            period_number=today.month,
            name=f"فترة {today.strftime('%B %Y')}",
            start_date=date(today.year, today.month, 1),
            end_date=date(today.year, 12, 31),
            is_closed=False,
        )

        # Academic structure
        self.year = AcademicYear.objects.create(
            school=self.school,
            code="AY-2026",
            name=f"العام الدراسي {today.year}-{today.year+1}",
            starts_on=today,
            ends_on=today + timedelta(days=250),
            status=AcademicYear.Status.ACTIVE,
            is_current=True,
        )
        self.next_year = AcademicYear.objects.create(
            school=self.school,
            code="AY-2027",
            name=f"العام الدراسي {today.year+1}-{today.year+2}",
            starts_on=today + timedelta(days=260),
            ends_on=today + timedelta(days=500),
            status=AcademicYear.Status.PLANNING,
            is_current=False,
        )
        self.stage = EducationalStage.objects.create(school=self.school, code="PRI", name="الابتدائية", sequence=1)
        self.grade1 = GradeLevel.objects.create(school=self.school, stage=self.stage, code="G1", name="الصف الأول الابتدائي", sequence=1)
        self.grade2 = GradeLevel.objects.create(school=self.school, stage=self.stage, code="G2", name="الصف الثاني الابتدائي", sequence=2)
        self.sec1 = Section.objects.create(school=self.school, grade=self.grade1, academic_year=self.year, code="SEC1", name="شعبة أ")
        self.sec2 = Section.objects.create(school=self.school, grade=self.grade2, academic_year=self.next_year, code="SEC2", name="شعبة أ")

        # Users & Memberships
        self.admin_user = User.objects.create_user(phone="+966500000001", password="password123", first_name="مدير", last_name="المدرسة")
        self.cashier_user = User.objects.create_user(phone="+966500000002", password="password123", first_name="أمين", last_name="الصندوق")
        self.staff_only_user = User.objects.create_user(phone="+966500000003", password="password123", first_name="موظف", last_name="عام", is_staff=True)

        role_admin = SchoolRole.objects.filter(school=self.school, code="admin").first() or SchoolRole.objects.create(school=self.school, code="admin", name="مدير")
        role_accountant = SchoolRole.objects.filter(school=self.school, code="accountant").first() or SchoolRole.objects.create(school=self.school, code="accountant", name="محاسب")

        self.mem_admin = SchoolMembership.objects.create(user=self.admin_user, school=self.school, status="active", is_default=True)
        MembershipRole.objects.create(membership=self.mem_admin, role=role_admin)

        self.mem_cashier = SchoolMembership.objects.create(user=self.cashier_user, school=self.school, status="active", is_default=True)
        MembershipRole.objects.create(membership=self.mem_cashier, role=role_accountant)

        # Student
        self.student = Student.objects.create(
            school=self.school,
            student_id_number="STD-001",
            first_name="أحمد",
            last_name="المحمد",
            academic_year=self.year,
            grade_level=self.grade1,
            section=self.sec1,
            status=Student.Status.ACTIVE,
        )

        # Fee category
        self.category = FeeCategory.objects.create(school=self.school, name="رسوم دراسية", code="TUI")

    # ---------------- 1. Accounting Protection & Immutability ----------------
    def test_cannot_add_or_modify_or_delete_line_on_posted_journal_entry(self):
        """التحقق الصارم من منع إضافة أو تعديل أو حذف أسطر القيد بعد الترحيل وعزل المدارس."""
        entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=self.fp,
            entry_number="JV-TEST-001",
            date=timezone.localdate(),
            status=JournalEntry.Status.DRAFT,
            description="قيد اختباري",
        )
        acc1 = Account.objects.get(school=self.school, code="1101")
        acc2 = Account.objects.get(school=self.school, code="4101")

        line1 = JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=acc1,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
            description="مدين",
        )
        _line2 = JournalEntryLine.objects.create(
            school=self.school,
            journal_entry=entry,
            account=acc2,
            debit=Decimal("0.00"),
            credit=Decimal("500.00"),
            description="دائن",
        )

        # Post entry
        entry.post(user=self.admin_user)
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

        # Attempt to add new line to POSTED entry -> must fail
        with self.assertRaises(ValidationError):
            JournalEntryLine.objects.create(
                school=self.school,
                journal_entry=entry,
                account=acc1,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
                description="إضافة غير قانونية",
            )

        # Attempt to modify existing line on POSTED entry -> must fail
        with self.assertRaises(ValidationError):
            line1.debit = Decimal("600.00")
            line1.save()

        # Attempt to delete existing line on POSTED entry -> must fail
        with self.assertRaises(ValidationError):
            line1.delete()

        # Attempt to attach line from different school -> must fail
        draft_entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=self.fp,
            entry_number="JV-TEST-002",
            date=timezone.localdate(),
            status=JournalEntry.Status.DRAFT,
            description="قيد مسودة",
        )
        acc_school2 = Account.objects.get(school=self.school2, code="1101")
        with self.assertRaises(ValidationError):
            JournalEntryLine.objects.create(
                school=self.school2,
                journal_entry=draft_entry,
                account=acc_school2,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            )

    # ---------------- 2. Advanced Credit Reversal & Unwinding ----------------
    def test_reverse_payment_receipt_with_consumed_credit(self):
        """
        التحقق من إلغاء سند قبض تم استهلاك فائضه الدائن في سداد فاتورة لاحقة:
        يجب فك حركات الاستهلاك، إعادة فتح الفاتورة، عكس قيود التسوية، دون ترك رصيد سالب أو شاذ.
        """
        # Invoice 1: 1000 SAR
        inv1 = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.year,
            invoice_number="INV-REV-01",
            total_amount=Decimal("1000.00"),
            due_date=timezone.localdate(),
        )
        # Receipt 1: 1500 SAR (pays inv1 in full + 500 SAR excess credit)
        rcp1 = PaymentReceipt.objects.create(
            school=self.school,
            student=self.student,
            invoice=inv1,
            receipt_number="RCP-REV-01",
            amount=Decimal("1500.00"),
            received_by=self.cashier_user,
        )
        inv1.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(inv1.status, StudentInvoice.Status.PAID)
        self.assertEqual(self.student.credit_balance, Decimal("500.00"))

        # Invoice 2: 400 SAR
        inv2 = StudentInvoice.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.year,
            invoice_number="INV-REV-02",
            total_amount=Decimal("400.00"),
            due_date=timezone.localdate(),
        )
        # Apply 400 SAR from credit to inv2
        usage_tx = apply_credit_balance_to_invoice(
            student=self.student,
            invoice=inv2,
            amount=Decimal("400.00"),
            user=self.cashier_user,
        )
        inv2.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(inv2.status, StudentInvoice.Status.PAID)
        self.assertEqual(self.student.credit_balance, Decimal("100.00"))
        settlement_entry = JournalEntry.objects.filter(source_module="student_fees_credit", source_reference=str(usage_tx.id)).first()
        self.assertIsNotNone(settlement_entry)

        # Now reverse rcp1! The system must automatically unwind usage_tx, restore inv2 unpaid balance,
        # reverse settlement JV, and reset student credit balance cleanly to 0.
        reverse_payment_receipt(rcp1, reason="خطأ إيداع بنكي", reversed_by=self.cashier_user)

        rcp1.refresh_from_db()
        inv1.refresh_from_db()
        inv2.refresh_from_db()
        self.student.refresh_from_db()
        settlement_entry.refresh_from_db()

        self.assertTrue(rcp1.is_cancelled)
        self.assertEqual(inv1.paid_amount, Decimal("0.00"))
        self.assertEqual(inv1.status, StudentInvoice.Status.UNPAID)
        self.assertEqual(inv2.paid_amount, Decimal("0.00"))
        self.assertEqual(inv2.status, StudentInvoice.Status.UNPAID)
        self.assertEqual(self.student.credit_balance, Decimal("0.00"))
        self.assertTrue(settlement_entry.is_reversed)

    # ---------------- 3. Payroll Advance Date Filter & Reversal ----------------
    def test_payroll_advance_filter_and_full_reversal(self):
        """التحقق من عدم خصم السلف المستقبلية وعكس مسير الرواتب بالكامل وإعادة أرصدة السلف."""
        teacher_user = User.objects.create_user(phone="+966500000010", password="password123", first_name="معلم", last_name="متميز")
        teacher = Teacher.objects.create(school=self.school, user=teacher_user, specialization="رياضيات")
        EmployeeContract.objects.create(
            school=self.school,
            teacher=teacher,
            contract_number="CNT-2026-001",
            contract_type=EmployeeContract.ContractType.FULL_TIME,
            basic_salary=Decimal("6000.00"),
            housing_allowance=Decimal("1000.00"),
            transport_allowance=Decimal("500.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        # Loan starting next year (should NOT be deducted now)
        _future_loan = EmployeeLoanAdvance.objects.create(
            school=self.school,
            teacher=teacher,
            loan_number="LN-FUTURE-01",
            amount=Decimal("10000.00"),
            monthly_installment=Decimal("1000.00"),
            start_date=date(2027, 1, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )
        # Active loan starting now
        active_loan = EmployeeLoanAdvance.objects.create(
            school=self.school,
            teacher=teacher,
            loan_number="LN-ACTIVE-01",
            amount=Decimal("2000.00"),
            monthly_installment=Decimal("500.00"),
            start_date=date(2026, 1, 1),
            status=EmployeeLoanAdvance.Status.ACTIVE,
        )

        run = generate_monthly_payroll(school=self.school, month=10, year=2026, created_by=self.admin_user)
        slip = run.payslips.first()
        # Active loan was deducted (500), future loan was NOT deducted (total loan deduction = 500)
        self.assertEqual(slip.loan_deduction, Decimal("500.00"))

        # Approve and post payroll to accounting
        approve_payroll_run(run, approved_by=self.admin_user)
        entry = post_payroll_to_accounting(run, user=self.admin_user)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.POSTED)
        active_loan.refresh_from_db()
        self.assertEqual(active_loan.repaid_amount, Decimal("500.00"))

        # Reverse payroll run
        reverse_payroll_run(run, reason="خطأ في احتساب الحسميات", reversed_by=self.admin_user)
        run.refresh_from_db()
        active_loan.refresh_from_db()
        entry.refresh_from_db()

        self.assertEqual(run.status, PayrollRun.Status.DRAFT)
        self.assertEqual(active_loan.repaid_amount, Decimal("0.00"))
        self.assertTrue(entry.is_reversed)

    # ---------------- 4. Security Hardening (is_staff Tenant Bypass Removed) ----------------
    def test_reports_security_no_is_staff_bypass(self):
        """التحقق من أن موظف النظام (is_staff) لا يستطيع الاطلاع على تقارير المدرسة بدون عضوية صريحة."""
        self.client.force_authenticate(user=self.staff_only_user)
        url = f"/api/v1/reports/financial/balance-sheet/?school_code={self.school.code}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ---------------- 5. Webhook Inbound Deduplication ----------------
    def test_webhook_inbound_deduplication(self):
        """التحقق من منع معالجة الرسائل المكررة الواردة عبر Webhook."""
        SchoolMessagingGateway.objects.create(
            school=self.school,
            name="بوابة الواتساب",
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            provider=SchoolMessagingGateway.Provider.CUSTOM_WEBHOOK,
            api_endpoint_url="https://api.example.com/whatsapp",
            webhook_verify_token="test_secret_key",
            is_active=True,
        )
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "WAMID-123456789",
                            "from": "966500000001",
                            "text": {"body": "مرحبا بك"},
                        }]
                    }
                }]
            }]
        }
        body_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        sig = "sha256=" + hmac.new(b"test_secret_key", body_bytes, hashlib.sha256).hexdigest()

        # First request -> 200
        client = APIClient()
        resp1 = client.post(
            f"/api/v1/notifications/webhook/whatsapp/?school_code={self.school.code}",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertTrue(InboundWebhookMessage.objects.filter(school=self.school, provider_msg_id="WAMID-123456789").exists())

        # Second request with identical provider msg id -> accepted but ignored (duplicate)
        resp2 = client.post(
            f"/api/v1/notifications/webhook/whatsapp/?school_code={self.school.code}",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data.get("status"), "duplicate_ignored")
        self.assertEqual(InboundWebhookMessage.objects.filter(school=self.school, provider_msg_id="WAMID-123456789").count(), 1)

    # ---------------- 6. Inventory StockMovement Updates and Deletes ----------------
    def test_stock_movement_updates_and_deletes_adjusts_stock(self):
        """التحقق من تصحيح رصيد المخزون عند تعديل أو حذف حركات المخزون."""
        wh = Warehouse.objects.create(school=self.school, name="المستودع الرئيسي", code="WH-1")
        item = InventoryItem.objects.create(
            school=self.school,
            warehouse=wh,
            name="كتاب العلوم",
            code="SCI-01",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("20.00"),
        )
        # Create issue movement of 20 units -> stock drops to 80
        mv = StockMovement.objects.create(
            school=self.school,
            item=item,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=Decimal("20.00"),
            unit_cost=Decimal("20.00"),
        )
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("80.00"))

        # Update movement quantity to 35 -> stock should be 100 - 35 = 65
        mv.quantity = Decimal("35.00")
        mv.save()
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("65.00"))

        # Delete movement -> stock should restore back to 100
        mv.delete()
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("100.00"))

    # ---------------- 7. Student Promotion & Enrollment History ----------------
    def test_student_promotion_service(self):
        """التحقق من ترفيع الطالب وتحديث سجل قيده السنوي بدقة."""
        # Initial enrollment exists from student creation
        self.assertTrue(
            StudentEnrollment.objects.filter(
                school=self.school,
                student=self.student,
                academic_year=self.year,
            ).exists()
        )

        # Promote student
        promoted_std, new_enrollment = promote_student(
            student=self.student,
            next_academic_year=self.next_year,
            next_grade_level=self.grade2,
            next_section=self.sec2,
            user=self.admin_user,
        )
        promoted_std.refresh_from_db()
        self.assertEqual(promoted_std.academic_year, self.next_year)
        self.assertEqual(promoted_std.grade_level, self.grade2)
        self.assertEqual(promoted_std.section, self.sec2)

        prev_enr = StudentEnrollment.objects.get(student=self.student, academic_year=self.year)
        self.assertEqual(prev_enr.status, StudentEnrollment.Status.PROMOTED)
        self.assertEqual(prev_enr.final_result, StudentEnrollment.FinalResult.PASSED)

        self.assertEqual(new_enrollment.status, StudentEnrollment.Status.ENROLLED)
        self.assertEqual(new_enrollment.grade_level, self.grade2)

    # ---------------- 8. Book Distribution Locking and Returns ----------------
    def test_student_book_distribution_locking_and_return(self):
        """التحقق من دورة تسليم واسترجاع الكتب المدرسية مع توثيق المستلم والمستودع."""
        wh = Warehouse.objects.create(school=self.school, name="مستودع الكتب", code="WH-BOOKS")
        item = InventoryItem.objects.create(
            school=self.school,
            warehouse=wh,
            name="كتاب الرياضيات 1",
            code="BK-MATH-1",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("25.00"),
        )
        dist = StudentBookDistribution.objects.create(
            school=self.school,
            student=self.student,
            academic_year=self.year,
            inventory_item=item,
            book_title="كتاب الرياضيات 1",
            quantity=Decimal("2.00"),
            fee_amount=Decimal("50.00"),
        )
        dist.deliver_book(user=self.admin_user)
        dist.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.DELIVERED)
        self.assertEqual(dist.delivered_by, self.admin_user)
        self.assertEqual(item.current_stock, Decimal("48.00"))

        dist.return_book(user=self.cashier_user)
        dist.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.RETURNED)
        self.assertEqual(dist.returned_by, self.cashier_user)
        self.assertIsNotNone(dist.returned_at)
        self.assertEqual(item.current_stock, Decimal("50.00"))

    # ---------------- 9. Vendor Invoice Auto-Posting & Payment Disbursement ----------------
    def test_vendor_invoice_posting_and_payment_disbursement(self):
        """التحقق من قيد استحقاق فاتورة المورد وسدادها محاسبياً."""
        supplier = Supplier.objects.create(school=self.school, name="دار النشر الحديثة", code="SUP-01", phone="+966500000088")
        v_inv = VendorInvoice.objects.create(
            school=self.school,
            supplier=supplier,
            invoice_number="VINV-2026-001",
            total_amount=Decimal("3000.00"),
        )
        entry = post_vendor_invoice_to_journal(v_inv, user=self.admin_user)
        v_inv.refresh_from_db()
        self.assertEqual(v_inv.status, VendorInvoice.Status.APPROVED)
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

        bank_acc = Account.objects.get(school=self.school, code="1102")
        disb_entry, voucher = disburse_vendor_payment(
            vendor_invoice=v_inv,
            payment_account=bank_acc,
            amount=Decimal("1500.00"),
            user=self.admin_user,
        )
        v_inv.refresh_from_db()
        self.assertEqual(v_inv.paid_amount, Decimal("1500.00"))
        self.assertEqual(v_inv.remaining_amount, Decimal("1500.00"))
        self.assertEqual(v_inv.status, VendorInvoice.Status.PARTIAL)
        self.assertEqual(disb_entry.status, JournalEntry.Status.POSTED)

    # ---------------- 9. REST API Endpoints v1 ----------------
    def test_rest_api_v1_endpoints(self):
        """التحقق من عمل كافة واجهات API الجديدة للطلاب والرسوم والموظفين والرواتب."""
        token, _ = Token.objects.get_or_create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # Students API
        resp = self.client.get(f"/api/v1/students/?school_code={self.school.code}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data.get("results", resp.data)), 1)

        # Fees API - Invoices
        resp = self.client.get(f"/api/v1/fees/invoices/?school_code={self.school.code}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Staff API - Members
        resp = self.client.get(f"/api/v1/staff/members/?school_code={self.school.code}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Payroll API - Runs
        resp = self.client.get(f"/api/v1/payroll/runs/?school_code={self.school.code}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


    def test_student_api_create_update_archive_and_lifecycle_protection(self):
        """Student profile CRUD must not bypass promotion/retention/withdraw workflows."""
        token, _ = Token.objects.get_or_create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        payload = {
            "student_id_number": "STD-API-002",
            "first_name": "سارة",
            "middle_name": "محمد",
            "last_name": "العطاب",
            "gender": Student.Gender.FEMALE,
            "national_id": "NID-API-002",
            "birth_date": "2015-03-12",
            "academic_year": str(self.year.pk),
            "grade_level": str(self.grade1.pk),
            "section": str(self.sec1.pk),
            "enrollment_date": timezone.localdate().isoformat(),
            "status": Student.Status.ACTIVE,
            "credit_balance": "99999.00",
        }
        response = self.client.post(
            f"/api/v1/students/?school_code={self.school.code}",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        student_id = response.data["id"]
        student = Student.objects.get(pk=student_id, school=self.school)
        self.assertEqual(student.credit_balance, Decimal("0.00"))
        self.assertTrue(
            StudentEnrollment.objects.filter(
                student=student, academic_year=self.year,
            ).exists()
        )

        detail_url = f"/api/v1/students/{student_id}/?school_code={self.school.code}"
        response = self.client.patch(
            detail_url,
            {"first_name": "سارة الجديدة"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        student.refresh_from_db()
        self.assertEqual(student.first_name, "سارة الجديدة")

        # Academic placement/status changes must go through the explicit lifecycle APIs.
        response = self.client.patch(
            detail_url,
            {
                "academic_year": str(self.next_year.pk),
                "grade_level": str(self.grade2.pk),
                "section": str(self.sec2.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        student.refresh_from_db()
        self.assertEqual(student.academic_year_id, self.year.pk)
        self.assertEqual(student.section_id, self.sec1.pk)

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        student.refresh_from_db()
        self.assertTrue(student.is_archived)
