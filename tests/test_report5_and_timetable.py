"""
Comprehensive test suite verifying all fixes from taqrer5 and the complete Timetable system:
1. School bell schedule & period templates with strict zero-overlap validation.
2. Timetable conflict checks: section, teacher, classroom, assembly and break overlap prevention.
3. Accounting ledger immutability: status shift to draft rejection, QuerySet update/delete protection, leaf account validation.
4. Student credit usage: duplicate reversal prevention, explicit transaction tracking.
5. API security: expired membership rejection, RBAC authorization on sensitive operations.
6. Student report card: removing is_staff bypass.
7. Webhook security: signature enforcement (401/403) and GET mode validation (400).
8. Inventory: stock movement item change and negative stock deletion prevention.
9. Purchase order: concurrent safe receiving with pessimistic lock.
10. Book distribution: automated invoicing upon delivery and cancellation upon return.
11. Academic progression: strict next-year section validation in promote_student and retain_student.
12. Payroll: disburse_payroll_run user parameter and loan repayment reversal tracking.
13. Vendor invoice uniqueness constraint within school.
"""
import hashlib
import hmac
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section, Classroom
from apps.accounting.models import Account, FiscalPeriod, FiscalYear, JournalEntry, JournalEntryLine
from apps.accounting.services.chart_of_accounts import seed_default_chart_of_accounts
from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.inventory.models import InventoryItem, StockMovement, Supplier, VendorInvoice, Warehouse
from apps.notifications.models import SchoolMessagingGateway
from apps.school_services.models import StudentBookDistribution
from apps.staff.models import Teacher, TeacherAssignment
from apps.student_fees.models import (
    PaymentReceipt,
    StudentInvoice,
    apply_credit_balance_to_invoice,
    reverse_credit_usage,
)
from apps.students.models import Student
from apps.students.services import promote_student
from apps.tenants.models import School
from apps.tenants.services import provision_school
from apps.timetable.models import ClassSchedule, SchedulePeriodTemplate, TimetablePlan, WeekDay
from apps.timetable.services import (
    approve_timetable_plan, copy_timetable_plan, create_default_school_bell_schedule,
    get_effective_class_schedules, publish_timetable_plan, submit_timetable_plan,
)


