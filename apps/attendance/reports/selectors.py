"""Attendance reporting selectors with daily/period de-duplication and branch calendars."""
from __future__ import annotations

import calendar
import datetime
from collections import defaultdict
from uuid import UUID

from apps.academics.models import AcademicTerm, AcademicYear, Section
from apps.attendance.models import AttendanceRegister, AttendanceStatusType, SchoolCalendarDay, StudentAttendanceRecord
from apps.students.models import Student, StudentEnrollment


PRESENT_CATEGORIES = {
    AttendanceStatusType.Category.PRESENT,
    AttendanceStatusType.Category.SCHOOL_ACTIVITY,
    AttendanceStatusType.Category.DISTANCE_LEARNING,
}
ATTENDED_CATEGORIES = PRESENT_CATEGORIES | {
    AttendanceStatusType.Category.LATE,
    AttendanceStatusType.Category.LATE_EXCUSED,
    AttendanceStatusType.Category.AUTHORIZED_DEPARTURE,
    AttendanceStatusType.Category.EARLY_DEPARTURE,
    AttendanceStatusType.Category.PARTIAL_ATTENDANCE,
}
ABSENT_CATEGORIES = {
    AttendanceStatusType.Category.ABSENT_UNEXCUSED,
    AttendanceStatusType.Category.ABSENT_EXCUSED,
}


def _aggregate_day_status(categories):
    """Collapse multiple periods into one day without treating partial attendance as a full absence."""
    categories = list(categories)
    if not categories:
        return None
    absent = [value for value in categories if value in ABSENT_CATEGORIES]
    attended = [value for value in categories if value in ATTENDED_CATEGORIES]
    if absent and attended:
        return AttendanceStatusType.Category.PARTIAL_ATTENDANCE
    if absent:
        return (
            AttendanceStatusType.Category.ABSENT_UNEXCUSED
            if AttendanceStatusType.Category.ABSENT_UNEXCUSED in absent
            else AttendanceStatusType.Category.ABSENT_EXCUSED
        )
    if AttendanceStatusType.Category.AUTHORIZED_DEPARTURE in categories:
        return AttendanceStatusType.Category.AUTHORIZED_DEPARTURE
    if AttendanceStatusType.Category.EARLY_DEPARTURE in categories:
        return AttendanceStatusType.Category.EARLY_DEPARTURE
    if AttendanceStatusType.Category.LATE in categories:
        return AttendanceStatusType.Category.LATE
    if AttendanceStatusType.Category.LATE_EXCUSED in categories:
        return AttendanceStatusType.Category.LATE_EXCUSED
    if attended:
        return AttendanceStatusType.Category.PRESENT
    return categories[0]


def _select_daily_precedence(daily_categories, period_categories):
    """Use daily source when it exists; otherwise collapse per-period source for a day."""
    return _aggregate_day_status(daily_categories) if daily_categories else _aggregate_day_status(period_categories)


def _calendar_days(school, start_date, end_date, *, academic_year=None, branch=None):
    qs = SchoolCalendarDay.objects.filter(
        school=school, date__range=(start_date, end_date), is_archived=False,
        calendar__is_archived=False, calendar__is_active=True,
    )
    if academic_year is not None:
        qs = qs.filter(calendar__academic_year=academic_year)
    result = {}
    for day in qs.select_related("calendar").order_by("calendar__branch_id", "calendar__version"):
        current = result.get(day.date)
        is_branch_override = branch is not None and day.calendar.branch_id == branch.pk
        current_is_branch = current is not None and branch is not None and current.calendar.branch_id == branch.pk
        if current is None or (is_branch_override and not current_is_branch):
            if day.calendar.branch_id is None or is_branch_override:
                result[day.date] = day
    return result


