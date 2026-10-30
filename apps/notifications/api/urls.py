"""URLs for notifications and WhatsApp webhooks."""
from django.urls import path
from apps.notifications.api.views import (
    WhatsAppWebhookAPIView,
    SchoolWhatsAppWebhookAPIView,
    UserNotificationsAPIView,
    MarkNotificationReadAPIView,
)

app_name = "notifications_api"

urlpatterns = [
    path("", UserNotificationsAPIView.as_view(), name="user-notifications"),
    path("<uuid:notification_id>/read/", MarkNotificationReadAPIView.as_view(), name="mark-notification-read"),
    path("webhook/whatsapp/", WhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-general"),
    path("webhook/whatsapp/<str:school_code>/", SchoolWhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-school"),
]
