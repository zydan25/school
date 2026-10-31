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
    if section.school_id != school.pk or academic_year.school_id != school.pk:
        raise ValidationError("الشعبة والسنة الدراسية يجب أن تتبعا المدرسة المحددة.")
    if section.academic_year_id != academic_year.pk:
        raise ValidationError("الشعبة لا تنتمي إلى السنة الدراسية المحددة.")
    if date < academic_year.starts_on or date > academic_year.ends_on:
        raise ValidationError("تاريخ الحضور يقع خارج حدود السنة الدراسية المحددة.")
    if schedule and (
        schedule.school_id != school.pk
        or schedule.section_id != section.pk
        or schedule.academic_year_id != academic_year.pk
    ):
        raise ValidationError("الحصة المجدولة لا تتبع المدرسة والشعبة والسنة المحددة.")
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
    """رصد جماعي آمن؛ يقفل سجل الحضور ويرفض أي طالب خارج السجل."""
    if not records_data:
        raise ValidationError("أرسل طالباً واحداً على الأقل لتسجيل الحضور.")

    student_ids = [item.get("student_id") for item in records_data]
    if None in student_ids or len(student_ids) != len(set(student_ids)):
        raise ValidationError("قائمة الطلاب تحتوي على معرف مفقود أو مكرر.")

    updated_count = 0
    with transaction.atomic():
        locked_register = AttendanceRegister.objects.select_for_update().get(pk=register.pk)
        if locked_register.status != AttendanceRegister.Status.OPEN:
            raise ValidationError("لا يمكن تعديل السجل إلا عندما يكون مفتوحاً؛ اطلب إعادة فتحه رسمياً.")

        records = locked_register.student_records.select_for_update().select_related("student")
        student_records_map = {rec.student_id: rec for rec in records}
        unknown_ids = set(student_ids) - set(student_records_map)
        if unknown_ids:
            raise ValidationError(
                f"بعض الطلاب لا ينتمون إلى سجل الحضور المحدد: {sorted(str(item) for item in unknown_ids)}"
            )

        valid_categories = {value for value, _label in AttendanceStatusType.Category.choices}
        for item in records_data:
            rec = student_records_map[item["student_id"]]
            new_cat = item.get("status_category", rec.status_category)
            if new_cat not in valid_categories:
                raise ValidationError(f"حالة حضور غير مدعومة: {new_cat}")
            new_late = item.get("late_minutes", rec.late_minutes)
            if new_late < 0:
                raise ValidationError("دقائق التأخر لا يمكن أن تكون سالبة.")
            new_notes = item.get("notes", rec.notes)

            if (
                rec.status_category == new_cat
                and rec.late_minutes == new_late
                and rec.notes == new_notes
            ):
                continue

            old_value = {
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
                school=locked_register.school,
                register=locked_register,
                student_record=rec,
                action=AttendanceAuditLog.Action.RECORD_UPDATED,
                performed_by=recorded_by,
                old_value=old_value,
                new_value={
                    "status_category": new_cat,
                    "late_minutes": new_late,
                    "notes": new_notes,
                },
                ip_address=ip_address,
            )
            updated_count += 1

        if updated_count:
            cascade_daily_attendance_to_periods(locked_register, user=recorded_by)

    return updated_count




def submit_register(
    register: AttendanceRegister,
    submitted_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """تسليم سجل مفتوح للمراجعة مرة واحدة وإرسال التنبيهات بعد نجاح الانتقال."""
    with transaction.atomic():
        locked_register = AttendanceRegister.objects.select_for_update().get(pk=register.pk)
        if locked_register.status != AttendanceRegister.Status.OPEN:
            raise ValidationError("لا يمكن تسليم السجل إلا من الحالة المفتوحة.")

        locked_register.status = AttendanceRegister.Status.SUBMITTED
        locked_register.submitted_by = submitted_by
        locked_register.submitted_at = timezone.now()
        locked_register.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=locked_register.school,
            register=locked_register,
            action=AttendanceAuditLog.Action.REGISTER_SUBMITTED,
            performed_by=submitted_by,
            new_value={"status": locked_register.status},
            ip_address=ip_address,
        )

        for rec in locked_register.student_records.filter(
            status_category__in=[
                AttendanceStatusType.Category.ABSENT_UNEXCUSED,
                AttendanceStatusType.Category.LATE,
            ]
        ).select_related("student"):
            notify_absence_or_late(
                school=locked_register.school,
                student=rec.student,
                date=locked_register.date,
                status_category=rec.status_category,
                late_minutes=rec.late_minutes,
            )
    return locked_register




