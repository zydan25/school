"""
apps/notifications/api/views.py
REST API views for WhatsApp / SMS Gateway webhooks and intelligent AI Auto-Responders.
Supports per-school independent webhook routing, student/parent query resolution,
and automated authoritative Arabic replies.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.tenants.models import School
from apps.students.models import Student, Guardian
from apps.notifications.models import Notification, SchoolMessagingGateway
from apps.copilot.services.ai_student import fetch_today_lessons, fetch_pending_homework, fetch_academic_grades

logger = logging.getLogger(__name__)


def _generate_school_ai_reply(school: School, sender_phone: str, message_text: str) -> str:
    """
    محرك الرد الآلي الذكي للواتساب استناداً لسياق المدرسة وهوية المرسل.
    يتعرف على ما إذا كان المرسل ولي أمر أو طالباً أو عميلاً يستفسر عن القبول والتسجيل.
    """
    # Clean phone number
    clean_phone = sender_phone.replace("+", "").replace(" ", "").strip()
    
    # 1. Check if sender is a student
    student = Student.objects.filter(
        school=school,
        is_archived=False,
    ).filter(
        student_q_phone(clean_phone)
    ).first()

    # 2. Check if sender is a guardian
    guardian = None
    if not student:
        guardian = Guardian.objects.filter(
            school=school,
            is_archived=False,
        ).filter(
            guardian_q_phone(clean_phone)
        ).first()
        if guardian:
            student = guardian.students.filter(is_archived=False).first()

    # If student or guardian is identified, provide personalized school assistant response
    if student:
        st_name = f"{student.first_name} {student.last_name}"
        msg_lower = message_text.lower()

        if any(w in message_text for w in ["جدول", "حصص", "حصة", "اليوم"]):
            schedule_data = fetch_today_lessons(str(student.id))
            lessons = schedule_data.get("lessons", [])
            if lessons:
                lines = [f"أهلاً بك. جدول حصص الطالب {st_name} لليوم ({schedule_data.get('day')}):"]
                for l in lessons:
                    lines.append(f"• الحصة {l['period']}: {l['subject']} ({l['time']}) - أ/ {l['teacher']}")
                return "\n".join(lines)
            return f"مرحباً بك. لا توجد حصص مجدولة مسجلة للطالب {st_name} اليوم."

        elif any(w in message_text for w in ["واجب", "واجبات", "تكليف", "تسليم"]):
            hw_data = fetch_pending_homework(str(student.id))
            pending = hw_data.get("pending_homeworks", [])
            if pending:
                lines = [f"مرحباً بك. الواجبات المعلقة للطالب {st_name}:"]
                for h in pending:
                    lines.append(f"• {h['subject']}: {h['title']} (موعد التسليم: {h['due_date']})")
                return "\n".join(lines)
            return f"أهلاً بك. لا توجد واجبات معلقة حالياً على الطالب {st_name}. أحسنت!"

        elif any(w in message_text for w in ["درجة", "درجات", "شهادة", "نتيجة", "نتائج", "تقييم"]):
            grades_data = fetch_academic_grades(str(student.id))
            grades = grades_data.get("recent_grades", [])
            if grades:
                lines = [f"مرحباً بك. درجات الطالب {st_name} الأخيرة (المعدل: {grades_data.get('overall_percentage')}%):"]
                for g in grades[:5]:
                    lines.append(f"• {g['subject']} ({g['assessment_title']}): {g['score']}/{g['max_score']}")
                return "\n".join(lines)
            return f"أهلاً بك. لم تُنشر درجات جديدة بعد للطالب {st_name}."

        elif any(w in message_text for w in ["رسوم", "قسط", "سداد", "فاتورة", "حساب"]):
            from apps.reports.selectors.financial_reports import get_student_statement_of_account
            stmt = get_student_statement_of_account(student)
            summary = stmt["summary"]
            return (
                f"مرحباً بك. الموقف المالي للطالب {st_name} لدى {school.name}:\n"
                f"• إجمالي المطالبات: {summary['net_payable']} YER\n"
                f"• المسدد حتى الآن: {summary['total_paid']} YER\n"
                f"• الرصيد المتبقي المطلوب: {summary['outstanding_balance']} YER\n"
                f"نشكركم على تعاونكم وحرصكم المستمر."
            )

        return (
            f"مرحباً بكم في المساعد الذكي لـ {school.name}!\n"
            f"تم التعرف على الطالب: {st_name} ({student.section.name if student.section else ''}).\n"
            f"يمكنكم السؤال عن: (الجدول اليومي، الواجبات، الدرجات، أو الرسوم والأقساط)."
        )

    # General / Public prospective client inquiries (القبول، الفروع، المراحل، الموقع)
    return (
        f"أهلاً وسهلاً بكم في {school.name}.\n"
        f"يسعدنا تواصلكم واستفساركم. مرحباً بكم في العام الدراسي الجديد!\n"
        f"• المراحل المتاحة: الابتدائية، المتوسطة، والثانوية.\n"
        f"• للاستفسار عن القبول والتسجيل أو حجز مقعد، يرجى زيارة الإدارة أو تزويدنا بالاسم ورقم الهاتف ليتواصل معكم قسم القبول.\n"
        f"مع تحيات إدارة {school.name}."
    )


def student_q_phone(clean_phone: str):
    from django.db.models import Q
    return (
        Q(user__phone__icontains=clean_phone[-9:]) |
        Q(student_id_number__icontains=clean_phone[-9:])
    )


def guardian_q_phone(clean_phone: str):
    from django.db.models import Q
    return (
        Q(user__phone__icontains=clean_phone[-9:]) |
        Q(emergency_phone__icontains=clean_phone[-9:])
    )


class WhatsAppWebhookAPIView(APIView):
    """
    نقطة استقبال الويب هوك لرسائل الواتساب الواردة لكل مدرسة بشكل مستقل.
    تدعم التحقق الأمني (Webhook Verification) وتوليد الرد الآلي الذكي عبر الذكاء الاصطناعي.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, school_code=None, *args, **kwargs):
        """التحقق من صحة رابط الويب هوك (Webhook Handshake / Verification)."""
        hub_mode = request.query_params.get("hub.mode")
        hub_challenge = request.query_params.get("hub.challenge")
        hub_verify_token = request.query_params.get("hub.verify_token")

        if school_code:
            gateway = SchoolMessagingGateway.objects.filter(
                school__code=school_code,
                channel=SchoolMessagingGateway.Channel.WHATSAPP,
                is_active=True,
            ).first()
            if gateway and gateway.webhook_verify_token:
                if hub_verify_token == gateway.webhook_verify_token:
                    return Response(int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge)

        return Response({"status": "active", "service": "school-whatsapp-webhook"})

    def post(self, request, school_code=None, *args, **kwargs):
        """استقبال رسالة واتساب واردة ومعالجتها بالرد الذكي الفوري."""
        payload = request.data or {}
        school = None

        if school_code:
            school = School.objects.filter(code=school_code, is_archived=False).first()

        # Parse sender phone and incoming text
        sender_phone = ""
        message_text = ""

        # Format 1: UltraMsg format {"data": {"from": "...", "body": "..."}}
        if "data" in payload and isinstance(payload["data"], dict):
            sender_phone = str(payload["data"].get("from", ""))
            message_text = str(payload["data"].get("body", ""))
        # Format 2: Twilio format {"From": "whatsapp:+...", "Body": "..."}
        elif "From" in payload and "Body" in payload:
            sender_phone = str(payload.get("From", "")).replace("whatsapp:", "")
            message_text = str(payload.get("Body", ""))
        # Format 3: Generic payload {"from": "...", "message": "..."}
        else:
            sender_phone = str(payload.get("from") or payload.get("phone") or payload.get("sender") or "")
            message_text = str(payload.get("message") or payload.get("text") or payload.get("body") or "")

        if not sender_phone or not message_text:
            return Response({"status": "ignored", "reason": "No sender or body found in payload."}, status=status.HTTP_200_OK)

        # Fallback to identify school by phone if school_code was not in URL
        if not school:
            student = Student.objects.filter(
                user__phone__icontains=sender_phone[-9:],
                is_archived=False,
            ).select_related("school").first()
            if student:
                school = student.school
            else:
                school = School.objects.filter(status=School.Status.ACTIVE).first()

        if not school:
            return Response({"status": "error", "message": "School context not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if gateway has AI auto-reply enabled
        gateway = SchoolMessagingGateway.objects.filter(
            school=school,
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            is_active=True,
        ).first()

        reply_text = ""
        if not gateway or gateway.auto_ai_reply:
            reply_text = _generate_school_ai_reply(school, sender_phone, message_text)

        return Response({
            "status": "success",
            "school": school.code,
            "sender": sender_phone,
            "received_message": message_text,
            "auto_reply": reply_text,
            "timestamp": timezone.now().isoformat(),
        })
