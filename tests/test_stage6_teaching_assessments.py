from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.academics.models import (
    AcademicTerm, AcademicYear, EducationalStage, GradeLevel, Section, Subject,
)
from apps.assessments.models import (
    AssessmentType, ExamCommittee, ExamCommitteeProctor, ExamSeating,
    GradeBook, OnlineExam, QuestionBank,
)
from apps.assignments.models import Homework, HomeworkSubmission
from apps.staff.models import Teacher, TeacherAssignment
from apps.students.models import Student
from apps.tenants.models import School


class PhaseSixTeachingAssessmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967770006001", password="Strong-Phase6-6001!",
            first_name="مدير", last_name="المدرسة",
        )
        cls.school = School.objects.create(
            owner=cls.owner, code="PHASE6", name="مدرسة المرحلة السادسة",
            status=School.Status.ACTIVE,
        )
        cls.teacher_user = User.objects.create_user(
            phone="+967770006002", password="Strong-Phase6-6002!",
            first_name="معلم", last_name="الرياضيات",
        )
        cls.student_user = User.objects.create_user(
            phone="+967770006003", password="Strong-Phase6-6003!",
            first_name="طالب", last_name="الاختبار",
        )
        cls.admin_user = User.objects.create_user(
            phone="+967770006004", password="Strong-Phase6-6004!",
            first_name="مدير", last_name="أكاديمي",
        )
        cls._create_role(cls.school, cls.teacher_user, "teacher")
        cls._create_role(cls.school, cls.student_user, "student")
        cls._create_role(cls.school, cls.admin_user, "school-director")

        cls.year = AcademicYear.objects.create(
            school=cls.school, code="2026-2027", name="2026-2027",
            starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30),
            status=AcademicYear.Status.ACTIVE, is_current=True,
        )
        cls.term = AcademicTerm.objects.create(
            school=cls.school, academic_year=cls.year,
            name="الفصل الأول", number=1,
            starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 31),
            is_current=True,
        )
        cls.stage = EducationalStage.objects.create(
            school=cls.school, code="SEC", name="الثانوية", sequence=1,
        )
        cls.grade = GradeLevel.objects.create(
            school=cls.school, stage=cls.stage, code="G10",
            name="الصف العاشر", sequence=1,
        )
        cls.section = Section.objects.create(
            school=cls.school, academic_year=cls.year, grade=cls.grade,
            code="10-A", name="العاشر أ",
        )
        cls.subject = Subject.objects.create(
            school=cls.school, code="MATH", name="الرياضيات",
        )
        cls.teacher = Teacher.objects.create(
            school=cls.school, user=cls.teacher_user,
            specialization="رياضيات",
        )
        cls.student = Student.objects.create(
            school=cls.school, user=cls.student_user,
            student_id_number="PH6-ST-001",
            first_name="طالب", last_name="الاختبار",
            academic_year=cls.year, grade_level=cls.grade,
            section=cls.section,
        )
        TeacherAssignment.objects.create(
            school=cls.school, academic_year=cls.year,
            teacher=cls.teacher, subject=cls.subject,
            section=cls.section, weekly_periods=4,
        )

    @staticmethod
    def _create_role(school, user, code):
        role, _ = SchoolRole.objects.get_or_create(
            school=school, code=code, defaults={"name": code},
        )
        membership = SchoolMembership.objects.create(
            school=school, user=user,
            status=SchoolMembership.Status.ACTIVE, is_default=True,
        )
        MembershipRole.objects.create(membership=membership, role=role)

    def setUp(self):
        self.student_client = APIClient()
        self.student_client.force_authenticate(self.student_user)
        self.student_client.credentials(HTTP_X_SCHOOL_CODE=self.school.code)
        self.teacher_client = APIClient()
        self.teacher_client.force_authenticate(self.teacher_user)
        self.teacher_client.credentials(HTTP_X_SCHOOL_CODE=self.school.code)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin_user)
        self.admin_client.credentials(HTTP_X_SCHOOL_CODE=self.school.code)
        self.school_query = {"school_code": self.school.code}

    def test_homework_resubmission_preserves_every_attempt_and_requires_teacher_request(self):
        homework = Homework.objects.create(
            school=self.school, subject=self.subject, section=self.section,
            teacher=self.teacher, title="حل التمارين",
            description="حل التمارين المقررة",
            due_date=timezone.now() + timedelta(days=2),
            max_score=Decimal("10.00"),
        )
        submit_url = "/api/v1/app/homework-submissions/submit/"
        first = self.student_client.post(
            submit_url,
            {**self.school_query, "homework_id": str(homework.pk), "submission_text": "المحاولة الأولى"},
            format="multipart",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        submission_id = first.data["id"]
        self.assertEqual(len(first.data["attempts"]), 1)

        blocked = self.student_client.post(
            submit_url,
            {**self.school_query, "homework_id": str(homework.pk), "submission_text": "محاولة غير مصرح بها"},
            format="multipart",
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

        requested = self.teacher_client.post(
            f"/api/v1/app/homework-submissions/{submission_id}/request-resubmission/",
            {**self.school_query, "reason": "يرجى إكمال خطوات الحل وكتابة النتيجة النهائية."},
            format="json",
        )
        self.assertEqual(requested.status_code, status.HTTP_200_OK, requested.data)
        self.assertEqual(requested.data["status"], HomeworkSubmission.Status.RESUBMIT)

        second = self.student_client.post(
            submit_url,
            {**self.school_query, "homework_id": str(homework.pk), "submission_text": "المحاولة الثانية"},
            format="multipart",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(len(second.data["attempts"]), 2)
        self.assertEqual(
            [attempt["submission_text"] for attempt in second.data["attempts"]],
            ["المحاولة الأولى", "المحاولة الثانية"],
        )

        graded = self.teacher_client.post(
            f"/api/v1/app/homework-submissions/{submission_id}/grade/",
            {**self.school_query, "score": "8.50", "teacher_feedback": "عمل جيد"},
            format="json",
        )
        self.assertEqual(graded.status_code, status.HTTP_200_OK, graded.data)
        after_grade = self.student_client.post(
            submit_url,
            {**self.school_query, "homework_id": str(homework.pk), "submission_text": "محاولة بعد التصحيح"},
            format="multipart",
        )
        self.assertEqual(after_grade.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(homework.submissions.get(student=self.student).attempts.count(), 2)

    def test_gradebook_requires_submission_approval_and_publication_before_student_access(self):
        assessment_type = AssessmentType.objects.create(
            school=self.school, name="اختبار شهري", code="MONTHLY",
            default_max_score=Decimal("20.00"),
            weight_percentage=Decimal("40.00"),
        )
        created = self.teacher_client.post(
            "/api/v1/app/gradebook/",
            {
                **self.school_query,
                "student": str(self.student.pk),
                "subject": str(self.subject.pk),
                "academic_term": str(self.term.pk),
                "assessment_type": str(assessment_type.pk),
                "assessment_title": "اختبار الشهر الأول",
                "score": "18.00",
                "max_score": "20.00",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        grade_id = created.data["id"]
        self.assertEqual(created.data["workflow_status"], GradeBook.WorkflowStatus.DRAFT)
        self.assertFalse(created.data["is_published"])

        hidden = self.student_client.get(
            f"/api/v1/app/gradebook/{grade_id}/",
            self.school_query,
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

        submitted = self.teacher_client.post(
            f"/api/v1/app/gradebook/{grade_id}/submit-for-approval/",
            self.school_query, format="json",
        )
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertEqual(submitted.data["workflow_status"], GradeBook.WorkflowStatus.SUBMITTED)

        approved = self.admin_client.post(
            f"/api/v1/app/gradebook/{grade_id}/approve/",
            self.school_query, format="json",
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(approved.data["workflow_status"], GradeBook.WorkflowStatus.APPROVED)

        published = self.admin_client.post(
            f"/api/v1/app/gradebook/{grade_id}/publish/",
            self.school_query, format="json",
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        self.assertTrue(published.data["is_published"])

        visible = self.student_client.get(
            f"/api/v1/app/gradebook/{grade_id}/",
            self.school_query,
        )
        self.assertEqual(visible.status_code, status.HTTP_200_OK, visible.data)
        self.assertEqual(visible.data["score"], "18.00")

        weighted = self.student_client.get(
            "/api/v1/app/gradebook/weighted-summary/",
            {**self.school_query, "subject_id": str(self.subject.pk), "academic_term_id": str(self.term.pk)},
        )
        self.assertEqual(weighted.status_code, status.HTTP_200_OK, weighted.data)
        self.assertEqual(weighted.data["weighted_score_percentage"], "90.00")

        reopened = self.admin_client.post(
            f"/api/v1/app/gradebook/{grade_id}/reopen/",
            {**self.school_query, "reason": "تصحيح خطأ في الرصد بعد الاعتماد."},
            format="json",
        )
        self.assertEqual(reopened.status_code, status.HTTP_200_OK, reopened.data)
        self.assertEqual(reopened.data["workflow_status"], GradeBook.WorkflowStatus.DRAFT)
        self.assertFalse(reopened.data["is_published"])

    def test_exam_paper_hides_answer_key_and_results_remain_hidden_until_release(self):
        question = QuestionBank.objects.create(
            school=self.school, subject=self.subject, grade_level=self.grade,
            unit_name="الجبر", topic="المعادلات",
            question_text="1 + 1 = ؟",
            question_type=QuestionBank.QuestionType.MCQ,
            default_marks=Decimal("5.00"),
            options_json=[{"id": "A", "text": "2"}, {"id": "B", "text": "3"}],
            correct_answer="A", created_by=self.teacher_user,
        )
        exam = OnlineExam.objects.create(
            school=self.school, subject=self.subject, academic_term=self.term,
            grade_level=self.grade, section=self.section,
            title="اختبار الجبر", duration_minutes=20,
            total_marks=Decimal("5.00"), passing_marks=Decimal("2.50"),
            start_time=timezone.now() - timedelta(minutes=1),
            end_time=timezone.now() + timedelta(minutes=30),
            is_published=False, created_by=self.teacher_user,
        )
        exam.questions.add(question)
        published_exam = self.admin_client.post(
            f"/api/v1/app/online-exams/{exam.pk}/publish/",
            self.school_query, format="json",
        )
        self.assertEqual(published_exam.status_code, status.HTTP_200_OK, published_exam.data)

        paper = self.student_client.get(
            f"/api/v1/app/online-exams/{exam.pk}/paper/",
            self.school_query,
        )
        self.assertEqual(paper.status_code, status.HTTP_200_OK, paper.data)
        self.assertNotIn("correct_answer", paper.data["questions"][0])

        started = self.student_client.post(
            f"/api/v1/app/online-exams/{exam.pk}/start/",
            self.school_query, format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_201_CREATED, started.data)
        self.assertIn("deadline", started.data)

        submitted = self.student_client.post(
            f"/api/v1/app/online-exams/{exam.pk}/submit/",
            {**self.school_query, "answers": {str(question.pk): "A"}},
            format="json",
        )
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertNotIn("auto_score", submitted.data)

        attempt = exam.submissions.get(student=self.student)
        review_url = f"/api/v1/app/exam-submissions/{attempt.pk}/"
        graded = self.teacher_client.post(
            f"/api/v1/app/exam-submissions/{attempt.pk}/grade/",
            {**self.school_query, "manual_score": "0"},
            format="json",
        )
        self.assertEqual(graded.status_code, status.HTTP_200_OK, graded.data)

        hidden = self.student_client.get(review_url, self.school_query)
        self.assertEqual(hidden.status_code, status.HTTP_200_OK, hidden.data)
        self.assertNotIn("final_score", hidden.data)
        self.assertFalse(hidden.data["result_published"])

        released = self.admin_client.post(
            f"/api/v1/app/exam-submissions/{attempt.pk}/publish/",
            self.school_query, format="json",
        )
        self.assertEqual(released.status_code, status.HTTP_200_OK, released.data)

        visible = self.student_client.get(review_url, self.school_query)
        self.assertEqual(visible.status_code, status.HTTP_200_OK, visible.data)
        self.assertEqual(visible.data["final_score"], "5.00")
        self.assertTrue(visible.data["result_published"])

    def test_exam_committee_proctors_are_visible_only_to_assigned_teacher(self):
        committee = ExamCommittee.objects.create(
            school=self.school, name="اللجنة أ", committee_number="A-1",
            location_room="قاعة 1", capacity=30, head_supervisor=self.teacher,
        )
        assigned = self.admin_client.post(
            "/api/v1/app/exam-committee-proctors/",
            {**self.school_query, "committee": str(committee.pk), "teacher": str(self.teacher.pk), "duty": "proctor"},
            format="json",
        )
        self.assertEqual(assigned.status_code, status.HTTP_201_CREATED, assigned.data)
        self.assertEqual(
            ExamCommitteeProctor.objects.filter(
                school=self.school, committee=committee, teacher=self.teacher,
            ).count(),
            1,
        )
        listing = self.teacher_client.get(
            "/api/v1/app/exam-committee-proctors/", self.school_query,
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK, listing.data)
        self.assertEqual(len(listing.data["results"]), 1)

    def test_student_seating_api_does_not_expose_control_secret_code(self):
        committee = ExamCommittee.objects.create(
            school=self.school, name="اللجنة ب", committee_number="B-1",
            location_room="قاعة 2", capacity=30,
        )
        seating = ExamSeating.objects.create(
            school=self.school, academic_year=self.year,
            committee=committee, student=self.student,
            seating_number=101, secret_code="secret-101",
        )
        response = self.student_client.get(
            f"/api/v1/app/exam-seatings/{seating.pk}/", self.school_query,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertNotIn("secret_code", response.data)
