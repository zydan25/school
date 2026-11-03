"""Acceptance and security tests for Stage 12 communications and AI governance."""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import SchoolMembership, User
from apps.copilot.models import AIUsageRecord, SchoolAIUsagePolicy
from apps.copilot.usage import AIUsageLimitExceeded, run_budgeted_ai_call
from apps.notifications.models import (
    ConversationMessage,
    ConversationParticipant,
    InboundWebhookMessage,
    Notification,
    NotificationPreference,
    OutboxEvent,
    SchoolConversation,
    SchoolMessagingGateway,
)
from apps.notifications.services import (
    DeliveryError,
    _resolve_gateway_url,
    enqueue_notification,
    process_outbox_batch,
)
from apps.tenants.models import School
from apps.tenants.services import provision_school


class Stage12BaseTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+967770001201",
            password="StrongPassword123!",
            first_name="مالك",
            last_name="اختبار المرحلة الثانية عشرة",
        )
        self.school = School.objects.create(
            owner=self.owner,
            name="مدرسة اختبارات المرحلة الثانية عشرة",
            code="STAGE12",
            status=School.Status.ACTIVE,
        )
        provision_school(self.school)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def school_headers(self):
        return {"HTTP_X_SCHOOL_ID": str(self.school.pk)}

    def create_external_notification(self, *, channel=Notification.Channel.SMS, key="stage12-test-key"):
        return enqueue_notification(
            recipient=self.owner,
            school=self.school,
            channel=channel,
            category="attendance",
            title="تنبيه اختبار",
            body="رسالة اختبار",
            idempotency_key=key,
        )


