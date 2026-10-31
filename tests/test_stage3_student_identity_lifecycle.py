import csv
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MembershipRole, SchoolMembership, User
from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.students.models import (
    Guardian, Student, StudentGuardianRelation, StudentMovement,
)
from apps.students.services import (
    link_student_account,
    promote_student,
    record_student_movement,
    transfer_student,
    unlink_student_account,
)
from apps.tenants.models import School
from apps.tenants.services import provision_school


class StudentIdentityAndLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967770008801",
            password="Strong-Stage3-8801!",
            first_name="مدير",
            last_name="اختبار",
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="STG3-01",
            name="مدرسة المرحلة الثالثة",
            status=School.Status.ACTIVE,
        )
        provision_school(cls.school)

        cls.year1 = AcademicYear.objects.create(
            school=cls.school, code="2026-2027", name="2026-2027",
            starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30),
            status=AcademicYear.Status.ACTIVE, is_current=True,
        )
        cls.year2 = AcademicYear.objects.create(
            school=cls.school, code="2027-2028", name="2027-2028",
            starts_on=date(2027, 9, 1), ends_on=date(2028, 6, 30),
            status=AcademicYear.Status.PLANNING,
        )
        cls.stage = EducationalStage.objects.create(
            school=cls.school, code="PRIMARY", name="الابتدائية", sequence=1,
        )
        cls.grade1 = GradeLevel.objects.create(
            school=cls.school, stage=cls.stage, code="G1", name="الأول", sequence=1,
        )
        cls.grade2 = GradeLevel.objects.create(
            school=cls.school, stage=cls.stage, code="G2", name="الثاني", sequence=2,
        )
        cls.section1 = Section.objects.create(
            school=cls.school, academic_year=cls.year1, grade=cls.grade1,
            code="1-A", name="الأول أ", capacity=20,
        )
        cls.section2 = Section.objects.create(
            school=cls.school, academic_year=cls.year1, grade=cls.grade1,
            code="1-B", name="الأول ب", capacity=20,
        )
        cls.section_next = Section.objects.create(
            school=cls.school, academic_year=cls.year2, grade=cls.grade2,
            code="2-A", name="الثاني أ", capacity=20,
        )
        cls.student = Student.objects.create(
            school=cls.school,
            student_id_number="STG3-001",
            first_name="طالب",
            last_name="أول",
            academic_year=cls.year1,
            grade_level=cls.grade1,
            section=cls.section1,
            enrollment_date=date(2026, 9, 1),
        )

    def setUp(self):
        self.client = APIClient()

    def authenticate_school_admin(self):
        self.client.force_authenticate(user=self.owner)
        return f"?school_code={self.school.code}"

    def create_verified_user(self, phone):
        user = User.objects.create_user(
            phone=phone,
            password="Strong-Stage3-User!",
            first_name="حساب",
            last_name="موثق",
        )
        user.phone_verified_at = timezone.now()
        user.save(update_fields=["phone_verified_at", "updated_at"])
        return user

    def test_link_student_account_requires_verified_phone_and_is_unique_per_school(self):
        unverified = User.objects.create_user(
            phone="+967770008802",
            password="Strong-Stage3-User!",
            first_name="غير",
            last_name="موثق",
        )
        with self.assertRaises(Exception):
            link_student_account(student=self.student, user=unverified, actor=self.owner)

        verified = self.create_verified_user("+967770008803")
        linked = link_student_account(student=self.student, user=verified, actor=self.owner)
        self.assertEqual(linked.user_id, verified.pk)
        self.assertTrue(SchoolMembership.objects.filter(
            school=self.school,
            user=verified,
            status=SchoolMembership.Status.ACTIVE,
        ).exists())
        student_role = MembershipRole.objects.get(
            membership__school=self.school,
            membership__user=verified,
            role__school=self.school,
            role__code="student",
        )
        self.assertEqual(student_role.role.code, "student")

        second = Student.objects.create(
            school=self.school,
            student_id_number="STG3-002",
            first_name="طالب",
            last_name="ثان",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
        )
        with self.assertRaises(Exception):
            link_student_account(student=second, user=verified, actor=self.owner)

    def test_unlink_student_account_keeps_user_and_school_membership(self):
        verified = self.create_verified_user("+967770008804")
        link_student_account(student=self.student, user=verified, actor=self.owner)
        unlinked = unlink_student_account(student=self.student, actor=self.owner)
        verified.refresh_from_db()
        self.assertIsNone(unlinked.user_id)
        self.assertTrue(User.objects.filter(pk=verified.pk).exists())
        self.assertTrue(SchoolMembership.objects.filter(
            school=self.school, user=verified,
            status=SchoolMembership.Status.ACTIVE,
        ).exists())
        self.assertFalse(MembershipRole.objects.filter(
            membership__school=self.school,
            membership__user=verified,
            role__code="student",
        ).exists())

    def test_account_binding_api_and_sensitive_student_fields(self):
        verified = self.create_verified_user("+967770008805")
        query = self.authenticate_school_admin()
        linked = self.client.post(
            f"/api/v1/students/{self.student.pk}/account/{query}",
            {"phone": verified.phone},
            format="json",
        )
        self.assertEqual(linked.status_code, status.HTTP_200_OK)
        self.assertEqual(linked.data["user_id"], str(verified.pk))

        # Family/student profile representations do not reveal national ID or date of birth.
        family = self.create_verified_user("+967770008806")
        linked_role_membership = SchoolMembership.objects.create(
            school=self.school, user=family,
            status=SchoolMembership.Status.ACTIVE,
        )
        from apps.accounts.models import SchoolRole
        role, _ = SchoolRole.objects.get_or_create(
            school=self.school, code="student",
            defaults={"name": "طالب", "is_system": True},
        )
        MembershipRole.objects.get_or_create(membership=linked_role_membership, role=role)
        Student.objects.create(
            school=self.school,
            user=family,
            student_id_number="STG3-003",
            first_name="طالب",
            last_name="خصوصية",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
            national_id="PRIVATE-ID-003",
            birth_date=date(2014, 1, 2),
        )
        self.client.force_authenticate(user=family)
        own_profile = self.client.get(
            f"/api/v1/students/?school_code={self.school.code}",
        )
        self.assertEqual(own_profile.status_code, status.HTTP_200_OK)
        self.assertNotIn("credit_balance", own_profile.data[0])
        detail = self.client.get(
            f"/api/v1/students/{Student.objects.get(user=family).pk}/?school_code={self.school.code}",
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertNotIn("national_id", detail.data)
        self.assertNotIn("birth_date", detail.data)
        self.assertNotIn("credit_balance", detail.data)

    def test_guardian_account_profile_and_multiple_child_links(self):
        guardian_user = self.create_verified_user("+967770008807")
        query = self.authenticate_school_admin()
        created = self.client.post(
            f"/api/v1/app/guardians/?school_code={self.school.code}",
            {"phone": guardian_user.phone, "relationship_type": "father"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        guardian = Guardian.objects.get(pk=created.data["id"])
        self.assertEqual(guardian.user_id, guardian_user.pk)

        relation1 = self.client.post(
            f"/api/v1/app/guardian-relations/?school_code={self.school.code}",
            {"student": str(self.student.pk), "guardian": str(guardian.pk)},
            format="json",
        )
        self.assertEqual(relation1.status_code, status.HTTP_201_CREATED)

        second_student = Student.objects.create(
            school=self.school,
            student_id_number="STG3-004",
            first_name="طالب",
            last_name="آخر",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
        )
        relation2 = self.client.post(
            f"/api/v1/app/guardian-relations/?school_code={self.school.code}",
            {"student": str(second_student.pk), "guardian": str(guardian.pk)},
            format="json",
        )
        self.assertEqual(relation2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(guardian.children.filter(is_archived=False).count(), 2)

    def test_transfer_and_promotion_create_append_only_movements(self):
        transferred = transfer_student(
            student=self.student,
            target_section=self.section2,
            user=self.owner,
            reason="تغيير الشعبة بطلب ولي الأمر",
        )
        self.assertEqual(transferred.section_id, self.section2.pk)
        movement = StudentMovement.objects.get(
            student=self.student,
            movement_type=StudentMovement.MovementType.TRANSFERRED,
        )
        self.assertEqual(movement.previous_section_id, self.section1.pk)
        self.assertEqual(movement.next_section_id, self.section2.pk)

        promoted, enrollment = promote_student(
            student=transferred,
            next_academic_year=self.year2,
            next_grade_level=self.grade2,
            next_section=self.section_next,
            user=self.owner,
            notes="اجتاز العام الدراسي",
        )
        self.assertEqual(promoted.academic_year_id, self.year2.pk)
        self.assertEqual(enrollment.section_id, self.section_next.pk)
        self.assertTrue(StudentMovement.objects.filter(
            student=self.student,
            movement_type=StudentMovement.MovementType.PROMOTED,
        ).exists())

        movement.reason = "تعديل غير مسموح"
        with self.assertRaises(Exception):
            movement.save()
        with self.assertRaises(Exception):
            movement.delete()

    def test_student_csv_preview_commit_export_and_atomic_duplicate_protection(self):
        query = self.authenticate_school_admin()
        csv_text = (
            "student_id_number,first_name,middle_name,last_name,gender,"
            "academic_year_id,grade_level_id,section_id,enrollment_date,birth_date,national_id\n"
            f"CSV-001,مروان,,الحداد,male,{self.year1.pk},{self.grade1.pk},{self.section1.pk},2026-09-02,,,\n"
            f"CSV-002,سعاد,,الحداد,female,{self.year1.pk},{self.grade1.pk},{self.section1.pk},2026-09-02,,,\n"
        )
        preview_file = SimpleUploadedFile(
            "students.csv", csv_text.encode("utf-8"), content_type="text/csv",
        )
        preview = self.client.post(
            f"/api/v1/students/import/preview/{query}",
            {"file": preview_file},
            format="multipart",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["valid_rows"], 2)
        self.assertEqual(preview.data["invalid_rows"], 0)

        commit_file = SimpleUploadedFile(
            "students.csv", csv_text.encode("utf-8"), content_type="text/csv",
        )
        committed = self.client.post(
            f"/api/v1/students/import/commit/{query}",
            {"file": commit_file},
            format="multipart",
        )
        self.assertEqual(committed.status_code, status.HTTP_201_CREATED)
        self.assertEqual(committed.data["imported"], 2)
        self.assertEqual(StudentMovement.objects.filter(
            school=self.school,
            movement_type=StudentMovement.MovementType.ADMITTED,
            reason="استيراد جماعي من ملف CSV",
        ).count(), 2)

        duplicate_file = SimpleUploadedFile(
            "students.csv", csv_text.encode("utf-8"), content_type="text/csv",
        )
        duplicate_commit = self.client.post(
            f"/api/v1/students/import/commit/{query}",
            {"file": duplicate_file},
            format="multipart",
        )
        self.assertEqual(duplicate_commit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Student.objects.filter(
            school=self.school, student_id_number__startswith="CSV-",
        ).count(), 2)

        exported = self.client.get(f"/api/v1/students/export/{query}")
        self.assertEqual(exported.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", exported["Content-Type"])
        self.assertIn("CSV-001", exported.content.decode("utf-8-sig"))
