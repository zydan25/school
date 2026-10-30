"""URLs for notifications and WhatsApp webhooks."""
from django.urls import path
from apps.notifications.api.views import WhatsAppWebhookAPIView

app_name = "notifications_api"

urlpatterns = [
    path("webhook/whatsapp/", WhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-general"),
    path("webhook/whatsapp/<str:school_code>/", WhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook-school"),
]
