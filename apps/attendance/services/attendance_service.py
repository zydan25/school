"""Core Attendance Register and Student Attendance Management Services."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import AcademicTerm
from apps.attendance.models import (
    AttendancePolicy,
    AttendanceAuditLog,
    AttendanceExcuseRequest,
    AttendanceRegister,
    EarlyDepartureRequest,
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
    """فتح سجل الحضور بعد التحقق من نطاق الفرع والتقويم والجدول الفعلي."""
    if section.school_id != school.pk or academic_year.school_id != school.pk:
        raise ValidationError("الشعبة والسنة الدراسية يجب أن تتبعا المدرسة المحددة.")
    if section.academic_year_id != academic_year.pk:
        raise ValidationError("الشعبة لا تنتمي إلى السنة الدراسية المحددة.")
    if date < academic_year.starts_on or date > academic_year.ends_on:
        raise ValidationError("تاريخ الحضور يقع خارج حدود السنة الدراسية المحددة.")
    register_branch = schedule.branch if schedule and schedule.branch_id else section.branch
    if section.branch_id and register_branch and section.branch_id != register_branch.pk:
        raise ValidationError("الشعبة والحصة المجدولة تتبعان فرعين مختلفين.")
    if schedule:
        if schedule.school_id != school.pk or schedule.section_id != section.pk or schedule.academic_year_id != academic_year.pk:
            raise ValidationError("الحصة المجدولة لا تتبع المدرسة والشعبة والسنة المحددة.")
        from apps.timetable.services.workflow import get_effective_class_schedules
        effective_ids = get_effective_class_schedules(school=school, on_date=date, branch=register_branch, section_id=section.pk).values_list("pk", flat=True)
        if not effective_ids.filter(pk=schedule.pk).exists():
            raise ValidationError("الحصة ليست ضمن الجدول المنشور والنافذ في التاريخ المحدد.")
    if not bypass_calendar_check and not is_school_day(school, date, academic_year, branch=register_branch):
        raise ValidationError("لا يمكن فتح سجل حضور في يوم غير دراسي أو عطلة رسمية وفق التقويم المعتمد.")
    if academic_term:
        if academic_term.school_id != school.pk or academic_term.academic_year_id != academic_year.pk:
            raise ValidationError("الفصل الدراسي لا يتبع المدرسة والسنة المحددتين.")
        if not academic_term.starts_on <= date <= academic_term.ends_on:
            raise ValidationError("تاريخ الحضور خارج حدود الفصل الدراسي المحدد.")
        if academic_term.branch_id and academic_term.branch_id != getattr(register_branch, "pk", None):
            raise ValidationError("الفصل الدراسي يتبع فرعاً مختلفاً.")
    else:
        terms = AcademicTerm.objects.filter(academic_year=academic_year, starts_on__lte=date, ends_on__gte=date, is_archived=False)
        academic_term = (terms.filter(branch=register_branch).first() if register_branch else None) or terms.filter(branch__isnull=True).first()

    with transaction.atomic():
        if schedule:
            register, created = AttendanceRegister.objects.get_or_create(
                school=school, schedule=schedule, date=date,
                defaults={
                    "branch": register_branch, "academic_year": academic_year, "academic_term": academic_term,
                    "section": section, "session_type": AttendanceRegister.SessionType.PERIOD,
                    "event_occurrence": event_occurrence, "status": AttendanceRegister.Status.OPEN,
                },
            )
        else:
            register, created = AttendanceRegister.objects.get_or_create(
                school=school, section=section, date=date, session_type=session_type,
                defaults={
                    "branch": register_branch, "academic_year": academic_year, "academic_term": academic_term,
                    "schedule": None, "event_occurrence": event_occurrence, "status": AttendanceRegister.Status.OPEN,
                },
            )
        # Never append students or synchronize legacy rows after submission/approval/locking.
        if register.status != AttendanceRegister.Status.OPEN:
            return register, created
        existing_ids = set(register.student_records.values_list("student_id", flat=True))
        enrolled = Student.objects.filter(school=school, section=section, status=Student.Status.ACTIVE, is_archived=False)
        new_records = []
        for student in enrolled:
            if student.pk in existing_ids:
                continue
            excuses = AttendanceExcuseRequest.objects.filter(
                school=school, student=student, status=AttendanceExcuseRequest.Status.APPROVED,
                start_date__lte=date, end_date__gte=date, is_archived=False,
            )
            approved_excuse = (excuses.filter(branch=student.branch).first() if student.branch_id else None) or excuses.filter(branch__isnull=True).first()
            new_records.append(StudentAttendanceRecord(
                school=school, branch=register.branch, register=register, student=student,
                status_category=AttendanceStatusType.Category.ABSENT_EXCUSED if approved_excuse else AttendanceStatusType.Category.PRESENT,
                late_minutes=0, excuse_request=approved_excuse, recorded_by=user,
            ))
        if new_records:
            StudentAttendanceRecord.objects.bulk_create(new_records)
            for rec in register.student_records.select_related("student", "register"):
                _sync_legacy_attendance(rec, user)
            if register.schedule_id is None:
                cascade_daily_attendance_to_periods(register, user=user)
        if created:
            AttendanceAuditLog.objects.create(
                school=school, register=register, action=AttendanceAuditLog.Action.REGISTER_CREATED,
                performed_by=user, new_value={"status": register.status, "date": str(date), "session_type": register.session_type},
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
    register.refresh_from_db()
    return register




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
    register.refresh_from_db()
    return register




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
    register.refresh_from_db()
    return register




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
            AttendanceStatusType.Category.AUTHORIZED_DEPARTURE: PeriodAttendance.Status.EARLY_DEPARTURE,
            AttendanceStatusType.Category.EARLY_DEPARTURE: PeriodAttendance.Status.EARLY_DEPARTURE,
        }
        p_status = period_status_map.get(rec.status_category, PeriodAttendance.Status.PRESENT)
        PeriodAttendance.objects.update_or_create(
            school=rec.school,
            schedule=register.schedule,
            student=rec.student,
            date=register.date,
            defaults={
                "branch": rec.branch or register.branch,
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
                "branch": rec.branch or register.branch,
                "status": cat_daily,
                "late_minutes": rec.late_minutes,
                "excuse_reason": rec.notes,
                "recorded_by": user or rec.recorded_by,
                "register": register,
                "detailed_record": rec,
            },
        )


def cascade_daily_attendance_to_periods(register: AttendanceRegister, student: Student | None = None, user=None) -> int:
    """تعميم الحضور اليومي على الحصص القديمة دون تجاوز سجل حصة مستقل."""
    if register.schedule_id or register.session_type not in {AttendanceRegister.SessionType.DAILY_MORNING, AttendanceRegister.SessionType.DAILY_FULL, AttendanceRegister.SessionType.DAILY_EVENING}:
        return 0
    policy_query = AttendancePolicy.objects.filter(school=register.school, academic_year=register.academic_year, is_active=True, is_archived=False)
    policy = (policy_query.filter(branch=register.branch).first() if register.branch_id else None) or policy_query.filter(branch__isnull=True).first()
    if policy and not policy.cascade_daily_to_periods:
        return 0
    from apps.timetable.services.workflow import get_effective_class_schedules
    schedules = get_effective_class_schedules(school=register.school, on_date=register.date, branch=register.branch, section_id=register.section_id).order_by("period_number")
    if not schedules.exists():
        return 0
    records = register.student_records.select_related("student")
    if student:
        records = records.filter(student=student)
    departures = {item.student_id: item for item in EarlyDepartureRequest.objects.filter(
        school=register.school, date=register.date,
        status__in=[EarlyDepartureRequest.Status.APPROVED, EarlyDepartureRequest.Status.EXITED],
        is_archived=False,
    )}
    count = 0
    with transaction.atomic():
        for rec in records:
            departure = departures.get(rec.student_id)
            for schedule in schedules:
                if AttendanceRegister.objects.filter(school=register.school, schedule=schedule, date=register.date, is_archived=False).exists():
                    continue
                if rec.status_category in {AttendanceStatusType.Category.ABSENT_UNEXCUSED, AttendanceStatusType.Category.ABSENT_EXCUSED}:
                    period_status, note = PeriodAttendance.Status.ABSENT, "غياب اليوم وفق سجل الحضور اليومي"
                elif rec.status_category in {AttendanceStatusType.Category.LATE, AttendanceStatusType.Category.LATE_EXCUSED} and schedule.period_number == 1:
                    period_status, note = PeriodAttendance.Status.LATE, f"تأخر صباحي ({rec.late_minutes} دقيقة)"
                elif departure and schedule.end_time > departure.departure_time:
                    period_status, note = PeriodAttendance.Status.EARLY_DEPARTURE, f"انصراف مبكر عند {departure.departure_time.strftime('%H:%M')}"
                else:
                    period_status, note = PeriodAttendance.Status.PRESENT, "حاضر وفق سجل الحضور اليومي"
                PeriodAttendance.objects.update_or_create(
                    school=register.school, schedule=schedule, student=rec.student, date=register.date,
                    defaults={"branch": register.branch, "status": period_status, "notes": note, "register": register, "detailed_record": rec},
                )
                count += 1
    return count
