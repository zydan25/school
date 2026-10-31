from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.notifications.models import SchoolMessagingGateway
from apps.payroll.models import PayrollRun
from apps.student_fees.models import PaymentReceipt, StudentInvoice
from apps.students.models import Student
from apps.tenants.models import School
from apps.tenants.services import provision_school


class CriticalAccessRegressionTests(TestCase):
    """Regression coverage for the critical access-control fixes in stage 1."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967770009901",
            password="Strong-Test-Password-9901",
            first_name="مدير",
            last_name="المدرسة",
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="SEC-REG-01",
            name="مدرسة اختبار الحماية",
            status=School.Status.ACTIVE,
        )
        provision_school(cls.school)

        cls.year = AcademicYear.objects.create(
            school=cls.school,
            code="2026-2027",
            name="2026-2027",
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
            status=AcademicYear.Status.ACTIVE,
            is_current=True,
        )
        cls.stage = EducationalStage.objects.create(
            school=cls.school, code="PRI", name="الابتدائية", sequence=1,
        )
        cls.grade = GradeLevel.objects.create(
            school=cls.school, stage=cls.stage, code="G1",
            name="الصف الأول", sequence=1,
        )
        cls.section = Section.objects.create(
            school=cls.school, academic_year=cls.year, grade=cls.grade,
            code="1-A", name="الأول / أ",
        )

        cls.student_user = User.objects.create_user(
            phone="+967770009902",
            password="Strong-Test-Password-9902",
            first_name="طالب",
            last_name="أول",
        )
        cls.other_student_user = User.objects.create_user(
            phone="+967770009903",
            password="Strong-Test-Password-9903",
            first_name="طالب",
            last_name="ثان",
        )
        cls.teacher_user = User.objects.create_user(
            phone="+967770009904",
            password="Strong-Test-Password-9904",
            first_name="معلم",
            last_name="اختبار",
        )

        cls.student_role = SchoolRole.objects.create(
            school=cls.school, code="student", name="طالب",
        )
        cls.teacher_role = SchoolRole.objects.create(
            school=cls.school, code="teacher-test", name="معلم اختبار",
        )
        for user, role in (
            (cls.student_user, cls.student_role),
            (cls.teacher_user, cls.teacher_role),
        ):
            membership = SchoolMembership.objects.create(
                school=cls.school,
                user=user,
                status=SchoolMembership.Status.ACTIVE,
                is_default=True,
            )
            MembershipRole.objects.create(membership=membership, role=role)

        cls.student = Student.objects.create(
            school=cls.school,
            user=cls.student_user,
            student_id_number="SEC-ST-001",
            first_name="طالب",
            last_name="أول",
            academic_year=cls.year,
            grade_level=cls.grade,
            section=cls.section,
        )
        cls.other_student = Student.objects.create(
            school=cls.school,
            user=cls.other_student_user,
            student_id_number="SEC-ST-002",
            first_name="طالب",
            last_name="ثان",
            academic_year=cls.year,
            grade_level=cls.grade,
            section=cls.section,
        )

        cls.own_invoice = StudentInvoice.objects.create(
            school=cls.school,
            student=cls.student,
            academic_year=cls.year,
            invoice_number="SEC-INV-001",
            total_amount=Decimal("1000.00"),
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 12, 31),
        )
        cls.other_invoice = StudentInvoice.objects.create(
            school=cls.school,
            student=cls.other_student,
            academic_year=cls.year,
            invoice_number="SEC-INV-002",
            total_amount=Decimal("2000.00"),
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 12, 31),
        )
        PaymentReceipt.objects.create(
            school=cls.school,
            student=cls.student,
            invoice=cls.own_invoice,
            receipt_number="SEC-RCP-001",
            amount=Decimal("100.00"),
        )
        PaymentReceipt.objects.create(
            school=cls.school,
            student=cls.other_student,
            invoice=cls.other_invoice,
            receipt_number="SEC-RCP-002",
            amount=Decimal("200.00"),
        )
        cls.payroll_run = PayrollRun.objects.create(
            school=cls.school,
            name="مسير اختبار",
            year=2026,
            month=10,
        )

    def setUp(self):
        self.client = APIClient()

    def school_query(self):
        return {"school_code": self.school.code}

    def test_student_finance_lists_and_details_are_limited_to_linked_student(self):
        self.client.force_authenticate(user=self.student_user)

        invoices = self.client.get("/api/v1/fees/invoices/", self.school_query())
        self.assertEqual(invoices.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in invoices.data],
            [str(self.own_invoice.pk)],
        )

        receipts = self.client.get("/api/v1/fees/receipts/", self.school_query())
        self.assertEqual(receipts.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in receipts.data],
            [str(PaymentReceipt.objects.get(receipt_number="SEC-RCP-001").pk)],
        )

        other_invoice = self.client.get(
            f"/api/v1/fees/invoices/{self.other_invoice.pk}/",
            self.school_query(),
        )
        self.assertEqual(other_invoice.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_read_payroll_runs_or_payslip_details(self):
        self.client.force_authenticate(user=self.student_user)

        listing = self.client.get("/api/v1/payroll/runs/", self.school_query())
        self.assertEqual(listing.status_code, status.HTTP_403_FORBIDDEN)

        detail = self.client.get(
            f"/api/v1/payroll/runs/{self.payroll_run.pk}/",
            self.school_query(),
        )
        self.assertEqual(detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_use_teacher_copilot_or_select_another_student(self):
        self.client.force_authenticate(user=self.student_user)

        teacher_endpoint = self.client.post(
            f"/api/v1/copilot/teacher/quiz/?school_code={self.school.code}",
            {"lesson_plan_or_topic": "الكسور"},
            format="json",
        )
        self.assertEqual(teacher_endpoint.status_code, status.HTTP_403_FORBIDDEN)

        foreign_student = self.client.get(
            f"/api/v1/copilot/student/grades/?school_code={self.school.code}&student_id={self.other_student.pk}",
        )
        self.assertEqual(foreign_student.status_code, status.HTTP_403_FORBIDDEN)

    def test_webhook_rejects_gateway_without_signing_secret(self):
        SchoolMessagingGateway.objects.create(
            school=self.school,
            name="بوابة بلا سر",
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            provider=SchoolMessagingGateway.Provider.CUSTOM_WEBHOOK,
            api_endpoint_url="https://gateway.example.test/messages",
            webhook_verify_token="",
            is_active=True,
        )
        response = self.client.post(
            f"/api/v1/notifications/webhook/whatsapp/?school_code={self.school.code}",
            {"from": "967770000000", "message": "رسالة اختبار"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
