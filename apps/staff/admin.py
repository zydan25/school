from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.staff.models import StaffMember, Teacher, TeacherAssignment


@admin.register(StaffMember)
class StaffMemberAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "staff_role", "job_title", "floor_wing_assigned", "school", "employee_number", "is_active", "hire_date")
    list_filter = ("staff_role", "is_active", "school")
    search_fields = ("user__phone", "user__first_name", "user__last_name", "job_title", "employee_number", "school__name", "floor_wing_assigned")
    autocomplete_fields = ("school", "branch", "user")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Teacher)
class TeacherAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "specialization", "school", "employee_number", "max_weekly_periods", "is_active_teaching", "hire_date")
    list_filter = ("is_active_teaching", "school")
    search_fields = ("user__phone", "user__first_name", "user__last_name", "specialization", "employee_number", "school__name")
    autocomplete_fields = ("school", "branch", "user")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("teacher", "subject", "section", "academic_year", "weekly_periods", "school")
    list_filter = ("academic_year", "school", "subject")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "subject__name", "section__name", "school__name")
    autocomplete_fields = ("school", "branch", "teacher", "subject", "section", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")
