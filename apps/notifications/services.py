"""Reliable notification enqueueing and transactional outbox processing."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import base64
import re
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from string import Formatter

from django.conf import settings
from django.core.mail import EmailMessage, get_connection, send_mail
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import (
    ConversationParticipant,
    InboundWebhookMessage,
    Notification,
    NotificationDeliveryAttempt,
    NotificationDeliveryReceipt,
    NotificationPreference,
    NotificationTemplate,
    OutboxEvent,
    PushDevice,
    SchoolMessagingGateway,
)

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    def __init__(self, message: str, *, code: str = "delivery_error", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def enqueue_event(
    *,
    event_name,
    aggregate_type,
    aggregate_id,
    payload,
    idempotency_key,
    school=None,
    available_at=None,
):
    if not idempotency_key:
        raise ValueError("An idempotency key is required for every outbox event.")
    event, _created = OutboxEvent.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "school": school,
            "event_name": event_name,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "payload": payload,
            "available_at": available_at or timezone.now(),
        },
    )
    return event


def _user_belongs_to_school(user, school) -> bool:
    if school is None:
        return True
    from apps.accounts.models import SchoolMembership
    from apps.students.models import Guardian, Student
    from apps.staff.models import StaffMember, Teacher

    now = timezone.now()
    membership = SchoolMembership.objects.filter(
        user=user,
        school=school,
        status=SchoolMembership.Status.ACTIVE,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists()
    return membership or school.owner_id == user.pk or any((
        Student.objects.filter(user=user, school=school, is_archived=False).exists(),
        Guardian.objects.filter(user=user, school=school, is_archived=False).exists(),
        Teacher.objects.filter(user=user, school=school, is_archived=False).exists(),
        StaffMember.objects.filter(user=user, school=school, is_archived=False).exists(),
        ConversationParticipant.objects.filter(
            user=user, school=school, is_active=True, is_archived=False,
        ).exists(),
    ))


def _render_template(*, school, code, channel, variables, language_code="ar"):
    template = NotificationTemplate.objects.filter(
        school=school, code=code, channel=channel, language_code=language_code,
        is_active=True,
    ).first()
    if template is None and school is not None:
        template = NotificationTemplate.objects.filter(
            school__isnull=True, code=code, channel=channel,
            language_code=language_code, is_active=True,
        ).first()
    if template is None:
        raise ValueError(f"قالب الإشعار {code!r} غير موجود أو غير مفعل.")
    schema = template.variables_schema or {}
    required = schema.get("required", []) if isinstance(schema, dict) else schema
    if required and any(name not in variables for name in required):
        raise ValueError("توجد متغيرات مطلوبة مفقودة من قالب الإشعار.")
    allowed = schema.get("properties", {}).keys() if isinstance(schema, dict) and "properties" in schema else None
    if allowed is not None and set(variables) - set(allowed):
        raise ValueError("تحتوي متغيرات القالب على مفاتيح غير مسموح بها.")

    class SafeVariables(dict):
        def __missing__(self, key):
            raise ValueError(f"متغير قالب غير معرف: {key}")

    values = SafeVariables({key: str(value) for key, value in variables.items()})
    try:
        title = Formatter().vformat(template.title_template, (), values)
        body = Formatter().vformat(template.body_template, (), values)
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError("تعذر ملء متغيرات قالب الإشعار.") from exc
    return title, body


@transaction.atomic
def enqueue_notification(
    *,
    recipient,
    school=None,
    channel=Notification.Channel.IN_APP,
    category="general",
    title=None,
    body=None,
    template_code=None,
    variables=None,
    language_code="ar",
    action_url="",
    payload=None,
    idempotency_key="",
):
    """Create an in-app notification immediately or queue an external delivery."""
    if school is not None and not _user_belongs_to_school(recipient, school):
        raise ValueError("المستلم غير مرتبط بالمدرسة المحددة.")
    variables = variables or {}
    if template_code:
        title, body = _render_template(
            school=school, code=template_code, channel=channel,
            variables=variables, language_code=language_code,
        )
    if not title or not body:
        raise ValueError("عنوان الإشعار ومحتواه مطلوبان.")

    if channel != Notification.Channel.IN_APP:
        preference = NotificationPreference.objects.filter(
            user=recipient, category=category, channel=channel,
            school=school,
        ).first()
        if preference is None:
            preference = NotificationPreference.objects.filter(
                user=recipient, category=category, channel=channel,
                school__isnull=True,
            ).first()
        if preference is not None and not preference.is_enabled:
            return None, False

    defaults = {
        "recipient": recipient,
        "school": school,
        "channel": channel,
        "category": category,
        "title": title,
        "body": body,
        "action_url": action_url,
        "payload": payload or {},
        "status": Notification.Status.SENT if channel == Notification.Channel.IN_APP else Notification.Status.QUEUED,
        "sent_at": timezone.now() if channel == Notification.Channel.IN_APP else None,
    }
    if idempotency_key:
        notification, created = Notification.objects.get_or_create(
            idempotency_key=idempotency_key[:120], defaults=defaults,
        )
        if not created and (
            notification.recipient_id != recipient.pk or notification.school_id != getattr(school, "pk", None)
        ):
            raise ValueError("مفتاح منع التكرار مستخدم لإشعار آخر.")
    else:
        notification = Notification.objects.create(**defaults)
        created = True

    if created and channel != Notification.Channel.IN_APP:
        enqueue_event(
            event_name="notification.dispatch",
            aggregate_type="notification",
            aggregate_id=notification.pk,
            payload={"notification_id": str(notification.pk)},
            idempotency_key=f"notification:{notification.pk}",
            school=school,
        )
    return notification, created


def create_in_app_notification(
    *, recipient, title, body, school=None, category="general",
    action_url="", payload=None, idempotency_key="",
):
    return enqueue_notification(
        recipient=recipient,
        title=title,
        body=body,
        school=school,
        category=category,
        channel=Notification.Channel.IN_APP,
        action_url=action_url,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def mark_notification_read(*, notification_id, user, school=None):
    with transaction.atomic():
        queryset = Notification.objects.select_for_update().filter(
            pk=notification_id, recipient=user,
        )
        if school is not None:
            queryset = queryset.filter(school=school)
        notification = queryset.first()
        if notification is None:
            return None
        notification.mark_read()
        return notification


def _resolve_gateway_url(url: str):
    try:
        parsed = urllib.parse.urlsplit(url)
        allowed_schemes = {"https"} | ({"http"} if settings.DEBUG else set())
        if parsed.scheme not in allowed_schemes or not parsed.hostname:
            raise DeliveryError("يجب استخدام HTTPS لبوابة الرسائل.", code="unsafe_gateway_url", retryable=False)
        if parsed.username or parsed.password or parsed.fragment:
            raise DeliveryError("رابط البوابة يحتوي مكونات غير مسموحة.", code="unsafe_gateway_url", retryable=False)
        host = parsed.hostname.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain"}:
            raise DeliveryError("لا يسمح بالاتصال بمضيف محلي.", code="unsafe_gateway_url", retryable=False)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in ({443} if parsed.scheme == "https" else {80}):
            raise DeliveryError("منفذ بوابة الرسائل غير مسموح.", code="unsafe_gateway_url", retryable=False)
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0].split("%", 1)[0] for item in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise DeliveryError("رابط البوابة يحل إلى عنوان شبكة خاصة أو محلية.", code="unsafe_gateway_url", retryable=False)
        return parsed, ips[0], port
    except DeliveryError:
        raise
    except (ValueError, OSError, socket.gaierror) as exc:
        raise DeliveryError("تعذر التحقق من عنوان بوابة الرسائل.", code="gateway_dns_error", retryable=True) from exc


def _public_gateway_url(url: str) -> bool:
    try:
        _resolve_gateway_url(url)
        return True
    except DeliveryError:
        return False


def _gateway_for(school, channel):
    base = SchoolMessagingGateway.objects.filter(channel=channel, is_active=True)
    if school is not None:
        gateway = base.filter(school=school).order_by("-created_at").first()
        if gateway is not None:
            return gateway
    return base.filter(school__isnull=True).order_by("-created_at").first()


def _format_payload(value, values):
    if isinstance(value, dict):
        return {key: _format_payload(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [_format_payload(item, values) for item in value]
    if isinstance(value, str):
        try:
            return value.format_map(values)
        except (KeyError, ValueError) as exc:
            raise DeliveryError("قالب بوابة الرسائل يحتوي متغيراً غير صالح.", code="gateway_template", retryable=False) from exc
    return value


def _post_gateway_json(gateway, payload, idempotency_key):
    parsed, pinned_ip, port = _resolve_gateway_url(gateway.api_endpoint_url)
    provider = gateway.provider
    headers = {
        "Accept": "application/json",
        "User-Agent": "School-ERP-Notifications/1.0",
        "X-Idempotency-Key": idempotency_key,
    }
    endpoint_path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))

    if provider == SchoolMessagingGateway.Provider.TWILIO:
        match = re.search(r"/Accounts/([A-Z0-9]+)/Messages(?:\.json)?$", parsed.path, re.IGNORECASE)
        if not match or not gateway.auth_token or not gateway.sender_id:
            raise DeliveryError("إعداد Twilio يتطلب Account SID وAuth Token ورقم مرسل.", code="twilio_config", retryable=False)
        account_sid = match.group(1)
        credential = base64.b64encode(f"{account_sid}:{gateway.auth_token}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {credential}"
        to_number = str(payload.get("to", ""))
        from_number = gateway.sender_id
        if gateway.channel == SchoolMessagingGateway.Channel.WHATSAPP:
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number if to_number.startswith('+') else '+' + to_number}"
            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number if from_number.startswith('+') else '+' + from_number}"
        form_data = {
            "To": to_number,
            "From": from_number,
            "Body": str(payload.get("body") or payload.get("message") or ""),
        }
        callback_url = payload.get("StatusCallback") or payload.get("status_callback_url")
        if callback_url:
            if not _public_gateway_url(str(callback_url)):
                raise DeliveryError("رابط إيصال Twilio غير آمن.", code="unsafe_status_callback", retryable=False)
            form_data["StatusCallback"] = str(callback_url)
        body = urllib.parse.urlencode(form_data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    elif provider == SchoolMessagingGateway.Provider.ULTRAMSG:
        if not gateway.auth_token or not payload.get("to") or not (payload.get("body") or payload.get("message")):
            raise DeliveryError("إعداد UltraMsg أو محتوى الرسالة غير مكتمل.", code="ultramsg_config", retryable=False)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(key, value) for key, value in query if key.lower() != "token"]
        query.append(("token", gateway.auth_token))
        endpoint_path = urllib.parse.urlunsplit(("", "", parsed.path or "/", urllib.parse.urlencode(query), ""))
        body = urllib.parse.urlencode({
            "to": str(payload["to"]).replace("+", ""),
            "body": str(payload.get("body") or payload.get("message")),
            "priority": "1",
        }).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    elif provider == SchoolMessagingGateway.Provider.INFOBIP:
        if not gateway.auth_token or not gateway.sender_id:
            raise DeliveryError("إعداد Infobip يتطلب App API Key ومعرف مرسل.", code="infobip_config", retryable=False)
        headers["Authorization"] = f"App {gateway.auth_token}"
        destination = str(payload.get("to", ""))
        message_text = str(payload.get("body") or payload.get("message") or "")
        if gateway.channel == SchoolMessagingGateway.Channel.WHATSAPP:
            message = {
                "from": gateway.sender_id,
                "to": destination,
                "content": {"text": message_text},
                "callbackData": idempotency_key,
            }
        else:
            message = {
                "from": gateway.sender_id,
                "destinations": [{"to": destination}],
                "text": message_text,
            }
        body = json.dumps({"messages": [message]}, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    else:
        headers["Content-Type"] = "application/json"
        if gateway.auth_token:
            headers["Authorization"] = f"Bearer {gateway.auth_token}"
            headers["X-API-Key"] = gateway.auth_token
        for name, value in (gateway.custom_headers or {}).items():
            if name.lower() in {
                "authorization", "proxy-authorization", "host", "content-length",
                "x-api-key", "cookie", "set-cookie",
            }:
                continue
            if isinstance(value, (str, int, float)):
                headers[str(name)] = str(value)
        if not isinstance(payload, dict):
            raise DeliveryError("قالب بوابة الرسائل يجب أن ينتج كائن JSON.", code="gateway_template", retryable=False)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    path = urllib.parse.urlunsplit(("", "", parsed.path or "/", urllib.parse.urlsplit(endpoint_path).query, ""))
    if parsed.scheme == "https":
        class PinnedHTTPSConnection(http.client.HTTPSConnection):
            def connect(self):
                sock = socket.create_connection((pinned_ip, self.port), timeout=self.timeout)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        connection_class = PinnedHTTPSConnection
    else:
        class PinnedHTTPConnection(http.client.HTTPConnection):
            def connect(self):
                self.sock = socket.create_connection((pinned_ip, self.port), timeout=self.timeout)
        connection_class = PinnedHTTPConnection

    conn = connection_class(parsed.hostname, port=port, timeout=8)
    try:
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read(65536)
        if response.status < 200 or response.status >= 300:
            raise DeliveryError(
                f"بوابة الرسائل أعادت HTTP {response.status}.",
                code=f"http_{response.status}",
                retryable=response.status in {408, 425, 429} or response.status >= 500,
            )
        try:
            response_data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_data = {}
        reference = response_data.get("message_id") or response_data.get("id") or response_data.get("sid")
        if provider == SchoolMessagingGateway.Provider.INFOBIP:
            messages = response_data.get("messages") or []
            if messages:
                reference = messages[0].get("messageId") or reference
        return str(reference or "")[:160], response.status
    except DeliveryError:
        raise
    except (OSError, http.client.HTTPException, TimeoutError) as exc:
        raise DeliveryError("تعذر الاتصال ببوابة الرسائل.", code="gateway_unreachable", retryable=True) from exc
    finally:
        conn.close()


def _record_attempt(notification, attempt_number, destination, provider, *, succeeded, reference="", code=None, error=None):
    fingerprint = hashlib.sha256(destination.encode("utf-8")).hexdigest() if destination else ""
    NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=attempt_number,
        destination_fingerprint=fingerprint,
        provider=provider,
        status=NotificationDeliveryAttempt.Status.SUCCEEDED if succeeded else NotificationDeliveryAttempt.Status.FAILED,
        provider_reference=reference,
        response_code=code,
        error_code=getattr(error, "code", "") if error else "",
        error_message=str(error)[:500] if error else "",
    )




@transaction.atomic
def _reserve_send_slot(gateway):
    """Atomically reserve one send from a database-backed per-gateway minute window."""
    current = type(gateway).objects.select_for_update().get(pk=gateway.pk)
    now = timezone.now()
    window_start = current.rate_limit_window_started_at
    count = current.rate_limit_window_count
    if window_start is None or (now - window_start).total_seconds() >= 60:
        window_start = now
        count = 0
    if current.rate_limit_per_minute < 1:
        raise DeliveryError("إرسال هذه البوابة معطل بحد معدل يساوي صفراً.", code="gateway_rate_disabled", retryable=False)
    if count >= current.rate_limit_per_minute:
        wait = max(1, 60 - int((now - window_start).total_seconds()))
        raise DeliveryError(
            f"تم بلوغ حد الإرسال للبوابة؛ أعد المحاولة بعد {wait} ثانية.",
            code="gateway_rate_limited", retryable=True,
        )
    current.rate_limit_window_started_at = window_start
    current.rate_limit_window_count = count + 1
    current.save(update_fields=[
        "rate_limit_window_started_at", "rate_limit_window_count", "updated_at",
    ])


def _send_message_to_gateway(*, school, channel, destination, title, body, data, idempotency_key, notification=None, attempt_number=1):
    gateway = _gateway_for(school, channel)
    if gateway is None:
        raise DeliveryError(f"لا توجد بوابة نشطة لقناة {channel}.", code="gateway_not_configured", retryable=False)

    base_values = {
        "to": destination,
        "phone": destination,
        "body": body,
        "message": body,
        "title": title,
        "from": gateway.sender_id,
        "sender_id": gateway.sender_id,
        "idempotency_key": idempotency_key,
        "data": data or {},
    }
    targets = [destination]
    if channel == Notification.Channel.PUSH:
        devices = list(PushDevice.objects.filter(user_id=data.get("recipient_id"), is_active=True))
        if not devices:
            raise DeliveryError("لا توجد أجهزة Push نشطة لهذا المستخدم.", code="no_push_devices", retryable=False)
        targets = [device.push_token for device in devices]

    first_reference = ""
    for target in targets:
        values = dict(base_values)
        values["to"] = target
        values["device_token"] = target if channel == Notification.Channel.PUSH else ""
        payload_template = gateway.custom_payload_template or {}
        payload = _format_payload(payload_template, values) if payload_template else {
            "to": target,
            "from": gateway.sender_id,
            "title": title,
            "body": body,
            "data": data or {},
            "idempotency_key": idempotency_key,
        }
        if not isinstance(payload, dict):
            raise DeliveryError("قالب بوابة الرسائل يجب أن ينتج كائن JSON.", code="gateway_template", retryable=False)
        destination_for_audit = "push-token" if channel == Notification.Channel.PUSH else destination
        try:
            _reserve_send_slot(gateway)
            reference, code = _post_gateway_json(gateway, payload, idempotency_key)
            if notification:
                _record_attempt(
                    notification, attempt_number, destination_for_audit, gateway.provider,
                    succeeded=True, reference=reference, code=code,
                )
            first_reference = first_reference or reference
        except DeliveryError as exc:
            if notification:
                _record_attempt(
                    notification, attempt_number, destination_for_audit, gateway.provider,
                    succeeded=False, code=None, error=exc,
                )
            raise
    return first_reference, gateway.provider


def _dispatch_notification(notification, attempt_number):
    channel = notification.channel
    if channel == Notification.Channel.EMAIL:
        recipient = notification.recipient.email
        if not recipient or not getattr(notification.recipient, "email_verified_at", None):
            raise DeliveryError("لا يوجد بريد إلكتروني موثق أو مسجل للمستلم.", code="missing_email", retryable=False)
        from apps.notifications.models import SchoolEmailGateway
        school_gateway = (
            SchoolEmailGateway.objects.filter(school=notification.school, is_active=True).first()
            if notification.school_id else None
        )
        try:
            if school_gateway:
                connection = get_connection(
                    backend="django.core.mail.backends.smtp.EmailBackend",
                    host=school_gateway.host,
                    port=school_gateway.port,
                    username=school_gateway.username,
                    password=school_gateway.password,
                    use_tls=school_gateway.use_tls,
                    use_ssl=school_gateway.use_ssl,
                    timeout=10,
                )
                _reserve_send_slot(school_gateway)
                email = EmailMessage(
                    subject=notification.title,
                    body=notification.body,
                    from_email=school_gateway.from_email,
                    to=[recipient],
                    connection=connection,
                )
                sent = email.send(fail_silently=False)
                provider = "school-smtp"
            else:
                sent = send_mail(
                    subject=notification.title,
                    message=notification.body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                provider = "django-email"
        except Exception as exc:
            raise DeliveryError("تعذر إرسال البريد الإلكتروني.", code="smtp_error", retryable=True) from exc
        if sent != 1:
            raise DeliveryError("لم يقبل خادم البريد الرسالة.", code="email_rejected", retryable=True)
        _record_attempt(notification, attempt_number, recipient, provider, succeeded=True)
        return "", "email"

    if channel in {Notification.Channel.SMS, Notification.Channel.WHATSAPP, Notification.Channel.PUSH}:
        destination = notification.recipient.phone
        if channel != Notification.Channel.PUSH and (not destination or not getattr(notification.recipient, "phone_verified_at", None)):
            raise DeliveryError("لا يوجد رقم هاتف للمستلم.", code="missing_phone", retryable=False)
        return _send_message_to_gateway(
            school=notification.school,
            channel=channel,
            destination=destination,
            title=notification.title,
            body=notification.body,
            data={**(notification.payload or {}), "recipient_id": str(notification.recipient_id), "action_url": notification.action_url},
            idempotency_key=notification.idempotency_key or str(notification.pk),
            notification=notification,
            attempt_number=attempt_number,
        )

    raise DeliveryError(f"قناة إشعار غير مدعومة: {channel}", code="unsupported_channel", retryable=False)


def _safe_whatsapp_auto_reply(inbound, gateway, message_text):
    """Reply only to verified, directly linked accounts; never infer identity from student numbers."""
    from apps.students.models import Guardian, Student

    school = inbound.school
    phone = inbound.sender_phone.replace("+", "").replace(" ", "").strip()
    phone_variants = [phone, f"+{phone}"]
    student = Student.objects.filter(
        school=school, is_archived=False, user__phone__in=phone_variants,
        user__phone_verified_at__isnull=False, user__status="active",
    ).select_related("section").first()
    guardian = None
    if student is None:
        guardian = Guardian.objects.filter(
            school=school, is_archived=False, user__phone__in=phone_variants,
            user__phone_verified_at__isnull=False, user__status="active",
        ).select_related("user").first()
        children = guardian.children.filter(school=school, is_archived=False) if guardian else Student.objects.none()
        if children.count() == 1:
            student = children.first()
        elif children.exists():
            return "تم التحقق من حساب ولي الأمر. يرجى تحديد اسم الطالب المطلوب عبر تطبيق المدرسة لضمان عرض بياناته الصحيحة."

    message_text = str(message_text or "")[:2000]
    if student is None:
        return f"أهلاً بكم في {school.name}. لاستعراض بيانات الطلاب يرجى استخدام تطبيق المدرسة بالحساب الموثق."

    name = student.get_full_name()
    if any(word in message_text for word in ("جدول", "حصص", "حصة")):
        from apps.copilot.services.ai_student import fetch_today_lessons
        result = fetch_today_lessons(str(student.pk))
        lessons = result.get("lessons", [])
        return "\n".join(
            [f"جدول {name}:"] + [
                f"الحصة {item['period']}: {item['subject']} ({item['time']})"
                for item in lessons[:8]
            ]
        ) if lessons else f"لا يوجد جدول حصص مسجل حالياً للطالب {name}."
    if any(word in message_text for word in ("واجب", "واجبات", "تكليف")):
        from apps.copilot.services.ai_student import fetch_pending_homework
        result = fetch_pending_homework(str(student.pk))
        items = result.get("pending_homeworks", [])
        return "\n".join([f"الواجبات المعلقة لـ {name}:"] + [
            f"{item['subject']}: {item['title']} - {item['due_date']}"
            for item in items[:8]
        ]) if items else f"لا توجد واجبات معلقة حالياً للطالب {name}."
    if any(word in message_text for word in ("درجة", "درجات", "نتيجة", "نتائج")):
        from apps.copilot.services.ai_student import fetch_academic_grades
        result = fetch_academic_grades(str(student.pk))
        grades = result.get("recent_grades", [])
        return "\n".join([f"النتائج المنشورة لـ {name}:"] + [
            f"{item['subject']}: {item['score']}/{item['max_score']}"
            for item in grades[:8]
        ]) if grades else f"لم تُنشر درجات جديدة للطالب {name}."
    return f"مرحباً {name}. يمكن السؤال عن الجدول والواجبات والدرجات المنشورة."


def _process_inbound_webhook(event):
    inbound_id = event.payload.get("inbound_id")
    inbound = InboundWebhookMessage.objects.select_related("school").filter(pk=inbound_id).first()
    if inbound is None or inbound.processed:
        return
    gateway = SchoolMessagingGateway.objects.filter(
        school=inbound.school,
        channel=SchoolMessagingGateway.Channel.WHATSAPP,
        is_active=True,
    ).order_by("-created_at").first()
    if gateway is None or not gateway.auto_ai_reply:
        inbound.processed = True
        inbound.save(update_fields=["processed", "updated_at"])
        return
    try:
        reply = _safe_whatsapp_auto_reply(inbound, gateway, event.payload.get("message_text", ""))
        _send_message_to_gateway(
            school=inbound.school,
            channel=Notification.Channel.WHATSAPP,
            destination=inbound.sender_phone,
            title="",
            body=reply,
            data={},
            idempotency_key=f"whatsapp-reply:{inbound.pk}",
            attempt_number=event.attempts,
        )
        inbound.processed = True
        inbound.last_error = ""
        inbound.save(update_fields=["processed", "last_error", "updated_at"])
    except Exception as exc:
        inbound.last_error = str(exc)[:500]
        inbound.save(update_fields=["last_error", "updated_at"])
        raise


def _handle_outbox_event(event):
    if event.event_name == "notification.dispatch":
        notification = Notification.objects.select_related("recipient", "school").filter(
            pk=event.payload.get("notification_id"),
        ).first()
        if notification is None:
            raise DeliveryError("الإشعار المرتبط بالحدث غير موجود.", code="notification_missing", retryable=False)
        if notification.status in {Notification.Status.CANCELLED, Notification.Status.SENT, Notification.Status.DELIVERED, Notification.Status.READ}:
            return
        reference, provider = _dispatch_notification(notification, event.attempts)
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.provider_reference = reference
        notification.failure_reason = ""
        notification.save(update_fields=["status", "sent_at", "provider_reference", "failure_reason", "updated_at"])
        return
    if event.event_name == "notification.delivery_receipt":
        reference = str(event.payload.get("provider_reference", ""))[:160]
        provider_status = event.payload.get("status")
        provider = str(event.payload.get("provider", ""))[:40]
        error_code = str(event.payload.get("error_code", ""))[:80]
        attempt = NotificationDeliveryAttempt.objects.select_related("notification").filter(
            provider_reference=reference,
            notification__school=event.school,
        ).exclude(provider_reference="").order_by("-attempted_at").first()
        if attempt is not None and provider and attempt.provider and provider != attempt.provider:
            raise DeliveryError("مرجع إيصال التسليم لا يطابق مزود الإرسال.", code="receipt_provider_mismatch", retryable=False)
        if attempt is None:
            raise DeliveryError(
                "إيصال التسليم وصل قبل حفظ مرجع محاولة الإرسال؛ ستعاد معالجته.",
                code="delivery_attempt_not_found", retryable=True,
            )
        notification = attempt.notification
        receipt_status = {
            "accepted": NotificationDeliveryReceipt.Status.SENT,
            "sent": NotificationDeliveryReceipt.Status.SENT,
            "delivered": NotificationDeliveryReceipt.Status.DELIVERED,
            "read": NotificationDeliveryReceipt.Status.READ,
            "failed": NotificationDeliveryReceipt.Status.FAILED,
        }.get(provider_status)
        if receipt_status is None:
            raise DeliveryError("حالة إيصال التسليم غير مدعومة.", code="unknown_receipt_status", retryable=False)
        NotificationDeliveryReceipt.objects.get_or_create(
            notification=notification,
            provider=provider or attempt.provider or "unknown",
            provider_reference=reference,
            status=receipt_status,
            defaults={"error_code": error_code},
        )
        with transaction.atomic():
            locked = Notification.objects.select_for_update().get(pk=notification.pk)
            if receipt_status == NotificationDeliveryReceipt.Status.DELIVERED:
                if locked.status not in {Notification.Status.READ, Notification.Status.FAILED}:
                    locked.status = Notification.Status.DELIVERED
                    locked.delivered_at = locked.delivered_at or timezone.now()
                    locked.save(update_fields=["status", "delivered_at", "updated_at"])
            elif receipt_status == NotificationDeliveryReceipt.Status.READ:
                if locked.status != Notification.Status.FAILED:
                    locked.status = Notification.Status.READ
                    locked.is_read = True
                    locked.read_at = locked.read_at or timezone.now()
                    locked.delivered_at = locked.delivered_at or timezone.now()
                    locked.save(update_fields=["status", "is_read", "read_at", "delivered_at", "updated_at"])
            elif receipt_status == NotificationDeliveryReceipt.Status.FAILED:
                if locked.status not in {Notification.Status.DELIVERED, Notification.Status.READ}:
                    locked.status = Notification.Status.FAILED
                    locked.failure_reason = error_code or "فشل التسليم لدى المزود."
                    locked.save(update_fields=["status", "failure_reason", "updated_at"])
        return
    if event.event_name == "webhook.whatsapp.inbound":
        _process_inbound_webhook(event)
        return
    raise DeliveryError(f"نوع Outbox غير معروف: {event.event_name}", code="unknown_event", retryable=False)


def process_outbox_batch(*, limit=50, stale_after_seconds=600):
    """Claim a batch safely, execute outside the DB transaction, then persist retry state."""
    now = timezone.now()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    stats = {"claimed": 0, "succeeded": 0, "retrying": 0, "failed": 0}

    with transaction.atomic():
        queryset = OutboxEvent.objects.filter(
            Q(status=OutboxEvent.Status.PENDING, available_at__lte=now)
            | Q(status=OutboxEvent.Status.PROCESSING, locked_at__lt=stale_before)
            | Q(status=OutboxEvent.Status.PROCESSING, locked_at__isnull=True)
        ).order_by("available_at", "created_at")
        if connection.features.has_select_for_update:
            queryset = queryset.select_for_update(
                skip_locked=connection.features.has_select_for_update_skip_locked,
            )
        events = list(queryset[:max(1, min(int(limit), 500))])
        for event in events:
            event.status = OutboxEvent.Status.PROCESSING
            event.locked_at = now
            event.attempts += 1
            event.save(update_fields=["status", "locked_at", "attempts", "updated_at"])
    stats["claimed"] = len(events)

    for event in events:
        try:
            _handle_outbox_event(event)
        except Exception as exc:
            retryable = getattr(exc, "retryable", True)
            code = getattr(exc, "code", "unexpected_error")
            with transaction.atomic():
                event.last_error = f"{code}: {str(exc)}"[:4000]
                event.locked_at = None
                if retryable and event.attempts < event.max_attempts:
                    delay = min(60 * (2 ** max(event.attempts - 1, 0)), 3600)
                    event.status = OutboxEvent.Status.PENDING
                    event.available_at = timezone.now() + timedelta(seconds=delay)
                    stats["retrying"] += 1
                else:
                    event.status = OutboxEvent.Status.FAILED
                    event.processed_at = timezone.now()
                    stats["failed"] += 1
                event.save(update_fields=[
                    "status", "locked_at", "last_error", "available_at",
                    "processed_at", "updated_at",
                ])
                if event.event_name == "notification.dispatch":
                    Notification.objects.filter(pk=event.payload.get("notification_id")).update(
                        status=Notification.Status.FAILED if event.status == OutboxEvent.Status.FAILED else Notification.Status.QUEUED,
                        failure_reason=str(exc)[:500],
                        updated_at=timezone.now(),
                    )
            logger.warning("Notification outbox event %s failed (%s)", event.pk, code)
        else:
            with transaction.atomic():
                event.status = OutboxEvent.Status.PROCESSED
                event.processed_at = timezone.now()
                event.locked_at = None
                event.last_error = ""
                if event.event_name == "webhook.whatsapp.inbound":
                    event.payload = {"inbound_id": event.payload.get("inbound_id")}
                event.save(update_fields=[
                    "status", "processed_at", "locked_at", "last_error", "updated_at",
                ])
                stats["succeeded"] += 1
    return stats
