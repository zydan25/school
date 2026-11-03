from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.notifications.models import (
    InboundWebhookMessage, Notification, NotificationDeliveryAttempt, SchoolEmailGateway,
    NotificationPreference, NotificationTemplate, OutboxEvent, SchoolMessagingGateway,
    NotificationDeliveryReceipt,
)


class SchoolMessagingGatewayAdminForm(forms.ModelForm):
    auth_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False), label="مفتاح المصادقة")
    webhook_verify_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False), label="سر توقيع Webhook")

    class Meta:
        model = SchoolMessagingGateway
        fields = "__all__"

    def clean_auth_token(self):
        value = self.cleaned_data.get("auth_token")
        return value if value else (self.instance.auth_token if self.instance.pk else "")

    def clean_webhook_verify_token(self):
        value = self.cleaned_data.get("webhook_verify_token")
        return value if value else (self.instance.webhook_verify_token if self.instance.pk else "")


@admin.register(Notification)
class NotificationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "recipient", "school", "channel", "category", "status", "is_read", "created_at")
    list_filter = ("channel", "status", "is_read", "category", "school")
    search_fields = ("title", "body", "recipient__phone", "recipient__full_name", "school__name")
    autocomplete_fields = ("school", "recipient")
    readonly_fields = ("id", "read_at", "sent_at", "delivered_at", "provider_reference", "created_at", "updated_at")
    date_hierarchy = "created_at"
    list_select_related = ("school", "recipient")
    def has_delete_permission(self, request, obj=None): return False


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "school", "channel", "language_code", "is_active")
    list_filter = ("channel", "language_code", "is_active")
    search_fields = ("code", "title_template", "body_template", "school__name")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "school", "category", "channel", "is_enabled")
    list_filter = ("channel", "category", "is_enabled", "school")
    search_fields = ("user__phone", "user__full_name", "school__name")
    autocomplete_fields = ("user", "school")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolMessagingGateway)
class SchoolMessagingGatewayAdmin(AuditedAdminMixin, ModelAdmin):
    form = SchoolMessagingGatewayAdminForm
    list_display = ("name", "school", "channel", "provider", "sender_id", "rate_limit_per_minute", "auto_ai_reply", "is_active")
    list_filter = ("channel", "provider", "auto_ai_reply", "is_active", "school")
    search_fields = ("name", "sender_id", "api_endpoint_url", "school__name")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(InboundWebhookMessage)
class InboundWebhookMessageAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("provider_msg_id", "school", "sender_phone", "processed", "received_at", "created_at")
    list_filter = ("processed", "school", "created_at")
    search_fields = ("provider_msg_id", "sender_phone", "school__name")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at", "last_error")


@admin.register(OutboxEvent)
class OutboxEventAdmin(ModelAdmin):
    list_display = ("event_name", "school", "aggregate_type", "aggregate_id", "status", "attempts", "available_at", "processed_at")
    list_filter = ("status", "event_name", "school")
    search_fields = ("event_name", "aggregate_type", "aggregate_id", "idempotency_key")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "event_name", "school", "aggregate_type", "aggregate_id", "payload", "status", "idempotency_key", "available_at", "attempts", "max_attempts", "last_error", "processed_at", "locked_at", "created_at", "updated_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in ("GET", "HEAD", "OPTIONS")


@admin.register(NotificationDeliveryAttempt)
class NotificationDeliveryAttemptAdmin(ModelAdmin):
    list_display = ("notification", "attempt_number", "provider", "status", "response_code", "attempted_at")
    list_filter = ("status", "provider", "attempted_at")
    search_fields = ("notification__title", "provider_reference", "error_code")
    readonly_fields = tuple(field.name for field in NotificationDeliveryAttempt._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in ("GET", "HEAD", "OPTIONS")


class SchoolEmailGatewayAdminForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False), label="كلمة مرور SMTP")

    class Meta:
        model = SchoolEmailGateway
        fields = "__all__"

    def clean_password(self):
        value = self.cleaned_data.get("password")
        return value if value else (self.instance.password if self.instance.pk else "")


@admin.register(SchoolEmailGateway)
class SchoolEmailGatewayAdmin(AuditedAdminMixin, ModelAdmin):
    form = SchoolEmailGatewayAdminForm
    list_display = ("school", "is_active", "host", "port", "from_email", "rate_limit_per_minute", "use_tls", "use_ssl")
    list_filter = ("is_active", "use_tls", "use_ssl")
    search_fields = ("school__name", "host", "from_email")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(NotificationDeliveryReceipt)
class NotificationDeliveryReceiptAdmin(ModelAdmin):
    list_display = ("notification", "provider", "provider_reference", "status", "error_code", "received_at")
    list_filter = ("provider", "status", "received_at")
    search_fields = ("provider_reference", "notification__title", "error_code")
    readonly_fields = tuple(field.name for field in NotificationDeliveryReceipt._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in ("GET", "HEAD", "OPTIONS")