def approve_register(
    register: AttendanceRegister,
    approved_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """اعتماد سجل تم تسليمه للمراجعة فقط."""
    with transaction.atomic():
        locked_register = AttendanceRegister.objects.select_for_update().get(pk=register.pk)
        if locked_register.status != AttendanceRegister.Status.SUBMITTED:
            raise ValidationError("لا يمكن اعتماد السجل إلا بعد تسليمه للمراجعة.")

        locked_register.status = AttendanceRegister.Status.APPROVED
        locked_register.approved_by = approved_by
        locked_register.approved_at = timezone.now()
        locked_register.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=locked_register.school,
            register=locked_register,
            action=AttendanceAuditLog.Action.REGISTER_APPROVED,
            performed_by=approved_by,
            new_value={"status": locked_register.status},
            ip_address=ip_address,
        )
        cascade_daily_attendance_to_periods(locked_register, user=approved_by)
    return locked_register




def lock_register(
    register: AttendanceRegister,
    locked_by=None,
    ip_address: str | None = None,
) -> AttendanceRegister:
    """إقفال سجل تم اعتماده فقط."""
    with transaction.atomic():
        locked_register = AttendanceRegister.objects.select_for_update().get(pk=register.pk)
        if locked_register.status != AttendanceRegister.Status.APPROVED:
            raise ValidationError("لا يمكن إقفال السجل إلا بعد اعتماده.")

        locked_register.status = AttendanceRegister.Status.LOCKED
        locked_register.locked_by = locked_by
        locked_register.locked_at = timezone.now()
        locked_register.save(update_fields=["status", "locked_by", "locked_at", "updated_at"])

        AttendanceAuditLog.objects.create(
            school=locked_register.school,
            register=locked_register,
            action=AttendanceAuditLog.Action.REGISTER_LOCKED,
            performed_by=locked_by,
            new_value={"status": locked_register.status},
            ip_address=ip_address,
        )
    return locked_register




def request_reopen_register(
    register: AttendanceRegister,
    requested_by,
    reason: str,
) -> AttendanceReopenRequest:
    """طلب إعادة فتح سجل معتمد/مقفل مرة واحدة، مع توثيق السبب."""
    if not reason or not reason.strip():
        raise ValidationError("يرجى ذكر سبب طلب إعادة فتح سجل الحضور.")

    with transaction.atomic():
        locked_register = AttendanceRegister.objects.select_for_update().get(pk=register.pk)
        if locked_register.status not in [
            AttendanceRegister.Status.APPROVED,
            AttendanceRegister.Status.LOCKED,
        ]:
            raise ValidationError("يمكن طلب إعادة الفتح لسجل معتمد أو مقفل فقط.")
        if locked_register.reopen_requests.filter(
            status=AttendanceReopenRequest.Status.PENDING
        ).exists():
            raise ValidationError("يوجد بالفعل طلب إعادة فتح معلق لهذا السجل.")

        req = AttendanceReopenRequest.objects.create(
            school=locked_register.school,
            register=locked_register,
            requested_by=requested_by,
            reason=reason.strip(),
            status=AttendanceReopenRequest.Status.PENDING,
        )
        AttendanceAuditLog.objects.create(
            school=locked_register.school,
            register=locked_register,
            action=AttendanceAuditLog.Action.REOPEN_REQUESTED,
            performed_by=requested_by,
            reason=reason.strip(),
        )
    return req


def review_reopen_request(
    reopen_request: AttendanceReopenRequest,
    reviewed_by,
    is_approved: bool,
    review_notes: str = "",
) -> AttendanceReopenRequest:
    """مراجعة طلب إعادة فتح معلق مرة واحدة فقط مع قفل السجل والطلب."""
    with transaction.atomic():
        locked_request = AttendanceReopenRequest.objects.select_for_update().get(pk=reopen_request.pk)
        if locked_request.status != AttendanceReopenRequest.Status.PENDING:
            raise ValidationError("تمت معالجة طلب إعادة الفتح مسبقاً.")

        register = AttendanceRegister.objects.select_for_update().get(pk=locked_request.register_id)
        locked_request.reviewed_by = reviewed_by
        locked_request.reviewed_at = timezone.now()
        locked_request.review_notes = review_notes

        if is_approved:
            if register.status == AttendanceRegister.Status.OPEN:
                raise ValidationError("السجل مفتوح بالفعل ولا يحتاج إلى إعادة فتح.")
            locked_request.status = AttendanceReopenRequest.Status.APPROVED
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
            locked_request.status = AttendanceReopenRequest.Status.REJECTED

        locked_request.save()
    return locked_request




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

