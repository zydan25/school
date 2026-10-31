"""Comprehensive test suite for the new Attendance, Calendar, and Scoring system."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.academics.models import (
    AcademicTerm,
    AcademicYear,
    Classroom,
    EducationalStage,
    GradeLevel,
    Section,
    Subject,
)
from apps.accounts.models import SchoolMembership, User
from apps.assessments.models import AssessmentType, GradeBook
from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceExcuseRequest,
    AttendancePolicy,
    AttendanceRegister,
    AttendanceReopenRequest,
    AttendanceScoreEntry,
    AttendanceScoringPolicy,
    AttendanceStatusType,
    DailyAttendance,
    EarlyDepartureRequest,
    PeriodAttendance,
    SchoolCalendar,
    SchoolCalendarDay,
    StudentAttendanceRecord,
)
from apps.attendance.reports.selectors import (
    get_chronic_absenteeism_report,
    get_daily_section_summary,
    get_monthly_attendance_matrix,
    get_term_attendance_summary,
)
from apps.attendance.services import (
    approve_early_departure,
    approve_register,
    bulk_record_attendance,
    calculate_student_attendance_score,
    confirm_gate_exit,
    create_early_departure_request,
    create_excuse_request,
    get_or_create_register,
    is_school_day,
    lock_register,
    request_reopen_register,
    review_excuse_request,
    review_reopen_request,
    seed_default_calendar,
    submit_register,
    sync_score_to_gradebook,
)
from apps.students.models import Guardian, Student, StudentGuardianRelation
from apps.tenants.models import School


class AttendanceSystemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.owner_a = User.objects.create_user(
            phone="+967770001111", password="Test-Password-01",
            first_name="مدير", last_name="الأول", email="owner-a@example.com",
        )
        cls.owner_b = User.objects.create_user(
            phone="+967770002222", password="Test-Password-02",
            first_name="مدير", last_name="الثاني", email="owner-b@example.com",
        )
        cls.teacher_user = User.objects.create_user(
            phone="+967770003333", password="Test-Password-03",
            first_name="معلم", last_name="الفصل", email="teacher@example.com",
        )
        cls.guardian_user = User.objects.create_user(
            phone="+967770004444", password="Test-Password-04",
            first_name="ولي", last_name="الأمر", email="guardian@example.com",
        )

        # Schools
        cls.school_a = School.objects.create(owner=cls.owner_a, code="SCH_ATT_A", name="مدرسة الرواد", status=School.Status.ACTIVE)
        cls.school_b = School.objects.create(owner=cls.owner_b, code="SCH_ATT_B", name="مدرسة الأمل", status=School.Status.ACTIVE)

        SchoolMembership.objects.create(school=cls.school_a, user=cls.owner_a, status=SchoolMembership.Status.ACTIVE, is_default=True)
        SchoolMembership.objects.create(school=cls.school_b, user=cls.owner_b, status=SchoolMembership.Status.ACTIVE, is_default=True)
        SchoolMembership.objects.create(school=cls.school_a, user=cls.teacher_user, status=SchoolMembership.Status.ACTIVE)
        SchoolMembership.objects.create(school=cls.school_a, user=cls.guardian_user, status=SchoolMembership.Status.ACTIVE)

        # Academic structure
        cls.year_a = AcademicYear.objects.create(
            school=cls.school_a,
            name="2026-2027",
            code="AY26",
            starts_on=datetime.date(2026, 9, 1),
            ends_on=datetime.date(2027, 6, 30),
            status=AcademicYear.Status.ACTIVE,
            is_current=True,
        )
        cls.term_a = AcademicTerm.objects.create(
            school=cls.school_a,
            academic_year=cls.year_a,
            name="الفصل الأول",
            number=1,
            starts_on=datetime.date(2026, 9, 1),
            ends_on=datetime.date(2027, 1, 31),
            is_current=True,
        )
        cls.stage_a = EducationalStage.objects.create(
            school=cls.school_a,
            name="المرحلة الابتدائية",
            code="PRIM",
            sequence=1,
        )
        cls.grade_a = GradeLevel.objects.create(
            school=cls.school_a,
            stage=cls.stage_a,
            name="الصف الأول",
            code="G01",
            sequence=1,
        )
        cls.classroom_a = Classroom.objects.create(
            school=cls.school_a,
            name="قاعة 101",
            code="R101",
        )
        cls.section_a = Section.objects.create(
            school=cls.school_a,
            academic_year=cls.year_a,
            grade=cls.grade_a,
            name="الشعبة (أ)",
            code="SEC_A",
            homeroom_classroom=cls.classroom_a,
            capacity=30,
        )
        cls.subject_a = Subject.objects.create(
            school=cls.school_a,
            name="الرياضيات",
            code="MATH101",
        )

        # Students
        cls.student_1 = Student.objects.create(
            school=cls.school_a,
            student_id_number="STD001",
            first_name="سالم",
            last_name="المحمدي",
            grade_level=cls.grade_a,
            section=cls.section_a,
            academic_year=cls.year_a,
            status=Student.Status.ACTIVE,
        )
        cls.student_2 = Student.objects.create(
            school=cls.school_a,
            student_id_number="STD002",
            first_name="عمر",
            last_name="اليماني",
            grade_level=cls.grade_a,
            section=cls.section_a,
            academic_year=cls.year_a,
            status=Student.Status.ACTIVE,
        )

        # Guardian
        cls.guardian = Guardian.objects.create(
            school=cls.school_a,
            user=cls.guardian_user,
            relationship_type=Guardian.RelationshipType.FATHER,
        )
        StudentGuardianRelation.objects.create(
            school=cls.school_a,
            student=cls.student_1,
            guardian=cls.guardian,
            is_primary=True,
            receives_notifications=True,
            can_pickup=True,
        )

        # Policy
        cls.policy = AttendancePolicy.objects.create(
            school=cls.school_a,
            academic_year=cls.year_a,
            attendance_mode=AttendancePolicy.Mode.DAILY,
            morning_assembly_time=datetime.time(7, 30),
            day_end_time=datetime.time(13, 30),
            grace_period_minutes=15,
            late_to_absent_minutes=45,
            excuse_submission_deadline_days=3,
            require_excuse_attachment=False,
            auto_lock_after_days=2,
            is_active=True,
        )

    def test_seed_school_calendar_and_check_school_days(self):
        """اختبار تهيئة التقويم المدرسي وتصنيف أيام الأسبوع وعطل نهاية الأسبوع."""
        cal = seed_default_calendar(self.school_a, self.year_a)
        self.assertIsNotNone(cal)
        self.assertTrue(SchoolCalendarDay.objects.filter(calendar=cal).count() > 200)

        # Sunday 2026-09-06 is a school day in Arab schools
        sunday = datetime.date(2026, 9, 6)
        self.assertTrue(is_school_day(self.school_a, sunday, self.year_a))

        # Friday 2026-09-11 is a weekend day
        friday = datetime.date(2026, 9, 11)
        self.assertFalse(is_school_day(self.school_a, friday, self.year_a))

    def test_get_or_create_register_on_school_day(self):
        """اختبار فتح سجل الحضور ليوم دراسي والتحقق من تهيئة الطلاب التلقائية."""
        seed_default_calendar(self.school_a, self.year_a)
        target_date = datetime.date(2026, 9, 6)  # Sunday
        register, created = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            user=self.teacher_user,
        )
        self.assertTrue(created)
        self.assertEqual(register.status, AttendanceRegister.Status.OPEN)
        # Should have 2 records for the 2 students
        self.assertEqual(register.student_records.count(), 2)

        # Check default status is present
        rec = register.student_records.get(student=self.student_1)
        self.assertEqual(rec.status_category, AttendanceStatusType.Category.PRESENT)

        # Check legacy DailyAttendance sync
        legacy = DailyAttendance.objects.filter(school=self.school_a, student=self.student_1, date=target_date).first()
        self.assertIsNotNone(legacy)
        self.assertEqual(legacy.status, DailyAttendance.Status.PRESENT)

    def test_cannot_open_register_on_weekend_without_bypass(self):
        """منع فتح سجل حضور في يوم عطلة رسمية بدون تصريح تجاوز."""
        seed_default_calendar(self.school_a, self.year_a)
        friday = datetime.date(2026, 9, 11)
        with self.assertRaises(ValidationError):
            get_or_create_register(
                school=self.school_a,
                academic_year=self.year_a,
                section=self.section_a,
                date=friday,
                user=self.teacher_user,
            )

    def test_bulk_record_attendance_and_audit(self):
        """رصد وتحديث الحضور والتأخر والغياب مع توثيق سجل التدقيق ومزامنة السجلات القديمة."""
        target_date = datetime.date(2026, 9, 6)
        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )

        # Mark student 1 as unexcused absent, student 2 as late 20 minutes
        records_data = [
            {"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.ABSENT_UNEXCUSED, "late_minutes": 0, "notes": "لم يحضر"},
            {"student_id": self.student_2.id, "status_category": AttendanceStatusType.Category.LATE, "late_minutes": 20, "notes": "تأخر عن الطابور"},
        ]
        count = bulk_record_attendance(register, records_data, recorded_by=self.teacher_user)
        self.assertEqual(count, 2)

        # Verify updated records
        r1 = register.student_records.get(student=self.student_1)
        self.assertEqual(r1.status_category, AttendanceStatusType.Category.ABSENT_UNEXCUSED)
        r2 = register.student_records.get(student=self.student_2)
        self.assertEqual(r2.status_category, AttendanceStatusType.Category.LATE)
        self.assertEqual(r2.late_minutes, 20)

        # Verify legacy DailyAttendance updated
        leg1 = DailyAttendance.objects.get(school=self.school_a, student=self.student_1, date=target_date)
        self.assertEqual(leg1.status, DailyAttendance.Status.ABSENT_UNEXCUSED)
        leg2 = DailyAttendance.objects.get(school=self.school_a, student=self.student_2, date=target_date)
        self.assertEqual(leg2.status, DailyAttendance.Status.LATE)
        self.assertEqual(leg2.late_minutes, 20)

        # Verify Audit Log
        logs = AttendanceAuditLog.objects.filter(register=register, action=AttendanceAuditLog.Action.RECORD_UPDATED)
        self.assertEqual(logs.count(), 2)

    def test_register_lifecycle_submit_approve_lock_immutability(self):
        """دورة حياة السجل (تسليم -> اعتماد -> إقفال) والتحقق من حماية السجل المقفل."""
        target_date = datetime.date(2026, 9, 7)
        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )

        submit_register(register, submitted_by=self.teacher_user)
        self.assertEqual(register.status, AttendanceRegister.Status.SUBMITTED)

        approve_register(register, approved_by=self.owner_a)
        self.assertEqual(register.status, AttendanceRegister.Status.APPROVED)

        lock_register(register, locked_by=self.owner_a)
        self.assertEqual(register.status, AttendanceRegister.Status.LOCKED)

        # Attempting to bulk-record on locked register must raise ValidationError
        records_data = [{"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.PRESENT}]
        with self.assertRaises(ValidationError):
            bulk_record_attendance(register, records_data, recorded_by=self.teacher_user)

    def test_reopen_request_workflow(self):
        """طلب إعادة فتح السجل المقفل وموافقة الإدارة لإعادة فتح التعديل."""
        target_date = datetime.date(2026, 9, 8)
        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )
        lock_register(register, locked_by=self.owner_a)

        reopen_req = request_reopen_register(register, requested_by=self.teacher_user, reason="نسيان رصد طالب معذور")
        self.assertEqual(reopen_req.status, AttendanceReopenRequest.Status.PENDING)

        review_reopen_request(reopen_req, reviewed_by=self.owner_a, is_approved=True, review_notes="موافق")
        register.refresh_from_db()
        self.assertEqual(register.status, AttendanceRegister.Status.OPEN)

    def test_advance_excuse_request_auto_applied(self):
        """تقديم عذر مسبق من ولي الأمر واعتماده يطبق تلقائياً عند فتح السجل لليوم المحدد."""
        target_date = datetime.date(2026, 9, 15)
        excuse = create_excuse_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            request_type=AttendanceExcuseRequest.RequestType.ADVANCE_ABSENCE,
            start_date=target_date,
            end_date=target_date,
            reason="موعد مستشفى",
        )
        review_excuse_request(excuse, reviewed_by=self.owner_a, is_approved=True)

        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )

        rec = register.student_records.get(student=self.student_1)
        self.assertEqual(rec.status_category, AttendanceStatusType.Category.ABSENT_EXCUSED)
        self.assertEqual(rec.excuse_request, excuse)

    def test_retroactive_excuse_updates_past_records(self):
        """تقديم عذر لاحق وتحديث سجل الغياب غير المبرر إلى غياب بعذر بأثر رجعي."""
        target_date = datetime.date.today() - datetime.timedelta(days=1)
        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )
        bulk_record_attendance(
            register,
            [{"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.ABSENT_UNEXCUSED}],
            recorded_by=self.teacher_user,
        )

        excuse = create_excuse_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            request_type=AttendanceExcuseRequest.RequestType.POST_ABSENCE_EXCUSE,
            start_date=target_date,
            end_date=target_date,
            reason="عارض صحي مفاجئ",
        )
        review_excuse_request(excuse, reviewed_by=self.owner_a, is_approved=True, review_notes="مقبول")

        rec = register.student_records.get(student=self.student_1)
        self.assertEqual(rec.status_category, AttendanceStatusType.Category.ABSENT_EXCUSED)
        self.assertEqual(rec.excuse_request, excuse)

        # Legacy model check
        leg = DailyAttendance.objects.get(school=self.school_a, student=self.student_1, date=target_date)
        self.assertEqual(leg.status, DailyAttendance.Status.ABSENT_EXCUSED)

    def test_early_departure_and_gate_exit_flow(self):
        """دورة طلب الانصراف المبكر واعتماد الإدارة وتأكيد الخروج من البوابة الأمنية."""
        target_date = datetime.date(2026, 9, 17)
        register, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=target_date,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )

        dep_req = create_early_departure_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            date=target_date,
            departure_time=datetime.time(11, 0),
            reason="ظرف عائلي",
            recipient_name="عبدالله اليماني",
            recipient_phone="+967771234567",
            recipient_relationship="العم",
            recipient_national_id="1020304050",
        )
        self.assertEqual(dep_req.status, EarlyDepartureRequest.Status.PENDING)

        approve_early_departure(dep_req, approved_by=self.owner_a)
        self.assertEqual(dep_req.status, EarlyDepartureRequest.Status.APPROVED)

        confirm_gate_exit(dep_req, confirmed_by=self.teacher_user, exit_notes="تمت مطابقة الهوية")
        dep_req.refresh_from_db()
        self.assertEqual(dep_req.status, EarlyDepartureRequest.Status.EXITED)

        rec = register.student_records.get(student=self.student_1)
        self.assertEqual(rec.status_category, AttendanceStatusType.Category.AUTHORIZED_DEPARTURE)

    def test_attendance_scoring_and_gradebook_sync(self):
        """احتساب درجات المواظبة وفق السياسة وخصم الغياب والتأخر ومزامنتها مع سجل الدرجات."""
        target_date_1 = datetime.date(2026, 9, 20)
        target_date_2 = datetime.date(2026, 9, 21)

        reg1, _ = get_or_create_register(self.school_a, self.year_a, self.section_a, target_date_1, bypass_calendar_check=True)
        reg2, _ = get_or_create_register(self.school_a, self.year_a, self.section_a, target_date_2, bypass_calendar_check=True)

        # Student 1: 1 unexcused absence on day 1, 1 late (20 min) on day 2
        bulk_record_attendance(reg1, [{"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.ABSENT_UNEXCUSED}])
        bulk_record_attendance(reg2, [{"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.LATE, "late_minutes": 20}])

        # Calculate score: total=10, unexcused deduction=1.00, late deduction=0.25 -> final score = 8.75
        entry = calculate_student_attendance_score(self.school_a, self.student_1, self.term_a, subject=None)
        self.assertEqual(entry.raw_score, Decimal("10.00"))
        self.assertEqual(entry.unexcused_absence_count, 1)
        self.assertEqual(entry.late_count, 1)
        self.assertEqual(entry.deduction_total, Decimal("1.25"))
        self.assertEqual(entry.final_score, Decimal("8.75"))

        # Sync to GradeBook
        gradebook = sync_score_to_gradebook(entry)
        self.assertIsNotNone(gradebook)
        self.assertEqual(gradebook.score, Decimal("8.75"))
        self.assertTrue(entry.is_synced_to_gradebook)

    def test_multi_tenant_isolation_attendance(self):
        """التحقق التام من العزل الصارم بين المدارس في التقويم وسجلات الحضور."""
        reg_a, _ = get_or_create_register(self.school_a, self.year_a, self.section_a, datetime.date(2026, 9, 22), bypass_calendar_check=True)

        # School B cannot view or access register of School A
        b_registers = AttendanceRegister.objects.filter(school=self.school_b)
        self.assertFalse(b_registers.filter(id=reg_a.id).exists())

    def test_attendance_reports(self):
        """اختبار تقارير الموقف اليومي والمصفوفة الشهرية وكشف الغياب المزمن."""
        test_date = datetime.date(2026, 9, 23)
        reg, _ = get_or_create_register(self.school_a, self.year_a, self.section_a, test_date, bypass_calendar_check=True)
        bulk_record_attendance(reg, [
            {"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.PRESENT},
            {"student_id": self.student_2.id, "status_category": AttendanceStatusType.Category.ABSENT_UNEXCUSED},
        ])

        summary = get_daily_section_summary(self.school_a, test_date, self.section_a.id)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["present_count"], 1)
        self.assertEqual(summary[0]["absent_unexcused"], 1)
        self.assertEqual(summary[0]["attendance_rate"], 50.0)

        # Monthly matrix
        matrix = get_monthly_attendance_matrix(self.school_a, self.section_a.id, 2026, 9)
        self.assertEqual(len(matrix["students"]), 2)

        # Chronic absenteeism
        chronic = get_chronic_absenteeism_report(self.school_a, self.year_a.id, threshold_percentage=10.0)
        self.assertTrue(len(chronic) >= 1)
        # Student 2 has high absence percentage
        self.assertTrue(any(c["student_id"] == self.student_2.id for c in chronic))

    def test_cascade_daily_attendance_to_all_periods_and_early_departure(self):
        """اعتماد الحضور باليوم يعمم الحضور على كافة الحصص إلا في حال تسجيل انصراف مبكر."""
        from apps.staff.models import Teacher
        from apps.timetable.models import ClassSchedule

        teacher = Teacher.objects.create(
            school=self.school_a,
            user=self.teacher_user,
            specialization="رياضيات",
        )

        # Sunday weekday is 1 in ClassSchedule.WeekDay
        sunday_date = datetime.date(2026, 9, 6)
        sched_p1 = ClassSchedule.objects.create(
            school=self.school_a, academic_year=self.year_a, academic_term=self.term_a,
            section=self.section_a, subject=self.subject_a, teacher=teacher,
            day_of_week=ClassSchedule.WeekDay.SUNDAY, period_number=1,
            start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
        )
        sched_p2 = ClassSchedule.objects.create(
            school=self.school_a, academic_year=self.year_a, academic_term=self.term_a,
            section=self.section_a, subject=self.subject_a, teacher=teacher,
            day_of_week=ClassSchedule.WeekDay.SUNDAY, period_number=2,
            start_time=datetime.time(9, 0), end_time=datetime.time(9, 45),
        )
        sched_p3 = ClassSchedule.objects.create(
            school=self.school_a, academic_year=self.year_a, academic_term=self.term_a,
            section=self.section_a, subject=self.subject_a, teacher=teacher,
            day_of_week=ClassSchedule.WeekDay.SUNDAY, period_number=3,
            start_time=datetime.time(11, 30), end_time=datetime.time(12, 15),
        )

        # Student 1 has an approved early departure at 11:00 AM
        dep_req = create_early_departure_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            date=sunday_date,
            departure_time=datetime.time(11, 0),
            reason="موعد خارجي",
            recipient_name="عبدالله اليماني",
            recipient_phone="+967771234567",
            recipient_relationship="العم",
        )
        approve_early_departure(dep_req, approved_by=self.owner_a)

        # Open daily register for Sunday
        reg, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=sunday_date,
            session_type=AttendanceRegister.SessionType.DAILY_MORNING,
            bypass_calendar_check=True,
            user=self.teacher_user,
        )

        # Student 1 is Present daily, Student 2 is Absent Unexcused
        bulk_record_attendance(reg, [
            {"student_id": self.student_1.id, "status_category": AttendanceStatusType.Category.PRESENT},
            {"student_id": self.student_2.id, "status_category": AttendanceStatusType.Category.ABSENT_UNEXCUSED},
        ], recorded_by=self.teacher_user)

        # Submit then approve through the formal lifecycle.
        submit_register(reg, submitted_by=self.teacher_user)
        approve_register(reg, approved_by=self.owner_a)

        # Check Student 1 period attendances:
        # P1 (08:00) -> Present
        p1_st1 = PeriodAttendance.objects.get(school=self.school_a, schedule=sched_p1, student=self.student_1, date=sunday_date)
        self.assertEqual(p1_st1.status, PeriodAttendance.Status.PRESENT)
        # P2 (09:00) -> Present
        p2_st1 = PeriodAttendance.objects.get(school=self.school_a, schedule=sched_p2, student=self.student_1, date=sunday_date)
        self.assertEqual(p2_st1.status, PeriodAttendance.Status.PRESENT)
        # P3 (11:30 - after 11:00 departure) -> Early Departure!
        p3_st1 = PeriodAttendance.objects.get(school=self.school_a, schedule=sched_p3, student=self.student_1, date=sunday_date)
        self.assertEqual(p3_st1.status, PeriodAttendance.Status.EARLY_DEPARTURE)

        # Check Student 2 period attendances:
        # All periods should be Absent
        p1_st2 = PeriodAttendance.objects.get(school=self.school_a, schedule=sched_p1, student=self.student_2, date=sunday_date)
        self.assertEqual(p1_st2.status, PeriodAttendance.Status.ABSENT)
        p3_st2 = PeriodAttendance.objects.get(school=self.school_a, schedule=sched_p3, student=self.student_2, date=sunday_date)
        self.assertEqual(p3_st2.status, PeriodAttendance.Status.ABSENT)



    def test_register_approval_requires_submission(self):
        reg, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=datetime.date(2026, 9, 25),
            bypass_calendar_check=True,
            user=self.teacher_user,
        )
        with self.assertRaises(ValidationError):
            approve_register(reg, approved_by=self.owner_a)
        submit_register(reg, submitted_by=self.teacher_user)
        approve_register(reg, approved_by=self.owner_a)
        reg.refresh_from_db()
        self.assertEqual(reg.status, AttendanceRegister.Status.APPROVED)

    def test_bulk_record_rejects_student_outside_register(self):
        reg, _ = get_or_create_register(
            school=self.school_a,
            academic_year=self.year_a,
            section=self.section_a,
            date=datetime.date(2026, 9, 26),
            bypass_calendar_check=True,
            user=self.teacher_user,
        )
        with self.assertRaises(ValidationError):
            bulk_record_attendance(
                reg,
                [{"student_id": "00000000-0000-0000-0000-000000000999",
                  "status_category": AttendanceStatusType.Category.PRESENT}],
                recorded_by=self.teacher_user,
            )

    def test_repeated_early_departure_approval_is_rejected(self):
        request = create_early_departure_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            date=datetime.date(2026, 9, 27),
            departure_time=datetime.time(11, 0),
            reason="موعد طبي",
            recipient_name="الأب",
            recipient_phone="+967771234567",
            recipient_relationship="الأب",
        )
        approve_early_departure(request, approved_by=self.owner_a)
        with self.assertRaises(ValidationError):
            approve_early_departure(request, approved_by=self.owner_a)

    def test_repeated_excuse_review_is_rejected(self):
        request = create_excuse_request(
            school=self.school_a,
            student=self.student_1,
            guardian=self.guardian,
            request_type=AttendanceExcuseRequest.RequestType.POST_ABSENCE_EXCUSE,
            start_date=datetime.date(2026, 9, 28),
            end_date=datetime.date(2026, 9, 28),
            reason="عذر صحي",
        )
        review_excuse_request(request, reviewed_by=self.owner_a, is_approved=False)
        with self.assertRaises(ValidationError):
            review_excuse_request(request, reviewed_by=self.owner_a, is_approved=True)
