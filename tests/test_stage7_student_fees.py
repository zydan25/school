from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.accounting.models import JournalEntry
from apps.accounting.services.auto_posting import post_student_invoice_to_journal
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.student_fees.models import (
    FeeCategory,
    FeeDiscountPolicy,
    FeeDiscountRequest,
    FeeInstallment,
    FeeInstallmentPlan,
    FeeStructure,
    PaymentReceipt,
    StudentCreditTransaction,
    StudentInvoice,
    apply_credit_balance_to_invoice,
    approve_fee_discount_request,
    refund_student_credit,
    reverse_credit_refund,
    reverse_credit_usage,
    submit_fee_discount_request,
)
from apps.students.models import Student
from apps.tenants.models import Branch, School
from apps.tenants.services import provision_school


class Stage7StudentFeesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770007001", password="StrongPassword123!",
            first_name="مالك", last_name="المدرسة",
        )
        self.school = School.objects.create(
            owner=self.owner, name="مدرسة المرحلة السابعة",
            code="STAGE7", status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        seed_default_chart_of_accounts(self.school)

        self.cashier = User.objects.create_user(
            phone="+967770007002", password="StrongPassword123!",
            first_name="أمين", last_name="الصندوق",
        )
        accountant_role = SchoolRole.objects.filter(
            school=self.school, code="accountant",
        ).first()
        if accountant_role is None:
            accountant_role = SchoolRole.objects.create(
                school=self.school, code="accountant", name="محاسب",
            )
        membership = SchoolMembership.objects.create(
            user=self.cashier, school=self.school, status=SchoolMembership.Status.ACTIVE,
            is_default=True,
        )
        MembershipRole.objects.create(membership=membership, role=accountant_role)

        today = timezone.localdate()
        self.academic_year = AcademicYear.objects.create(
            school=self.school, code=f"AY-{today.year}",
            name=f"العام الدراسي {today.year}",
            starts_on=today - timedelta(days=30),
            ends_on=today + timedelta(days=300),
            status=AcademicYear.Status.ACTIVE, is_current=True,
        )
        self.stage = EducationalStage.objects.create(
            school=self.school, code="PRI", name="الابتدائية", sequence=1,
        )
        self.grade = GradeLevel.objects.create(
            school=self.school, stage=self.stage, code="G1",
            name="الصف الأول", sequence=1,
        )
        self.section = Section.objects.create(
            school=self.school, academic_year=self.academic_year,
            grade=self.grade, code="A", name="أ",
        )
        self.student = Student.objects.create(
            school=self.school, student_id_number="S7-001",
            first_name="أحمد", last_name="الطالب",
            academic_year=self.academic_year, grade_level=self.grade,
            section=self.section, status=Student.Status.ACTIVE,
        )
        self.category = FeeCategory.objects.create(
            school=self.school, name="رسوم دراسية", code="TUITION",
        )

    def seed_credit_balance(self, amount, receipt_number):
        return PaymentReceipt.objects.create(
            school=self.school, student=self.student,
            receipt_number=receipt_number, amount=Decimal(amount),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )

    def make_invoice(self, number="S7-INV-001", amount="100.00"):
        invoice = StudentInvoice.objects.create(
            school=self.school, student=self.student,
            academic_year=self.academic_year, invoice_number=number,
            total_amount=Decimal(amount), discount_amount=Decimal("0.00"),
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=30),
        )
        post_student_invoice_to_journal(invoice)
        invoice.refresh_from_db()
        return invoice

    def test_student_credit_balance_cannot_be_changed_directly(self):
        self.student.credit_balance = Decimal("10.00")
        with self.assertRaises(ValidationError):
            self.student.save(update_fields=["credit_balance"])
        self.student.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("0.00"))
        with self.assertRaises(ValidationError):
            Student.objects.filter(pk=self.student.pk).update(
                credit_balance=Decimal("20.00"),
            )
        self.student.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("0.00"))

    def test_invoice_and_receipt_inherit_student_branch_for_legacy_callers(self):
        branch = Branch.objects.create(
            school=self.school, code="BR-A", name="الفرع أ",
        )
        student = Student.objects.create(
            school=self.school, branch=branch,
            student_id_number="S7-BR-001",
            first_name="سالم", last_name="الفرعي",
            academic_year=self.academic_year, grade_level=self.grade,
            section=self.section, status=Student.Status.ACTIVE,
        )
        invoice = StudentInvoice.objects.create(
            school=self.school, student=student,
            academic_year=self.academic_year,
            invoice_number="S7-BR-INV-001",
            total_amount=Decimal("100.00"),
            due_date=timezone.localdate() + timedelta(days=20),
        )
        post_student_invoice_to_journal(invoice)
        receipt = PaymentReceipt.objects.create(
            school=self.school, student=student, invoice=invoice,
            receipt_number="S7-BR-RCP-001",
            amount=Decimal("25.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )
        invoice.refresh_from_db()
        receipt.refresh_from_db()
        allocation = receipt.allocations.get(status="active")
        self.assertEqual(invoice.branch_id, branch.pk)
        self.assertEqual(receipt.branch_id, branch.pk)
        self.assertEqual(allocation.branch_id, branch.pk)
        self.assertEqual(invoice.journal_entry.branch_id, branch.pk)
        self.assertEqual(receipt.journal_entry.branch_id, branch.pk)
        self.assertTrue(invoice.journal_entry.lines.filter(branch=branch).exists())
        self.assertTrue(receipt.journal_entry.lines.filter(branch=branch).exists())

    def test_fee_structures_support_global_and_branch_overrides(self):
        branch_a = Branch.objects.create(
            school=self.school, code="A", name="الفرع أ",
        )
        branch_b = Branch.objects.create(
            school=self.school, code="B", name="الفرع ب",
        )
        global_structure = FeeStructure.objects.create(
            school=self.school, academic_year=self.academic_year,
            grade_level=self.grade, fee_category=self.category,
            amount=Decimal("100.00"),
        )
        structure_a = FeeStructure.objects.create(
            school=self.school, branch=branch_a,
            academic_year=self.academic_year, grade_level=self.grade,
            fee_category=self.category, amount=Decimal("110.00"),
        )
        structure_b = FeeStructure.objects.create(
            school=self.school, branch=branch_b,
            academic_year=self.academic_year, grade_level=self.grade,
            fee_category=self.category, amount=Decimal("120.00"),
        )
        self.assertEqual(global_structure.amount, Decimal("100.00"))
        self.assertEqual(structure_a.amount, Decimal("110.00"))
        self.assertEqual(structure_b.amount, Decimal("120.00"))

        duplicate = FeeStructure(
            school=self.school, branch=branch_a,
            academic_year=self.academic_year, grade_level=self.grade,
            fee_category=self.category, amount=Decimal("115.00"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                duplicate.save()

    def test_receipt_financial_fields_are_immutable_after_creation(self):
        invoice = self.make_invoice()
        receipt = PaymentReceipt.objects.create(
            school=self.school, student=self.student, invoice=invoice,
            receipt_number="S7-RCP-001", amount=Decimal("25.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            idempotency_key="receipt-immutable-001",
        )
        invoice.refresh_from_db()
        original_paid_amount = invoice.paid_amount
        receipt.amount = Decimal("35.00")
        with self.assertRaises(ValidationError):
            receipt.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, original_paid_amount)

    def test_credit_usage_allocates_to_installments_is_idempotent_and_reversible(self):
        self.seed_credit_balance("100.00", "S7-CREDIT-RCP-001")
        invoice = self.make_invoice("S7-INV-002", "80.00")
        plan = FeeInstallmentPlan.objects.create(
            school=self.school, student=self.student, invoice=invoice,
            plan_name="قسطان", total_amount=Decimal("80.00"),
            number_of_installments=2,
        )
        first = FeeInstallment.objects.create(
            school=self.school, plan=plan, installment_number=1,
            title="القسط الأول", amount=Decimal("30.00"),
            due_date=timezone.localdate() + timedelta(days=10),
        )
        second = FeeInstallment.objects.create(
            school=self.school, plan=plan, installment_number=2,
            title="القسط الثاني", amount=Decimal("50.00"),
            due_date=timezone.localdate() + timedelta(days=20),
        )

        tx = apply_credit_balance_to_invoice(
            student=self.student, invoice=invoice,
            amount=Decimal("40.00"), user=self.cashier,
            idempotency_key="credit-use-stage7-001",
        )
        repeated = apply_credit_balance_to_invoice(
            student=self.student, invoice=invoice,
            amount=Decimal("40.00"), user=self.cashier,
            idempotency_key="credit-use-stage7-001",
        )
        self.assertEqual(tx.pk, repeated.pk)
        self.assertEqual(
            StudentCreditTransaction.objects.filter(
                school=self.school,
                idempotency_key="credit-use-stage7-001",
            ).count(),
            1,
        )

        self.student.refresh_from_db()
        invoice.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("60.00"))
        self.assertEqual(invoice.paid_amount, Decimal("40.00"))
        self.assertEqual(first.paid_amount, Decimal("30.00"))
        self.assertEqual(second.paid_amount, Decimal("10.00"))
        self.assertEqual(
            sum(tx.allocations.values_list("allocated_amount", flat=True)),
            Decimal("40.00"),
        )

        reverse_credit_usage(tx, reason="اختبار عكس الاستخدام", reversed_by=self.cashier)
        self.student.refresh_from_db()
        invoice.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("100.00"))
        self.assertEqual(invoice.paid_amount, Decimal("0.00"))
        self.assertEqual(first.paid_amount, Decimal("0.00"))
        self.assertEqual(second.paid_amount, Decimal("0.00"))
        self.assertFalse(tx.allocations.filter(status="active").exists())

    def test_discount_policy_rejects_percent_above_100_and_negative_auto_limit(self):
        policy = FeeDiscountPolicy(
            school=self.school,
            max_discount_percent=Decimal("100.01"),
            auto_approval_limit=Decimal("0.00"),
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()
        policy.max_discount_percent = Decimal("100.00")
        policy.auto_approval_limit = Decimal("-0.01")
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_discount_approval_updates_receivable_and_posts_balanced_journal(self):
        invoice = self.make_invoice("S7-INV-003", "100.00")
        FeeDiscountPolicy.objects.create(
            school=self.school,
            max_discount_percent=Decimal("50.00"),
            auto_approval_limit=Decimal("0.00"),
            allow_full_exemption=False,
        )
        request = submit_fee_discount_request(
            invoice=invoice, amount=Decimal("30.00"),
            reason="منحة جزئية معتمدة", requested_by=self.cashier,
            idempotency_key="discount-stage7-001",
        )
        duplicate = submit_fee_discount_request(
            invoice=invoice, amount=Decimal("30.00"),
            reason="منحة جزئية معتمدة", requested_by=self.cashier,
            idempotency_key="discount-stage7-001",
        )
        self.assertEqual(request.pk, duplicate.pk)
        self.assertEqual(request.status, FeeDiscountRequest.Status.PENDING)
        with self.assertRaises(ValidationError):
            submit_fee_discount_request(
                invoice=invoice, amount=Decimal("5.00"),
                reason="طلب ثانٍ معلق", requested_by=self.cashier,
                idempotency_key="discount-stage7-002",
            )

        approved = approve_fee_discount_request(
            request, approved_by=self.cashier, decision_notes="موافقة",
        )
        invoice.refresh_from_db()
        self.assertEqual(approved.status, FeeDiscountRequest.Status.APPROVED)
        self.assertEqual(invoice.discount_amount, Decimal("30.00"))
        self.assertEqual(invoice.remaining_amount, Decimal("70.00"))

        journal = JournalEntry.objects.get(
            school=self.school, source_module="student_invoice_discount",
            source_reference=str(request.pk),
        )
        lines = list(journal.lines.all())
        self.assertEqual(
            sum((line.debit for line in lines), Decimal("0.00")),
            sum((line.credit for line in lines), Decimal("0.00")),
        )
        with self.assertRaises(ValidationError):
            submit_fee_discount_request(
                invoice=invoice, amount=Decimal("30.00"),
                reason="يتجاوز النسبة المعتمدة", requested_by=self.cashier,
                idempotency_key="discount-stage7-002",
            )

    def test_discount_after_partial_payment_creates_student_credit(self):
        invoice = self.make_invoice("S7-INV-DISC-PAID", "100.00")
        PaymentReceipt.objects.create(
            school=self.school, student=self.student, invoice=invoice,
            receipt_number="S7-DISC-PAID-RCP", amount=Decimal("80.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )
        FeeDiscountPolicy.objects.create(
            school=self.school, max_discount_percent=Decimal("50.00"),
            auto_approval_limit=Decimal("0.00"),
        )
        request = submit_fee_discount_request(
            invoice=invoice, amount=Decimal("30.00"),
            reason="خصم بعد سداد جزئي", requested_by=self.cashier,
            idempotency_key="discount-paid-stage7-001",
        )
        approve_fee_discount_request(
            request, approved_by=self.cashier, decision_notes="اعتماد الخصم",
        )
        invoice.refresh_from_db()
        self.student.refresh_from_db()
        credit_tx = StudentCreditTransaction.objects.get(
            school=self.school, invoice=invoice,
            transaction_type=StudentCreditTransaction.TransactionType.ADJUSTMENT,
        )
        journal = JournalEntry.objects.get(
            school=self.school, source_module="student_invoice_discount",
            source_reference=str(request.pk),
        )
        self.assertEqual(invoice.remaining_amount, Decimal("0.00"))
        self.assertEqual(self.student.credit_balance, Decimal("10.00"))
        self.assertEqual(credit_tx.amount, Decimal("10.00"))
        self.assertEqual(
            sum((line.debit for line in journal.lines.all()), Decimal("0.00")),
            Decimal("30.00"),
        )
        self.assertEqual(
            sum((line.credit for line in journal.lines.all()), Decimal("0.00")),
            Decimal("30.00"),
        )
        self.assertEqual(
            sum((line.credit for line in journal.lines.filter(account__code="1104")), Decimal("0.00")),
            Decimal("20.00"),
        )
        self.assertEqual(
            sum((line.credit for line in journal.lines.filter(account__code="2102")), Decimal("0.00")),
            Decimal("10.00"),
        )

    def test_credit_refund_is_idempotent_and_reversible(self):
        self.seed_credit_balance("50.00", "S7-CREDIT-RCP-002")
        refund = refund_student_credit(
            student=self.student, amount=Decimal("15.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            reference="REF-001", user=self.cashier,
            idempotency_key="refund-stage7-001",
        )
        duplicate = refund_student_credit(
            student=self.student, amount=Decimal("15.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            reference="REF-001", user=self.cashier,
            idempotency_key="refund-stage7-001",
        )
        self.assertEqual(refund.pk, duplicate.pk)
        self.student.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("35.00"))
        self.assertTrue(
            JournalEntry.objects.filter(
                school=self.school,
                source_module="student_fees_credit_refund",
                source_reference=str(refund.pk),
            ).exists()
        )

        reverse_credit_refund(
            refund, reason="إلغاء عملية الصرف", reversed_by=self.cashier,
        )
        self.student.refresh_from_db()
        refund.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("50.00"))
        self.assertTrue(refund.is_reversed)

    def test_receipt_api_replay_does_not_create_a_second_payment(self):
        invoice = self.make_invoice("S7-INV-004", "100.00")
        client = APIClient()
        client.force_authenticate(self.cashier)
        url = "/api/v1/fees/receipts/"
        payload = {
            "student_id": str(self.student.pk),
            "invoice_id": str(invoice.pk),
            "amount": "25.00",
            "payment_method": "cash",
            "idempotency_key": "receipt-api-stage7-001",
        }

        first = client.post(url, payload, format="json", HTTP_X_SCHOOL_CODE=self.school.code)
        replay = client.post(url, payload, format="json", HTTP_X_SCHOOL_CODE=self.school.code)
        changed = {**payload, "amount": "30.00"}
        conflict = client.post(url, changed, format="json", HTTP_X_SCHOOL_CODE=self.school.code)

        invoice.refresh_from_db()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(
            PaymentReceipt.objects.filter(
                school=self.school, idempotency_key=payload["idempotency_key"],
            ).count(),
            1,
        )
        self.assertEqual(invoice.paid_amount, Decimal("25.00"))
        statement = client.get(
            f"/api/v1/fees/students/{self.student.pk}/statement/",
            HTTP_X_SCHOOL_CODE=self.school.code,
        )
        self.assertEqual(statement.status_code, 200, statement.data)
        self.assertTrue(statement.data["summary"]["credit_balance_matches_ledger"])
        self.assertEqual(
            statement.data["summary"]["credit_ledger_balance"],
            statement.data["summary"]["credit_balance"],
        )

    def test_invoice_api_replay_is_idempotent_and_rejects_changed_payload(self):
        client = APIClient()
        client.force_authenticate(self.cashier)
        url = "/api/v1/fees/invoices/"
        payload = {
            "idempotency_key": "invoice-api-stage7-001",
            "student_id": str(self.student.pk),
            "academic_year_id": str(self.academic_year.pk),
            "due_date": (timezone.localdate() + timedelta(days=20)).isoformat(),
            "notes": "فاتورة اختبار منع التكرار",
            "discount_amount": "0.00",
            "items": [{
                "fee_category_id": str(self.category.pk),
                "amount": "100.00",
                "discount_amount": "0.00",
                "description": "رسوم دراسية",
            }],
        }
        first = client.post(url, payload, format="json", HTTP_X_SCHOOL_CODE=self.school.code)
        replay = client.post(url, payload, format="json", HTTP_X_SCHOOL_CODE=self.school.code)
        changed = {
            **payload,
            "items": [{**payload["items"][0], "amount": "90.00"}],
        }
        conflict = client.post(url, changed, format="json", HTTP_X_SCHOOL_CODE=self.school.code)

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(first.data["id"], replay.data["id"])
        self.assertEqual(conflict.status_code, 400, conflict.data)
        self.assertEqual(
            StudentInvoice.objects.filter(
                school=self.school,
                idempotency_key=payload["idempotency_key"],
            ).count(),
            1,
        )
        self.assertEqual(
            JournalEntry.objects.filter(
                school=self.school,
                source_module="student_invoice",
                source_reference=first.data["invoice_number"],
            ).count(),
            1,
        )


@skipUnless(connection.vendor == "postgresql", "اختبار الأقفال المتزامنة خاص بـ PostgreSQL")
class Stage7FinancialConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770007101", password="StrongPassword123!",
            first_name="مالك", last_name="مدرسة التزامن",
        )
        self.school = School.objects.create(
            owner=self.owner, name="مدرسة اختبار التزامن",
            code="STAGE7LOCK", status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        seed_default_chart_of_accounts(self.school)
        today = timezone.localdate()
        year = AcademicYear.objects.create(
            school=self.school, code=f"LOCK-{today.year}",
            name=f"عام التزامن {today.year}",
            starts_on=today - timedelta(days=10),
            ends_on=today + timedelta(days=300),
        )
        stage = EducationalStage.objects.create(
            school=self.school, code="LOCK-PRI", name="ابتدائي", sequence=1,
        )
        grade = GradeLevel.objects.create(
            school=self.school, stage=stage, code="LOCK-G1",
            name="الأول", sequence=1,
        )
        section = Section.objects.create(
            school=self.school, academic_year=year, grade=grade,
            code="LOCK-A", name="أ",
        )
        self.student = Student.objects.create(
            school=self.school, student_id_number="LOCK-001",
            first_name="طالب", last_name="تزامن",
            academic_year=year, grade_level=grade, section=section,
            status=Student.Status.ACTIVE,
        )
        PaymentReceipt.objects.create(
            school=self.school, student=self.student,
            receipt_number="LOCK-CREDIT-RCP-001",
            amount=Decimal("100.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
        )
        self.invoice = StudentInvoice.objects.create(
            school=self.school, student=self.student,
            academic_year=year, invoice_number="LOCK-INV-001",
            total_amount=Decimal("100.00"),
            due_date=today + timedelta(days=30),
        )
        post_student_invoice_to_journal(self.invoice)

    def test_concurrent_same_idempotency_key_applies_credit_once(self):
        student_id = self.student.pk
        invoice_id = self.invoice.pk
        school_id = self.school.pk

        def apply():
            close_old_connections()
            try:
                student = Student.objects.get(pk=student_id, school_id=school_id)
                invoice = StudentInvoice.objects.get(pk=invoice_id, school_id=school_id)
                tx = apply_credit_balance_to_invoice(
                    student=student, invoice=invoice,
                    amount=Decimal("40.00"),
                    idempotency_key="credit-concurrent-stage7-001",
                )
                return str(tx.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: apply(), range(2)))

        self.assertEqual(results[0], results[1])
        self.student.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.student.credit_balance, Decimal("60.00"))
        self.assertEqual(self.invoice.paid_amount, Decimal("40.00"))
        self.assertEqual(
            StudentCreditTransaction.objects.filter(
                school=self.school,
                idempotency_key="credit-concurrent-stage7-001",
            ).count(),
            1,
        )
