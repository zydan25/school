"""
apps/timetable/services/ai_generator.py
محرك الذكاء الاصطناعي والتوليد التلقائي للجدول المدرسي.
يوزع الحصص الأسبوعية تلقائياً لكل مدرسة وفرع مع منع التعارض التام (للمعلمين، الشعب، والقاعات).
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from django.db import transaction

from apps.academics.models import AcademicYear, Classroom, Section
from apps.staff.models import TeacherAssignment
from apps.timetable.models import ClassSchedule


DEFAULT_PERIOD_TIMES = [
    (1, datetime.time(8, 0), datetime.time(8, 45)),
    (2, datetime.time(8, 50), datetime.time(9, 35)),
    (3, datetime.time(9, 40), datetime.time(10, 25)),
    (4, datetime.time(10, 45), datetime.time(11, 30)),
    (5, datetime.time(11, 35), datetime.time(12, 20)),
    (6, datetime.time(12, 25), datetime.time(13, 10)),
    (7, datetime.time(13, 15), datetime.time(14, 0)),
]

WORKING_DAYS = [
    ClassSchedule.WeekDay.SUNDAY,
    ClassSchedule.WeekDay.MONDAY,
    ClassSchedule.WeekDay.TUESDAY,
    ClassSchedule.WeekDay.WEDNESDAY,
    ClassSchedule.WeekDay.THURSDAY,
]


def generate_school_timetable(
    school,
    academic_year: AcademicYear,
    branch=None,
    dry_run: bool = True,
    clear_existing: bool = False,
) -> Dict[str, Any]:
    """
    توليد جدول الحصص الأسبوعي الذكي لكافة شعب المدرسة مع حل القيود برمجياً.
    """
    sections_qs = Section.objects.filter(
        school=school,
        academic_year=academic_year,
        is_active=True,
        is_archived=False,
    ).select_related("grade", "homeroom_classroom")

    if branch:
        sections_qs = sections_qs.filter(branch=branch)

    classrooms = list(Classroom.objects.filter(school=school, is_active=True, is_archived=False))

    # Tracking sets to enforce 0-conflict constraints: (teacher_id, day, period), (section_id, day, period), (classroom_id, day, period)
    teacher_busy = set()
    section_busy = set()
    classroom_busy = set()

    if not clear_existing:
        existing_schedules = ClassSchedule.objects.filter(
            school=school,
            academic_year=academic_year,
            is_archived=False,
        )
        for s in existing_schedules:
            teacher_busy.add((s.teacher_id, s.day_of_week, s.period_number))
            section_busy.add((s.section_id, s.day_of_week, s.period_number))
            if s.classroom_id:
                classroom_busy.add((s.classroom_id, s.day_of_week, s.period_number))

    generated_lessons = []
    unplaced_assignments = []

    for section in sections_qs:
        assignments = list(TeacherAssignment.objects.filter(
            school=school,
            academic_year=academic_year,
            section=section,
            is_archived=False,
        ).select_related("teacher", "subject"))

        classroom = section.homeroom_classroom or (classrooms[0] if classrooms else None)

        # Distribute lessons for each assignment according to its weekly_periods quota
        for assign in assignments:
            needed_periods = assign.weekly_periods
            placed_for_assign = 0

            # Try to place lessons spread across the 5 days
            for day in WORKING_DAYS:
                if placed_for_assign >= needed_periods:
                    break
                for period_num, start_t, end_t in DEFAULT_PERIOD_TIMES:
                    if placed_for_assign >= needed_periods:
                        break

                    # Check all conflict constraints
                    teacher_clash = (assign.teacher_id, day, period_num) in teacher_busy
                    section_clash = (section.id, day, period_num) in section_busy
                    room_clash = classroom and ((classroom.id, day, period_num) in classroom_busy)

                    if not (teacher_clash or section_clash or room_clash):
                        # Safe slot found!
                        teacher_busy.add((assign.teacher_id, day, period_num))
                        section_busy.add((section.id, day, period_num))
                        if classroom:
                            classroom_busy.add((classroom.id, day, period_num))

                        generated_lessons.append({
                            "school": school,
                            "academic_year": academic_year,
                            "branch": branch or section.branch,
                            "section": section,
                            "subject": assign.subject,
                            "teacher": assign.teacher,
                            "classroom": classroom,
                            "day_of_week": day,
                            "period_number": period_num,
                            "start_time": start_t,
                            "end_time": end_t,
                        })
                        placed_for_assign += 1

            if placed_for_assign < needed_periods:
                unplaced_assignments.append({
                    "section": str(section),
                    "subject": assign.subject.name,
                    "teacher": str(assign.teacher),
                    "missing_periods": needed_periods - placed_for_assign,
                })

    # If committing to database
    saved_count = 0
    if not dry_run and generated_lessons:
        with transaction.atomic():
            if clear_existing:
                ClassSchedule.objects.filter(
                    school=school,
                    academic_year=academic_year,
                ).delete()

            objects_to_create = [
                ClassSchedule(
                    school=l["school"],
                    academic_year=l["academic_year"],
                    branch=l["branch"],
                    section=l["section"],
                    subject=l["subject"],
                    teacher=l["teacher"],
                    classroom=l["classroom"],
                    day_of_week=l["day_of_week"],
                    period_number=l["period_number"],
                    start_time=l["start_time"],
                    end_time=l["end_time"],
                )
                for l in generated_lessons
            ]
            ClassSchedule.objects.bulk_create(objects_to_create)
            saved_count = len(objects_to_create)

    return {
        "status": "success",
        "dry_run": dry_run,
        "school": school.name,
        "sections_processed": sections_qs.count(),
        "generated_lessons_count": len(generated_lessons),
        "committed_to_db": saved_count,
        "unplaced_count": len(unplaced_assignments),
        "unplaced_details": unplaced_assignments,
        "conflict_rate": "0% (No Clashes)",
    }
