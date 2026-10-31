from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.timetable.models import (
    ClassSchedule,
    DailyLessonLog,
    SchedulePeriodTemplate,
    SchoolBellSchedule,
)


class SchedulePeriodTemplateInline(TabularInline):
    model = SchedulePeriodTemplate
    extra = 0
    fields = ("order", "period_type", "period_number", "name", "start_time", "end_time", "day_of_week", "is_active")
    ordering = ("order", "start_time")


@admin.register(SchoolBellSchedule)
class SchoolBellScheduleAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "name",
        "school",
        "academic_year",
        "day_start_time",
        "day_end_time",
        "periods_per_day",
        "has_morning_assembly",
        "is_default",
        "is_active",
    )
    list_filter = ("is_default", "is_active", "has_morning_assembly", "school", "academic_year")
    search_fields = ("name", "school__name", "academic_year__name")
    autocomplete_fields = ("school", "branch", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SchedulePeriodTemplateInline]

    fieldsets = (
        ("البيانات العامة", {
            "fields": ("school", "branch", "academic_year", "name", "is_active", "is_default"),
        }),
        ("طابور الصباح والإذاعة", {
            "fields": ("has_morning_assembly", "assembly_start_time", "assembly_end_time"),
        }),
        ("مواعيد الحصص واليوم الدراسي", {
            "fields": ("day_start_time", "day_end_time", "periods_per_day", "period_duration_minutes", "passing_duration_minutes"),
        }),
        ("الفسح والاستراحات", {
            "fields": ("break_after_period", "break_duration_minutes", "has_second_break", "second_break_after_period", "second_break_duration_minutes"),
        }),
        ("ملاحظات إضافية", {
            "fields": ("notes",),
        }),
    )


@admin.register(SchedulePeriodTemplate)
class SchedulePeriodTemplateAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("schedule", "order", "period_type", "period_number", "name", "start_time", "end_time", "day_of_week", "is_active", "school")
    list_filter = ("period_type", "day_of_week", "is_active", "school", "schedule")
    search_fields = ("name", "schedule__name", "school__name")
    autocomplete_fields = ("school", "branch", "schedule")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ClassSchedule)
class ClassScheduleAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("get_day_of_week_display", "period_number", "start_time", "end_time", "subject", "section", "teacher", "classroom", "school")
    list_filter = ("day_of_week", "academic_year", "school", "subject", "bell_schedule")
    search_fields = ("subject__name", "section__name", "teacher__user__first_name", "teacher__user__last_name", "school__name")
    autocomplete_fields = ("school", "branch", "bell_schedule", "academic_year", "academic_term", "section", "subject", "teacher", "classroom")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DailyLessonLog)
class DailyLessonLogAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("schedule", "date", "topic", "is_completed", "school")
    list_filter = ("date", "is_completed", "school")
    search_fields = ("topic", "lesson_summary", "schedule__subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "schedule")
    readonly_fields = ("id", "created_at", "updated_at")
