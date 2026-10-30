"""Transactional outbox primitives for reliable asynchronous notifications."""
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification, OutboxEvent


def enqueue_event(*, event_name, aggregate_type, aggregate_id, payload, idempotency_key, school=None, available_at=None):
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


def create_in_app_notification(*, recipient, title, body, school=None, category="general", action_url="", payload=None, idempotency_key=""):
    if school is not None:
        from apps.accounts.models import SchoolMembership
        if not SchoolMembership.objects.filter(user=recipient, school=school, status=SchoolMembership.Status.ACTIVE).exists():
            raise ValueError("المستلم لا يمتلك عضوية نشطة في المدرسة المحددة.")
    notification, created = Notification.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "recipient": recipient,
            "school": school,
            "channel": Notification.Channel.IN_APP,
            "category": category,
            "title": title,
            "body": body,
            "action_url": action_url,
            "payload": payload or {},
            "status": Notification.Status.SENT,
            "sent_at": timezone.now(),
        },
    ) if idempotency_key else (Notification.objects.create(
        recipient=recipient, school=school, channel=Notification.Channel.IN_APP,
        category=category, title=title, body=body, action_url=action_url,
        payload=payload or {}, status=Notification.Status.SENT, sent_at=timezone.now(),
    ), True)
    return notification, created


@transaction.atomic
def mark_notification_read(*, notification_id, user, school=None):
    queryset = Notification.objects.select_for_update().filter(pk=notification_id, recipient=user)
    if school is not None:
        queryset = queryset.filter(school=school)
    notification = queryset.first()
    if notification is None:
        return None
    notification.mark_read()
    return notification
