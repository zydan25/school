"""Notification helpers for attendance and absence events."""
from __future__ import annotations

import hashlib
import logging
from apps.notifications.models import Notification
from apps.notifications.services import enqueue_notification

logger = logging.getLogger(__name__)


def notify_guardian_attendance_event(
    school,
    student,
    title: str,
    body: str,
    category: str = "attendance",
) -> list[Notification]:
    """ينشئ إشعاراً داخل النظام لجميع أولياء أمور الطالب المخولين باستلام الإشعارات."""
    created = []
    try:
        guardian_rels = student.guardians.filter(
            receives_notifications=True,
            is_archived=False,
        ).select_related("guardian__user")
        
        for rel in guardian_rels:
            user = rel.guardian.user
            if not user:
                continue
            fingerprint = hashlib.sha256(
                f"{school.pk}:{student.pk}:{user.pk}:{category}:{title}:{body}".encode("utf-8")
            ).hexdigest()
            notif, was_created = enqueue_notification(
                school=school,
                recipient=user,
                channel=Notification.Channel.IN_APP,
                category=category,
                title=title,
                body=body,
                idempotency_key=f"attendance:{fingerprint}",
            )
            if was_created and notif is not None:
                created.append(notif)
    except Exception as exc:
        logger.warning("فشل إرسال إشعار الحضور لولي الأمر: %s", exc)
    return created


def notify_absence_or_late(school, student, date, status_category: str, late_minutes: int = 0):
    """إشعار ولي الأمر عند رصد غياب أو تأخر للطالب."""
    date_str = date.strftime("%Y-%m-%d")
    student_name = f"{student.first_name} {student.last_name}"
    
    if status_category == "absent_unexcused":
        title = f"تنبيه غياب: {student_name}"
        body = f"نحيطكم علماً بأنه تم تسجيل غياب بدون عذر مسبق للطالب/ـة {student_name} بتاريخ {date_str}. يرجى تزويد المدرسة بالعذر المقبول خلال المهلة المحددة."
    elif status_category == "late":
        title = f"تنبيه تأخر صباحي: {student_name}"
        body = f"نحيطكم علماً بأن الطالب/ـة {student_name} وصل متأخراً عن الطابور الصباحي بتاريخ {date_str} بمقدار {late_minutes} دقيقة."
    elif status_category == "authorized_departure":
        title = f"إشعار انصراف مصرح: {student_name}"
        body = f"تم تسجيل خروج الطالب/ـة {student_name} من المدرسة بموجب إذن رسمي بتاريخ {date_str}."
    else:
        return []

    return notify_guardian_attendance_event(school, student, title, body, category="attendance_alert")


def notify_excuse_status_change(excuse_request):
    """إشعار ولي الأمر عند مراجعة واعتماد أو رفض عذر الغياب."""
    student_name = f"{excuse_request.student.first_name} {excuse_request.student.last_name}"
    status_label = excuse_request.get_status_display()
    title = f"تحديث طلب عذر الغياب: {student_name}"
    notes = f" ملاحظات: {excuse_request.review_notes}" if excuse_request.review_notes else ""
    body = f"تم تحديث حالة طلب عذر الغياب المقدم للطالب/ـة {student_name} للفترة من {excuse_request.start_date} إلى {excuse_request.end_date} إلى: {status_label}.{notes}"
    return notify_guardian_attendance_event(excuse_request.school, excuse_request.student, title, body, category="excuse_review")


def notify_early_departure_change(departure_request, is_exit: bool = False):
    """إشعار ولي الأمر بتحديث حالة طلب الانصراف المبكر أو خروج الطالب من البوابة."""
    student_name = f"{departure_request.student.first_name} {departure_request.student.last_name}"
    if is_exit:
        title = f"تأكيد خروج الطالب من بوابة المدرسة: {student_name}"
        body = f"تم استلام الطالب/ـة {student_name} وخروجه بأمان من بوابة المدرسة بواسطة ({departure_request.recipient_name}) بتاريخ {departure_request.date}."
    else:
        title = f"حالة طلب الانصراف المبكر: {student_name}"
        body = f"تم تحديث حالة طلب الانصراف المبكر للطالب/ـة {student_name} بتاريخ {departure_request.date} إلى: {departure_request.get_status_display()}."
    return notify_guardian_attendance_event(departure_request.school, departure_request.student, title, body, category="early_departure")
