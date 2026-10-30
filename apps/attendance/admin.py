from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.attendance.models import DailyAttendance, PeriodAttendance


@admin.register(DailyAttendance)
class DailyAttendanceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "date", "status", "late_minutes", "recorded_by", "school")
    list_filter = ("status", "date", "school")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number", "school__name")
    autocomplete_fields = ("school", "branch", "student")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PeriodAttendance)
class PeriodAttendanceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "schedule", "date", "status", "school")
    list_filter = ("status", "date", "school")
    search_fields = ("student__first_name", "student__last_name", "schedule__subject__name", "school__name")
    autocomplete_fields = ("school", "branch", "schedule", "student")
    readonly_fields = ("id", "created_at", "updated_at")
