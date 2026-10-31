"""Django Admin interface with Unfold styling for Attendance and Calendar."""
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.attendance.models import (
    AttendanceAuditLog,
    AttendanceExcuseRequest,
    AttendancePolicy,
    AttendanceRegister,
    AttendanceReopenRequest,
    AttendanceScoreEntry,
    AttendanceScoringPolicy,
    AttendanceStatusType,
    CalendarEvent,
    CalendarOccurrence,
    DailyAttendance,
    EarlyDepartureRequest,
    PeriodAttendance,
    SchoolCalendar,
    SchoolCalendarDay,
    StudentAttendanceRecord,
)
from apps.attendance.services import (
    approve_early_departure,
    approve_register,
    confirm_gate_exit,
    lock_register,
    review_excuse_request,
    review_reopen_request,
    sync_score_to_gradebook,
)
from apps.core.admin import AuditedAdminMixin


class StudentAttendanceRecordInline(TabularInline):
    model = StudentAttendanceRecord
    extra = 0
    fields = ("student", "status_category", "late_minutes", "excuse_request", "notes")
    readonly_fields = ("excuse_request",)
    autocomplete_fields = ("student",)


class SchoolCalendarDayInline(TabularInline):
    model = SchoolCalendarDay
    extra = 0
    fields = ("date", "day_type", "title", "is_school_day")
    ordering = ("date",)


class CalendarOccurrenceInline(TabularInline):
    model = CalendarOccurrence
    extra = 0
    fields = ("date", "start_time", "end_time", "status", "exception_reason")


@admin.register(AttendancePolicy)
class AttendancePolicyAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("academic_year", "attendance_mode", "morning_assembly_time", "grace_period_minutes", "is_active", "school")
    list_filter = ("attendance_mode", "is_active", "school")
    autocomplete_fields = ("school", "branch", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AttendanceStatusType)
class AttendanceStatusTypeAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "category", "color_code", "counts_as_present", "counts_as_absent", "is_default", "is_active", "school")
    list_filter = ("category", "counts_as_present", "is_active", "school")
    search_fields = ("name", "code")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolCalendar)
class SchoolCalendarAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "academic_year", "is_central_template", "version", "is_active", "school")
    list_filter = ("is_central_template", "is_active", "school")
    search_fields = ("name", "academic_year__name")
    autocomplete_fields = ("school", "branch", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SchoolCalendarDayInline]


@admin.register(SchoolCalendarDay)
class SchoolCalendarDayAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("calendar", "date", "day_type", "title", "is_school_day", "school")
    list_filter = ("day_type", "is_school_day", "date", "school")
    search_fields = ("title", "calendar__name")
    autocomplete_fields = ("school", "branch", "calendar")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CalendarEvent)
class CalendarEventAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "event_type", "recurrence_type", "start_date", "end_date", "target_scope", "is_active", "school")
    list_filter = ("event_type", "recurrence_type", "target_scope", "is_active", "school")
    search_fields = ("title", "teacher__user__first_name")
    autocomplete_fields = ("school", "branch", "academic_year", "stage", "grade_level", "section", "subject", "teacher", "classroom")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CalendarOccurrenceInline]


@admin.register(AttendanceRegister)
class AttendanceRegisterAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("section", "date", "session_type", "status", "submitted_by", "approved_by", "school")
    list_filter = ("status", "session_type", "date", "school")
    search_fields = ("section__name", "section__grade__name")
    autocomplete_fields = ("school", "branch", "academic_year", "academic_term", "section", "schedule")
    readonly_fields = ("id", "submitted_at", "approved_at", "locked_at", "created_at", "updated_at")
    inlines = [StudentAttendanceRecordInline]
    actions = ["action_approve_registers", "action_lock_registers"]

    @admin.action(description="اعتماد السجلات المحددة رسمياً")
    def action_approve_registers(self, request, queryset):
        count = 0
        for reg in queryset:
            if reg.status != AttendanceRegister.Status.LOCKED:
                approve_register(reg, approved_by=request.user)
                count += 1
        self.message_user(request, f"تم اعتماد {count} سجل حضور بنجاح.")

    @admin.action(description="إقفال السجلات المحددة نهائياً وحمايتها")
    def action_lock_registers(self, request, queryset):
        count = 0
        for reg in queryset:
            lock_register(reg, locked_by=request.user)
            count += 1
        self.message_user(request, f"تم إقفال {count} سجل حضور بنجاح.")


@admin.register(StudentAttendanceRecord)
class StudentAttendanceRecordAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "register", "status_category", "late_minutes", "recorded_by", "school")
    list_filter = ("status_category", "register__date", "school")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("school", "branch", "register", "student", "status_type", "excuse_request")
    readonly_fields = ("id", "recorded_at", "created_at", "updated_at")


