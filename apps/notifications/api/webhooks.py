"""Fail-closed, signed WhatsApp webhook intake; processing is delegated to Outbox."""
from __future__ import annotations

import hashlib
import hmac
import json

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import InboundWebhookMessage, SchoolMessagingGateway
from apps.notifications.services import enqueue_event
from apps.tenants.models import School


def _extract_message(payload):
    sender = message = provider_id = ""
    if isinstance(payload.get("entry"), list) and payload["entry"]:
        for change in payload["entry"][0].get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            if messages:
                item = messages[0]
                sender = str(item.get("from", ""))
                provider_id = str(item.get("id", ""))
                text = item.get("text") or {}
                message = str(text.get("body", "")) if isinstance(text, dict) else str(text)
                break
    elif isinstance(payload.get("data"), dict):
        item = payload["data"]
        sender = str(item.get("from", ""))
        message = str(item.get("body", ""))
        provider_id = str(item.get("id", ""))
    elif "From" in payload and "Body" in payload:
        sender = str(payload.get("From", "")).replace("whatsapp:", "")
        message = str(payload.get("Body", ""))
        provider_id = str(payload.get("MessageSid", ""))
    else:
        sender = str(payload.get("from") or payload.get("phone") or payload.get("sender") or "")
        message = str(payload.get("message") or payload.get("text") or payload.get("body") or "")
        provider_id = str(payload.get("id") or payload.get("message_id") or "")
    return sender.strip(), message.strip(), provider_id.strip()


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

        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature.startswith("sha256="):
            return Response({"detail": "توقيع X-Hub-Signature-256 مطلوب."}, status=status.HTTP_401_UNAUTHORIZED)
        expected = "sha256=" + hmac.new(
            gateway.webhook_verify_token.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return Response({"detail": "توقيع Webhook غير صحيح."}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data if isinstance(request.data, dict) else {}
        sender, message, provider_id = _extract_message(payload)
        if not sender or not message:
            return Response({"status": "ignored", "reason": "لا توجد رسالة نصية واردة."}, status=status.HTTP_200_OK)
        if len(sender) > 50 or len(message) > 2000:
            return Response({"detail": "بيانات الرسالة تتجاوز الحدود المسموحة."}, status=status.HTTP_400_BAD_REQUEST)
        if not provider_id:
            provider_id = "sha256:" + hashlib.sha256(
                (sender + "\0" + message + "\0" + request.body.decode("utf-8", "ignore")).encode("utf-8")
            ).hexdigest()

        try:
            with transaction.atomic():
                inbound = InboundWebhookMessage.objects.create(
                    school=school,
                    provider_msg_id=provider_id[:255],
                    sender_phone=sender,
                    processed=False,
                )
                enqueue_event(
                    event_name="webhook.whatsapp.inbound",
                    aggregate_type="inbound_webhook",
                    aggregate_id=inbound.pk,
                    payload={"inbound_id": str(inbound.pk), "message_text": message},
                    idempotency_key=f"whatsapp-inbound:{school.pk}:{hashlib.sha256(provider_id.encode()).hexdigest()}",
                    school=school,
                )
        except IntegrityError:
            return Response({"status": "duplicate_ignored"}, status=status.HTTP_200_OK)

        return Response({
            "status": "accepted",
            "message_id": str(inbound.pk),
            "queued_at": timezone.now().isoformat(),
        }, status=status.HTTP_202_ACCEPTED)


class SchoolWhatsAppWebhookAPIView(WhatsAppWebhookAPIView):
    """Per-school endpoint retaining the existing URL contract."""
    pass