def _attendance_records_by_student_date(school, start_date, end_date, *, academic_year=None, section_id=None):
    qs = StudentAttendanceRecord.objects.filter(
        school=school, register__date__range=(start_date, end_date), is_archived=False,
        register__is_archived=False,
    ).select_related("register", "student")
    if academic_year is not None:
        qs = qs.filter(register__academic_year=academic_year)
    if section_id is not None:
        qs = qs.filter(register__section_id=section_id)
    groups = defaultdict(lambda: {"daily": [], "periods": []})
    for record in qs.order_by("register__date", "register__schedule_id", "created_at"):
        key = (record.student_id, record.register.date)
        target = "periods" if record.register.schedule_id else "daily"
        groups[key][target].append(record)
    return groups


def _resolve_day_status(group):
    if group is None:
        return None
    return _select_daily_precedence(
        [record.status_category for record in group["daily"]],
        [record.status_category for record in group["periods"]],
    )


def _section_students(school, section):
    return Student.objects.filter(
        school=school, section=section, status=Student.Status.ACTIVE, is_archived=False,
    ).order_by("first_name", "last_name")


def _is_school_day(day, current_date):
    if day is not None:
        return day.is_school_day
    return current_date.weekday() not in (4, 5)


def _attendance_counts(categories):
    values = list(categories)
    total = len(values)
    present = sum(value in PRESENT_CATEGORIES for value in values)
    absent_unexcused = sum(value == AttendanceStatusType.Category.ABSENT_UNEXCUSED for value in values)
    absent_excused = sum(value == AttendanceStatusType.Category.ABSENT_EXCUSED for value in values)
    late = sum(value in {AttendanceStatusType.Category.LATE, AttendanceStatusType.Category.LATE_EXCUSED} for value in values)
    early = sum(value in {AttendanceStatusType.Category.EARLY_DEPARTURE, AttendanceStatusType.Category.AUTHORIZED_DEPARTURE} for value in values)
    attended = sum(value in ATTENDED_CATEGORIES for value in values)
    return {
        "total_students": total, "present_count": present,
        "absent_unexcused": absent_unexcused, "absent_excused": absent_excused,
        "late_count": late, "early_departure_count": early, "attended_count": attended,
        "attendance_rate": round(attended / total * 100, 2) if total else 0.0,
    }


def get_daily_section_summary(school, date: datetime.date, section_id: UUID | None = None) -> list[dict]:
    """One daily summary per section; period-only schools are folded to one status per student/day."""
    registers = AttendanceRegister.objects.filter(
        school=school, date=date, is_archived=False,
    ).select_related("section", "section__grade").order_by("section__name", "schedule_id")
    if section_id is not None:
        registers = registers.filter(section_id=section_id)
    by_section = defaultdict(list)
    for register in registers:
        by_section[register.section_id].append(register)
    summaries = []
    for section_pk, section_registers in by_section.items():
        section = section_registers[0].section
        daily_registers = [item for item in section_registers if item.schedule_id is None]
        selected_registers = daily_registers or section_registers
        records = StudentAttendanceRecord.objects.filter(
            school=school, register__in=selected_registers, is_archived=False,
        ).select_related("student", "register")
        per_student = defaultdict(list)
        for record in records:
            per_student[record.student_id].append(record.status_category)
        statuses = [_aggregate_day_status(per_student[student_id]) for student_id in per_student]
        statuses = [value for value in statuses if value is not None]
        counts = _attendance_counts(statuses)
        summaries.append({
            "register_id": str(selected_registers[0].pk) if len(selected_registers) == 1 else None,
            "register_ids": [str(item.pk) for item in selected_registers],
            "section_id": str(section.pk), "section_name": section.name,
            "grade_name": section.grade.name,
            "session_type": selected_registers[0].session_type if daily_registers else "period_aggregate",
            "status": selected_registers[0].status if len(selected_registers) == 1 else None,
            **counts,
        })
    return summaries


