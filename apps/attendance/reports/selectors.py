"""Attendance reporting data selectors and aggregations."""
from __future__ import annotations

import calendar
import datetime
from decimal import Decimal
from django.db.models import Count, Q

from apps.attendance.models import (
    AttendanceRegister,
    AttendanceStatusType,
    SchoolCalendarDay,
    StudentAttendanceRecord,
)
from apps.students.models import Student


def get_daily_section_summary(school, date: datetime.date, section_id: int | None = None) -> list[dict]:
    """تقرير الموقف اليومي للحضور والغياب على مستوى الشعب والمدرسة بالكامل."""
    registers = AttendanceRegister.objects.filter(
        school=school,
        date=date,
        is_archived=False,
    ).select_related("section", "section__grade")

    if section_id:
        registers = registers.filter(section_id=section_id)

    summaries = []
    for reg in registers:
        records = reg.student_records.filter(is_archived=False)
        total_students = records.count()
        present_count = records.filter(
            status_category__in=[
                AttendanceStatusType.Category.PRESENT,
                AttendanceStatusType.Category.SCHOOL_ACTIVITY,
                AttendanceStatusType.Category.DISTANCE_LEARNING,
            ]
        ).count()
        absent_unexcused = records.filter(
            status_category=AttendanceStatusType.Category.ABSENT_UNEXCUSED
        ).count()
        absent_excused = records.filter(
            status_category=AttendanceStatusType.Category.ABSENT_EXCUSED
        ).count()
        late_count = records.filter(
            status_category__in=[
                AttendanceStatusType.Category.LATE,
                AttendanceStatusType.Category.LATE_EXCUSED,
            ]
        ).count()
        early_departure_count = records.filter(
            status_category__in=[
                AttendanceStatusType.Category.EARLY_DEPARTURE,
                AttendanceStatusType.Category.AUTHORIZED_DEPARTURE,
            ]
        ).count()

        attendance_rate = (
            round((present_count / total_students) * 100, 2)
            if total_students > 0
            else 0.0
        )

        summaries.append({
            "register_id": reg.id,
            "section_id": reg.section_id,
            "section_name": reg.section.name,
            "grade_name": reg.section.grade.name,
            "session_type": reg.session_type,
            "status": reg.status,
            "total_students": total_students,
            "present_count": present_count,
            "absent_unexcused": absent_unexcused,
            "absent_excused": absent_excused,
            "late_count": late_count,
            "early_departure_count": early_departure_count,
            "attendance_rate": attendance_rate,
        })

    return summaries


def get_monthly_attendance_matrix(school, section_id: int, year: int, month: int) -> dict:
    """كشف الحضور الشهري التراكمي (جدول شبكي للطلاب وأيام الشهر ومعدل الحضور)."""
    _, num_days = calendar.monthrange(year, month)
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)

    students = Student.objects.filter(
        school=school,
        section_id=section_id,
        status=Student.Status.ACTIVE,
        is_archived=False,
    ).order_by("first_name", "last_name")

    # Calendar day status for this month
    calendar_days = {
        cd.date: cd
        for cd in SchoolCalendarDay.objects.filter(
            school=school,
            date__range=[start_date, end_date],
            is_archived=False,
        )
    }

    # Fetch all records for section in this month
    records = StudentAttendanceRecord.objects.filter(
        school=school,
        register__section_id=section_id,
        register__date__range=[start_date, end_date],
        is_archived=False,
    ).select_related("register")

    record_lookup = {
        (rec.student_id, rec.register.date): rec.status_category
        for rec in records
    }

    days_header = []
    total_school_days = 0
    for day in range(1, num_days + 1):
        d = datetime.date(year, month, day)
        c_day = calendar_days.get(d)
        is_school = c_day.is_school_day if c_day else (d.weekday() not in (4, 5))
        if is_school:
            total_school_days += 1
        days_header.append({
            "day": day,
            "date": d.strftime("%Y-%m-%d"),
            "weekday": d.strftime("%A"),
            "is_school_day": is_school,
        })

    student_rows = []
    for st in students:
        day_statuses = {}
        present_count = 0
        absent_count = 0
        late_count = 0

        for day in range(1, num_days + 1):
            d = datetime.date(year, month, day)
            c_day = calendar_days.get(d)
            is_school = c_day.is_school_day if c_day else (d.weekday() not in (4, 5))

            if not is_school:
                status_cat = "non_school_day"
            else:
                status_cat = record_lookup.get((st.id, d), "unrecorded")
                if status_cat in ["present", "school_activity", "distance_learning", "authorized_departure"]:
                    present_count += 1
                elif "absent" in status_cat:
                    absent_count += 1
                elif "late" in status_cat:
                    late_count += 1
                    present_count += 1

            day_statuses[day] = status_cat

        attendance_rate = (
            round((present_count / total_school_days) * 100, 1)
            if total_school_days > 0
            else 0.0
        )

        student_rows.append({
            "student_id": st.id,
            "student_name": f"{st.first_name} {st.last_name}",
            "student_number": st.student_id_number,
            "day_statuses": day_statuses,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "attendance_rate": attendance_rate,
        })

    return {
        "section_id": section_id,
        "year": year,
        "month": month,
        "total_school_days": total_school_days,
        "days_header": days_header,
        "students": student_rows,
    }


