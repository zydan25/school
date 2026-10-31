"""Attendance rates, section statistics, and chronic absence alert selectors."""
from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from apps.academics.models import Section
from apps.attendance.models import DailyAttendance
from apps.students.models import Student


def get_section_attendance_summary(section: Section, start_date=None, end_date=None) -> dict[str, Any]:
    """ملخص نسب الحضور والغياب والتأخير لشعبة دراسية خلال فترة زمنية."""
    query = DailyAttendance.objects.filter(
        student__section=section,
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
        absent_unexcused=Count("id", filter=Q(status=DailyAttendance.Status.ABSENT_UNEXCUSED)),
        absent_excused=Count("id", filter=Q(status=DailyAttendance.Status.ABSENT_EXCUSED)),
        late=Count("id", filter=Q(status=DailyAttendance.Status.LATE)),
    )

    present_pct = round((counts["present"] / total_records) * 100, 2)
    absent_pct = round((counts["absent_unexcused"] / total_records) * 100, 2)
    late_pct = round((counts["late"] / total_records) * 100, 2)
    excused_pct = round((counts["absent_excused"] / total_records) * 100, 2)

    return {
        "section": {
            "id": str(section.id),
            "name": section.name,
            "grade_level": section.grade.name if section.grade else None,
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


def get_chronic_absenteeism_report(school, threshold: int = 5) -> dict[str, Any]:
    """تقرير الطلاب المتغيبين غياباً متكرراً يعرضهم للإنذار أو الحرمان الأكاديمي."""
    students = Student.objects.filter(
        school=school,
        status=Student.Status.ACTIVE,
        is_archived=False,
    ).annotate(
        unexcused_absences=Count("daily_attendances", filter=Q(daily_attendances__status=DailyAttendance.Status.ABSENT_UNEXCUSED, daily_attendances__is_archived=False)),
        total_lates=Count("daily_attendances", filter=Q(daily_attendances__status=DailyAttendance.Status.LATE, daily_attendances__is_archived=False)),
    ).filter(unexcused_absences__gte=threshold).order_by("-unexcused_absences")

    alerted_students = []
    for st in students:
        alerted_students.append({
            "student_id": str(st.id),
            "student_name": f"{st.first_name} {st.last_name}",
            "student_id_number": st.student_id_number,
            "section": st.section.name if st.section else None,
            "unexcused_absences": st.unexcused_absences,
            "total_lates": st.total_lates,
            "risk_level": "مرتفع جداً (حرمان)" if st.unexcused_absences >= 15 else ("مرتفع (إنذار نهائي)" if st.unexcused_absences >= 10 else "متوسط (إنذار أول)"),
        })

    return {
        "threshold": threshold,
        "alerted_count": len(alerted_students),
        "students": alerted_students,
    }