def get_monthly_attendance_matrix(school, section_id: UUID, year: int, month: int) -> dict:
    """Monthly day matrix; daily records override periods and UUID section identifiers are preserved."""
    section = Section.objects.select_related("academic_year", "branch", "grade").filter(
        pk=section_id, school=school, is_archived=False,
    ).first()
    if section is None:
        raise ValueError("الشعبة غير موجودة في المدرسة المحددة.")
    if month < 1 or month > 12:
        raise ValueError("الشهر يجب أن يكون بين 1 و12.")
    _, day_count = calendar.monthrange(year, month)
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, day_count)
    days = _calendar_days(school, start_date, end_date, academic_year=section.academic_year, branch=section.branch)
    records = _attendance_records_by_student_date(
        school, start_date, end_date, academic_year=section.academic_year, section_id=section.pk,
    )
    students = _section_students(school, section)
    total_school_days = 0
    days_header = []
    for day_number in range(1, day_count + 1):
        current_date = datetime.date(year, month, day_number)
        within_year = section.academic_year.starts_on <= current_date <= section.academic_year.ends_on
        is_school = within_year and _is_school_day(days.get(current_date), current_date)
        total_school_days += int(is_school)
        days_header.append({
            "day": day_number, "date": current_date.isoformat(),
            "weekday": current_date.strftime("%A"), "is_school_day": is_school,
        })
    student_rows = []
    for student in students:
        day_statuses = {}
        present_count = absent_count = late_count = 0
        for day_number in range(1, day_count + 1):
            current_date = datetime.date(year, month, day_number)
            within_year = section.academic_year.starts_on <= current_date <= section.academic_year.ends_on
            is_school = within_year and _is_school_day(days.get(current_date), current_date)
            if not is_school:
                category = AttendanceStatusType.Category.NON_SCHOOL_DAY
            else:
                category = _resolve_day_status(records.get((student.pk, current_date))) or "unrecorded"
                if category in ATTENDED_CATEGORIES:
                    present_count += 1
                elif category in ABSENT_CATEGORIES:
                    absent_count += 1
                if category in {AttendanceStatusType.Category.LATE, AttendanceStatusType.Category.LATE_EXCUSED}:
                    late_count += 1
            day_statuses[day_number] = category
        attendance_rate = round(present_count / total_school_days * 100, 1) if total_school_days else 0.0
        student_rows.append({
            "student_id": str(student.pk),
            "student_name": f"{student.first_name} {student.last_name}",
            "student_number": student.student_id_number, "day_statuses": day_statuses,
            "present_count": present_count, "absent_count": absent_count,
            "late_count": late_count, "attendance_rate": attendance_rate,
        })
    return {
        "section_id": str(section.pk), "year": year, "month": month,
        "total_school_days": total_school_days, "days_header": days_header, "students": student_rows,
    }


def get_term_attendance_summary(school, academic_term_id: UUID, section_id: UUID | None = None) -> list[dict]:
    """Term summary counts one daily session per date, or period sessions where no daily record exists."""
    term = AcademicTerm.objects.select_related("academic_year").filter(pk=academic_term_id, school=school, is_archived=False).first()
    if term is None:
        raise ValueError("الفصل الدراسي غير موجود في المدرسة المحددة.")
    if section_id is not None and not Section.objects.filter(pk=section_id, school=school, academic_year=term.academic_year, is_archived=False).exists():
        raise ValueError("الشعبة لا تتبع السنة والمدرسة للفصل المحدد.")
    enrollments = StudentEnrollment.objects.filter(
        school=school, academic_year=term.academic_year, is_archived=False,
    ).select_related("student", "student__branch", "section", "section__branch").order_by("student__first_name", "student__last_name")
    if section_id is not None:
        enrollments = enrollments.filter(section_id=section_id)
    if not enrollments.exists():
        fallback_students = Student.objects.filter(school=school, academic_year=term.academic_year, is_archived=False).select_related("branch", "section", "section__branch")
        if section_id is not None:
            fallback_students = fallback_students.filter(section_id=section_id)
        enrol_rows = [(student, student.section) for student in fallback_students.select_related("section")]
    else:
        enrol_rows = [(item.student, item.section) for item in enrollments]
    records = StudentAttendanceRecord.objects.filter(
        school=school, register__academic_term=term,
        register__date__range=(term.starts_on, term.ends_on), is_archived=False, register__is_archived=False,
    ).select_related("register")
    if section_id is not None:
        records = records.filter(register__section_id=section_id)
    by_student = defaultdict(lambda: defaultdict(lambda: {"daily": [], "periods": []}))
    for rec in records.order_by("register__date", "register__schedule_id"):
        target = "periods" if rec.register.schedule_id else "daily"
        by_student[rec.student_id][rec.register.date][target].append(rec.status_category)
    results = []
    for student, enrolled_section in enrol_rows:
        measures = []
        period_sessions = 0
        for day, group in by_student.get(student.pk, {}).items():
            if group["daily"]:
                measures.append(_aggregate_day_status(group["daily"]))
            else:
                measures.extend(group["periods"])
                period_sessions += len(group["periods"])
        counts = _attendance_counts(measures)
        total_sessions = counts["total_students"]
        results.append({
            "student_id": str(student.pk), "student_name": f"{student.first_name} {student.last_name}",
            "student_number": student.student_id_number,
            "section_name": enrolled_section.name if enrolled_section else "",
            "total_sessions": total_sessions, "total_days": len(by_student.get(student.pk, {})),
            "period_sessions": period_sessions,
            "present_count": counts["attended_count"],
            "absent_unexcused": counts["absent_unexcused"],
            "absent_excused": counts["absent_excused"], "late_count": counts["late_count"],
            "attendance_rate": round(counts["attended_count"] / total_sessions * 100, 1) if total_sessions else 0.0,
        })
    return results


