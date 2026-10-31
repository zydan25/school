"""
apps/notifications/api/views.py
REST API views for WhatsApp / SMS Gateway webhooks and intelligent AI Auto-Responders.
Supports per-school independent webhook routing, student/parent query resolution,
and automated authoritative Arabic replies.
"""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.request

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.copilot.services.ai_student import (
    fetch_academic_grades,
    fetch_pending_homework,
    fetch_today_lessons,
)
from apps.notifications.models import Notification, SchoolMessagingGateway
from apps.students.models import Guardian, Student
from apps.tenants.models import School

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
            student = guardian.children.filter(is_archived=False).first()

    # If student or guardian is identified, provide personalized school assistant response
    if student:
        st_name = f"{student.first_name} {student.last_name}"

        if any(w in message_text for w in ["جدول", "حصص", "حصة", "اليوم"]):
            schedule_data = fetch_today_lessons(str(student.id))
            lessons = schedule_data.get("lessons", [])
            if lessons:
                lines = [f"أهلاً بك. جدول حصص الطالب {st_name} لليوم ({schedule_data.get('day')}):"]
                for lesson_item in lessons:
                    lines.append(f"• الحصة {lesson_item['period']}: {lesson_item['subject']} ({lesson_item['time']}) - أ/ {lesson_item['teacher']}")
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

        if not hub_mode and not hub_verify_token:
            return Response({"status": "active", "service": "whatsapp_webhook"}, status=status.HTTP_200_OK)

        if hub_mode == "subscribe":
            gateway = None
            if school_code:
                gateway = SchoolMessagingGateway.objects.filter(
                    school__code=school_code,
                    channel=SchoolMessagingGateway.Channel.WHATSAPP,
                    is_active=True,
                ).first()
            else:
                gateway = SchoolMessagingGateway.objects.filter(
                    school__isnull=True,
                    channel=SchoolMessagingGateway.Channel.WHATSAPP,
                    is_active=True,
                ).first()

            if gateway and gateway.webhook_verify_token:
                if hub_verify_token == gateway.webhook_verify_token:
                    return Response(int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge, status=status.HTTP_200_OK)
            return Response({"detail": "فشل التحقق: رمز التحقق غير مطابق أو البوابة غير مهيأة."}, status=status.HTTP_403_FORBIDDEN)

        return Response({"detail": "طلب غير صالح: وضع التحقق hub.mode غير مطابق."}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, school_code=None, *args, **kwargs):
        """استقبال رسالة واتساب واردة ومعالجتها بالرد الذكي الفوري مع التحقق الأمني الكامل."""
        payload = request.data or {}
        school = None

        school_code = school_code or request.query_params.get("school_code") or request.headers.get("X-School-Code")
        if school_code:
            school = School.objects.filter(code=school_code, is_archived=False).first()

        # Parse sender phone and incoming text
        sender_phone = ""
        message_text = ""
        extracted_msg_id = ""

        # Format 0: Meta / WhatsApp Cloud API format {"entry": [{"changes": [{"value": {"messages": [...]}}]}]}
        if "entry" in payload and isinstance(payload["entry"], list) and payload["entry"]:
            try:
                entry0 = payload["entry"][0]
                changes = entry0.get("changes", [])
                if changes:
                    value = changes[0].get("value", {})
                    messages = value.get("messages", [])
                    if messages:
                        msg0 = messages[0]
                        sender_phone = str(msg0.get("from", ""))
                        extracted_msg_id = str(msg0.get("id", ""))
                        text_obj = msg0.get("text", {})
                        if isinstance(text_obj, dict):
                            message_text = str(text_obj.get("body", ""))
                        elif isinstance(text_obj, str):
                            message_text = text_obj
            except Exception:
                pass

        # Format 1: UltraMsg format {"data": {"from": "...", "body": "..."}}
        if not sender_phone and "data" in payload and isinstance(payload["data"], dict):
            sender_phone = str(payload["data"].get("from", ""))
            message_text = str(payload["data"].get("body", ""))
            extracted_msg_id = str(payload["data"].get("id", ""))
        # Format 2: Twilio format {"From": "whatsapp:+...", "Body": "..."}
        elif not sender_phone and "From" in payload and "Body" in payload:
            sender_phone = str(payload.get("From", "")).replace("whatsapp:", "")
            message_text = str(payload.get("Body", ""))
            extracted_msg_id = str(payload.get("MessageSid", ""))
        # Format 3: Generic payload {"from": "...", "message": "..."}
        elif not sender_phone:
            sender_phone = str(payload.get("from") or payload.get("phone") or payload.get("sender") or "")
            message_text = str(payload.get("message") or payload.get("text") or payload.get("body") or "")
            extracted_msg_id = str(payload.get("id") or payload.get("message_id") or "")

        if not sender_phone or not message_text:
            return Response({"status": "ignored", "reason": "No sender or body found in payload."}, status=status.HTTP_200_OK)

        clean_phone = sender_phone.replace("+", "").replace(" ", "").strip()

        # Fallback to identify school securely by verified student/guardian phone if school_code was not in URL
        if not school:
            candidate_schools = list(School.objects.filter(
                Q(students__in=Student.objects.filter(student_q_phone(clean_phone), is_archived=False)) |
                Q(guardians__in=Guardian.objects.filter(guardian_q_phone(clean_phone), is_archived=False)),
                is_archived=False,
            ).distinct())
            if len(candidate_schools) == 1:
                school = candidate_schools[0]
            elif len(candidate_schools) > 1:
                return Response(
                    {"status": "error", "message": "رقم الهاتف مسجل في أكثر من مدرسة؛ يلزم تحديد رمز المدرسة بالرابط."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not school:
            return Response({"status": "error", "message": "لم يتم العثور على مدرسة مصرح بها لهذا الويب هوك."}, status=status.HTTP_404_NOT_FOUND)

        # Fail closed: an inbound webhook is accepted only for an active gateway
        # with a configured signing secret and a valid signature.
        gateway = SchoolMessagingGateway.objects.filter(
            school=school,
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            is_active=True,
        ).first()
        if gateway is None or not gateway.webhook_verify_token:
            return Response(
                {"detail": "بوابة الواتساب أو سر التحقق غير مهيأ؛ تم رفض الرسالة."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sig_header = request.headers.get("X-Hub-Signature-256")
        if not sig_header:
            return Response(
                {"detail": "ترويسة التوقيع X-Hub-Signature-256 مطلوبة ومفقودة في الطلب."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        import hmac
        expected_sig = "sha256=" + hmac.new(
            gateway.webhook_verify_token.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected_sig):
            return Response({"detail": "توقيع الرسالة غير صحيح."}, status=status.HTTP_403_FORBIDDEN)

        # Permanent deduplication and lifecycle state tracking
        from apps.notifications.models import InboundWebhookMessage
        provider_msg_id = str(
            extracted_msg_id or
            payload.get("id") or 
            payload.get("message_id") or 
            payload.get("MessageSid") or
            (payload.get("data") and isinstance(payload["data"], dict) and payload["data"].get("id")) or
            f"hash_{hashlib.sha256((clean_phone + message_text.strip()).encode()).hexdigest()[:24]}"
        )

        existing_msg = InboundWebhookMessage.objects.filter(school=school, provider_msg_id=provider_msg_id).first()
        if existing_msg and existing_msg.processed:
            return Response({"status": "duplicate_ignored", "reason": "Message already processed."}, status=status.HTTP_200_OK)

        if not existing_msg:
            try:
                existing_msg = InboundWebhookMessage.objects.create(
                    school=school,
                    provider_msg_id=provider_msg_id,
                    sender_phone=clean_phone,
                    processed=False,
                )
            except Exception:
                return Response({"status": "duplicate_ignored", "reason": "Message already processed."}, status=status.HTTP_200_OK)

        # Check if gateway has AI auto-reply enabled
        reply_text = ""
        if not gateway or gateway.auto_ai_reply:
            reply_text = _generate_school_ai_reply(school, sender_phone, message_text)

        # Optional dispatch to actual WhatsApp Gateway API if configured
        if gateway and gateway.api_endpoint_url and gateway.auth_token and reply_text:
            _dispatch_to_gateway(gateway, sender_phone, reply_text)

        # Mark message as successfully processed
        existing_msg.processed = True
        existing_msg.save(update_fields=["processed"])

        return Response({
            "status": "success",
            "school": school.code,
            "auto_reply": reply_text if reply_text else None,
            "timestamp": timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


class SchoolWhatsAppWebhookAPIView(WhatsAppWebhookAPIView):
    """نقطة استقبال الويب هوك المخصصة لرمز المدرسة."""
    pass


def _is_safe_url(url: str) -> bool:
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"):
            return False
        if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
            return False
        return True
    except Exception:
        return False


def _dispatch_to_gateway(gateway: SchoolMessagingGateway, recipient: str, text: str):
    """إرسال فعلي للرد إلى خادم مزود خدمة الواتساب عبر HTTP REST API مع حماية SSRF."""
    try:
        url = gateway.api_endpoint_url
        if not _is_safe_url(url):
            logger.warning(f"Blocked SSRF attempt or invalid gateway URL: {url}")
            return
        payload = {
            "token": gateway.auth_token,
            "to": recipient,
            "body": text,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "School-ERP-WhatsApp-Gateway/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        # Gateway failure is captured without breaking incoming webhook flow
        pass


class UserNotificationsAPIView(APIView):
    """
    استعراض إشعارات المستخدم المسجل حالياً، وحساب عدد غير المقروء منها،
    وإمكانية تحديد الكل كمقروء.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        notifications_qs = Notification.objects.filter(recipient=user).order_by("-created_at")
        unread_only = request.query_params.get("unread_only", "").lower() in ("true", "1")
        if unread_only:
            notifications_qs = notifications_qs.filter(is_read=False)

        unread_count = Notification.objects.filter(recipient=user, is_read=False).count()
        recent = notifications_qs[:50]
        data = [
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "category": n.category,
                "channel": n.channel,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in recent
        ]
        return Response({
            "unread_count": unread_count,
            "notifications": data,
        })

    def post(self, request, *args, **kwargs):
        """تحديد جميع إشعارات المستخدم كمقروءة دفعة واحدة."""
        user = request.user
        now = timezone.now()
        updated = Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True,
            read_at=now,
            status=Notification.Status.READ,
        )
        return Response({"status": "success", "marked_read_count": updated})


class MarkNotificationReadAPIView(APIView):
    """
    تحديد إشعار محدد كمقروء للمستخدم.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id, *args, **kwargs):
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.mark_read()
        return Response({"status": "success", "id": str(notification.id), "is_read": True})
