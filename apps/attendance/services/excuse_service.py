"""Guardian Requests, Absence Excuses, and Early Departure Gate Exit Services."""
from __future__ import annotations

import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceExcuseRequest,
    AttendancePolicy,
    AttendanceStatusType,
    DailyAttendance,
    EarlyDepartureRequest,
    StudentAttendanceRecord,
)
from apps.attendance.services.notification_service import (
    notify_early_departure_change,
    notify_excuse_status_change,
)
from apps.students.models import StudentGuardianRelation


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
    if end_date < start_date:
        raise ValidationError("تاريخ نهاية العذر لا يمكن أن يسبق تاريخ البداية.")

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
    policy = AttendancePolicy.objects.filter(
        school=school,
        is_active=True,
        is_archived=False,
    ).first()

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


def review_excuse_request(
    excuse_request: AttendanceExcuseRequest,
    reviewed_by,
    is_approved: bool,
    review_notes: str = "",
) -> AttendanceExcuseRequest:
    """مراجعة طلب عذر قيد التقديم مرة واحدة مع حماية سجلات الحضور التابعة."""
    with transaction.atomic():
        locked_request = AttendanceExcuseRequest.objects.select_for_update().get(pk=excuse_request.pk)
        if locked_request.status != AttendanceExcuseRequest.Status.SUBMITTED:
            raise ValidationError("لا يمكن مراجعة العذر إلا إذا كان قيد التقديم ولم تتم معالجته مسبقاً.")

        locked_request.reviewed_by = reviewed_by
        locked_request.reviewed_at = timezone.now()
        locked_request.review_notes = review_notes

        if is_approved:
            locked_request.status = AttendanceExcuseRequest.Status.APPROVED
            records = StudentAttendanceRecord.objects.select_for_update().filter(
                school=locked_request.school,
                student=locked_request.student,
                register__date__gte=locked_request.start_date,
                register__date__lte=locked_request.end_date,
                is_archived=False,
            ).select_related("register")

            for rec in records:
                old_cat = rec.status_category
                if rec.status_category in [
                    AttendanceStatusType.Category.ABSENT_UNEXCUSED,
                    AttendanceStatusType.Category.PRESENT,
                ]:
                    rec.status_category = AttendanceStatusType.Category.ABSENT_EXCUSED
                elif rec.status_category == AttendanceStatusType.Category.LATE:
                    rec.status_category = AttendanceStatusType.Category.LATE_EXCUSED

                rec.excuse_request = locked_request
                rec.save(update_fields=["status_category", "excuse_request", "updated_at"])

                DailyAttendance.objects.filter(
                    school=rec.school,
                    student=rec.student,
                    date=rec.register.date,
                ).update(
                    status=DailyAttendance.Status.ABSENT_EXCUSED,
                    excuse_reason=locked_request.reason,
                )

                AttendanceAuditLog.objects.create(
                    school=locked_request.school,
                    register=rec.register,
                    student_record=rec,
                    action=AttendanceAuditLog.Action.EXCUSE_REVIEWED,
                    performed_by=reviewed_by,
                    old_value={"status_category": old_cat},
                    new_value={
                        "status_category": rec.status_category,
                        "excuse_id": str(locked_request.id),
                    },
                    reason=f"تم قبول العذر: {review_notes}",
                )
        else:
            locked_request.status = AttendanceExcuseRequest.Status.REJECTED

        locked_request.save()
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

    policy = AttendancePolicy.objects.filter(
        school=school,
        academic_year=student.academic_year,
        is_active=True,
        is_archived=False,
    ).first()
    if policy and not policy.allow_guardian_early_departure:
        raise ValidationError("المدرسة لا تفعل ميزة طلبات الانصراف المبكر الإلكترونية.")

    req = EarlyDepartureRequest.objects.create(
        school=school,
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




def confirm_gate_exit(
    departure_request: EarlyDepartureRequest,
    confirmed_by,
    exit_notes: str = "",
) -> EarlyDepartureRequest:
    """تأكيد الخروج من البوابة مرة واحدة بعد اعتماد الطلب."""
    with transaction.atomic():
        locked_request = EarlyDepartureRequest.objects.select_for_update().get(pk=departure_request.pk)
        if locked_request.status != EarlyDepartureRequest.Status.APPROVED:
            raise ValidationError("لا يمكن تأكيد خروج الطالب إلا بعد اعتماد طلب الانصراف رسمياً.")

        locked_request.status = EarlyDepartureRequest.Status.EXITED
        locked_request.exit_confirmed_at = timezone.now()
        locked_request.exit_confirmed_by = confirmed_by
        locked_request.exit_notes = exit_notes
        locked_request.save(update_fields=[
            "status", "exit_confirmed_at", "exit_confirmed_by", "exit_notes", "updated_at"
        ])

        records = StudentAttendanceRecord.objects.select_for_update().filter(
            school=locked_request.school,
            student=locked_request.student,
            register__date=locked_request.date,
            is_archived=False,
        ).select_related("register")

        for rec in records:
            rec.status_category = AttendanceStatusType.Category.AUTHORIZED_DEPARTURE
            rec.notes = f"انصراف مبكر مصرح به مع ({locked_request.recipient_name})"
            rec.save(update_fields=["status_category", "notes", "updated_at"])

            from apps.attendance.services.attendance_service import cascade_daily_attendance_to_periods
            cascade_daily_attendance_to_periods(rec.register, student=rec.student, user=confirmed_by)

            AttendanceAuditLog.objects.create(
                school=locked_request.school,
                register=rec.register,
                student_record=rec,
                action=AttendanceAuditLog.Action.EARLY_EXIT_CONFIRMED,
                performed_by=confirmed_by,
                reason=exit_notes or "خروج مصرح به من البوابة",
            )

        notify_early_departure_change(locked_request, is_exit=True)

    departure_request.refresh_from_db()
    return departure_request
