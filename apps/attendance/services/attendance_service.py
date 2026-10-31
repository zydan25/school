"""Core Attendance Register and Student Attendance Management Services."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import AcademicTerm
from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceExcuseRequest,
    AttendanceRegister,
    AttendanceReopenRequest,
    AttendanceStatusType,
    DailyAttendance,
    PeriodAttendance,
    StudentAttendanceRecord,
)
from apps.attendance.services.calendar_service import is_school_day
from apps.attendance.services.notification_service import notify_absence_or_late
from apps.students.models import Student


def get_or_create_register(
    school,
    academic_year,
    section,
    date: datetime.date,
    session_type: str = AttendanceRegister.SessionType.DAILY_MORNING,
    schedule=None,
    event_occurrence=None,
    academic_term=None,
    user=None,
    bypass_calendar_check: bool = False,
) -> tuple[AttendanceRegister, bool]:
    """فتح أو جلب سجل الحضور المعتمد مع تهيئة سجلات الطلاب وربط الأعذار المسبقة."""
    if not bypass_calendar_check and not is_school_day(school, date, academic_year):
        raise ValidationError("لا يمكن فتح سجل حضور في يوم غير دراسي أو عطلة رسمية وفقاً للتقويم المدرسي.")

    if not academic_term:
        academic_term = AcademicTerm.objects.filter(
            academic_year=academic_year,
            starts_on__lte=date,
            ends_on__gte=date,
            is_archived=False,
        ).first()

    with transaction.atomic():
        if schedule:
            register, created = AttendanceRegister.objects.get_or_create(
                school=school,
                schedule=schedule,
                date=date,
                defaults={
                    "academic_year": academic_year,
                    "academic_term": academic_term,
                    "section": section,
                    "session_type": AttendanceRegister.SessionType.PERIOD,
                    "event_occurrence": event_occurrence,
                    "status": AttendanceRegister.Status.OPEN,
                },
            )
        else:
            register, created = AttendanceRegister.objects.get_or_create(
                school=school,
                section=section,
                date=date,
                session_type=session_type,
                defaults={
                    "academic_year": academic_year,
                    "academic_term": academic_term,
                    "schedule": None,
                    "event_occurrence": event_occurrence,
                    "status": AttendanceRegister.Status.OPEN,
                },
            )

        # Seed students if register is newly created or missing student records
        existing_student_ids = set(
            register.student_records.values_list("student_id", flat=True)
        )
        enrolled_students = Student.objects.filter(
            school=school,
            section=section,
            status=Student.Status.ACTIVE,
            is_archived=False,
        )

        records_to_create = []
        for student in enrolled_students:
            if student.id in existing_student_ids:
                continue

            # Check for approved advance absence excuse
            approved_excuse = AttendanceExcuseRequest.objects.filter(
                school=school,
                student=student,
                status=AttendanceExcuseRequest.Status.APPROVED,
                start_date__lte=date,
                end_date__gte=date,
                is_archived=False,
            ).first()

            if approved_excuse:
                cat = AttendanceStatusType.Category.ABSENT_EXCUSED
                excuse_ref = approved_excuse
            else:
                cat = AttendanceStatusType.Category.PRESENT
                excuse_ref = None

            rec = StudentAttendanceRecord(
                school=school,
                register=register,
                student=student,
                status_category=cat,
                late_minutes=0,
                excuse_request=excuse_ref,
                recorded_by=user,
            )
            records_to_create.append(rec)

        if records_to_create:
            StudentAttendanceRecord.objects.bulk_create(records_to_create)

            # Sync legacy models for backward compatibility
            for rec in register.student_records.all():
                _sync_legacy_attendance(rec, user)

            cascade_daily_attendance_to_periods(register, user=user)

        if created:
            AttendanceAuditLog.objects.create(
                school=school,
                register=register,
                action=AttendanceAuditLog.Action.REGISTER_CREATED,
                performed_by=user,
                new_value={"status": register.status, "date": str(date), "session_type": register.session_type},
            )

    return register, created


def bulk_record_attendance(
    register: AttendanceRegister,
    records_data: list[dict],
    recorded_by=None,
    ip_address: str | None = None,
) -> int:
    """رصد وتحديث حالات الحضور والغياب للطلاب دفعة واحدة مع التدقيق الكامل."""
    if not register.is_modifiable:
        raise ValidationError("سجل الحضور مقفل أو معتمد نهائياً ولا يمكن التعديل عليه إلا بإذن إعادة فتح رسمي.")

    updated_count = 0
    with transaction.atomic():
        student_records_map = {
            rec.student_id: rec
            for rec in register.student_records.select_related("student")
        }

        for item in records_data:
            student_id = item.get("student_id")
            if student_id not in student_records_map:
                continue

            rec = student_records_map[student_id]
            new_cat = item.get("status_category", rec.status_category)
            new_late = item.get("late_minutes", rec.late_minutes)
            new_notes = item.get("notes", rec.notes)

            changed = (
                rec.status_category != new_cat
                or rec.late_minutes != new_late
                or rec.notes != new_notes
            )

            if changed:
                old_val = {
                    "status_category": rec.status_category,
                    "late_minutes": rec.late_minutes,
                    "notes": rec.notes,
                }
                rec.status_category = new_cat
                rec.late_minutes = new_late
                rec.notes = new_notes
                rec.recorded_by = recorded_by
                rec.recorded_at = timezone.now()
                rec.save()

                _sync_legacy_attendance(rec, recorded_by)

                AttendanceAuditLog.objects.create(
                    school=register.school,
                    register=register,
                    student_record=rec,
                    action=AttendanceAuditLog.Action.RECORD_UPDATED,
                    performed_by=recorded_by,
                    old_value=old_val,
                    new_value={
                        "status_category": new_cat,
                        "late_minutes": new_late,
                        "notes": new_notes,
                    },
                    ip_address=ip_address,
                )
                updated_count += 1

        if updated_count > 0:
            cascade_daily_attendance_to_periods(register, user=recorded_by)

    return updated_count


def submit_register(
    register: AttendanceRegister,
    submitted_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """تسليم سجل الحضور للمراجعة والاعتماد وإشعار أولياء الأمور بالحالات المرصودة."""
    if register.status == AttendanceRegister.Status.LOCKED:
        raise ValidationError("السجل مقفل نهائياً.")

    with transaction.atomic():
        register.status = AttendanceRegister.Status.SUBMITTED
        register.submitted_by = submitted_by
        register.submitted_at = timezone.now()
        register.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=register.school,
            register=register,
            action=AttendanceAuditLog.Action.REGISTER_SUBMITTED,
            performed_by=submitted_by,
            new_value={"status": register.status},
            ip_address=ip_address,
        )

        # Notify guardians for unexcused absence and late records
        for rec in register.student_records.filter(
            status_category__in=[
                AttendanceStatusType.Category.ABSENT_UNEXCUSED,
                AttendanceStatusType.Category.LATE,
            ]
        ).select_related("student"):
            notify_absence_or_late(
                school=register.school,
                student=rec.student,
                date=register.date,
                status_category=rec.status_category,
                late_minutes=rec.late_minutes,
            )

    return register


def approve_register(
    register: AttendanceRegister,
    approved_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """اعتماد سجل الحضور من إدارة المدرسة أو المشرف المعتمد."""
    if register.status == AttendanceRegister.Status.LOCKED:
        raise ValidationError("السجل مقفل نهائياً.")

    with transaction.atomic():
        register.status = AttendanceRegister.Status.APPROVED
        register.approved_by = approved_by
        register.approved_at = timezone.now()
        register.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=register.school,
            register=register,
            action=AttendanceAuditLog.Action.REGISTER_APPROVED,
            performed_by=approved_by,
            new_value={"status": register.status},
            ip_address=ip_address,
        )

        cascade_daily_attendance_to_periods(register, user=approved_by)

    return register


def lock_register(
    register: AttendanceRegister,
    locked_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """إقفال سجل الحضور نهائياً وحمايته من أي تعديل مستقبلي."""
    with transaction.atomic():
        register.status = AttendanceRegister.Status.LOCKED
        register.locked_by = locked_by
        register.locked_at = timezone.now()
        register.save(update_fields=["status", "locked_by", "locked_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=register.school,
            register=register,
            action=AttendanceAuditLog.Action.REGISTER_LOCKED,
            performed_by=locked_by,
            new_value={"status": register.status},
            ip_address=ip_address,
        )

    return register


def request_reopen_register(
    register: AttendanceRegister,
    requested_by,
    reason: str,
) -> AttendanceReopenRequest:
    """تقديم طلب لإعادة فتح سجل مقفل أو معتمد مع بيان الأسباب."""
    if register.status == AttendanceRegister.Status.OPEN:
        raise ValidationError("السجل مفتوح بالفعل ولا يحتاج لإعادة فتح.")

    req = AttendanceReopenRequest.objects.create(
        school=register.school,
        register=register,
        requested_by=requested_by,
        reason=reason,
        status=AttendanceReopenRequest.Status.PENDING,
    )

    AttendanceAuditLog.objects.create(
        school=register.school,
        register=register,
        action=AttendanceAuditLog.Action.REOPEN_REQUESTED,
        performed_by=requested_by,
        reason=reason,
    )
    return req


def review_reopen_request(
    reopen_request: AttendanceReopenRequest,
    reviewed_by,
    is_approved: bool,
    review_notes: str = "",
) -> AttendanceReopenRequest:
    """مراجعة واعتماد أو رفض طلب إعادة فتح السجل."""
    with transaction.atomic():
        reopen_request.reviewed_by = reviewed_by
        reopen_request.reviewed_at = timezone.now()
        reopen_request.review_notes = review_notes

        if is_approved:
            reopen_request.status = AttendanceReopenRequest.Status.APPROVED
            register = reopen_request.register
            register.status = AttendanceRegister.Status.OPEN
            register.save(update_fields=["status", "updated_at"])

            AttendanceAuditLog.objects.create(
                school=register.school,
                register=register,
                action=AttendanceAuditLog.Action.REOPEN_APPROVED,
                performed_by=reviewed_by,
                reason=review_notes,
            )
        else:
            reopen_request.status = AttendanceReopenRequest.Status.REJECTED

        reopen_request.save()

    return reopen_request


def _sync_legacy_attendance(rec: StudentAttendanceRecord, user=None):
    """مزامنة السجل المفصل مع نماذج الحضور السابقة لضمان التوافق الكامل."""
    register = rec.register
    # Map category to DailyAttendance.Status
    daily_status_map = {
        AttendanceStatusType.Category.PRESENT: DailyAttendance.Status.PRESENT,
        AttendanceStatusType.Category.ABSENT_UNEXCUSED: DailyAttendance.Status.ABSENT_UNEXCUSED,
        AttendanceStatusType.Category.ABSENT_EXCUSED: DailyAttendance.Status.ABSENT_EXCUSED,
        AttendanceStatusType.Category.LATE: DailyAttendance.Status.LATE,
        AttendanceStatusType.Category.LATE_EXCUSED: DailyAttendance.Status.LATE,
        AttendanceStatusType.Category.AUTHORIZED_DEPARTURE: DailyAttendance.Status.PRESENT,
        AttendanceStatusType.Category.DISTANCE_LEARNING: DailyAttendance.Status.PRESENT,
        AttendanceStatusType.Category.SCHOOL_ACTIVITY: DailyAttendance.Status.PRESENT,
    }
    cat_daily = daily_status_map.get(rec.status_category, DailyAttendance.Status.PRESENT)

    if register.schedule:
        # Period attendance
        period_status_map = {
            AttendanceStatusType.Category.PRESENT: PeriodAttendance.Status.PRESENT,
            AttendanceStatusType.Category.ABSENT_UNEXCUSED: PeriodAttendance.Status.ABSENT,
            AttendanceStatusType.Category.ABSENT_EXCUSED: PeriodAttendance.Status.ABSENT,
            AttendanceStatusType.Category.LATE: PeriodAttendance.Status.LATE,
            AttendanceStatusType.Category.LATE_EXCUSED: PeriodAttendance.Status.LATE,
        }
        p_status = period_status_map.get(rec.status_category, PeriodAttendance.Status.PRESENT)
        PeriodAttendance.objects.update_or_create(
            school=rec.school,
            schedule=register.schedule,
            student=rec.student,
            date=register.date,
            defaults={
                "status": p_status,
                "notes": rec.notes,
                "register": register,
                "detailed_record": rec,
            },
        )
    else:
        # Daily attendance
        DailyAttendance.objects.update_or_create(
            school=rec.school,
            student=rec.student,
            date=register.date,
            defaults={
                "status": cat_daily,
                "late_minutes": rec.late_minutes,
                "excuse_reason": rec.notes,
                "recorded_by": user or rec.recorded_by,
                "register": register,
                "detailed_record": rec,
            },
        )


def cascade_daily_attendance_to_periods(
    register: AttendanceRegister,
    student: Student | None = None,
    user=None,
) -> int:
    """تعميم حالة الحضور اليومي على حصص اليوم المجدولة مع استثناء فترات ما بعد الانصراف المبكر."""
    from apps.attendance.models import AttendancePolicy, EarlyDepartureRequest
    from apps.timetable.models import ClassSchedule

    policy = AttendancePolicy.objects.filter(
        school=register.school,
        academic_year=register.academic_year,
        is_active=True,
        is_archived=False,
    ).first()

    if policy and not policy.cascade_daily_to_periods:
        return 0

    if register.session_type not in [
        AttendanceRegister.SessionType.DAILY_MORNING,
        AttendanceRegister.SessionType.DAILY_FULL,
        AttendanceRegister.SessionType.DAILY_EVENING,
    ]:
        return 0

    # Sunday: 6 -> 1; Monday: 0 -> 2; Tuesday: 1 -> 3; Wednesday: 2 -> 4; Thursday: 3 -> 5; Friday: 4 -> 6; Saturday: 5 -> 7
    weekday_map = {6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7}
    schedule_weekday = weekday_map.get(register.date.weekday(), 1)

    schedules = ClassSchedule.objects.filter(
        school=register.school,
        section=register.section,
        academic_year=register.academic_year,
        day_of_week=schedule_weekday,
        is_archived=False,
    ).order_by("period_number")

    if not schedules.exists():
        return 0

    student_records = register.student_records.all()
    if student:
        student_records = student_records.filter(student=student)

    early_departures = {
        ed.student_id: ed
        for ed in EarlyDepartureRequest.objects.filter(
            school=register.school,
            date=register.date,
            status__in=[EarlyDepartureRequest.Status.APPROVED, EarlyDepartureRequest.Status.EXITED],
            is_archived=False,
        )
    }

    synced_count = 0
    with transaction.atomic():
        for rec in student_records.select_related("student"):
            st = rec.student
            departure = early_departures.get(st.id)

            for sched in schedules:
                if rec.status_category == AttendanceStatusType.Category.PRESENT:
                    if departure and sched.start_time and sched.start_time >= departure.departure_time:
                        p_status = PeriodAttendance.Status.EARLY_DEPARTURE
                        notes = f"انصراف مبكر في الساعة {departure.departure_time.strftime('%H:%M')}"
                    else:
                        p_status = PeriodAttendance.Status.PRESENT
                        notes = "حاضر (وفق اعتماد الحضور اليومي)"
                elif rec.status_category in [
                    AttendanceStatusType.Category.ABSENT_UNEXCUSED,
                    AttendanceStatusType.Category.ABSENT_EXCUSED,
                ]:
                    p_status = PeriodAttendance.Status.ABSENT
                    notes = "غائب (وفق سجل الغياب اليومي)"
                elif rec.status_category in [
                    AttendanceStatusType.Category.LATE,
                    AttendanceStatusType.Category.LATE_EXCUSED,
                ]:
                    if sched.period_number == 1:
                        p_status = PeriodAttendance.Status.LATE
                        notes = f"متأخر ({rec.late_minutes} دقيقة)"
                    else:
                        p_status = PeriodAttendance.Status.PRESENT
                        notes = "حاضر في الحصة"
                elif rec.status_category == AttendanceStatusType.Category.AUTHORIZED_DEPARTURE:
                    if departure and sched.start_time and sched.start_time < departure.departure_time:
                        p_status = PeriodAttendance.Status.PRESENT
                        notes = "حاضر قبل الانصراف"
                    else:
                        p_status = PeriodAttendance.Status.EARLY_DEPARTURE
                        notes = "انصراف مبكر مصرح به"
                else:
                    p_status = PeriodAttendance.Status.PRESENT
                    notes = ""

                PeriodAttendance.objects.update_or_create(
                    school=register.school,
                    schedule=sched,
                    student=st,
                    date=register.date,
                    defaults={
                        "status": p_status,
                        "notes": notes,
                        "register": register,
                        "detailed_record": rec,
                    },
                )
                synced_count += 1

    return synced_count

