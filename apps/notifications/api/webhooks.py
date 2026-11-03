"""Signed WhatsApp message and delivery-status webhook intake."""
from __future__ import annotations

import base64
import hashlib
import hmac

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import InboundWebhookMessage, SchoolMessagingGateway
from apps.notifications.services import enqueue_event
from apps.tenants.models import School


def _plain_payload(request):
    if isinstance(request.data, dict):
        return request.data
    if hasattr(request.data, "dict"):
        return request.data.dict()
    return {}


def _extract_message(payload):
    sender = message = provider_id = ""
    if isinstance(payload.get("entry"), list):
        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if messages:
                    item = messages[0]
                    sender = str(item.get("from", ""))
                    provider_id = str(item.get("id", ""))
                    text = item.get("text") or {}
                    message = str(text.get("body", "")) if isinstance(text, dict) else str(text)
                    if sender and message:
                        return sender.strip(), message.strip(), provider_id.strip()
    elif "From" in payload and "Body" in payload:
        sender = str(payload.get("From", "")).replace("whatsapp:", "")
        message = str(payload.get("Body", ""))
        provider_id = str(payload.get("MessageSid", ""))
    elif isinstance(payload.get("data"), dict):
        item = payload["data"]
        sender = str(item.get("from", ""))
        message = str(item.get("body", ""))
        provider_id = str(item.get("id", ""))
    else:
        sender = str(payload.get("from") or payload.get("phone") or payload.get("sender") or "")
        message = str(payload.get("message") or payload.get("text") or payload.get("body") or "")
        provider_id = str(payload.get("id") or payload.get("message_id") or "")
    return sender.strip(), message.strip(), provider_id.strip()


def _extract_delivery_receipts(payload):
    receipts = []
    if isinstance(payload.get("entry"), list):
        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for item in value.get("statuses", []):
                    errors = item.get("errors") or []
                    receipts.append({
                        "provider_reference": str(item.get("id", "")),
                        "status": str(item.get("status", "")).lower(),
                        "error_code": str(errors[0].get("code", "")) if errors else "",
                    })
    elif payload.get("MessageSid") and payload.get("MessageStatus"):
        receipts.append({
            "provider_reference": str(payload.get("MessageSid", "")),
            "status": str(payload.get("MessageStatus", "")).lower(),
            "error_code": str(payload.get("ErrorCode", "")),
        })
    else:
        status_updates = payload.get("status_updates")
        if isinstance(status_updates, list):
            for item in status_updates:
                if isinstance(item, dict):
                    receipts.append({
                        "provider_reference": str(item.get("provider_reference") or item.get("id") or ""),
                        "status": str(item.get("status", "")).lower(),
                        "error_code": str(item.get("error_code", "")),
                    })
        elif payload.get("provider_reference") and payload.get("status"):
            receipts.append({
                "provider_reference": str(payload.get("provider_reference")),
                "status": str(payload.get("status")).lower(),
                "error_code": str(payload.get("error_code", "")),
            })
    return receipts


