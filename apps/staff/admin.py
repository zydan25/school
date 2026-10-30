from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.core.admin import AuditedAdminMixin
from apps.staff.models import (
    StaffMember,
    Teacher,
    TeacherAssignment,
    Department,
    WorkShift,
    LeaveType,
    LeaveRequest,
    StaffAttendance,
)


@admin.register(Department)
class DepartmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "manager", "school", "created_at")
    list_filter = ("school",)
    search_fields = ("code", "name", "description")
    raw_id_fields = ("school", "branch", "manager")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WorkShift)
class WorkShiftAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "start_time", "end_time", "grace_period_minutes", "school")
    list_filter = ("school",)
    search_fields = ("name",)
    raw_id_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LeaveType)
class LeaveTypeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "days_allowed", "is_paid", "school")
    list_filter = ("is_paid", "school")
    search_fields = ("code", "name")
    raw_id_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("get_applicant", "leave_type", "start_date", "end_date", "status", "approved_by", "school")
    list_filter = ("status", "leave_type", "school")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "staff_member__user__first_name", "reason")
    raw_id_fields = ("school", "branch", "teacher", "staff_member", "leave_type", "approved_by")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at")

    def get_applicant(self, obj):
        return str(obj)
    get_applicant.short_description = "الموظف"


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("get_staff", "date", "status", "time_in", "time_out", "delay_minutes", "shift", "school")
    list_filter = ("status", "date", "school")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "staff_member__user__first_name", "notes")
    raw_id_fields = ("school", "branch", "teacher", "staff_member", "shift")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_staff(self, obj):
        return str(obj)
    get_staff.short_description = "الموظف"


@admin.register(StaffMember)
class StaffMemberAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "role", "job_title", "assigned_floor_wing", "school", "employee_number", "is_active", "hire_date")
    list_filter = ("role", "is_active", "school")
    search_fields = ("user__phone", "user__first_name", "user__last_name", "job_title", "employee_number", "school__name", "assigned_floor_wing")
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
