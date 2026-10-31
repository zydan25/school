"""School Calendar, Day Classifications, and Recurring Events Service."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.attendance.models import (
    CalendarEvent,
    CalendarOccurrence,
    SchoolCalendar,
    SchoolCalendarDay,
)


def seed_default_calendar(
    school,
    academic_year,
    name: str = "التقويم الدراسي المعتمد",
    weekend_days: list[int] | None = None,
) -> SchoolCalendar:
    """ينشئ أو يحدث التقويم الدراسي للمدرسة مع تصنيف كافة الأيام وعطل نهاية الأسبوع."""
    if weekend_days is None:
        # Default weekend in Arab region: Friday (4) and Saturday (5)
        weekend_days = [4, 5]

    calendar, _ = SchoolCalendar.objects.get_or_create(
        school=school,
        academic_year=academic_year,
        name=name,
        defaults={"is_active": True},
    )

    current_date = academic_year.starts_on
    end_date = academic_year.ends_on

    days_to_create = []
    existing_dates = set(
        SchoolCalendarDay.objects.filter(calendar=calendar).values_list("date", flat=True)
    )

    while current_date <= end_date:
        if current_date not in existing_dates:
            is_weekend = current_date.weekday() in weekend_days
            days_to_create.append(
                SchoolCalendarDay(
                    school=school,
                    calendar=calendar,
                    date=current_date,
                    day_type=SchoolCalendarDay.DayType.WEEKEND if is_weekend else SchoolCalendarDay.DayType.REGULAR,
                    title="عطلة نهاية الأسبوع" if is_weekend else "يوم دراسي",
                    is_school_day=not is_weekend,
                )
            )
        current_date += datetime.timedelta(days=1)

    if days_to_create:
        SchoolCalendarDay.objects.bulk_create(days_to_create, batch_size=500)

    return calendar


def is_school_day(school, date: datetime.date, academic_year=None) -> bool:
    """التحقق مما إذا كان التاريخ المحدد يوماً دراسياً رسمياً يسمح بالرصد."""
    query = SchoolCalendarDay.objects.filter(
        school=school,
        date=date,
        is_archived=False,
    )
    if academic_year:
        query = query.filter(calendar__academic_year=academic_year)

    day_record = query.first()
    if day_record is not None:
        return day_record.is_school_day

    # Default fallback: Friday (4) and Saturday (5) are non-school days
    return date.weekday() not in (4, 5)


def apply_central_template(
    school,
    central_calendar: SchoolCalendar,
    target_academic_year,
    target_name: str | None = None,
) -> SchoolCalendar:
    """نسخ قالب تقويم وزاري أو مركزي وتطبيقه على مدرسة معينة."""
    if not central_calendar.is_central_template:
        raise ValidationError("التقويم المصدر ليس قالباً مركزياً.")

    name = target_name or f"تقويم {target_academic_year.name} - مشتق"
    with transaction.atomic():
        new_calendar = SchoolCalendar.objects.create(
            school=school,
            academic_year=target_academic_year,
            name=name,
            is_central_template=False,
            source_template=central_calendar,
            is_active=True,
            description=f"مشتق من القالب المركزي: {central_calendar.name}",
        )

        source_days = central_calendar.days.filter(is_archived=False)
        cloned_days = [
            SchoolCalendarDay(
                school=school,
                calendar=new_calendar,
                date=day.date,
                day_type=day.day_type,
                title=day.title,
                is_school_day=day.is_school_day,
                notes=day.notes,
            )
            for day in source_days
        ]
        SchoolCalendarDay.objects.bulk_create(cloned_days, batch_size=500)

    return new_calendar


def generate_event_occurrences(calendar_event: CalendarEvent) -> list[CalendarOccurrence]:
    """توليد جلسات الانعقاد الدورية لفعالية أو برنامج مدرسي محدد."""
    occurrences = []
    start_date = calendar_event.start_date
    end_date = calendar_event.end_date or start_date
    recurrence = calendar_event.recurrence_type

    existing_dates = set(
        CalendarOccurrence.objects.filter(event=calendar_event).values_list("date", flat=True)
    )

    if recurrence == CalendarEvent.RecurrenceType.NONE:
        if start_date not in existing_dates:
            occ = CalendarOccurrence.objects.create(
                school=calendar_event.school,
                event=calendar_event,
                date=start_date,
                start_time=calendar_event.start_time,
                end_time=calendar_event.end_time,
                status=CalendarOccurrence.Status.SCHEDULED,
            )
            occurrences.append(occ)
        return occurrences

    # Weekly recurrence step
    delta_days = 7 if recurrence == CalendarEvent.RecurrenceType.WEEKLY else 14
    curr = start_date

    # Align with target day_of_week if specified
    # ClassSchedule.WeekDay: 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday
    # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    weekday_map = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    if calendar_event.day_of_week and calendar_event.day_of_week in weekday_map:
        target_py_weekday = weekday_map[calendar_event.day_of_week]
        while curr.weekday() != target_py_weekday and curr <= end_date:
            curr += datetime.timedelta(days=1)

    while curr <= end_date:
        if curr not in existing_dates:
            occ = CalendarOccurrence(
                school=calendar_event.school,
                event=calendar_event,
                date=curr,
                start_time=calendar_event.start_time,
                end_time=calendar_event.end_time,
                status=CalendarOccurrence.Status.SCHEDULED,
            )
            occurrences.append(occ)
        curr += datetime.timedelta(days=delta_days)

    if occurrences:
        CalendarOccurrence.objects.bulk_create(occurrences, batch_size=200)

    return occurrences