def _twilio_signature_is_valid(request, secret):
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    signed = request.build_absolute_uri()
    params = request.data
    if hasattr(params, "lists"):
        values = params.lists()
    elif isinstance(params, dict):
        values = [(key, [value] if not isinstance(value, list) else value) for key, value in params.items()]
    else:
        values = []
    for key, items in sorted(values, key=lambda pair: pair[0]):
        for value in sorted(str(item) for item in items):
            signed += str(key) + value
    expected = base64.b64encode(
        hmac.new(secret.encode(), signed.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    return hmac.compare_digest(signature, expected)


def _signature_is_valid(request, gateway):
    if gateway.provider == SchoolMessagingGateway.Provider.TWILIO:
        return _twilio_signature_is_valid(request, gateway.webhook_verify_token)
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        gateway.webhook_verify_token.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


class WhatsAppWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def _gateway(self, school_code):
        if school_code:
            school = School.objects.filter(
                code=school_code.strip().upper(),
                status=School.Status.ACTIVE,
                is_archived=False,
            ).first()
            if school is None:
                return None, None
            gateway = SchoolMessagingGateway.objects.filter(
                school=school,
                channel=SchoolMessagingGateway.Channel.WHATSAPP,
                is_active=True,
            ).order_by("-created_at").first()
            return school, gateway
        gateway = SchoolMessagingGateway.objects.filter(
            school__isnull=True,
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            is_active=True,
        ).order_by("-created_at").first()
        return None, gateway

    def get(self, request, school_code=None, *args, **kwargs):
        mode = request.query_params.get("hub.mode")
        challenge = request.query_params.get("hub.challenge", "")
        token = request.query_params.get("hub.verify_token", "")
        # Lightweight provider health-check: no subscription challenge was requested.
        # Explicit but unsupported modes remain rejected.
        if not mode:
            return Response({"status": "ok"}, status=status.HTTP_200_OK)
        if mode != "subscribe":
            return Response({"detail": "طلب تحقق غير صالح."}, status=status.HTTP_400_BAD_REQUEST)
        school_code = school_code or request.query_params.get("school_code")
        _school, gateway = self._gateway(school_code)
        if not gateway or not gateway.webhook_verify_token or not hmac.compare_digest(
            token, gateway.webhook_verify_token,
        ):
            return Response({"detail": "فشل التحقق من سر Webhook."}, status=status.HTTP_403_FORBIDDEN)
        return Response(challenge, status=status.HTTP_200_OK)

    def post(self, request, school_code=None, *args, **kwargs):
        school_code = (
            school_code or request.query_params.get("school_code")
            or request.headers.get("X-School-Code")
        )
        if not school_code:
            return Response({"detail": "رمز المدرسة مطلوب في مسار Webhook."}, status=status.HTTP_400_BAD_REQUEST)
        school, gateway = self._gateway(school_code)
        if school is None or gateway is None or not gateway.webhook_verify_token:
            return Response({"detail": "المدرسة أو بوابة Webhook غير نشطة أو غير مهيأة."}, status=status.HTTP_403_FORBIDDEN)
        if not _signature_is_valid(request, gateway):
            required = "X-Twilio-Signature" if gateway.provider == SchoolMessagingGateway.Provider.TWILIO else "X-Hub-Signature-256"
            return Response({"detail": f"توقيع Webhook صالح عبر {required} مطلوب."}, status=status.HTTP_401_UNAUTHORIZED)

        payload = _plain_payload(request)
        receipts = _extract_delivery_receipts(payload)
        queued_receipts = 0
        for receipt in receipts:
            reference = receipt["provider_reference"][:160]
            provider_status = receipt["status"]
            if not reference or provider_status not in {"sent", "accepted", "delivered", "read", "failed"}:
                continue
            key_digest = hashlib.sha256(
                f"{reference}|{provider_status}|{gateway.provider}".encode()
            ).hexdigest()
            enqueue_event(
                event_name="notification.delivery_receipt",
                aggregate_type="notification_delivery",
                aggregate_id=reference,
                payload={
                    "provider_reference": reference,
                    "status": provider_status,
                    "provider": gateway.provider,
                    "error_code": receipt["error_code"][:80],
                },
                idempotency_key=f"receipt:{school.pk}:{key_digest}",
                school=school,
            )
            queued_receipts += 1
        if queued_receipts:
            return Response({"status": "receipts_accepted", "count": queued_receipts}, status=status.HTTP_202_ACCEPTED)

        sender, message, provider_id = _extract_message(payload)
        if not sender or not message:
            return Response({"status": "ignored", "reason": "لا توجد رسالة أو إيصال تسليم صالح."}, status=status.HTTP_200_OK)
        if len(sender) > 50 or len(message) > 2000:
            return Response({"detail": "بيانات الرسالة تتجاوز الحدود المسموحة."}, status=status.HTTP_400_BAD_REQUEST)
        if not provider_id:
            provider_id = "sha256:" + hashlib.sha256(
                (sender + "\0" + message + "\0" + request.body.decode("utf-8", "ignore")).encode("utf-8")
            ).hexdigest()

        with transaction.atomic():
            inbound, created = InboundWebhookMessage.objects.get_or_create(
                school=school,
                provider_msg_id=provider_id[:255],
                defaults={
                    "sender_phone": sender,
                    "processed": False,
                },
            )
            if not created:
                return Response({"status": "duplicate_ignored"}, status=status.HTTP_200_OK)
            enqueue_event(
                event_name="webhook.whatsapp.inbound",
                aggregate_type="inbound_webhook",
                aggregate_id=inbound.pk,
                payload={"inbound_id": str(inbound.pk), "message_text": message},
                idempotency_key=f"whatsapp-inbound:{school.pk}:{hashlib.sha256(provider_id.encode()).hexdigest()}",
                school=school,
            )

        return Response({
            "status": "success",
            "accepted": True,
            "message_id": str(inbound.pk),
            "queued_at": timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


class SchoolWhatsAppWebhookAPIView(WhatsAppWebhookAPIView):
    """Per-school endpoint retaining the existing URL contract."""
    pass
