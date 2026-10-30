from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.auditlog.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ("occurred_at", "school", "actor", "action", "object_type", "object_id", "severity", "ip_address")
    list_filter = ("severity", "action", "school", "occurred_at")
    search_fields = ("description", "action", "object_type", "object_id", "actor__phone", "actor__full_name", "request_id")
    autocomplete_fields = ("school", "actor")
    readonly_fields = ("id", "school", "actor", "action", "object_type", "object_id", "description", "severity", "metadata", "request_id", "ip_address", "user_agent", "occurred_at", "created_at", "updated_at")
    date_hierarchy = "occurred_at"
    list_select_related = ("school", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