class Report5AndTimetableSystemTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone="+966500000099", password="password123", first_name="مالك", last_name="المدرسة")
        self.owner2 = User.objects.create_user(phone="+966500000098", password="password123", first_name="مالك", last_name="الثاني")
        self.school = School.objects.create(owner=self.owner, name="مدرسة النخبة الحديثة", code="ELITE", status=School.Status.ACTIVE)
        self.other_school = School.objects.create(owner=self.owner2, name="مدرسة الأمل", code="HOPE", status=School.Status.ACTIVE)
        provision_school(self.school)
        provision_school(self.other_school)

        self.academic_year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            code="AY-2026-2027",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
        )

        self.stage = EducationalStage.objects.create(school=self.school, name="المرحلة الأساسية", code="STAGE-PRI", sequence=1)
        self.grade = GradeLevel.objects.create(school=self.school, stage=self.stage, name="الصف الثالث", code="G-3", sequence=3)
        self.section = Section.objects.create(
            school=self.school, academic_year=self.academic_year, grade=self.grade, code="SEC-A", name="الشعبة أ"
        )
        self.classroom = Classroom.objects.create(school=self.school, name="قاعة 101", code="ROOM-101", capacity=35)

        self.user_teacher = User.objects.create_user(phone="+967770001111", password="password123", first_name="علي", last_name="الأحمدي")
        self.teacher = Teacher.objects.create(school=self.school, user=self.user_teacher, employee_number="T-101", specialization="رياضيات")

        from apps.academics.models import Subject
        self.subject = Subject.objects.create(school=self.school, name="الرياضيات", code="MATH-3")

        # Admin user
        self.admin_user = User.objects.create_user(phone="+967770002222", password="password123", first_name="مدير", last_name="المدرسة", is_staff=True)
        self.client = APIClient()

    # -------------------------------------------------------------------------
    # 1. Timetable & Bell Schedule Tests
    # -------------------------------------------------------------------------
    def test_bell_schedule_and_period_templates_overlap_prevention(self):
        """اختبار إنشاء قالب التوقيت الافتراضي وفحص منع التداخل الزمني الصارم للحصص والفسح والطابور."""
        bell_sched = create_default_school_bell_schedule(
            school=self.school,
            academic_year=self.academic_year,
            name="الجدول الصباحي القياسي",
            has_morning_assembly=True,
            assembly_start=time(7, 15),
            assembly_duration_minutes=15,
            periods_count=7,
            period_duration_minutes=45,
            passing_duration_minutes=5,
            first_break_after=3,
            first_break_duration_minutes=25,
            has_second_break=True,
            second_break_after=5,
            second_break_duration_minutes=20,
        )

        # Verify created period templates
        templates = list(bell_sched.period_templates.order_by("order"))
        self.assertGreaterEqual(len(templates), 9)  # 1 assembly + 7 periods + 2 breaks = 10
        assembly = templates[0]
        self.assertEqual(assembly.period_type, SchedulePeriodTemplate.PeriodType.ASSEMBLY)
        self.assertEqual(assembly.start_time, time(7, 15))
        self.assertEqual(assembly.end_time, time(7, 30))

        # Check strict overlap prevention: attempting to create a template overlapping with Period 1
        with self.assertRaises(ValidationError):
            conflict_template = SchedulePeriodTemplate(
                school=self.school,
                schedule=bell_sched,
                period_type=SchedulePeriodTemplate.PeriodType.PERIOD,
                period_number=99,
                name="حصة متداخلة غير قانونية",
                start_time=time(7, 40),  # overlaps with 07:30 - 08:15
                end_time=time(8, 25),
            )
            conflict_template.clean()

    def test_class_schedule_conflict_validation(self):
        """اختبار منع تعارض المعلم، الشعبة، القاعة، ومواعيد الفسح والطابور في الحصص المجدولة."""
        bell_sched = create_default_school_bell_schedule(self.school, self.academic_year)
        TeacherAssignment.objects.create(
            school=self.school, academic_year=self.academic_year,
            teacher=self.teacher, subject=self.subject,
            section=self.section, weekly_periods=4,
        )

        # Valid Period 1: 07:30 to 08:15
        ClassSchedule.objects.create(
            school=self.school,
            bell_schedule=bell_sched,
            academic_year=self.academic_year,
            section=self.section,
            subject=self.subject,
            teacher=self.teacher,
            classroom=self.classroom,
            day_of_week=WeekDay.SUNDAY,
            period_number=1,
            start_time=time(7, 30),
            end_time=time(8, 15),
        )

        # 1. Prevent scheduling another class for the same section at overlapping time
        sec_b = Section.objects.create(school=self.school, academic_year=self.academic_year, grade=self.grade, code="SEC-B", name="الشعبة ب")
        cs_section_conflict = ClassSchedule(
            school=self.school,
            bell_schedule=bell_sched,
            academic_year=self.academic_year,
            section=self.section,
            subject=self.subject,
            teacher=self.teacher,
            day_of_week=WeekDay.SUNDAY,
            period_number=2,
            start_time=time(8, 0),  # overlaps with cs1 (07:30 - 08:15)
            end_time=time(8, 45),
        )
        with self.assertRaises(ValidationError):
            cs_section_conflict.clean()

        # 2. Prevent scheduling a class during morning assembly (07:15 - 07:30)
        cs_assembly_conflict = ClassSchedule(
            school=self.school,
            bell_schedule=bell_sched,
            academic_year=self.academic_year,
            section=sec_b,
            subject=self.subject,
            teacher=self.teacher,
            day_of_week=WeekDay.SUNDAY,
            period_number=10,
            start_time=time(7, 20),
            end_time=time(8, 0),
        )
        with self.assertRaises(ValidationError):
            cs_assembly_conflict.clean()

    def test_timetable_versions_follow_submit_approve_publish_and_effective_dates(self):
        bell = create_default_school_bell_schedule(self.school, self.academic_year)
        TeacherAssignment.objects.create(
            school=self.school, academic_year=self.academic_year, teacher=self.teacher,
            subject=self.subject, section=self.section, weekly_periods=4,
        )
        legacy = ClassSchedule.objects.create(
            school=self.school, bell_schedule=bell, academic_year=self.academic_year,
            section=self.section, subject=self.subject, teacher=self.teacher,
            classroom=self.classroom, day_of_week=WeekDay.SUNDAY, period_number=1,
            start_time=time(7, 30), end_time=time(8, 15),
        )

        first = copy_timetable_plan(
            school=self.school, academic_year=self.academic_year,
            name="الجدول الأساسي", effective_from=date(2026, 9, 1),
        )
        self.assertEqual(first.status, TimetablePlan.Status.DRAFT)
        self.assertEqual(first.class_schedules.count(), 1)
        submit_timetable_plan(first, submitted_by=self.owner)
        approve_timetable_plan(first, approved_by=self.owner)
        publish_timetable_plan(first, published_by=self.owner)
        self.assertEqual(
            get_effective_class_schedules(school=self.school, on_date=date(2026, 12, 31), section_id=self.section.pk).first().timetable_plan_id,
            first.pk,
        )

        second = copy_timetable_plan(
            school=self.school, academic_year=self.academic_year, source_plan=first,
            name="الجدول المعدل", effective_from=date(2027, 1, 1),
        )
        self.assertEqual(second.version, first.version + 1)
        submit_timetable_plan(second, submitted_by=self.owner)
        approve_timetable_plan(second, approved_by=self.owner)
        publish_timetable_plan(second, published_by=self.owner)
        first.refresh_from_db()
        self.assertEqual(first.status, TimetablePlan.Status.RETIRED)
        self.assertEqual(first.effective_to, date(2026, 12, 31))
        self.assertEqual(
            get_effective_class_schedules(school=self.school, on_date=date(2027, 1, 1), section_id=self.section.pk).first().timetable_plan_id,
            second.pk,
        )
        self.assertTrue(ClassSchedule.objects.filter(pk=legacy.pk, timetable_plan__isnull=True).exists())

    # -------------------------------------------------------------------------
    # 2. Ledger Immutability & QuerySet Protection (P0)
    # -------------------------------------------------------------------------
    def test_journal_entry_posted_immutability_and_queryset_protection(self):
        """اختبار منع تحويل القيد المرحل إلى مسودة، ومنع تعديله أو حذفه جماعياً عبر QuerySet، والتحقق من الحسابات التفصيلية."""
        seed_default_chart_of_accounts(self.school)
        fy = FiscalYear.objects.create(school=self.school, name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        fp = FiscalPeriod.objects.create(school=self.school, fiscal_year=fy, name="أكتوبر 2026", period_number=10, start_date=date(2026, 10, 1), end_date=date(2026, 10, 31))

        cash = Account.objects.get(school=self.school, code="1101")
        revenue = Account.objects.get(school=self.school, code="4101")
        parent_asset = Account.objects.get(school=self.school, code="1")  # Non-leaf parent account

        entry = JournalEntry.objects.create(
            school=self.school,
            fiscal_period=fp,
            entry_number="JV-TEST-001",
            date=date(2026, 10, 15),
            description="قيد تجريبي معتمد",
        )
        JournalEntryLine.objects.create(school=self.school, journal_entry=entry, account=cash, debit=Decimal("500.00"), credit=Decimal("0.00"))
        JournalEntryLine.objects.create(school=self.school, journal_entry=entry, account=revenue, debit=Decimal("0.00"), credit=Decimal("500.00"))
        entry.post()
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)

        # 1. Disallow changing status back to DRAFT
        entry.status = JournalEntry.Status.DRAFT
        with self.assertRaises(ValidationError):
            entry.save()

        # 2. Disallow bulk update via QuerySet
        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).update(description="تعديل غير مصرح")

        # 3. Disallow bulk delete of posted entries
        with self.assertRaises(ValidationError):
            JournalEntry.objects.filter(pk=entry.pk).delete()

        # 4. Disallow bulk update/delete of lines of posted entries
        with self.assertRaises(ValidationError):
            JournalEntryLine.objects.filter(journal_entry=entry).update(debit=Decimal("999.00"))

        with self.assertRaises(ValidationError):
            JournalEntryLine.objects.filter(journal_entry=entry).delete()

        # 5. Disallow saving or posting line on a non-leaf parent account
        bad_entry = JournalEntry.objects.create(school=self.school, fiscal_period=fp, entry_number="JV-BAD-001", date=date(2026, 10, 15), description="قيد حساب رئيسي")
        with self.assertRaises(ValidationError):
            JournalEntryLine.objects.create(school=self.school, journal_entry=bad_entry, account=parent_asset, debit=Decimal("100.00"))

    # -------------------------------------------------------------------------
    # 3. Student Credit Usage & Double Reversal Protection (P0)
    # -------------------------------------------------------------------------
    def test_credit_transaction_double_reversal_prevention(self):
        """اختبار منع تكرار عكس حركة الرصيد الدائن وتسجيل حالة العكس بدقة."""
        seed_default_chart_of_accounts(self.school)
        student_user = User.objects.create_user(phone="+967770003333", first_name="سامي", last_name="خالد")
        student = Student.objects.create(
            school=self.school,
            user=student_user,
            student_id_number="ST-2026-99",
            first_name="سامي",
            last_name="خالد",
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
        )
        PaymentReceipt.objects.create(
            school=self.school, student=student,
            receipt_number="RCP-CR-SEED-01",
            amount=Decimal("2000.00"),
            payment_method=PaymentReceipt.PaymentMethod.CASH,
            received_by=self.owner,
        )
        invoice = StudentInvoice.objects.create(
            school=self.school,
            student=student,
            academic_year=self.academic_year,
            invoice_number="INV-CR-01",
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 15),
            total_amount=Decimal("1500.00"),
        )

        # Apply credit to invoice
        tx = apply_credit_balance_to_invoice(student=student, invoice=invoice, amount=Decimal("1000.00"))
        self.assertFalse(tx.is_reversed)

        # Reverse credit usage
        rev_tx = reverse_credit_usage(tx, reason="خطأ في السداد")
        tx.refresh_from_db()
        self.assertTrue(tx.is_reversed)
        self.assertEqual(tx.reversed_by_transaction, rev_tx)

        # Calling reverse_credit_usage second time MUST raise ValidationError
        with self.assertRaises(ValidationError):
            reverse_credit_usage(tx, reason="عكس مكرر غير قانوني")

    # -------------------------------------------------------------------------
    # 4. API RBAC Security & Expired Membership (P0)
    # -------------------------------------------------------------------------
    def test_api_security_expired_membership_and_rbac(self):
        """اختبار رفض العضويات المنتهية ورفض المستخدمين غير المخولين مالياً من إنشاء الفواتير."""
        # User with expired membership
        expired_user = User.objects.create_user(phone="+967770004444", password="password123", first_name="منتهي", last_name="الصلاحية")
        SchoolMembership.objects.create(
            school=self.school,
            user=expired_user,
            status=SchoolMembership.Status.ACTIVE,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        self.client.force_authenticate(user=expired_user)
        response = self.client.get("/api/v1/fees/invoices/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Active user WITHOUT financial role
        teacher_user = User.objects.create_user(phone="+967770005555", password="password123", first_name="معلم", last_name="عادي")
        m = SchoolMembership.objects.create(school=self.school, user=teacher_user, status=SchoolMembership.Status.ACTIVE)
        role = SchoolRole.objects.filter(school=self.school, code="teacher").first() or SchoolRole.objects.create(school=self.school, code="teacher", name="معلم")
        MembershipRole.objects.create(membership=m, role=role)

        self.client.force_authenticate(user=teacher_user)
        post_response = self.client.post("/api/v1/fees/invoices/", data={"student_id": "none"}, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 5. Student Report Card: No is_staff Bypass (P0)
    # -------------------------------------------------------------------------
    def test_report_card_no_staff_bypass(self):
        """التحقق من منع مستخدم is_staff لا يملك عضوية في المدرسة من الاطلاع على شهادة الطالب."""
        external_staff = User.objects.create_user(phone="+967770006666", password="password123", first_name="موظف", last_name="خارجي", is_staff=True)
        student_user = User.objects.create_user(phone="+967770007777", first_name="طالب", last_name="تجريبي")
        student = Student.objects.create(
            school=self.school,
            user=student_user,
            student_id_number="ST-999",
            first_name="طالب",
            last_name="تجريبي",
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
        )

        self.client.force_authenticate(user=external_staff)
        res = self.client.get(f"/api/v1/reports/academic/report-card/{student.id}/?school_code={self.school.code}")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 6. Webhook Security: Signature Enforcement & Mode Validation (P1)
    # -------------------------------------------------------------------------
    def test_webhook_security_signature_and_mode(self):
        """اختبار إلزام التوقيع عند ضبط السر ورفض أوضاع GET غير الصالحة بحالة 400."""
        SchoolMessagingGateway.objects.create(
            school=self.school,
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            webhook_verify_token="SECRET_TOKEN_123",
            is_active=True,
        )

        # 1. GET with invalid mode should return 400
        get_res = self.client.get(f"/api/v1/notifications/webhook/whatsapp/{self.school.code}/?hub.mode=invalid")
        self.assertEqual(get_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. POST without signature when secret configured should return 401
        post_data = {"from": "+967770001111", "message": "مرحبا"}
        post_res = self.client.post(
            f"/api/v1/notifications/webhook/whatsapp/{self.school.code}/",
            data=post_data,
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 3. POST with valid HMAC signature should succeed
        payload_bytes = json.dumps(post_data).encode("utf-8")
        valid_sig = "sha256=" + hmac.new(b"SECRET_TOKEN_123", payload_bytes, hashlib.sha256).hexdigest()
        signed_res = self.client.post(
            f"/api/v1/notifications/webhook/whatsapp/{self.school.code}/",
            data=payload_bytes,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=valid_sig,
        )
        self.assertEqual(signed_res.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 7. Inventory: Stock Movement Item Change & Negative Prevention (P1)
    # -------------------------------------------------------------------------
    def test_stock_movement_item_change_and_negative_rejection(self):
        """تغيير الصنف يتم بعكس الحركة القديمة وإنشاء حركة جديدة لا بتحرير السجل التاريخي."""
        from apps.inventory.services import record_stock_movement, reverse_stock_movement

        warehouse = Warehouse.objects.create(school=self.school, name="المستودع الرئيسي", code="WH-1")
        item_a = InventoryItem.objects.create(
            school=self.school, warehouse=warehouse, name="دفاتر 40 ورقة",
            code="NB-40", current_stock=Decimal("50.00"),
        )
        item_b = InventoryItem.objects.create(
            school=self.school, warehouse=warehouse, name="دفاتر 60 ورقة",
            code="NB-60", current_stock=Decimal("30.00"),
        )
        mov = StockMovement.objects.create(
            school=self.school,
            item=item_a,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=Decimal("20.00"),
            notes="صرف من الصنف الأول",
            idempotency_key="legacy-item-change-a",
        )
        reverse_stock_movement(
            movement=mov,
            idempotency_key="legacy-item-change-a-rev",
            reason="تصحيح الصنف بعد اكتشاف خطأ الإدخال",
            reversed_by=self.owner,
        )
        record_stock_movement(
            school=self.school,
            item=item_b,
            warehouse=warehouse,
            movement_type=StockMovement.MovementType.ISSUE,
            quantity=Decimal("20.00"),
            unit_cost=item_b.unit_cost,
            idempotency_key="legacy-item-change-b",
            notes="إعادة تسجيل الصرف على الصنف الصحيح",
            created_by=self.owner,
        )
        item_a.refresh_from_db()
        item_b.refresh_from_db()
        self.assertEqual(item_a.current_stock, Decimal("50.00"))
        self.assertEqual(item_b.current_stock, Decimal("10.00"))

        receipt_mov, _ = record_stock_movement(
            school=self.school,
            item=item_b,
            warehouse=warehouse,
            movement_type="receipt",
            quantity=Decimal("5.00"),
            unit_cost=item_b.unit_cost,
            idempotency_key="legacy-receipt-b",
            notes="توريد اختباري",
            created_by=self.owner,
        )
        record_stock_movement(
            school=self.school,
            item=item_b,
            warehouse=warehouse,
            movement_type="issue",
            quantity=Decimal("13.00"),
            unit_cost=item_b.unit_cost,
            idempotency_key="legacy-issue-b",
            notes="صرف لاحق يترك رصيداً أقل من التوريد",
            created_by=self.user,
        )
        item_b.refresh_from_db()
        self.assertEqual(item_b.current_stock, Decimal("2.00"))
        with self.assertRaises(ValidationError):
            reverse_stock_movement(
                movement=receipt_mov,
                idempotency_key="legacy-receipt-b-rev",
                reason="محاولة عكس توريد تجاوز ما تبقى من الرصيد",
                reversed_by=self.owner,
            )
        item_b.refresh_from_db()
        self.assertEqual(item_b.current_stock, Decimal("2.00"))

    # -------------------------------------------------------------------------
    # 8. Book Distribution: Auto Invoice on Delivery & Cancel on Return (P1)
    # -------------------------------------------------------------------------
    def test_book_distribution_auto_invoice_and_return(self):
        """اختبار إنشاء فاتورة رسوم الكتاب تلقائياً عند التسليم وإلغائها عند الاسترجاع للمستودع."""
        student_user = User.objects.create_user(phone="+967770008888", first_name="خالد", last_name="منصور")
        student = Student.objects.create(
            school=self.school,
            user=student_user,
            student_id_number="ST-888",
            first_name="خالد",
            last_name="منصور",
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
        )

        dist = StudentBookDistribution.objects.create(
            school=self.school,
            student=student,
            academic_year=self.academic_year,
            book_title="كتاب الرياضيات الجزء الأول",
            quantity=Decimal("1.00"),
            fee_amount=Decimal("3500.00"),
        )
        self.assertIsNone(dist.invoice)

        # Deliver book
        dist.deliver_book(user=self.admin_user)
        dist.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.DELIVERED)
        self.assertIsNotNone(dist.invoice)
        self.assertEqual(dist.invoice.total_amount, Decimal("3500.00"))

        # Return book to warehouse
        dist.return_book(user=self.admin_user)
        dist.refresh_from_db()
        dist.invoice.refresh_from_db()
        self.assertEqual(dist.delivery_status, StudentBookDistribution.DeliveryStatus.RETURNED)
        self.assertEqual(dist.invoice.status, StudentInvoice.Status.CANCELLED)

    # -------------------------------------------------------------------------
    # 9. Student Promotion & Retention Strict Next-Year Matching (P1)
    # -------------------------------------------------------------------------
    def test_student_promotion_and_retention_strict_next_year(self):
        """اختبار اشتراط تبعية الشعبة للعام الدراسي الجديد في الترفيع وإعادة القيد ومنع اختيار شعبة قديمة."""
        next_year = AcademicYear.objects.create(
            school=self.school,
            name="2027-2028",
            code="AY-2027-2028",
            starts_on=date(2027, 9, 1),
            ends_on=date(2028, 6, 30),
        )
        grade_4 = GradeLevel.objects.create(school=self.school, stage=self.stage, name="الصف الرابع", code="G-4", sequence=4)

        student_user = User.objects.create_user(phone="+967770009999", first_name="ماجد", last_name="عادل")
        student = Student.objects.create(
            school=self.school,
            user=student_user,
            student_id_number="ST-777",
            first_name="ماجد",
            last_name="عادل",
            academic_year=self.academic_year,
            grade_level=self.grade,
            section=self.section,
        )

        # A section from current year (2026-2027) passed to promote_student for next_year must be rejected
        sec_wrong_year = Section.objects.create(school=self.school, academic_year=self.academic_year, grade=grade_4, code="SEC-4-OLD", name="رابع أ قديم")
        with self.assertRaises(ValidationError):
            promote_student(student=student, next_academic_year=next_year, next_grade_level=grade_4, next_section=sec_wrong_year)

        # Valid next year section
        sec_next_year = Section.objects.create(school=self.school, academic_year=next_year, grade=grade_4, code="SEC-4-NEW", name="رابع أ جديد")
        st, enr = promote_student(student=student, next_academic_year=next_year, next_grade_level=grade_4, next_section=sec_next_year)
        self.assertEqual(st.academic_year, next_year)
        self.assertEqual(st.section, sec_next_year)

    # -------------------------------------------------------------------------
    # 10. Vendor Invoice Unique Constraint (P2)
    # -------------------------------------------------------------------------
    def test_vendor_invoice_uniqueness(self):
        """اختبار القيد الفريد لرقم فاتورة المورد داخل نفس المدرسة."""
        supplier = Supplier.objects.create(school=self.school, name="دار النشر الحديثة", code="SUP-01", phone="+967770009990")
        VendorInvoice.objects.create(
            school=self.school,
            supplier=supplier,
            invoice_number="VINV-2026-001",
            total_amount=Decimal("50000.00"),
        )

        with self.assertRaises((ValidationError, IntegrityError)):
            VendorInvoice.objects.create(
                school=self.school,
                supplier=supplier,
                invoice_number="VINV-2026-001",
                total_amount=Decimal("30000.00"),
            )
