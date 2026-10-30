from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.copilot.models import AIChatMessage, AIChatSession, CurriculumDocument


class AIChatMessageInline(TabularInline):
    model = AIChatMessage
    extra = 0
    readonly_fields = ("sender", "content", "token_count", "created_at")
    can_delete = False


@admin.register(CurriculumDocument)
class CurriculumDocumentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "subject", "grade_level", "uploaded_by", "is_indexed", "school", "created_at")
    list_filter = ("is_indexed", "subject", "grade_level", "school")
    search_fields = ("title", "description", "subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "subject", "grade_level", "uploaded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AIChatSession)
class AIChatSessionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "role_scope", "user", "model_name", "is_active", "school", "created_at")
    list_filter = ("role_scope", "is_active", "school")
    search_fields = ("title", "user__phone", "user__first_name", "school__name")
    autocomplete_fields = ("school", "branch", "user")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (AIChatMessageInline,)


@admin.register(AIChatMessage)
class AIChatMessageAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("session", "sender", "token_count", "school", "created_at")
    list_filter = ("sender", "school")
    search_fields = ("content", "session__title", "school__name")
    autocomplete_fields = ("school", "branch", "session")
    readonly_fields = ("id", "created_at", "updated_at")
