from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.timetable.models import ClassSchedule, DailyLessonLog


@admin.register(ClassSchedule)
class ClassScheduleAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("get_day_of_week_display", "period_number", "subject", "section", "teacher", "classroom", "school")
    list_filter = ("day_of_week", "academic_year", "school", "subject")
    search_fields = ("subject__name", "section__name", "teacher__user__first_name", "teacher__user__last_name", "school__name")
    autocomplete_fields = ("school", "branch", "academic_year", "academic_term", "section", "subject", "teacher", "classroom")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DailyLessonLog)
class DailyLessonLogAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("schedule", "date", "topic", "is_completed", "school")
    list_filter = ("date", "is_completed", "school")
    search_fields = ("topic", "lesson_summary", "schedule__subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "schedule")
    readonly_fields = ("id", "created_at", "updated_at")