class NotificationOutboxTests(Stage12BaseTestCase):
    def test_external_notice_is_queued_once_and_preferences_are_respected(self):
        first, created = self.create_external_notification()
        second, created_again = self.create_external_notification()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.status, Notification.Status.QUEUED)
        self.assertEqual(
            OutboxEvent.objects.filter(
                event_name="notification.dispatch",
                payload__notification_id=str(first.pk),
            ).count(),
            1,
        )

        NotificationPreference.objects.create(
            user=self.owner,
            school=self.school,
            category="attendance",
            channel=Notification.Channel.SMS,
            is_enabled=False,
        )
        suppressed, was_created = enqueue_notification(
            recipient=self.owner,
            school=self.school,
            channel=Notification.Channel.SMS,
            category="attendance",
            title="تنبيه ثان",
            body="لن يرسل",
            idempotency_key="stage12-opted-out",
        )
        self.assertIsNone(suppressed)
        self.assertFalse(was_created)
        self.assertEqual(Notification.objects.filter(idempotency_key="stage12-opted-out").count(), 0)

    def test_outbox_worker_records_provider_acceptance_and_completes_event(self):
        notification, _ = self.create_external_notification(key="stage12-success")
        with patch(
            "apps.notifications.services._dispatch_notification",
            return_value=("provider-msg-1", "test-provider"),
        ):
            result = process_outbox_batch(limit=10)

        notification.refresh_from_db()
        event = OutboxEvent.objects.get(idempotency_key=f"notification:{notification.pk}")
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(notification.status, Notification.Status.SENT)
        self.assertEqual(notification.provider_reference, "provider-msg-1")
        self.assertEqual(event.status, OutboxEvent.Status.PROCESSED)
        self.assertIsNotNone(event.processed_at)

    def test_retryable_failure_is_scheduled_and_terminal_failure_is_retained(self):
        notification, _ = self.create_external_notification(key="stage12-retry")
        event = OutboxEvent.objects.get(idempotency_key=f"notification:{notification.pk}")
        with patch(
            "apps.notifications.services._dispatch_notification",
            side_effect=DeliveryError("gateway temporarily unavailable", code="gateway_unavailable", retryable=True),
        ):
            result = process_outbox_batch(limit=1)
        event.refresh_from_db()
        self.assertEqual(result["retrying"], 1)
        self.assertEqual(event.status, OutboxEvent.Status.PENDING)
        self.assertEqual(event.attempts, 1)
        self.assertGreater(event.available_at, timezone.now())
        self.assertIn("gateway_unavailable", event.last_error)

        event.available_at = timezone.now()
        event.max_attempts = event.attempts + 1
        event.save(update_fields=["available_at", "max_attempts", "updated_at"])
        with patch(
            "apps.notifications.services._dispatch_notification",
            side_effect=DeliveryError("permanent provider rejection", code="provider_rejected", retryable=False),
        ):
            result = process_outbox_batch(limit=1)
        event.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(event.status, OutboxEvent.Status.FAILED)
        self.assertEqual(notification.status, Notification.Status.FAILED)

    def test_signed_whatsapp_webhook_is_queued_and_duplicate_is_ignored(self):
        gateway = SchoolMessagingGateway.objects.create(
            school=self.school,
            name="بوابة واتساب اختبار",
            channel=SchoolMessagingGateway.Channel.WHATSAPP,
            provider=SchoolMessagingGateway.Provider.GENERIC_HTTP,
            api_endpoint_url="https://gateway.example.test/messages",
            auth_token="outbound-token",
            webhook_verify_token="inbound-signature-secret",
            is_active=True,
            auto_ai_reply=False,
        )
        body = json.dumps(
            {"from": "967770001201", "message": "مرحباً", "message_id": "provider-event-001"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        path = "/api/v1/notifications/webhook/whatsapp/STAGE12/"
        unsigned = self.client.generic("POST", path, body, content_type="application/json")
        self.assertEqual(unsigned.status_code, 401)
        self.assertEqual(InboundWebhookMessage.objects.count(), 0)

        signature = "sha256=" + hmac.new(
            gateway.webhook_verify_token.encode("utf-8"), body, hashlib.sha256,
        ).hexdigest()
        response = self.client.generic(
            "POST",
            path,
            body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        self.assertEqual(response.status_code, 200)
        inbound = InboundWebhookMessage.objects.get(provider_msg_id="provider-event-001")
        self.assertFalse(inbound.processed)
        event = OutboxEvent.objects.get(
            event_name="webhook.whatsapp.inbound",
            payload__inbound_id=str(inbound.pk),
        )
        self.assertEqual(event.status, OutboxEvent.Status.PENDING)
        self.assertEqual(event.payload["message_text"], "مرحباً")

        duplicate = self.client.generic(
            "POST",
            path,
            body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(InboundWebhookMessage.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_name="webhook.whatsapp.inbound").count(), 1)
        process_outbox_batch(limit=1)
        inbound.refresh_from_db()
        self.assertTrue(inbound.processed)

    def test_gateway_credentials_are_encrypted_at_rest(self):
        gateway = SchoolMessagingGateway.objects.create(
            school=self.school,
            name="بوابة سرية",
            channel=SchoolMessagingGateway.Channel.SMS,
            provider=SchoolMessagingGateway.Provider.GENERIC_HTTP,
            api_endpoint_url="https://gateway.example.test/send",
            auth_token="do-not-store-this-plaintext",
            webhook_verify_token="secret-hook",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT auth_token, webhook_verify_token FROM notifications_schoolmessaginggateway WHERE id = %s",
                [str(gateway.pk)],
            )
            stored_token, stored_webhook = cursor.fetchone()
        self.assertTrue(stored_token.startswith("enc:v1:"))
        self.assertTrue(stored_webhook.startswith("enc:v1:"))
        self.assertNotIn("do-not-store-this-plaintext", stored_token)
        gateway.refresh_from_db()
        self.assertEqual(gateway.auth_token, "do-not-store-this-plaintext")
        self.assertEqual(gateway.webhook_verify_token, "secret-hook")

    @override_settings(DEBUG=False)
    def test_gateway_url_rejects_private_and_loopback_dns_targets(self):
        with patch(
            "apps.notifications.services.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 443))],
        ):
            with self.assertRaises(DeliveryError):
                _resolve_gateway_url("https://gateway.example.test/send")


class ConversationAPITests(Stage12BaseTestCase):
    def setUp(self):
        super().setUp()
        self.participant_user = User.objects.create_user(
            phone="+967770001202",
            password="StrongPassword123!",
            first_name="مشارك",
            last_name="اختبار",
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=self.participant_user,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
            is_default=False,
        )

    def test_conversation_messages_are_visible_only_to_active_participants(self):
        response = self.client.post(
            "/api/v1/notifications/conversations/",
            {"subject": "متابعة الطالب", "type": "general", "participant_ids": [str(self.participant_user.pk)]},
            format="json",
            **self.school_headers(),
        )
        self.assertEqual(response.status_code, 201, response.data)
        conversation_id = response.data["conversation"]["id"]
        conversation = SchoolConversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.participants.filter(is_active=True).count(), 2)

        self.client.post(
            f"/api/v1/notifications/conversations/{conversation_id}/messages/",
            {"body": "رسالة خاصة"},
            format="json",
            **self.school_headers(),
        )
        self.assertEqual(
            ConversationMessage.objects.filter(conversation=conversation, body="رسالة خاصة").count(),
            1,
        )

        participant_client = APIClient()
        participant_client.force_authenticate(self.participant_user)
        messages = participant_client.get(
            f"/api/v1/notifications/conversations/{conversation_id}/messages/",
            **self.school_headers(),
        )
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(messages.data["messages"][0]["body"], "رسالة خاصة")
        participant = ConversationParticipant.objects.get(
            conversation=conversation, user=self.participant_user,
        )
        self.assertIsNotNone(participant.last_read_at)

        outsider = User.objects.create_user(
            phone="+967770001203",
            password="StrongPassword123!",
            first_name="مستخدم",
            last_name="خارجي",
        )
        outsider_client = APIClient()
        outsider_client.force_authenticate(outsider)
        forbidden = outsider_client.get(
            f"/api/v1/notifications/conversations/{conversation_id}/messages/",
            **self.school_headers(),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_push_device_registration_never_returns_the_full_token(self):
        response = self.client.post(
            "/api/v1/notifications/devices/",
            {
                "device_id": "android-main-device",
                "platform": "android",
                "push_token": "fcm-token-secret-abcdefghijklmnop",
                "device_name": "هاتف الاختبار",
                "app_version": "1.0.0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        listed = self.client.get("/api/v1/notifications/devices/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["devices"][0]["token_suffix"], "ijklmnop")
        self.assertNotIn("fcm-token-secret-abcdefghijklmnop", str(listed.data))


class AIUsageGovernanceTests(Stage12BaseTestCase):
    def test_ai_call_reserves_quota_records_estimated_cost_and_enforces_limit(self):
        SchoolAIUsagePolicy.objects.create(
            school=self.school,
            enabled=True,
            daily_request_limit=1,
            daily_token_limit=1000,
            monthly_budget_amount=Decimal("1.0000"),
            input_cost_per_1k_tokens=Decimal("0.00100000"),
            output_cost_per_1k_tokens=Decimal("0.00200000"),
            currency="USD",
            max_output_tokens=100,
        )
        result = run_budgeted_ai_call(
            school=self.school,
            user=self.owner,
            tool="test.tool",
            input_text="طلب اختبار",
            source_refs={"student_id": "student-123", "subject_id": "subject-123"},
            call=lambda: {"answer": "نتيجة اختبار"},
            max_output_tokens=20,
        )
        self.assertEqual(result["answer"], "نتيجة اختبار")
        record = AIUsageRecord.objects.get(tool="test.tool", school=self.school)
        self.assertEqual(record.status, AIUsageRecord.Status.SUCCEEDED)
        self.assertGreater(record.input_tokens, 0)
        self.assertGreater(record.output_tokens, 0)
        self.assertGreater(record.estimated_cost, Decimal("0"))
        self.assertEqual(record.source_refs["student_id"], "student-123")
        self.assertNotIn("طلب اختبار", str(record.source_refs))

        with self.assertRaises(AIUsageLimitExceeded):
            run_budgeted_ai_call(
                school=self.school,
                user=self.owner,
                tool="test.tool",
                input_text="طلب إضافي",
                source_refs={},
                call=lambda: "يجب ألا يعمل",
                max_output_tokens=20,
            )
        self.assertEqual(AIUsageRecord.objects.filter(school=self.school).count(), 1)

    def test_ai_is_disabled_until_school_configures_a_budget(self):
        SchoolAIUsagePolicy.objects.create(school=self.school, enabled=False)
        called = False

        def provider_call():
            nonlocal called
            called = True
            return "not allowed"

        with self.assertRaises(AIUsageLimitExceeded):
            run_budgeted_ai_call(
                school=self.school,
                user=self.owner,
                tool="test.disabled",
                input_text="اختبار",
                source_refs={},
                call=provider_call,
            )
        self.assertFalse(called)
        self.assertEqual(AIUsageRecord.objects.count(), 0)
