from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.assignments.models import Homework, HomeworkSubmission


class HomeworkSubmissionInline(TabularInline):
    model = HomeworkSubmission
    extra = 0
    readonly_fields = ("student", "submitted_at", "status", "score")
    can_delete = False


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
    list_display = ("student", "homework", "submitted_at", "status", "score", "graded_by", "school")
    list_filter = ("status", "school")
    search_fields = ("student__first_name", "student__last_name", "homework__title", "school__name")
    autocomplete_fields = ("school", "branch", "homework", "student", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at")