def get_chronic_absenteeism_report(school, academic_year_id: UUID, threshold_percentage: float = 10.0) -> list[dict]:
    """Chronic absenteeism is calculated per unique school day, never per duplicated daily+period row."""
    academic_year = AcademicYear.objects.filter(pk=academic_year_id, school=school, is_archived=False).first()
    if academic_year is None:
        raise ValueError("السنة الدراسية غير موجودة في المدرسة المحددة.")
    enrollments = StudentEnrollment.objects.filter(
        school=school, academic_year=academic_year, is_archived=False,
    ).select_related("student", "student__branch", "section", "section__branch", "student__grade_level").order_by("student__first_name", "student__last_name")
    if not enrollments.exists():
        fallback = Student.objects.filter(school=school, academic_year=academic_year, status=Student.Status.ACTIVE, is_archived=False).select_related("grade_level", "section", "branch", "section__branch")
        enrol_rows = [(student, student.section) for student in fallback]
    else:
        enrol_rows = [(item.student, item.section) for item in enrollments]
    records = _attendance_records_by_student_date(
        school, academic_year.starts_on, academic_year.ends_on, academic_year=academic_year,
    )
    chronic = []
    for student, enrollment_section in enrol_rows:
        student_branch = student.branch or (enrollment_section.branch if enrollment_section else None)
        calendar_days = _calendar_days(
            school, academic_year.starts_on, academic_year.ends_on,
            academic_year=academic_year, branch=student_branch,
        )
        school_days = 0
        absent_days = 0
        categories = []
        for (student_id, day), group in records.items():
            if student_id != student.pk:
                continue
            if not _is_school_day(calendar_days.get(day), day):
                continue
            category = _resolve_day_status(group)
            if category is None:
                continue
            school_days += 1
            categories.append(category)
            if category in ABSENT_CATEGORIES:
                absent_days += 1
        # Include only days that were actually represented by attendance records to avoid classifying unrecorded days as absences.
        if not school_days:
            continue
        rate = round(absent_days / school_days * 100, 1)
        if rate >= threshold_percentage:
            chronic.append({
                "student_id": student.pk,
                "student_name": f"{student.first_name} {student.last_name}",
                "student_number": student.student_id_number,
                "grade_name": student.grade_level.name if student.grade_level else "",
                "section_name": enrollment_section.name if enrollment_section else "",
                "total_days": school_days, "absent_days": absent_days,
                "absence_rate": rate, "is_critical": rate >= 20.0,
            })
    return sorted(chronic, key=lambda item: item["absence_rate"], reverse=True)