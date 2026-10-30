from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.assessments.models import AssessmentType, GradeBook


@admin.register(AssessmentType)
class AssessmentTypeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "weight_percentage", "default_max_score", "school")
    list_filter = ("school",)
    search_fields = ("name", "code", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GradeBook)
class GradeBookAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "subject", "assessment_title", "score", "max_score", "is_published", "graded_by", "graded_at", "school")
    list_filter = ("is_published", "subject", "academic_term", "school")
    search_fields = ("student__first_name", "student__last_name", "assessment_title", "subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "subject", "academic_term", "assessment_type", "homework", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at")
