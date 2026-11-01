from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.academics.models import (
    AcademicYear,
    Classroom,
    EducationalStage,
    GradeLevel,
    PeriodDefinition,
    Section,
    SchoolWorkingDay,
)
from apps.tenants.models import Branch, School
from apps.tenants.services import provision_school
from apps.students.models import Student, StudentEnrollment
from apps.students.services import promote_student
from apps.attendance.models import SchoolCalendar, SchoolCalendarDay
from apps.attendance.services.calendar_service import is_school_day, seed_default_calendar


class AcademicBranchModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967770004401",
            password="Strong-Branch-4401!",
            first_name="مدير",
            last_name="الفروع",
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="BRANCH-SCHOOL",
            name="مدرسة الفروع",
            status=School.Status.ACTIVE,
        )
        cls.branch_a = Branch.objects.create(
            school=cls.school, code="NORTH", name="الفرع الشمالي",
        )
        cls.branch_b = Branch.objects.create(
            school=cls.school, code="SOUTH", name="الفرع الجنوبي",
        )

    def test_same_academic_codes_and_current_years_are_scoped_per_branch(self):
        year_data = {
            "school": self.school,
            "code": "2026-2027",
            "name": "2026-2027",
            "starts_on": date(2026, 9, 1),
            "ends_on": date(2027, 6, 30),
            "status": AcademicYear.Status.ACTIVE,
            "is_current": True,
        }
        north_year = AcademicYear.objects.create(**year_data, branch=self.branch_a)
        south_year = AcademicYear.objects.create(**year_data, branch=self.branch_b)
        self.assertNotEqual(north_year.pk, south_year.pk)
        self.assertTrue(north_year.is_current)
        self.assertTrue(south_year.is_current)

        EducationalStage.objects.create(
            school=self.school, branch=self.branch_a, code="PRIMARY",
            name="الابتدائية - شمال", sequence=1,
        )
        EducationalStage.objects.create(
            school=self.school, branch=self.branch_b, code="PRIMARY",
            name="الابتدائية - جنوب", sequence=1,
        )

    def test_grade_cannot_reference_a_stage_from_another_branch(self):
        stage_south = EducationalStage.objects.create(
            school=self.school, branch=self.branch_b, code="SECONDARY",
            name="الثانوية - جنوب", sequence=2,
        )
        with self.assertRaises(ValidationError):
            GradeLevel.objects.create(
                school=self.school, branch=self.branch_a,
                stage=stage_south, code="G10", name="العاشر", sequence=1,
            )

    def test_section_cannot_mix_year_grade_or_classroom_from_another_branch(self):
        year_north = AcademicYear.objects.create(
            school=self.school, branch=self.branch_a, code="N-2026",
            name="شمال 2026", starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30),
        )
        stage_south = EducationalStage.objects.create(
            school=self.school, branch=self.branch_b, code="S-PRI",
            name="ابتدائية جنوب", sequence=1,
        )
        grade_south = GradeLevel.objects.create(
            school=self.school, branch=self.branch_b, stage=stage_south,
            code="S-G1", name="الأول", sequence=1,
        )
        with self.assertRaises(ValidationError):
            Section.objects.create(
                school=self.school, branch=self.branch_a,
                academic_year=year_north, grade=grade_south,
                code="1-A", name="الأول أ",
            )

        global_stage = EducationalStage.objects.create(
            school=self.school, code="COMMON", name="مرحلة مشتركة", sequence=1,
        )
        global_grade = GradeLevel.objects.create(
            school=self.school, stage=global_stage,
            code="COMMON-G1", name="الأول المشترك", sequence=1,
        )
        section = Section.objects.create(
            school=self.school, branch=self.branch_a,
            academic_year=year_north, grade=global_grade,
            code="N-1-A", name="الأول أ",
        )
        self.assertEqual(section.branch_id, self.branch_a.pk)

    def test_active_periods_may_differ_between_branches_but_not_overlap_locally(self):
        PeriodDefinition.objects.create(
            school=self.school, branch=self.branch_a,
            name="الحصة الأولى شمال", period_number=1,
            starts_at=time(8, 0), ends_at=time(8, 45),
        )
        PeriodDefinition.objects.create(
            school=self.school, branch=self.branch_b,
            name="الحصة الأولى جنوب", period_number=1,
            starts_at=time(8, 0), ends_at=time(8, 50),
        )
        with self.assertRaises(ValidationError):
            PeriodDefinition.objects.create(
                school=self.school, branch=self.branch_a,
                name="فترة متداخلة", period_number=2,
                starts_at=time(8, 30), ends_at=time(9, 0),
            )

    def test_working_day_periods_must_belong_to_compatible_branch(self):
        south_period = PeriodDefinition.objects.create(
            school=self.school, branch=self.branch_b,
            name="الحصة الأولى", period_number=1,
            starts_at=time(8, 0), ends_at=time(8, 45),
        )
        with self.assertRaises(ValidationError):
            SchoolWorkingDay.objects.create(
                school=self.school, branch=self.branch_a, weekday=0,
                is_working=True, sequence=1, first_period=south_period,
            )

    def test_academic_capacities_must_be_positive(self):
        with self.assertRaises(ValidationError):
            Classroom.objects.create(
                school=self.school, branch=self.branch_a,
                code="ROOM-0", name="قاعة بلا سعة", capacity=0,
            )
        year_north = AcademicYear.objects.create(
            school=self.school, branch=self.branch_a, code="N-2027",
            name="شمال 2027", starts_on=date(2027, 9, 1),
            ends_on=date(2028, 6, 30),
        )
        stage = EducationalStage.objects.create(
            school=self.school, branch=self.branch_a,
            code="N-STAGE", name="مرحلة شمال", sequence=1,
        )
        grade = GradeLevel.objects.create(
            school=self.school, branch=self.branch_a, stage=stage,
            code="N-GRADE", name="صف شمال", sequence=1,
        )
        with self.assertRaises(ValidationError):
            Section.objects.create(
                school=self.school, branch=self.branch_a,
                academic_year=year_north, grade=grade,
                code="N-0", name="شعبة بلا سعة", capacity=0,
            )

    def test_student_enrollment_and_transitions_remain_inside_its_branch(self):
        year_north = AcademicYear.objects.create(
            school=self.school, branch=self.branch_a, code="STU-N-2026",
            name="سنة شمال", starts_on=date(2026, 9, 1),
            ends_on=date(2027, 6, 30), status=AcademicYear.Status.ACTIVE,
        )
        stage_north = EducationalStage.objects.create(
            school=self.school, branch=self.branch_a,
            code="STU-N-PRI", name="ابتدائية شمال", sequence=1,
        )
        grade_north = GradeLevel.objects.create(
            school=self.school, branch=self.branch_a, stage=stage_north,
            code="STU-N-G1", name="الأول شمال", sequence=1,
        )
        section_north = Section.objects.create(
            school=self.school, branch=self.branch_a,
            academic_year=year_north, grade=grade_north,
            code="STU-N-1-A", name="الأول أ شمال",
        )
        student = Student.objects.create(
            school=self.school, branch=self.branch_a,
            academic_year=year_north, grade_level=grade_north,
            section=section_north, student_id_number="BR-STU-001",
            first_name="طالب", last_name="الشمال",
            gender=Student.Gender.MALE, enrollment_date=date(2026, 9, 1),
        )
        enrollment = StudentEnrollment.objects.get(
            school=self.school, student=student, academic_year=year_north,
        )
        self.assertEqual(enrollment.branch_id, self.branch_a.pk)

        year_south = AcademicYear.objects.create(
            school=self.school, branch=self.branch_b, code="STU-S-2027",
            name="سنة جنوب", starts_on=date(2027, 9, 1),
            ends_on=date(2028, 6, 30), status=AcademicYear.Status.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            promote_student(
                student=student,
                next_academic_year=year_south,
                next_grade_level=grade_north,
            )

    def test_calendar_seed_uses_branch_working_days_and_branch_calendar_overrides_shared(self):
        year = AcademicYear.objects.create(
            school=self.school, branch=self.branch_a, code="CAL-N-2026",
            name="تقويم شمال", starts_on=date(2026, 9, 1),
            ends_on=date(2026, 9, 5), status=AcademicYear.Status.ACTIVE,
        )
        SchoolWorkingDay.objects.create(
            school=self.school, weekday=1, is_working=False, sequence=1,
        )
        SchoolWorkingDay.objects.create(
            school=self.school, branch=self.branch_a,
            weekday=4, is_working=True, sequence=1,
        )
        calendar = seed_default_calendar(
            school=self.school, academic_year=year, branch=self.branch_a,
        )
        days = {
            item.date: item
            for item in SchoolCalendarDay.objects.filter(calendar=calendar)
        }
        self.assertFalse(days[date(2026, 9, 1)].is_school_day)
        self.assertTrue(days[date(2026, 9, 4)].is_school_day)
        self.assertEqual(days[date(2026, 9, 4)].branch_id, self.branch_a.pk)

        shared_year = AcademicYear.objects.create(
            school=self.school, code="CAL-SHARED-2026", name="سنة مشتركة",
            starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 5),
            status=AcademicYear.Status.ACTIVE,
        )
        shared_calendar = SchoolCalendar.objects.create(
            school=self.school, academic_year=shared_year,
            name="تقويم عام", is_active=True,
        )
        branch_calendar = SchoolCalendar.objects.create(
            school=self.school, branch=self.branch_a,
            academic_year=shared_year, name="تقويم فرع شمال", is_active=True,
        )
        SchoolCalendarDay.objects.create(
            school=self.school, calendar=shared_calendar,
            date=date(2026, 9, 4), day_type=SchoolCalendarDay.DayType.WEEKEND,
            is_school_day=False,
        )
        SchoolCalendarDay.objects.create(
            school=self.school, branch=self.branch_a, calendar=branch_calendar,
            date=date(2026, 9, 4), day_type=SchoolCalendarDay.DayType.REGULAR,
            is_school_day=True,
        )
        self.assertTrue(is_school_day(
            self.school, date(2026, 9, 4),
            academic_year=shared_year, branch=self.branch_a,
        ))

class AcademicBranchApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            phone="+967770004402",
            password="Strong-Branch-4402!",
            first_name="مدير",
            last_name="API",
        )
        cls.school = School.objects.create(
            owner=cls.owner,
            code="BRANCH-API",
            name="مدرسة API للفروع",
            status=School.Status.ACTIVE,
        )
        provision_school(cls.school)
        cls.main_branch = Branch.objects.get(school=cls.school, is_main=True)
        cls.branch_b = Branch.objects.create(
            school=cls.school, code="WEST", name="الفرع الغربي",
        )
        cls.other_owner = User.objects.create_user(
            phone="+967770004403",
            password="Strong-Branch-4403!",
            first_name="مدير",
            last_name="آخر",
        )
        cls.other_school = School.objects.create(
            owner=cls.other_owner,
            code="BRANCH-OTHER",
            name="مدرسة أخرى",
            status=School.Status.ACTIVE,
        )
        cls.other_branch = Branch.objects.create(
            school=cls.other_school, code="OTHER", name="فرع آخر",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
        self.school_query = f"?school_code={self.school.code}"

    def test_branch_route_is_mounted_once_and_can_create_branch(self):
        self.assertEqual(
            resolve("/api/v1/app/branches/").url_name,
            "app-branch-list",
        )
        response = self.client.post(
            f"/api/v1/app/branches/{self.school_query}",
            {"code": "EAST", "name": "الفرع الشرقي", "is_main": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(str(response.data["school"]), str(self.school.pk))

    def test_academic_api_accepts_only_a_branch_from_the_active_school(self):
        payload = {
            "name": "2027-2028",
            "code": "2027-2028",
            "starts_on": "2027-09-01",
            "ends_on": "2028-06-30",
            "status": "planning",
            "branch": str(self.branch_b.pk),
        }
        response = self.client.post(
            f"/api/v1/app/academic-years/{self.school_query}",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(str(response.data["branch"]), str(self.branch_b.pk))

        payload["code"] = "2028-2029"
        payload["branch"] = str(self.other_branch.pk)
        rejected = self.client.post(
            f"/api/v1/app/academic-years/{self.school_query}",
            payload,
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_branch_filter_returns_branch_records_and_school_shared_records(self):
        shared = EducationalStage.objects.create(
            school=self.school, code="SHARED", name="مرحلة مشتركة", sequence=1,
        )
        north = EducationalStage.objects.create(
            school=self.school, branch=self.main_branch,
            code="NORTH-ONLY", name="مرحلة شمال", sequence=2,
        )
        south = EducationalStage.objects.create(
            school=self.school, branch=self.branch_b,
            code="SOUTH-ONLY", name="مرحلة غرب", sequence=3,
        )
        response = self.client.get(
            f"/api/v1/app/stages/{self.school_query}&branch_id={self.main_branch.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(shared.pk), returned_ids)
        self.assertIn(str(north.pk), returned_ids)
        self.assertNotIn(str(south.pk), returned_ids)

    def test_invalid_or_foreign_branch_filter_is_rejected(self):
        response = self.client.get(
            f"/api/v1/app/stages/{self.school_query}&branch_id={self.other_branch.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        malformed = self.client.get(
            f"/api/v1/app/stages/{self.school_query}&branch_id=not-a-uuid"
        )
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)
