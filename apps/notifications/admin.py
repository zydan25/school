from apps.core.admin import AuditedAdminMixin
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.notifications.models import Notification, NotificationPreference, NotificationTemplate, OutboxEvent


@admin.register(Notification)
class NotificationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "recipient", "school", "channel", "category", "status", "is_read", "created_at")
    list_filter = ("channel", "status", "is_read", "category", "school")
    search_fields = ("title", "body", "recipient__phone", "recipient__full_name", "school__name")
    autocomplete_fields = ("school", "recipient")
    readonly_fields = ("id", "read_at", "sent_at", "delivered_at", "provider_reference", "created_at", "updated_at")
    date_hierarchy = "created_at"
    list_select_related = ("school", "recipient")

    def has_delete_permission(self, request, obj=None):
        return False


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


@admin.register(OutboxEvent)
class OutboxEventAdmin(ModelAdmin):
    list_display = ("event_name", "school", "aggregate_type", "aggregate_id", "status", "attempts", "available_at", "processed_at")
    list_filter = ("status", "event_name", "school")
    search_fields = ("event_name", "aggregate_type", "aggregate_id", "idempotency_key")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "event_name", "school", "aggregate_type", "aggregate_id", "payload", "status", "idempotency_key", "available_at", "attempts", "max_attempts", "last_error", "processed_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
