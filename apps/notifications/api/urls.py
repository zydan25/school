"""Notification, preference, device and conversation routes."""
from django.urls import path

from apps.notifications.api.communication_views import (
    CancelNotificationAPIView,
    ConversationAttachmentAPIView,
    ConversationMessagesAPIView,
    ConversationParticipantsAPIView,
    ConversationStatusAPIView,
    NotificationPreferencesAPIView,
    PushDevicesAPIView,
    SchoolConversationsAPIView,
)
from apps.notifications.api.webhooks import WhatsAppWebhookAPIView, SchoolWhatsAppWebhookAPIView
from apps.notifications.api.views import MarkNotificationReadAPIView, UserNotificationsAPIView

app_name = "notifications_api"

urlpatterns = [
    path("", UserNotificationsAPIView.as_view(), name="user-notifications"),
    path("<uuid:notification_id>/read/", MarkNotificationReadAPIView.as_view(), name="mark-notification-read"),
    path("<uuid:notification_id>/cancel/", CancelNotificationAPIView.as_view(), name="cancel-notification"),
    path("preferences/", NotificationPreferencesAPIView.as_view(), name="notification-preferences"),
    path("devices/", PushDevicesAPIView.as_view(), name="push-devices"),
    path("conversations/", SchoolConversationsAPIView.as_view(), name="school-conversations"),
    path("conversations/<uuid:conversation_id>/messages/", ConversationMessagesAPIView.as_view(), name="conversation-messages"),
    path("conversations/<uuid:conversation_id>/participants/", ConversationParticipantsAPIView.as_view(), name="conversation-participants"),
    path("conversations/<uuid:conversation_id>/status/", ConversationStatusAPIView.as_view(), name="conversation-status"),
    path("conversations/<uuid:conversation_id>/messages/<uuid:message_id>/attachment/", ConversationAttachmentAPIView.as_view(), name="conversation-attachment"),
    path("webhook/whatsapp/", WhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-general"),
    path("webhook/whatsapp/<str:school_code>/", SchoolWhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-school"),
]
