from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MembershipRole, SchoolMembership, User
from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section
from apps.students.models import (
    Guardian,
    GuardianConsent,
    Student,
    StudentDocument,
    StudentGuardianRelation,
    StudentMovement,
)
from apps.students.services import (
    graduate_student,
    link_student_account,
    promote_student,
    retain_student,
    transfer_student,
    unlink_student_account,
    withdraw_student,
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
        cls.section_retain_next = Section.objects.create(
            school=cls.school, academic_year=cls.year2, grade=cls.grade1,
            code="1-A-NEXT", name="الأول أ - العام التالي", capacity=20,
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

    def test_annual_enrollment_rejects_section_from_another_academic_year(self):
        from apps.students.models import StudentEnrollment

        invalid = StudentEnrollment(
            school=self.school,
            student=self.student,
            academic_year=self.year2,
            grade_level=self.grade2,
            section=self.section1,
            enrollment_date=date(2027, 9, 1),
        )
        with self.assertRaises(ValidationError):
            invalid.save()

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
        own_results = own_profile.data.get("results", own_profile.data)
        self.assertNotIn("credit_balance", own_results[0])
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

        second_guardian_user = self.create_verified_user("+967770008808")
        second_guardian_response = self.client.post(
            f"/api/v1/app/guardians/?school_code={self.school.code}",
            {"phone": second_guardian_user.phone, "relationship_type": "mother"},
            format="json",
        )
        self.assertEqual(second_guardian_response.status_code, status.HTTP_201_CREATED)
        second_guardian = Guardian.objects.get(pk=second_guardian_response.data["id"])
        relation3 = self.client.post(
            f"/api/v1/app/guardian-relations/?school_code={self.school.code}",
            {"student": str(self.student.pk), "guardian": str(second_guardian.pk)},
            format="json",
        )
        self.assertEqual(relation3.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.student.guardians.filter(is_archived=False).count(), 2)

    def test_teacher_and_staff_profiles_require_verified_accounts_and_active_memberships(self):
        unverified_teacher = User.objects.create_user(
            phone="+967770008809",
            password="Strong-Stage3-User!",
            first_name="معلم",
            last_name="غيرموثق",
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=unverified_teacher,
            status=SchoolMembership.Status.ACTIVE,
        )
        query = self.authenticate_school_admin()
        rejected_teacher = self.client.post(
            f"/api/v1/app/teachers/{query}",
            {"user_id": str(unverified_teacher.pk), "specialization": "رياضيات"},
            format="json",
        )
        self.assertEqual(rejected_teacher.status_code, status.HTTP_400_BAD_REQUEST)

        verified_teacher = self.create_verified_user("+967770008810")
        SchoolMembership.objects.create(
            school=self.school,
            user=verified_teacher,
            status=SchoolMembership.Status.ACTIVE,
        )
        created_teacher = self.client.post(
            f"/api/v1/app/teachers/{query}",
            {"user_id": str(verified_teacher.pk), "specialization": "رياضيات"},
            format="json",
        )
        self.assertEqual(created_teacher.status_code, status.HTTP_201_CREATED)

        unverified_staff = User.objects.create_user(
            phone="+967770008811",
            password="Strong-Stage3-User!",
            first_name="موظف",
            last_name="غيرموثق",
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=unverified_staff,
            status=SchoolMembership.Status.ACTIVE,
        )
        rejected_staff = self.client.post(
            f"/api/v1/staff/members/{query}",
            {"user": str(unverified_staff.pk), "job_title": "سكرتير", "role": "secretary"},
            format="json",
        )
        self.assertEqual(rejected_staff.status_code, status.HTTP_400_BAD_REQUEST)

        verified_staff = self.create_verified_user("+967770008812")
        SchoolMembership.objects.create(
            school=self.school,
            user=verified_staff,
            status=SchoolMembership.Status.ACTIVE,
        )
        created_staff = self.client.post(
            f"/api/v1/staff/members/{query}",
            {"user": str(verified_staff.pk), "job_title": "سكرتير", "role": "secretary"},
            format="json",
        )
        self.assertEqual(created_staff.status_code, status.HTTP_201_CREATED)

    def create_linked_guardian(self, phone, *, student=None, relationship_type="father"):
        from apps.students.services import ensure_guardian_membership

        student = student or self.student
        user = self.create_verified_user(phone)
        ensure_guardian_membership(user=user, school=self.school, actor=self.owner)
        guardian = Guardian.objects.create(
            school=self.school,
            user=user,
            relationship_type=relationship_type,
        )
        StudentGuardianRelation.objects.create(
            school=self.school,
            student=student,
            guardian=guardian,
        )
        return user, guardian

    def test_private_student_documents_are_uploaded_and_downloaded_only_by_linked_family(self):
        query = self.authenticate_school_admin()
        guardian_user, guardian = self.create_linked_guardian("+967770008813")
        other_user, _other_guardian = self.create_linked_guardian(
            "+967770008814",
            student=Student.objects.create(
                school=self.school,
                student_id_number="STG3-DOC-OTHER",
                first_name="طالب",
                last_name="آخر",
                academic_year=self.year1,
                grade_level=self.grade1,
                section=self.section1,
            ),
        )

        visible_upload = SimpleUploadedFile(
            "birth-certificate.pdf",
            b"%PDF-1.4 private sample",
            content_type="application/pdf",
        )
        visible_response = self.client.post(
            f"/api/v1/students/documents/{query}",
            {
                "student": str(self.student.pk),
                "title": "شهادة الميلاد",
                "document_type": "birth_certificate",
                "file": visible_upload,
                "visible_to_guardian": "true",
            },
            format="multipart",
        )
        self.assertEqual(visible_response.status_code, status.HTTP_201_CREATED, getattr(visible_response, "data", visible_response.content))
        visible_document = StudentDocument.objects.get(pk=visible_response.data["id"])
        self.assertIn("/documents/", visible_response.data["download_url"])
        self.assertNotIn("student-documents/", visible_response.data["download_url"])

        private_upload = SimpleUploadedFile(
            "internal-note.pdf",
            b"%PDF-1.4 internal only",
            content_type="application/pdf",
        )
        private_response = self.client.post(
            f"/api/v1/students/documents/{query}",
            {
                "student": str(self.student.pk),
                "title": "وثيقة داخلية",
                "document_type": "other",
                "file": private_upload,
                "visible_to_guardian": "false",
            },
            format="multipart",
        )
        self.assertEqual(private_response.status_code, status.HTTP_201_CREATED)
        private_document = StudentDocument.objects.get(pk=private_response.data["id"])

        parent_client = APIClient()
        parent_client.force_authenticate(user=guardian_user)
        parent_query = f"?school_code={self.school.code}"
        visible_list = parent_client.get(
            f"/api/v1/students/documents/{parent_query}"
        )
        self.assertEqual(visible_list.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in visible_list.data["results"]],
            [str(visible_document.pk)],
        )
        download = parent_client.get(
            f"/api/v1/students/documents/{visible_document.pk}/download/{parent_query}"
        )
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertIn(
            b"%PDF-1.4 private sample",
            b"".join(download.streaming_content),
        )
        self.assertEqual(
            parent_client.get(
                f"/api/v1/students/documents/{private_document.pk}/download/{parent_query}"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        outsider_client = APIClient()
        outsider_client.force_authenticate(user=other_user)
        outsider_list = outsider_client.get(
            f"/api/v1/students/documents/{parent_query}"
        )
        self.assertEqual(outsider_list.status_code, status.HTTP_200_OK)
        self.assertEqual(outsider_list.data["results"], [])
        self.assertEqual(
            outsider_client.get(
                f"/api/v1/students/documents/{visible_document.pk}/download/{parent_query}"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        bad_upload = SimpleUploadedFile(
            "executable.exe",
            b"not allowed",
            content_type="application/octet-stream",
        )
        rejected = self.client.post(
            f"/api/v1/students/documents/{query}",
            {
                "student": str(self.student.pk),
                "title": "ملف غير مسموح",
                "file": bad_upload,
            },
            format="multipart",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_guardian_consent_is_private_and_only_the_addressed_linked_guardian_can_respond(self):
        query = self.authenticate_school_admin()
        guardian_user, guardian = self.create_linked_guardian(
            "+967770008815", relationship_type="father"
        )
        other_guardian_user, _other_guardian = self.create_linked_guardian(
            "+967770008816", relationship_type="mother"
        )

        created = self.client.post(
            f"/api/v1/students/consents/{query}",
            {
                "student": str(self.student.pk),
                "guardian": str(guardian.pk),
                "consent_type": "trip",
                "title": "الموافقة على الرحلة المدرسية",
                "details": "يرجى الموافقة على مشاركة الطالب في الرحلة.",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        consent = GuardianConsent.objects.get(pk=created.data["id"])
        self.assertEqual(consent.status, GuardianConsent.Status.PENDING)
        self.assertEqual(consent.requested_by_id, self.owner.pk)

        guardian_client = APIClient()
        guardian_client.force_authenticate(user=guardian_user)
        parent_query = f"?school_code={self.school.code}"
        listed = guardian_client.get(
            f"/api/v1/students/consents/{parent_query}"
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data["results"]), 1)
        self.assertEqual(listed.data["results"][0]["id"], str(consent.pk))

        other_client = APIClient()
        other_client.force_authenticate(user=other_guardian_user)
        other_listed = other_client.get(
            f"/api/v1/students/consents/{parent_query}"
        )
        self.assertEqual(other_listed.status_code, status.HTTP_200_OK)
        self.assertEqual(other_listed.data["results"], [])
        denied = other_client.post(
            f"/api/v1/students/consents/{consent.pk}/respond/{parent_query}",
            {"status": "approved", "response_note": "موافق"},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

        response = guardian_client.post(
            f"/api/v1/students/consents/{consent.pk}/respond/{parent_query}",
            {"status": "approved", "response_note": "أوافق على مشاركة الطالب."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        consent.refresh_from_db()
        self.assertEqual(consent.status, GuardianConsent.Status.APPROVED)
        self.assertEqual(consent.responded_by_id, guardian_user.pk)
        self.assertIsNotNone(consent.responded_at)
        self.assertEqual(consent.response_note, "أوافق على مشاركة الطالب.")

        repeated = guardian_client.post(
            f"/api/v1/students/consents/{consent.pk}/respond/{parent_query}",
            {"status": "rejected"},
            format="json",
        )
        self.assertEqual(repeated.status_code, status.HTTP_409_CONFLICT)

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

    def test_retention_graduation_and_withdrawal_preserve_annual_history(self):
        from apps.students.models import StudentEnrollment

        retained_candidate = Student.objects.create(
            school=self.school,
            student_id_number="STG3-005",
            first_name="طالب",
            last_name="إعادة",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
        )
        retained, next_enrollment = retain_student(
            student=retained_candidate,
            next_academic_year=self.year2,
            section=self.section_retain_next,
            user=self.owner,
            notes="إعادة قيد بعد نتيجة العام",
        )
        self.assertEqual(retained.academic_year_id, self.year2.pk)
        self.assertEqual(next_enrollment.grade_level_id, self.grade1.pk)
        previous_enrollment = StudentEnrollment.objects.get(
            student=retained,
            academic_year=self.year1,
        )
        self.assertEqual(previous_enrollment.status, StudentEnrollment.Status.RETAINED)
        self.assertEqual(
            previous_enrollment.final_result,
            StudentEnrollment.FinalResult.FAILED,
        )
        self.assertTrue(StudentMovement.objects.filter(
            student=retained,
            movement_type=StudentMovement.MovementType.RETAINED,
        ).exists())

        graduating_candidate = Student.objects.create(
            school=self.school,
            student_id_number="STG3-006",
            first_name="طالب",
            last_name="متخرج",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
        )
        graduated = graduate_student(
            student=graduating_candidate,
            user=self.owner,
            notes="إتمام المرحلة الدراسية",
        )
        self.assertEqual(graduated.status, Student.Status.GRADUATED)
        graduation_enrollment = StudentEnrollment.objects.get(
            student=graduated,
            academic_year=self.year1,
        )
        self.assertEqual(
            graduation_enrollment.status,
            StudentEnrollment.Status.GRADUATED,
        )
        self.assertEqual(
            graduation_enrollment.final_result,
            StudentEnrollment.FinalResult.PASSED,
        )

        withdrawing_candidate = Student.objects.create(
            school=self.school,
            student_id_number="STG3-007",
            first_name="طالب",
            last_name="منسحب",
            academic_year=self.year1,
            grade_level=self.grade1,
            section=self.section1,
        )
        withdrawn = withdraw_student(
            student=withdrawing_candidate,
            user=self.owner,
            reason="انتقال الأسرة إلى منطقة أخرى",
        )
        self.assertEqual(withdrawn.status, Student.Status.WITHDRAWN)
        withdrawal_enrollment = StudentEnrollment.objects.get(
            student=withdrawn,
            academic_year=self.year1,
        )
        self.assertEqual(
            withdrawal_enrollment.status,
            StudentEnrollment.Status.WITHDRAWN,
        )
        self.assertTrue(StudentMovement.objects.filter(
            student=withdrawn,
            movement_type=StudentMovement.MovementType.WITHDRAWN,
        ).exists())

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
