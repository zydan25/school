"""Guardian Requests, Absence Excuses, and Early Departure Gate Exit Services."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceRegister,
    AttendanceExcuseRequest,
    AttendancePolicy,
    AttendanceStatusType,
    EarlyDepartureRequest,
    StudentAttendanceRecord,
)
from apps.attendance.services.notification_service import (
    notify_early_departure_change,
    notify_excuse_status_change,
)
from apps.students.models import StudentGuardianRelation


def _policy_for_student(student):
    policies = AttendancePolicy.objects.filter(
        school=student.school, academic_year=student.academic_year,
        is_active=True, is_archived=False,
    )
    if student.branch_id:
        branch_policy = policies.filter(branch_id=student.branch_id).first()
        if branch_policy:
            return branch_policy
    return policies.filter(branch__isnull=True).first()


def create_excuse_request(
    school,
    student,
    guardian,
    request_type: str,
    start_date: datetime.date,
    end_date: datetime.date,
    reason: str,
    attachment=None,
) -> AttendanceExcuseRequest:
    """إنشاء طلب عذر أو استئذان غياب من ولي الأمر والتحقق من سياسات المدرسة."""
    if student.school_id != school.pk or guardian.school_id != school.pk:
        raise ValidationError("الطالب وولي الأمر يجب أن يتبعا المدرسة المحددة.")
    if end_date < start_date:
        raise ValidationError("تاريخ نهاية العذر لا يمكن أن يسبق تاريخ البداية.")
    if not (reason or "").strip():
        raise ValidationError("سبب العذر مطلوب.")
    if student.academic_year_id and (
        start_date < student.academic_year.starts_on or end_date > student.academic_year.ends_on
    ):
        raise ValidationError("فترة العذر يجب أن تقع داخل السنة الدراسية الحالية للطالب.")

    # Check student relation with guardian
    is_related = StudentGuardianRelation.objects.filter(
        school=school,
        student=student,
        guardian=guardian,
        is_archived=False,
    ).exists()
    if not is_related:
        raise ValidationError("ولي الأمر غير مسجل كولي أمر رسمي لهذا الطالب.")

    # Check school policy
    policy = _policy_for_student(student)

    if policy:
        if request_type == AttendanceExcuseRequest.RequestType.ADVANCE_ABSENCE and not policy.allow_guardian_advance_excuse:
            raise ValidationError("المدرسة لا تفعل ميزة تقديم استئذان الغياب المسبق عبر التطبيق.")
        if request_type == AttendanceExcuseRequest.RequestType.POST_ABSENCE_EXCUSE:
            if not policy.allow_guardian_post_excuse:
                raise ValidationError("المدرسة لا تفعل ميزة تقديم الأعذار اللاحقة عبر التطبيق.")
            # Check deadline
            days_passed = (timezone.localdate() - end_date).days
            if days_passed > policy.excuse_submission_deadline_days:
                raise ValidationError(
                    f"تجاوز الطلب المهلة المحددة في سياسة المدرسة لتقديم الأعذار ({policy.excuse_submission_deadline_days} أيام)."
                )
        if policy.require_excuse_attachment and not attachment:
            raise ValidationError("تنص سياسة المدرسة على ضرورة إرفاق تقرير طبي أو مستند يثبت العذر.")

    req = AttendanceExcuseRequest.objects.create(
        school=school,
        branch=student.branch,
        student=student,
        guardian=guardian,
        request_type=request_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        attachment=attachment,
        status=AttendanceExcuseRequest.Status.SUBMITTED,
    )
    return req


def review_excuse_request(excuse_request: AttendanceExcuseRequest, reviewed_by, is_approved: bool, review_notes: str = "") -> AttendanceExcuseRequest:
    """مراجعة العذر دون تحويل الحاضر إلى غائب أو تجاوز سجل معتمد/مقفل."""
    with transaction.atomic():
        locked_request = AttendanceExcuseRequest.objects.select_for_update().get(pk=excuse_request.pk)
        if locked_request.status != AttendanceExcuseRequest.Status.SUBMITTED:
            raise ValidationError("لا يمكن مراجعة العذر إلا إذا كان قيد التقديم ولم تتم معالجته مسبقاً.")
        if is_approved:
            records = list(StudentAttendanceRecord.objects.select_for_update().filter(
                school=locked_request.school, student=locked_request.student,
                register__date__gte=locked_request.start_date, register__date__lte=locked_request.end_date,
                is_archived=False,
                status_category__in=[AttendanceStatusType.Category.ABSENT_UNEXCUSED, AttendanceStatusType.Category.LATE],
            ).select_related("register"))
            if any(not rec.register.is_modifiable for rec in records):
                raise ValidationError("يوجد سجل حضور معتمد أو مقفل ضمن فترة العذر؛ يجب إعادة فتحه رسمياً قبل تطبيق العذر.")
            from apps.attendance.services.attendance_service import _sync_legacy_attendance
            for rec in records:
                old_category = rec.status_category
                rec.status_category = (
                    AttendanceStatusType.Category.ABSENT_EXCUSED
                    if old_category == AttendanceStatusType.Category.ABSENT_UNEXCUSED
                    else AttendanceStatusType.Category.LATE_EXCUSED
                )
                rec.excuse_request = locked_request
                rec.notes = (f"{rec.notes}\n{locked_request.reason}").strip()
                rec.save(update_fields=["status_category", "excuse_request", "notes", "updated_at"])
                _sync_legacy_attendance(rec, reviewed_by)
                AttendanceAuditLog.objects.create(
                    school=locked_request.school, register=rec.register, student_record=rec,
                    action=AttendanceAuditLog.Action.EXCUSE_REVIEWED, performed_by=reviewed_by,
                    old_value={"status_category": old_category},
                    new_value={"status_category": rec.status_category, "excuse_id": str(locked_request.pk)},
                    reason=f"تم قبول العذر: {review_notes}",
                )
        locked_request.status = AttendanceExcuseRequest.Status.APPROVED if is_approved else AttendanceExcuseRequest.Status.REJECTED
        locked_request.reviewed_by = reviewed_by
        locked_request.reviewed_at = timezone.now()
        locked_request.review_notes = review_notes
        locked_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"])
        notify_excuse_status_change(locked_request)
    excuse_request.refresh_from_db()
    return excuse_request
def create_early_departure_request(
    school,
    student,
    guardian,
    date: datetime.date,
    departure_time: datetime.time,
    reason: str,
    recipient_name: str,
    recipient_phone: str,
    recipient_relationship: str,
    recipient_national_id: str = "",
) -> EarlyDepartureRequest:
    """إنشاء طلب انصراف مبكر والتحقق من هوية وصلاحية الشخص المستلم للطالب."""
    # Check guardian relation
    if student.school_id != school.pk or guardian.school_id != school.pk:
        raise ValidationError("الطالب وولي الأمر يجب أن يتبعا المدرسة المحددة.")
    if not (reason or "").strip():
        raise ValidationError("مبرر الانصراف مطلوب.")
    rel = StudentGuardianRelation.objects.filter(
        school=school,
        student=student,
        guardian=guardian,
        is_archived=False,
    ).first()
    if not rel:
        raise ValidationError("ولي الأمر غير مسجل رسمياً لهذا الطالب.")
    if not rel.can_pickup:
        raise ValidationError("ولي الأمر غير مخول باستلام الطالب أو طلب انصرافه وفق بيانات المدرسة.")
    if student.school_id != school.pk or guardian.school_id != school.pk:
        raise ValidationError("الطالب وولي الأمر يجب أن يتبعا المدرسة المحددة.")
    if student.academic_year_id:
        year = student.academic_year
        if date < year.starts_on or date > year.ends_on:
            raise ValidationError("تاريخ الانصراف يقع خارج السنة الدراسية الحالية للطالب.")

    policy = _policy_for_student(student)
    if policy and not policy.allow_guardian_early_departure:
        raise ValidationError("المدرسة لا تفعل ميزة طلبات الانصراف المبكر الإلكترونية.")

    if EarlyDepartureRequest.objects.filter(
        school=school, student=student, date=date, is_archived=False,
        status__in=[EarlyDepartureRequest.Status.PENDING, EarlyDepartureRequest.Status.APPROVED],
    ).exists():
        raise ValidationError("يوجد بالفعل طلب انصراف مبكر غير منتهٍ لهذا الطالب في التاريخ نفسه.")

    req = EarlyDepartureRequest.objects.create(
        school=school,
        branch=student.branch,
        student=student,
        guardian=guardian,
        date=date,
        departure_time=departure_time,
        reason=reason,
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        recipient_relationship=recipient_relationship,
        recipient_national_id=recipient_national_id,
        status=EarlyDepartureRequest.Status.PENDING,
    )
    return req


def approve_early_departure(
    departure_request: EarlyDepartureRequest,
    approved_by,
) -> EarlyDepartureRequest:
    """اعتماد طلب انصراف معلق مرة واحدة فقط."""
    with transaction.atomic():
        locked_request = EarlyDepartureRequest.objects.select_for_update().get(pk=departure_request.pk)
        if locked_request.status != EarlyDepartureRequest.Status.PENDING:
            raise ValidationError("لا يمكن اعتماد طلب الانصراف إلا إذا كان معلقاً ولم تتم معالجته مسبقاً.")
        locked_request.status = EarlyDepartureRequest.Status.APPROVED
        locked_request.approved_by = approved_by
        locked_request.approved_at = timezone.now()
        locked_request.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        notify_early_departure_change(locked_request, is_exit=False)

    departure_request.refresh_from_db()
    return departure_request




def confirm_gate_exit(departure_request: EarlyDepartureRequest, confirmed_by, exit_notes: str = "") -> EarlyDepartureRequest:
    """تأكيد الخروج الفعلي وتحديث سجلات الحضور القابلة للتعديل فقط."""
    with transaction.atomic():
        locked_request = EarlyDepartureRequest.objects.select_for_update().get(pk=departure_request.pk)
        if locked_request.status != EarlyDepartureRequest.Status.APPROVED:
            raise ValidationError("لا يمكن تأكيد خروج الطالب إلا بعد اعتماد طلب الانصراف رسمياً.")
        records = list(StudentAttendanceRecord.objects.select_for_update(of=("self",)).filter(
            school=locked_request.school, student=locked_request.student,
            register__date=locked_request.date, is_archived=False,
        ).select_related("register", "register__schedule"))
        relevant = [rec for rec in records if rec.register.schedule_id is None or rec.register.schedule.end_time > locked_request.departure_time]
        if any(not rec.register.is_modifiable for rec in relevant):
            raise ValidationError("يوجد سجل حضور معتمد أو مقفل؛ أعد فتحه رسمياً قبل تحديث أثر الانصراف.")
        locked_request.status = EarlyDepartureRequest.Status.EXITED
        locked_request.exit_confirmed_at = timezone.now()
        locked_request.exit_confirmed_by = confirmed_by
        locked_request.exit_notes = exit_notes
        locked_request.save(update_fields=["status", "exit_confirmed_at", "exit_confirmed_by", "exit_notes", "updated_at"])
        from apps.attendance.services.attendance_service import _sync_legacy_attendance, cascade_daily_attendance_to_periods
        daily_register_ids = set()
        for rec in relevant:
            if rec.status_category in {
                AttendanceStatusType.Category.ABSENT_UNEXCUSED, AttendanceStatusType.Category.ABSENT_EXCUSED,
                AttendanceStatusType.Category.NON_SCHOOL_DAY, AttendanceStatusType.Category.CANCELLED_SESSION,
            }:
                continue
            old_category = rec.status_category
            rec.status_category = AttendanceStatusType.Category.AUTHORIZED_DEPARTURE
            rec.notes = f"انصراف مبكر مصرح به مع ({locked_request.recipient_name})"
            rec.save(update_fields=["status_category", "notes", "updated_at"])
            _sync_legacy_attendance(rec, confirmed_by)
            if rec.register.schedule_id is None:
                daily_register_ids.add(rec.register_id)
            AttendanceAuditLog.objects.create(
                school=locked_request.school, register=rec.register, student_record=rec,
                action=AttendanceAuditLog.Action.EARLY_EXIT_CONFIRMED, performed_by=confirmed_by,
                old_value={"status_category": old_category},
                new_value={"status_category": rec.status_category, "departure_time": str(locked_request.departure_time)},
                reason=exit_notes or "خروج مصرح به من البوابة",
            )
        for register_id in daily_register_ids:
            daily_register = AttendanceRegister.objects.get(pk=register_id)
            cascade_daily_attendance_to_periods(daily_register, student=locked_request.student, user=confirmed_by)
        notify_early_departure_change(locked_request, is_exit=True)
    departure_request.refresh_from_db()
    return departure_request