@admin.register(AttendanceReopenRequest)
class AttendanceReopenRequestAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("register", "requested_by", "status", "reviewed_by", "reviewed_at", "school")
    list_filter = ("status", "school")
    search_fields = ("register__section__name", "reason")
    autocomplete_fields = ("school", "branch", "register")
    readonly_fields = ("id", "reviewed_at", "created_at", "updated_at")
    actions = ["action_approve_reopen"]

    @admin.action(description="الموافقة على إعادة فتح السجلات وإتاحة التعديل")
    def action_approve_reopen(self, request, queryset):
        count = 0
        for req in queryset.filter(status=AttendanceReopenRequest.Status.PENDING):
            review_reopen_request(req, reviewed_by=request.user, is_approved=True, review_notes="معتمد من الإدارة")
            count += 1
        self.message_user(request, f"تمت الموافقة على إعادة فتح {count} سجل حضور.")


@admin.register(AttendanceExcuseRequest)
class AttendanceExcuseRequestAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "guardian", "request_type", "start_date", "end_date", "status", "reviewed_by", "school")
    list_filter = ("status", "request_type", "school")
    search_fields = ("student__first_name", "student__last_name", "guardian__user__first_name", "reason")
    autocomplete_fields = ("school", "branch", "student", "guardian")
    readonly_fields = ("id", "reviewed_at", "created_at", "updated_at")
    actions = ["action_approve_excuse", "action_reject_excuse"]

    @admin.action(description="اعتماد وقبول طلبات الأعذار وتحديث الغياب تلقائياً")
    def action_approve_excuse(self, request, queryset):
        count = 0
        for exc in queryset.filter(status=AttendanceExcuseRequest.Status.SUBMITTED):
            review_excuse_request(exc, reviewed_by=request.user, is_approved=True, review_notes="تم التحقق من العذر وقبوله")
            count += 1
        self.message_user(request, f"تم اعتماد {count} عذر وتحديث سجلات الحضور بنجاح.")

    @admin.action(description="رفض طلبات الأعذار المحددة")
    def action_reject_excuse(self, request, queryset):
        count = 0
        for exc in queryset.filter(status=AttendanceExcuseRequest.Status.SUBMITTED):
            review_excuse_request(exc, reviewed_by=request.user, is_approved=False, review_notes="العذر غير مقبول")
            count += 1
        self.message_user(request, f"تم رفض {count} عذر.")


@admin.register(EarlyDepartureRequest)
class EarlyDepartureRequestAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "guardian", "date", "departure_time", "recipient_name", "status", "approved_by", "school")
    list_filter = ("status", "date", "school")
    search_fields = ("student__first_name", "student__last_name", "recipient_name", "recipient_phone")
    autocomplete_fields = ("school", "branch", "student", "guardian")
    readonly_fields = ("id", "approved_at", "exit_confirmed_at", "created_at", "updated_at")
    actions = ["action_approve_early_departure", "action_confirm_gate_exit"]

    @admin.action(description="اعتماد طلبات الانصراف المبكر المحددة")
    def action_approve_early_departure(self, request, queryset):
        count = 0
        for req in queryset.filter(status=EarlyDepartureRequest.Status.PENDING):
            approve_early_departure(req, approved_by=request.user)
            count += 1
        self.message_user(request, f"تم اعتماد {count} طلب انصراف مبكر بنجاح.")

    @admin.action(description="تأكيد خروج الطالب من البوابة الأمنية")
    def action_confirm_gate_exit(self, request, queryset):
        count = 0
        for req in queryset.filter(status=EarlyDepartureRequest.Status.APPROVED):
            confirm_gate_exit(req, confirmed_by=request.user, exit_notes="تم الاستلام عند البوابة")
            count += 1
        self.message_user(request, f"تم توثيق خروج {count} طالب من البوابة.")


@admin.register(AttendanceScoringPolicy)
class AttendanceScoringPolicyAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("academic_year", "subject", "total_attendance_score", "calculation_mode", "unexcused_absence_deduction", "is_active", "school")
    list_filter = ("calculation_mode", "is_active", "school")
    search_fields = ("academic_year__name", "subject__name")
    autocomplete_fields = ("school", "branch", "academic_year", "subject")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AttendanceScoreEntry)
class AttendanceScoreEntryAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "academic_term", "subject", "final_score", "raw_score", "deduction_total", "is_synced_to_gradebook", "school")
    list_filter = ("is_synced_to_gradebook", "academic_term", "school")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("school", "branch", "student", "academic_term", "subject", "scoring_policy")
    readonly_fields = ("id", "calculated_at", "created_at", "updated_at")
    actions = ["action_sync_to_gradebook"]

    @admin.action(description="مزامنة درجات المواظبة المحددة مع سجل الدرجات GradeBook")
    def action_sync_to_gradebook(self, request, queryset):
        count = 0
        for entry in queryset:
            sync_score_to_gradebook(entry, teacher=None)
            count += 1
        self.message_user(request, f"تمت مزامنة {count} درجة مواظبة مع سجل الدرجات بنجاح.")


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("action", "register", "student_record", "performed_by", "timestamp", "school")
    list_filter = ("action", "timestamp", "school")
    search_fields = ("register__section__name", "reason")
    autocomplete_fields = ("school", "branch", "register", "student_record")
    readonly_fields = ("id", "register", "student_record", "action", "performed_by", "timestamp", "old_value", "new_value", "reason", "ip_address", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
