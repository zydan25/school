"""Attendance rates, section statistics, and chronic absence alert selectors."""
from __future__ import annotations

from typing import Any, Dict, List
from django.db.models import Count, Q
from django.utils import timezone

from apps.students.models import Student
from apps.academics.models import Section
from apps.attendance.models import DailyAttendance


def get_section_attendance_summary(section: Section, start_date=None, end_date=None) -> Dict[str, Any]:
    """ملخص نسب الحضور والغياب والتأخير لشعبة دراسية خلال فترة زمنية."""
    query = DailyAttendance.objects.filter(
        student__current_section=section,
        is_archived=False,
    )
    if start_date:
        query = query.filter(date__gte=start_date)
    if end_date:
        query = query.filter(date__lte=end_date)

    total_records = query.count()
    if total_records == 0:
        return {
            "section": {"id": str(section.id), "name": section.name},
            "total_records": 0,
            "rates": {"present": 0.0, "absent": 0.0, "late": 0.0, "excused": 0.0},
        }

    counts = query.aggregate(
        present=Count("id", filter=Q(status=DailyAttendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=DailyAttendance.Status.ABSENT)),
        late=Count("id", filter=Q(status=DailyAttendance.Status.LATE)),
        excused=Count("id", filter=Q(status=DailyAttendance.Status.EXCUSED)),
    )

    present_pct = round((counts["present"] / total_records) * 100, 2)
    absent_pct = round((counts["absent"] / total_records) * 100, 2)
    late_pct = round((counts["late"] / total_records) * 100, 2)
    excused_pct = round((counts["excused"] / total_records) * 100, 2)

    return {
        "section": {
            "id": str(section.id),
            "name": section.name,
            "grade_level": section.grade_level.name if section.grade_level else None,
        },
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "total_days_recorded": total_records,
        "counts": counts,
        "percentages": {
            "present_rate": present_pct,
            "absent_rate": absent_pct,
            "late_rate": late_pct,
            "excused_rate": excused_pct,
        },
    }


def get_chronic_absenteeism_report(school, threshold: int = 5) -> Dict[str, Any]:
    """تقرير الطلاب المتغيبين غياباً متكرراً يعرضهم للإنذار أو الحرمان الأكاديمي."""
    students = Student.objects.filter(
        school=school,
        enrollment_status=Student.EnrollmentStatus.ACTIVE,
        is_archived=False,
    ).annotate(
        unexcused_absences=Count("attendance_records", filter=Q(attendance_records__status=DailyAttendance.Status.ABSENT, attendance_records__is_archived=False)),
        total_lates=Count("attendance_records", filter=Q(attendance_records__status=DailyAttendance.Status.LATE, attendance_records__is_archived=False)),
    ).filter(unexcused_absences__gte=threshold).order_by("-unexcused_absences")

    alerted_students = []
    for st in students:
        alerted_students.append({
            "student_id": str(st.id),
            "student_name": f"{st.first_name} {st.last_name}",
            "student_number": st.student_number,
            "section": st.current_section.name if st.current_section else None,
            "unexcused_absences": st.unexcused_absences,
            "total_lates": st.total_lates,
            "risk_level": "مرتفع جداً (حرمان)" if st.unexcused_absences >= 15 else ("مرتفع (إنذار نهائي)" if st.unexcused_absences >= 10 else "متوسط (إنذار أول)"),
        })

    return {
        "threshold": threshold,
        "alerted_count": len(alerted_students),
        "students": alerted_students,
    }
