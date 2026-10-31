"""
Service for generating, customizing, and validating school bell schedules and periods.
Allows centralized default generation as well as per-school custom configurations.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics.models import AcademicYear
from apps.tenants.models import School
from apps.timetable.models import ClassSchedule, SchedulePeriodTemplate, SchoolBellSchedule


def _add_minutes_to_time(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 1, t.hour, t.minute, t.second) + timedelta(minutes=minutes)
    return dt.time()


@transaction.atomic
def create_default_school_bell_schedule(
    school: School,
    academic_year: AcademicYear,
    name: str = "الجدول الصباحي القياسي",
    has_morning_assembly: bool = True,
    assembly_start: time = time(7, 15),
    assembly_duration_minutes: int = 15,
    periods_count: int = 7,
    period_duration_minutes: int = 45,
    passing_duration_minutes: int = 5,
    first_break_after: int = 3,
    first_break_duration_minutes: int = 25,
    has_second_break: bool = True,
    second_break_after: int = 5,
    second_break_duration_minutes: int = 20,
    set_as_default: bool = True,
) -> SchoolBellSchedule:
    """
    إنشاء قالب مواعيد اليوم الدراسي الافتراضي للمدرسة وتوليد كافة فترات الحصص والفسح والطابور تلقائياً
    بدون أي تداخل زمني، مع إمكانية تعديل كل مدرسة لأوقاتها وحصصها لاحقاً بكل مرونة.
    """
    if academic_year.school_id != school.pk:
        raise ValidationError("السنة الدراسية لا تتبع نفس المدرسة.")

    assembly_end = _add_minutes_to_time(assembly_start, assembly_duration_minutes) if has_morning_assembly else assembly_start

    # احسب التوقيت النهائي المتوقع لليوم الدراسي
    curr_time = assembly_end
    for p in range(1, periods_count + 1):
        curr_time = _add_minutes_to_time(curr_time, period_duration_minutes)
        if p == first_break_after:
            curr_time = _add_minutes_to_time(curr_time, first_break_duration_minutes)
        elif has_second_break and p == second_break_after:
            curr_time = _add_minutes_to_time(curr_time, second_break_duration_minutes)
        elif p < periods_count:
            curr_time = _add_minutes_to_time(curr_time, passing_duration_minutes)

    day_end = curr_time

    bell_sched, _ = SchoolBellSchedule.objects.update_or_create(
        school=school,
        academic_year=academic_year,
        name=name,
        is_archived=False,
        defaults={
            "is_active": True,
            "is_default": set_as_default,
            "has_morning_assembly": has_morning_assembly,
            "assembly_start_time": assembly_start,
            "assembly_end_time": assembly_end,
            "day_start_time": assembly_start if has_morning_assembly else _add_minutes_to_time(assembly_start, 0),
            "day_end_time": day_end,
            "periods_per_day": periods_count,
            "period_duration_minutes": period_duration_minutes,
            "passing_duration_minutes": passing_duration_minutes,
            "break_duration_minutes": first_break_duration_minutes,
            "break_after_period": first_break_after,
            "has_second_break": has_second_break,
            "second_break_after_period": second_break_after,
            "second_break_duration_minutes": second_break_duration_minutes,
            "notes": "تم إنشاء القالب وتوليد فترات الحصص والفسح تلقائياً بنظام منع التداخل الذكي.",
        },
    )

    # حذف أي فترات قديمة غير مرتبطة وإعادة بنائها
    bell_sched.period_templates.all().delete()

    order = 1
    cursor_time = assembly_start

    # 1. إضافة الطابور الصباحي
    if has_morning_assembly:
        SchedulePeriodTemplate.objects.create(
            school=school,
            schedule=bell_sched,
            period_type=SchedulePeriodTemplate.PeriodType.ASSEMBLY,
            period_number=None,
            name="الطابور الصباحي والإذاعة المدرسية",
            start_time=cursor_time,
            end_time=assembly_end,
            order=order,
            is_active=True,
        )
        order += 1
        cursor_time = assembly_end

    # 2. بناء فترات الحصص والفسح
    for p_num in range(1, periods_count + 1):
        p_start = cursor_time
        p_end = _add_minutes_to_time(p_start, period_duration_minutes)

        SchedulePeriodTemplate.objects.create(
            school=school,
            schedule=bell_sched,
            period_type=SchedulePeriodTemplate.PeriodType.PERIOD,
            period_number=p_num,
            name=f"الحصة {p_num}",
            start_time=p_start,
            end_time=p_end,
            order=order,
            is_active=True,
        )
        order += 1
        cursor_time = p_end

        # الفسحة الأولى
        if p_num == first_break_after:
            b_start = cursor_time
            b_end = _add_minutes_to_time(b_start, first_break_duration_minutes)
            SchedulePeriodTemplate.objects.create(
                school=school,
                schedule=bell_sched,
                period_type=SchedulePeriodTemplate.PeriodType.BREAK,
                period_number=None,
                name="الفسحة الأولى (استراحة ووجبة خفيفة)",
                start_time=b_start,
                end_time=b_end,
                order=order,
                is_active=True,
            )
            order += 1
            cursor_time = b_end

        # الفسحة الثانية / استراحة الصلاة
        elif has_second_break and p_num == second_break_after:
            s_start = cursor_time
            s_end = _add_minutes_to_time(s_start, second_break_duration_minutes)
            SchedulePeriodTemplate.objects.create(
                school=school,
                schedule=bell_sched,
                period_type=SchedulePeriodTemplate.PeriodType.PRAYER_BREAK,
                period_number=None,
                name="استراحة صلاة الظهر والفسحة الثانية",
                start_time=s_start,
                end_time=s_end,
                order=order,
                is_active=True,
            )
            order += 1
            cursor_time = s_end

        # وقت انتقال عادي بين الحصص
        elif p_num < periods_count and passing_duration_minutes > 0:
            cursor_time = _add_minutes_to_time(cursor_time, passing_duration_minutes)

    return bell_sched
