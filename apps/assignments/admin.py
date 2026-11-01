from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.assignments.models import Homework, HomeworkSubmission, HomeworkSubmissionAttempt
from apps.core.admin import AuditedAdminMixin


class HomeworkSubmissionInline(TabularInline):
    model = HomeworkSubmission
    extra = 0
    readonly_fields = ("student", "submitted_at", "status", "score")
    can_delete = False


class HomeworkSubmissionAttemptInline(TabularInline):
    model = HomeworkSubmissionAttempt
    extra = 0
    can_delete = False
    fields = ("attempt_number", "submitted_at", "status", "submission_text", "attachment")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Homework)
class HomeworkAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "subject", "section", "teacher", "assigned_date", "due_date", "max_score", "is_active", "school")
    list_filter = ("is_active", "subject", "school")
    search_fields = ("title", "description", "subject__name", "section__name", "school__name")
    autocomplete_fields = ("school", "branch", "subject", "section", "teacher")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (HomeworkSubmissionInline,)


@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(AuditedAdminMixin, ModelAdmin):
    inlines = (HomeworkSubmissionAttemptInline,)
    list_display = ("student", "homework", "submitted_at", "status", "score", "graded_by", "school")
    list_filter = ("status", "school")
    search_fields = ("student__first_name", "student__last_name", "homework__title", "school__name")
    autocomplete_fields = ("school", "branch", "homework", "student", "graded_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch", "homework",
        "student", "submission_text", "attachment", "submitted_at", "status",
        "score", "teacher_feedback", "graded_by", "graded_at",
    )


@admin.register(HomeworkSubmissionAttempt)
class HomeworkSubmissionAttemptAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("submission", "attempt_number", "submitted_at", "status", "school")
    list_filter = ("status", "school")
    search_fields = ("submission__student__first_name", "submission__student__last_name", "submission__homework__title")
    readonly_fields = ("id", "school", "branch", "submission", "attempt_number", "submission_text", "attachment", "submitted_at", "status", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