def get_term_attendance_summary(school, academic_term_id: int, section_id: int | None = None) -> list[dict]:
    """ملخص الحضور التراكمي للفصل الدراسي مع إحصائيات الغياب المبرر وغير المبرر."""
    query = StudentAttendanceRecord.objects.filter(
        school=school,
        register__academic_term_id=academic_term_id,
        is_archived=False,
    )
    if section_id:
        query = query.filter(register__section_id=section_id)

    students = Student.objects.filter(
        school=school,
        status=Student.Status.ACTIVE,
        is_archived=False,
    )
    if section_id:
        students = students.filter(section_id=section_id)

    results = []
    for st in students:
        st_records = query.filter(student=st)
        total_sessions = st_records.count()
        present = st_records.filter(
            status_category__in=[
                AttendanceStatusType.Category.PRESENT,
                AttendanceStatusType.Category.SCHOOL_ACTIVITY,
                AttendanceStatusType.Category.DISTANCE_LEARNING,
            ]
        ).count()
        absent_unexcused = st_records.filter(
            status_category=AttendanceStatusType.Category.ABSENT_UNEXCUSED
        ).count()
        absent_excused = st_records.filter(
            status_category=AttendanceStatusType.Category.ABSENT_EXCUSED
        ).count()
        late = st_records.filter(
            status_category__in=[
                AttendanceStatusType.Category.LATE,
                AttendanceStatusType.Category.LATE_EXCUSED,
            ]
        ).count()

        rate = round((present / total_sessions) * 100, 1) if total_sessions > 0 else 0.0

        results.append({
            "student_id": st.id,
            "student_name": f"{st.first_name} {st.last_name}",
            "student_number": st.student_id_number,
            "section_name": st.section.name if st.section else "",
            "total_sessions": total_sessions,
            "present_count": present,
            "absent_unexcused": absent_unexcused,
            "absent_excused": absent_excused,
            "late_count": late,
            "attendance_rate": rate,
        })

    return results


def get_chronic_absenteeism_report(
    school,
    academic_year_id: int,
    threshold_percentage: float = 10.0,
) -> list[dict]:
    """كشف الإنذار المبكر للغياب المزمن (الطلاب الذين تجاوزت نسبة غيابهم الحد الحرج 10%)."""
    students = Student.objects.filter(
        school=school,
        academic_year_id=academic_year_id,
        status=Student.Status.ACTIVE,
        is_archived=False,
    ).select_related("grade_level", "section")

    chronic_cases = []
    for st in students:
        records = StudentAttendanceRecord.objects.filter(
            school=school,
            student=st,
            register__academic_year_id=academic_year_id,
            is_archived=False,
        )
        total_days = records.count()
        if total_days == 0:
            continue

        absent_days = records.filter(
            status_category__in=[
                AttendanceStatusType.Category.ABSENT_UNEXCUSED,
                AttendanceStatusType.Category.ABSENT_EXCUSED,
            ]
        ).count()

        absence_rate = round((absent_days / total_days) * 100, 1)
        if absence_rate >= threshold_percentage:
            chronic_cases.append({
                "student_id": st.id,
                "student_name": f"{st.first_name} {st.last_name}",
                "student_number": st.student_id_number,
                "grade_name": st.grade_level.name if st.grade_level else "",
                "section_name": st.section.name if st.section else "",
                "total_days": total_days,
                "absent_days": absent_days,
                "absence_rate": absence_rate,
                "is_critical": absence_rate >= 20.0,
            })

    return sorted(chronic_cases, key=lambda x: x["absence_rate"], reverse=True)
