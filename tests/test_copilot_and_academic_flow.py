from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.academics.models import AcademicYear, EducationalStage, GradeLevel, Section, Subject
from apps.accounts.models import User
from apps.assessments.models import GradeBook
from apps.copilot.services.ai_student import (
    fetch_academic_grades,
)
from apps.staff.models import Teacher, TeacherAssignment
from apps.students.models import Student
from apps.tenants.models import School
from apps.timetable.models import ClassSchedule


class CopilotAndAcademicFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.teacher_user = User.objects.create_user(
            phone="+967777111001", password="StrongPassword123!",
            first_name="سعيد", last_name="الأستاذ",
        )
        cls.student_user_a = User.objects.create_user(
            phone="+967777111002", password="StrongPassword123!",
            first_name="علي", last_name="الطالب",
        )
        cls.student_user_b = User.objects.create_user(
            phone="+967777111003", password="StrongPassword123!",
            first_name="عمر", last_name="الطالب الآخر",
        )

        # Schools
        cls.school_a = School.objects.create(owner=cls.teacher_user, code="SCH_AI_1", name="مدرسة الأوائل", status=School.Status.ACTIVE)
        cls.school_b = School.objects.create(owner=cls.teacher_user, code="SCH_AI_2", name="مدرسة الرواد", status=School.Status.ACTIVE)

        # Academic structure in School A
        cls.year_a = AcademicYear.objects.create(school=cls.school_a, code="2026-2027", name="2026-2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30))
        cls.stage_a = EducationalStage.objects.create(school=cls.school_a, code="SEC", name="المرحلة الثانوية", sequence=1)
        cls.grade_a = GradeLevel.objects.create(school=cls.school_a, stage=cls.stage_a, code="G10", name="الصف العاشر", sequence=1)
        cls.section_a = Section.objects.create(school=cls.school_a, academic_year=cls.year_a, grade=cls.grade_a, code="10-A", name="العاشر / أ")
        cls.subject_math = Subject.objects.create(school=cls.school_a, code="MATH10", name="الرياضيات")

        # Academic structure in School B
        cls.year_b = AcademicYear.objects.create(school=cls.school_b, code="2026-2027-B", name="2026-2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30))
        cls.stage_b = EducationalStage.objects.create(school=cls.school_b, code="SEC-B", name="المرحلة الثانوية", sequence=1)
        cls.grade_b = GradeLevel.objects.create(school=cls.school_b, stage=cls.stage_b, code="G10-B", name="الصف العاشر", sequence=1)
        cls.section_b = Section.objects.create(school=cls.school_b, academic_year=cls.year_b, grade=cls.grade_b, code="10-B", name="العاشر / ب")

        # Staff in School A
        cls.teacher_a = Teacher.objects.create(school=cls.school_a, user=cls.teacher_user, specialization="رياضيات")

        # Students
        cls.student_a = Student.objects.create(
            school=cls.school_a,
            user=cls.student_user_a,
            student_id_number="STD-001",
            first_name="علي",
            last_name="الطالب",
            grade_level=cls.grade_a,
            section=cls.section_a,
            academic_year=cls.year_a,
        )
        cls.student_b = Student.objects.create(
            school=cls.school_b,
            user=cls.student_user_b,
            student_id_number="STD-002",
            first_name="عمر",
            last_name="المنافس",
            grade_level=cls.grade_b,
            section=cls.section_b,
            academic_year=cls.year_b,
        )

    def test_student_cannot_have_cross_school_section(self):
        """التحقق من منع تسجيل طالب في شعبة تابعة لمدرسة أخرى."""
        invalid_student = Student(
            school=self.school_a,
            student_id_number="STD-ERR",
            first_name="خطأ",
            last_name="عزل",
            grade_level=self.grade_a,
            section=self.section_b,  # from school_b!
            academic_year=self.year_a,
        )
        with self.assertRaises(ValidationError):
            invalid_student.save()

    def test_schedule_creation_and_period_conflict(self):
        """التحقق من منع تعارض الحصص لنفس الشعبة أو المعلم."""
        TeacherAssignment.objects.create(
            school=self.school_a, academic_year=self.year_a,
            teacher=self.teacher_a, subject=self.subject_math,
            section=self.section_a, weekly_periods=4,
        )
        ClassSchedule.objects.create(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            subject=self.subject_math,
            teacher=self.teacher_a,
            day_of_week=ClassSchedule.WeekDay.SUNDAY,
            period_number=1,
            start_time=time(8, 0),
            end_time=time(8, 45),
        )

        # Attempt to schedule another class for the same section at the same day & period
        duplicate_schedule = ClassSchedule(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            subject=self.subject_math,
            teacher=self.teacher_a,
            day_of_week=ClassSchedule.WeekDay.SUNDAY,
            period_number=1,
            start_time=time(8, 0),
            end_time=time(8, 45),
        )
        with self.assertRaises(Exception):
            duplicate_schedule.save()

    def test_copilot_grades_tool_isolation(self):
        """التحقق من أن أداة درجات الطالب لا تعرض إلا درجاته المعتمدة ولا تسرب درجات غيره."""
        # Create published grade for student A
        GradeBook.objects.create(
            school=self.school_a,
            student=self.student_a,
            subject=self.subject_math,
            assessment_title="اختبار الجبر الشهري",
            score=95.0,
            max_score=100.0,
            is_published=True,
        )
        # Create published grade for student B
        GradeBook.objects.create(
            school=self.school_b,
            student=self.student_b,
            subject=Subject.objects.create(school=self.school_b, code="MATH-B", name="رياضيات ب"),
            assessment_title="اختبار سري لمدرسة أخرى",
            score=70.0,
            max_score=100.0,
            is_published=True,
        )

        # Query grades for student A
        result = fetch_academic_grades(str(self.student_a.id))
        self.assertEqual(result["student_name"], self.student_a.get_full_name())
        self.assertEqual(len(result["recent_grades"]), 1)
        self.assertEqual(result["recent_grades"][0]["assessment_title"], "اختبار الجبر الشهري")
        self.assertEqual(result["recent_grades"][0]["score"], 95.0)

        # Confirm student A's query does NOT contain student B's grade
        for r in result["recent_grades"]:
            self.assertNotEqual(r["assessment_title"], "اختبار سري لمدرسة أخرى")
