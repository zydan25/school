from apps.core.admin import AuditedAdminMixin

"""Dedicated per-school admin site with mandatory tenant scoping at queryset level."""
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.sites import UnfoldAdminSite

from apps.academics.models import (
    AcademicTerm,
    AcademicYear,
    Classroom,
    EducationalStage,
    GradeLevel,
    PeriodDefinition,
    SchoolWorkingDay,
    Section,
    Subject,
)
from apps.accounts.models import (
    MembershipRole,
    SchoolInvitation,
    SchoolMembership,
    SchoolRole,
    User,
)
from apps.accounts.services import has_school_permission, is_platform_operator
from apps.notifications.models import Notification, NotificationPreference, NotificationTemplate
from apps.tenants.models import Branch, School


class SchoolAdminAuthenticationForm(AdminAuthenticationForm):
    """School staff do not need platform-wide is_staff; membership is checked instead."""
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError("هذا الحساب غير مفعل.", code="inactive")
        if user.is_superuser:
            return
        if not SchoolMembership.objects.filter(
            user=user,
            status=SchoolMembership.Status.ACTIVE,
            school__status=School.Status.ACTIVE,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).exists():
            raise ValidationError("لا توجد عضوية مدرسية نشطة لهذا الحساب.", code="no_school_membership")


class SchoolAdminSite(UnfoldAdminSite):
    site_header = "سكول | إدارة المدرسة"
    site_title = "إدارة المدرسة - سكول"
    index_title = "لوحة المدرسة"
    login_form = SchoolAdminAuthenticationForm

    def each_context(self, request):
        context = super().each_context(request)
        context.update({"site_header": "سكول | إدارة المدرسة", "site_title": "إدارة المدرسة - سكول", "title": "لوحة المدرسة"})
        return context

    def has_permission(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return False
        if is_platform_operator(user):
            return getattr(request, "school", None) is not None
        membership = getattr(request, "school_membership", None)
        if membership is None or membership.status != SchoolMembership.Status.ACTIVE:
            return False
        if membership.expires_at and membership.expires_at <= timezone.now():
            return False
        return MembershipRole.objects.filter(
            membership=membership,
            role__is_active=True,
            role__is_archived=False,
            valid_from__lte=timezone.localdate(),
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.localdate())).exists()


school_admin_site = SchoolAdminSite(name="school_admin")


class SchoolScopedAdmin(AuditedAdminMixin, ModelAdmin):
    """Tenant guard shared by every school-facing Django admin registration."""
    school_lookup = "school"
    allow_delete = False

    def _school(self, request):
        school = getattr(request, "school", None)
        if school is None:
            raise PermissionDenied("لا توجد مدرسة محددة في سياق الجلسة.")
        if getattr(request, "school_context_error", None):
            raise PermissionDenied(request.school_context_error)
        return school

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        school = self._school(request)
        return queryset.filter(**{self.school_lookup: school})

    def _allowed(self, request, action):
        school = getattr(request, "school", None)
        if school is None:
            return False
        opts = self.model._meta
        return has_school_permission(
            user=request.user,
            school=school,
            permission=f"{opts.app_label}.{action}_{opts.model_name}",
        )

    def has_module_permission(self, request):
        return self._allowed(request, "view") or self._allowed(request, "add")

    def has_view_permission(self, request, obj=None):
        if not self._allowed(request, "view") and not self._allowed(request, "change"):
            return False
        if obj is not None:
            return self.get_queryset(request).filter(pk=obj.pk).exists()
        return True

    def has_add_permission(self, request):
        return self._allowed(request, "add")

    def has_change_permission(self, request, obj=None):
        if not self._allowed(request, "change"):
            return False
        return obj is None or self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_delete_permission(self, request, obj=None):
        return self.allow_delete and self._allowed(request, "delete")

    def save_model(self, request, obj, form, change):
        school = self._school(request)
        if self.school_lookup == "school":
            obj.school = school
        elif self.school_lookup == "membership__school":
            if obj.membership.school_id != school.pk:
                raise PermissionDenied("لا يمكن تعديل دور لعضوية تابعة لمدرسة أخرى.")
        super().save_model(request, obj, form, change)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        school = getattr(request, "school", None)
        related = db_field.remote_field.model
        if school is not None and related is SchoolRole and db_field.name == "roles":
            kwargs["queryset"] = related.objects.filter(school=school, is_active=True, is_archived=False)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        school = getattr(request, "school", None)
        related = db_field.remote_field.model
        if school is not None and db_field.name in {"school", "branch", "academic_year", "academic_term", "stage", "grade", "classroom", "homeroom_classroom", "first_period", "last_period", "role", "membership"}:
            if db_field.name == "school":
                kwargs["queryset"] = related.objects.filter(pk=school.pk)
            elif db_field.name in {"membership"}:
                kwargs["queryset"] = related.objects.filter(school=school)
            elif db_field.name == "role":
                kwargs["queryset"] = related.objects.filter(school=school)
            elif db_field.name == "branch":
                kwargs["queryset"] = related.objects.filter(school=school)
            elif hasattr(related, "school"):
                kwargs["queryset"] = related.objects.filter(school=school)
        if school is not None and related is User:
            kwargs["queryset"] = related.objects.filter(school_memberships__school=school, school_memberships__status=SchoolMembership.Status.ACTIVE).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Branch, site=school_admin_site)
class SchoolBranchAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "is_main", "status", "capacity", "is_archived")
    list_filter = ("status", "is_main", "is_archived")
    search_fields = ("name", "code", "manager_name")
    readonly_fields = ("id", "created_at", "updated_at", "archived_at", "archived_by")


@admin.register(AcademicYear, site=school_admin_site)
class SchoolAcademicYearAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "starts_on", "ends_on", "status", "is_current")
    list_filter = ("status", "is_current")
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AcademicTerm, site=school_admin_site)
class SchoolAcademicTermAdmin(SchoolScopedAdmin):
    list_display = ("name", "academic_year", "number", "starts_on", "ends_on", "is_current", "is_closed")
    list_filter = ("academic_year", "is_current", "is_closed")
    search_fields = ("name", "academic_year__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(EducationalStage, site=school_admin_site)
class SchoolEducationalStageAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "sequence", "is_active", "is_archived")
    list_filter = ("is_active", "is_archived")
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GradeLevel, site=school_admin_site)
class SchoolGradeLevelAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "stage", "sequence", "age_from", "age_to", "is_active")
    list_filter = ("stage", "is_active")
    search_fields = ("name", "code", "stage__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Classroom, site=school_admin_site)
class SchoolClassroomAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "classroom_type", "capacity", "building", "is_active")
    list_filter = ("classroom_type", "is_active")
    search_fields = ("name", "code", "building")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Section, site=school_admin_site)
class SchoolSectionAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "grade", "floor_wing", "supervisor_user", "students_count_display", "capacity", "is_active")
    list_filter = ("academic_year", "grade", "floor_wing", "is_active")
    search_fields = ("name", "code", "floor_wing", "grade__name", "supervisor_user__phone")
    raw_id_fields = ("academic_year", "grade", "homeroom_classroom", "supervisor_user")
    readonly_fields = ("id", "created_at", "updated_at")

    def students_count_display(self, obj):
        return f"{obj.current_student_count} / {obj.capacity}"
    students_count_display.short_description = "الطلاب / السعة"


@admin.register(Subject, site=school_admin_site)
class SchoolSubjectAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "is_core", "default_weekly_periods", "max_score", "is_active")
    list_filter = ("is_core", "is_active")
    search_fields = ("name", "short_name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PeriodDefinition, site=school_admin_site)
class SchoolPeriodAdmin(SchoolScopedAdmin):
    list_display = ("period_number", "name", "starts_at", "ends_at", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolWorkingDay, site=school_admin_site)
class SchoolWorkingDayAdmin(SchoolScopedAdmin):
    list_display = ("weekday", "is_working", "sequence", "first_period", "last_period")
    list_filter = ("is_working",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolMembership, site=school_admin_site)
class SchoolMembershipAdmin(SchoolScopedAdmin):
    list_display = ("user", "status", "is_default", "joined_at", "expires_at")
    list_filter = ("status", "is_default")
    search_fields = ("user__full_name", "user__phone", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolRole, site=school_admin_site)
class SchoolRoleAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "is_system", "is_active", "is_archived")
    list_filter = ("is_system", "is_active", "is_archived")
    search_fields = ("name", "code", "description")
    filter_horizontal = ("permissions",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MembershipRole, site=school_admin_site)
class SchoolMembershipRoleAdmin(SchoolScopedAdmin):
    school_lookup = "membership__school"
    list_display = ("membership", "role", "valid_from", "valid_until", "assigned_by")
    list_filter = ("role",)
    autocomplete_fields = ("membership", "role")
    raw_id_fields = ("assigned_by",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Notification, site=school_admin_site)
class SchoolNotificationAdmin(SchoolScopedAdmin):
    list_display = ("title", "recipient", "channel", "category", "status", "is_read", "created_at")
    list_filter = ("channel", "status", "is_read", "category")
    search_fields = ("title", "body", "recipient__phone", "recipient__full_name")
    readonly_fields = ("id", "read_at", "sent_at", "delivered_at", "provider_reference", "created_at", "updated_at")


@admin.register(NotificationPreference, site=school_admin_site)
class SchoolNotificationPreferenceAdmin(SchoolScopedAdmin):
    list_display = ("user", "category", "channel", "is_enabled")
    list_filter = ("category", "channel", "is_enabled")
    search_fields = ("user__phone", "user__full_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(NotificationTemplate, site=school_admin_site)
class SchoolNotificationTemplateAdmin(SchoolScopedAdmin):
    list_display = ("code", "channel", "language_code", "is_active")
    list_filter = ("channel", "language_code", "is_active")
    search_fields = ("code", "title_template", "body_template")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolInvitation, site=school_admin_site)
class SchoolInvitationAdmin(SchoolScopedAdmin):
    """Invitation records are visible per school; creation is performed by the invitation service."""
    list_display = ("email", "phone", "status", "expires_at", "invited_by", "accepted_at")
    list_filter = ("status", "expires_at")
    search_fields = ("email", "phone", "message")
    readonly_fields = (
        "id", "school", "email", "phone", "token_digest", "status", "expires_at",
        "invited_by", "accepted_by", "accepted_at", "message", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS") and super().has_view_permission(request, obj)


# -----------------------------------------------------------------------------
# New Operational Modules Registered in School Admin
# -----------------------------------------------------------------------------
from apps.assessments.models import AssessmentType, GradeBook
from apps.assignments.models import Homework, HomeworkSubmission
from apps.copilot.models import AIChatSession, CurriculumDocument
from apps.staff.models import (
    Department,
    LeaveRequest,
    LeaveType,
    StaffAttendance,
    StaffMember,
    Teacher,
    TeacherAssignment,
    WorkShift,
)
from apps.students.models import (
    AdministrativeSummon,
    Guardian,
    SchoolComplaint,
    Student,
    StudentEnrollment,
    StudentGuardianRelation,
    StudentIncidentReport,
)
from apps.timetable.models import (
    ClassSchedule,
    DailyLessonLog,
    SchedulePeriodTemplate,
    SchoolBellSchedule,
)


@admin.register(StaffMember, site=school_admin_site)
class SchoolStaffMemberAdmin(SchoolScopedAdmin):
    list_display = ("user", "role", "job_title", "assigned_floor_wing", "employee_number", "is_active", "hire_date")
    list_filter = ("role", "is_active")
    search_fields = ("user__phone", "user__first_name", "user__last_name", "job_title", "employee_number", "assigned_floor_wing")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Teacher, site=school_admin_site)
class SchoolTeacherAdmin(SchoolScopedAdmin):
    list_display = ("user", "specialization", "employee_number", "max_weekly_periods", "is_active_teaching")
    list_filter = ("is_active_teaching",)
    search_fields = ("user__phone", "user__first_name", "user__last_name", "specialization")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TeacherAssignment, site=school_admin_site)
class SchoolTeacherAssignmentAdmin(SchoolScopedAdmin):
    list_display = ("teacher", "subject", "section", "academic_year", "weekly_periods")
    list_filter = ("academic_year", "subject")
    search_fields = ("teacher__user__first_name", "subject__name", "section__name")
    autocomplete_fields = ("teacher", "subject", "section", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Department, site=school_admin_site)
class SchoolDepartmentAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "manager", "created_at")
    search_fields = ("code", "name")
    raw_id_fields = ("manager",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WorkShift, site=school_admin_site)
class SchoolWorkShiftAdmin(SchoolScopedAdmin):
    list_display = ("name", "start_time", "end_time", "grace_period_minutes")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LeaveType, site=school_admin_site)
class SchoolLeaveTypeAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "days_allowed", "is_paid")
    list_filter = ("is_paid",)
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LeaveRequest, site=school_admin_site)
class SchoolLeaveRequestAdmin(SchoolScopedAdmin):
    list_display = ("get_applicant", "leave_type", "start_date", "end_date", "status", "approved_by")
    list_filter = ("status", "leave_type")
    search_fields = ("teacher__user__first_name", "staff_member__user__first_name", "reason")
    raw_id_fields = ("teacher", "staff_member", "leave_type", "approved_by")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at")

    def get_applicant(self, obj):
        return str(obj)
    get_applicant.short_description = "الموظف"


@admin.register(StaffAttendance, site=school_admin_site)
class SchoolStaffAttendanceAdmin(SchoolScopedAdmin):
    list_display = ("get_staff", "date", "status", "time_in", "time_out", "delay_minutes", "shift")
    list_filter = ("status", "date")
    search_fields = ("teacher__user__first_name", "staff_member__user__first_name")
    raw_id_fields = ("teacher", "staff_member", "shift")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_staff(self, obj):
        return str(obj)
    get_staff.short_description = "الموظف"


@admin.register(Student, site=school_admin_site)
class SchoolStudentAdmin(SchoolScopedAdmin):
    list_display = ("get_full_name", "student_id_number", "grade_level", "section", "status")
    list_filter = ("status", "grade_level", "academic_year")
    search_fields = ("student_id_number", "first_name", "last_name", "national_id")
    autocomplete_fields = ("grade_level", "section", "academic_year")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentEnrollment, site=school_admin_site)
class SchoolStudentEnrollmentAdmin(SchoolScopedAdmin):
    list_display = ("student", "academic_year", "grade_level", "section", "status", "enrollment_date")
    list_filter = ("status", "academic_year", "grade_level")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("student", "academic_year", "grade_level", "section")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Guardian, site=school_admin_site)
class SchoolGuardianAdmin(SchoolScopedAdmin):
    list_display = ("user", "relationship_type", "national_id", "emergency_phone")
    list_filter = ("relationship_type",)
    search_fields = ("user__phone", "user__first_name", "user__last_name", "national_id")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentGuardianRelation, site=school_admin_site)
class SchoolStudentGuardianRelationAdmin(SchoolScopedAdmin):
    list_display = ("student", "guardian", "is_primary", "receives_notifications", "can_pickup")
    list_filter = ("is_primary", "receives_notifications", "can_pickup")
    search_fields = ("student__first_name", "student__last_name", "guardian__user__first_name")
    autocomplete_fields = ("student", "guardian")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentIncidentReport, site=school_admin_site)
class SchoolStudentIncidentReportAdmin(SchoolScopedAdmin):
    list_display = ("title", "student", "reporter", "severity", "incident_type", "date", "parent_notified", "is_resolved")
    list_filter = ("severity", "incident_type", "parent_notified", "is_resolved")
    search_fields = ("title", "student__first_name", "student__last_name", "reporter__phone", "details")
    raw_id_fields = ("student", "reporter")
    readonly_fields = ("id", "created_at", "updated_at", "parent_seen_at")


@admin.register(AdministrativeSummon, site=school_admin_site)
class SchoolAdministrativeSummonAdmin(SchoolScopedAdmin):
    list_display = ("summon_type", "target_user", "student", "appointment_date", "is_attended", "issued_by")
    list_filter = ("summon_type", "is_attended")
    search_fields = ("student__first_name", "student__last_name", "target_user__phone", "target_user__first_name", "reason")
    raw_id_fields = ("student", "target_user", "issued_by")
    readonly_fields = ("id", "created_at", "updated_at", "attended_at")


@admin.register(SchoolComplaint, site=school_admin_site)
class SchoolComplaintAdmin(SchoolScopedAdmin):
    list_display = ("subject", "category", "status", "submitter", "resolved_by", "resolved_at")
    list_filter = ("category", "status")
    search_fields = ("subject", "details", "submitter__phone")
    raw_id_fields = ("submitter", "resolved_by")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at")


class SchoolSchedulePeriodTemplateInline(TabularInline):
    model = SchedulePeriodTemplate
    extra = 0
    fields = ("order", "period_type", "period_number", "name", "start_time", "end_time", "day_of_week", "is_active")
    ordering = ("order", "start_time")


@admin.register(SchoolBellSchedule, site=school_admin_site)
class SchoolBellScheduleAdmin(SchoolScopedAdmin):
    list_display = (
        "name",
        "academic_year",
        "day_start_time",
        "day_end_time",
        "periods_per_day",
        "has_morning_assembly",
        "is_default",
        "is_active",
    )
    list_filter = ("is_default", "is_active", "has_morning_assembly", "academic_year")
    search_fields = ("name", "academic_year__name")
    autocomplete_fields = ("branch", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SchoolSchedulePeriodTemplateInline]


@admin.register(SchedulePeriodTemplate, site=school_admin_site)
class SchoolSchedulePeriodTemplateAdmin(SchoolScopedAdmin):
    list_display = ("schedule", "order", "period_type", "period_number", "name", "start_time", "end_time", "day_of_week", "is_active")
    list_filter = ("period_type", "day_of_week", "is_active", "schedule")
    search_fields = ("name", "schedule__name")
    autocomplete_fields = ("branch", "schedule")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ClassSchedule, site=school_admin_site)
class SchoolClassScheduleAdmin(SchoolScopedAdmin):
    list_display = ("get_day_of_week_display", "period_number", "start_time", "end_time", "subject", "section", "teacher", "classroom")
    list_filter = ("day_of_week", "academic_year", "subject", "bell_schedule")
    search_fields = ("subject__name", "section__name", "teacher__user__first_name")
    autocomplete_fields = ("bell_schedule", "academic_year", "academic_term", "section", "subject", "teacher", "classroom")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DailyLessonLog, site=school_admin_site)
class SchoolDailyLessonLogAdmin(SchoolScopedAdmin):
    list_display = ("schedule", "date", "topic", "is_completed")
    list_filter = ("date", "is_completed")
    search_fields = ("topic", "lesson_summary")
    autocomplete_fields = ("schedule",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Homework, site=school_admin_site)
class SchoolHomeworkAdmin(SchoolScopedAdmin):
    list_display = ("title", "subject", "section", "teacher", "assigned_date", "due_date", "max_score", "is_active")
    list_filter = ("is_active", "subject")
    search_fields = ("title", "description", "subject__name", "section__name")
    autocomplete_fields = ("subject", "section", "teacher")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(HomeworkSubmission, site=school_admin_site)
class SchoolHomeworkSubmissionAdmin(SchoolScopedAdmin):
    list_display = ("student", "homework", "submitted_at", "status", "score", "graded_by")
    list_filter = ("status",)
    search_fields = ("student__first_name", "student__last_name", "homework__title")
    autocomplete_fields = ("homework", "student", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AssessmentType, site=school_admin_site)
class SchoolAssessmentTypeAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "weight_percentage", "default_max_score")
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GradeBook, site=school_admin_site)
class SchoolGradeBookAdmin(SchoolScopedAdmin):
    list_display = ("student", "subject", "assessment_title", "score", "max_score", "is_published", "graded_by")
    list_filter = ("is_published", "subject", "academic_term")
    search_fields = ("student__first_name", "student__last_name", "assessment_title", "subject__name")
    autocomplete_fields = ("student", "subject", "academic_term", "assessment_type", "homework", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CurriculumDocument, site=school_admin_site)
class SchoolCurriculumDocumentAdmin(SchoolScopedAdmin):
    list_display = ("title", "subject", "grade_level", "uploaded_by", "is_indexed", "created_at")
    list_filter = ("is_indexed", "subject", "grade_level")
    search_fields = ("title", "description", "subject__name")
    autocomplete_fields = ("subject", "grade_level", "uploaded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AIChatSession, site=school_admin_site)
class SchoolAIChatSessionAdmin(SchoolScopedAdmin):
    list_display = ("title", "role_scope", "user", "model_name", "is_active", "created_at")
    list_filter = ("role_scope", "is_active")
    search_fields = ("title", "user__phone", "user__first_name")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Attendance, Student Fees & Accounting in School Admin
# -----------------------------------------------------------------------------
from apps.accounting.models import Account, CostCenter, FiscalYear, JournalEntry
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
from apps.student_fees.models import FeeCategory, FeeStructure, PaymentReceipt, StudentInvoice


class SchoolStudentAttendanceRecordInline(TabularInline):
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


class SchoolCalendarOccurrenceInline(TabularInline):
    model = CalendarOccurrence
    extra = 0
    fields = ("date", "start_time", "end_time", "status", "exception_reason")


@admin.register(AttendancePolicy, site=school_admin_site)
class SchoolAttendancePolicyAdmin(SchoolScopedAdmin):
    list_display = ("academic_year", "attendance_mode", "morning_assembly_time", "grace_period_minutes", "cascade_daily_to_periods", "is_active")
    list_filter = ("attendance_mode", "cascade_daily_to_periods", "is_active")
    autocomplete_fields = ("academic_year",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AttendanceStatusType, site=school_admin_site)
class SchoolAttendanceStatusTypeAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "category", "color_code", "counts_as_present", "counts_as_absent", "is_default", "is_active")
    list_filter = ("category", "counts_as_present", "is_active")
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolCalendar, site=school_admin_site)
class SchoolCalendarAdmin(SchoolScopedAdmin):
    list_display = ("name", "academic_year", "is_central_template", "version", "is_active")
    list_filter = ("is_central_template", "is_active")
    search_fields = ("name", "academic_year__name")
    autocomplete_fields = ("academic_year",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SchoolCalendarDayInline]


@admin.register(SchoolCalendarDay, site=school_admin_site)
class SchoolCalendarDayAdmin(SchoolScopedAdmin):
    list_display = ("calendar", "date", "day_type", "title", "is_school_day")
    list_filter = ("day_type", "is_school_day", "date")
    search_fields = ("title", "calendar__name")
    autocomplete_fields = ("calendar",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CalendarEvent, site=school_admin_site)
class SchoolCalendarEventAdmin(SchoolScopedAdmin):
    list_display = ("title", "event_type", "recurrence_type", "start_date", "end_date", "target_scope", "is_active")
    list_filter = ("event_type", "recurrence_type", "target_scope", "is_active")
    search_fields = ("title", "teacher__user__first_name")
    autocomplete_fields = ("academic_year", "stage", "grade_level", "section", "subject", "teacher", "classroom")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SchoolCalendarOccurrenceInline]


@admin.register(AttendanceRegister, site=school_admin_site)
class SchoolAttendanceRegisterAdmin(SchoolScopedAdmin):
    list_display = ("section", "date", "session_type", "status", "submitted_by", "approved_by")
    list_filter = ("status", "session_type", "date")
    search_fields = ("section__name", "section__grade__name")
    autocomplete_fields = ("academic_year", "academic_term", "section", "schedule")
    readonly_fields = ("id", "submitted_at", "approved_at", "locked_at", "created_at", "updated_at")
    inlines = [SchoolStudentAttendanceRecordInline]
    actions = ["action_approve_registers", "action_lock_registers"]

    @admin.action(description="اعتماد السجلات المحددة رسمياً وتعميم الحضور")
    def action_approve_registers(self, request, queryset):
        count = 0
        for reg in queryset:
            if reg.status != AttendanceRegister.Status.LOCKED:
                approve_register(reg, approved_by=request.user)
                count += 1
        self.message_user(request, f"تم اعتماد {count} سجل حضور وتعميم الحصص بنجاح.")

    @admin.action(description="إقفال السجلات المحددة نهائياً وحمايتها")
    def action_lock_registers(self, request, queryset):
        count = 0
        for reg in queryset:
            lock_register(reg, locked_by=request.user)
            count += 1
        self.message_user(request, f"تم إقفال {count} سجل حضور بنجاح.")


@admin.register(StudentAttendanceRecord, site=school_admin_site)
class SchoolStudentAttendanceRecordAdmin(SchoolScopedAdmin):
    list_display = ("student", "register", "status_category", "late_minutes", "recorded_by")
    list_filter = ("status_category", "register__date")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("register", "student", "status_type", "excuse_request")
    readonly_fields = ("id", "recorded_at", "created_at", "updated_at")


@admin.register(AttendanceReopenRequest, site=school_admin_site)
class SchoolAttendanceReopenRequestAdmin(SchoolScopedAdmin):
    list_display = ("register", "requested_by", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("register__section__name", "reason")
    autocomplete_fields = ("register",)
    readonly_fields = ("id", "reviewed_at", "created_at", "updated_at")
    actions = ["action_approve_reopen"]

    @admin.action(description="الموافقة على إعادة فتح السجلات المحددة")
    def action_approve_reopen(self, request, queryset):
        count = 0
        for req in queryset.filter(status=AttendanceReopenRequest.Status.PENDING):
            review_reopen_request(req, reviewed_by=request.user, is_approved=True, review_notes="معتمد من الإدارة")
            count += 1
        self.message_user(request, f"تمت الموافقة على فتح {count} سجل حضور.")


@admin.register(AttendanceExcuseRequest, site=school_admin_site)
class SchoolAttendanceExcuseRequestAdmin(SchoolScopedAdmin):
    list_display = ("student", "guardian", "request_type", "start_date", "end_date", "status", "reviewed_by")
    list_filter = ("status", "request_type")
    search_fields = ("student__first_name", "student__last_name", "guardian__user__first_name", "reason")
    autocomplete_fields = ("student", "guardian")
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


@admin.register(EarlyDepartureRequest, site=school_admin_site)
class SchoolEarlyDepartureRequestAdmin(SchoolScopedAdmin):
    list_display = ("student", "guardian", "date", "departure_time", "recipient_name", "status", "approved_by")
    list_filter = ("status", "date")
    search_fields = ("student__first_name", "student__last_name", "recipient_name", "recipient_phone")
    autocomplete_fields = ("student", "guardian")
    readonly_fields = ("id", "approved_at", "exit_confirmed_at", "created_at", "updated_at")
    actions = ["action_approve_early_departure", "action_confirm_gate_exit"]

    @admin.action(description="اعتماد طلبات الانصراف المبكر المحددة")
    def action_approve_early_departure(self, request, queryset):
        count = 0
        for req in queryset.filter(status=EarlyDepartureRequest.Status.PENDING):
            approve_early_departure(req, approved_by=request.user)
            count += 1
        self.message_user(request, f"تم اعتماد {count} طلب انصراف مبكر بنجاح.")

    @admin.action(description="تأكيد خروج الطالب من البوابة الأمنية وتحديث الحصص")
    def action_confirm_gate_exit(self, request, queryset):
        count = 0
        for req in queryset.filter(status=EarlyDepartureRequest.Status.APPROVED):
            confirm_gate_exit(req, confirmed_by=request.user, exit_notes="تم الاستلام عند البوابة")
            count += 1
        self.message_user(request, f"تم توثيق خروج {count} طالب من البوابة وتحديث حصصهم.")


@admin.register(AttendanceScoringPolicy, site=school_admin_site)
class SchoolAttendanceScoringPolicyAdmin(SchoolScopedAdmin):
    list_display = ("academic_year", "subject", "total_attendance_score", "calculation_mode", "unexcused_absence_deduction", "is_active")
    list_filter = ("calculation_mode", "is_active")
    search_fields = ("academic_year__name", "subject__name")
    autocomplete_fields = ("academic_year", "subject")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AttendanceScoreEntry, site=school_admin_site)
class SchoolAttendanceScoreEntryAdmin(SchoolScopedAdmin):
    list_display = ("student", "academic_term", "subject", "final_score", "raw_score", "deduction_total", "is_synced_to_gradebook")
    list_filter = ("is_synced_to_gradebook", "academic_term")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("student", "academic_term", "subject", "scoring_policy")
    readonly_fields = ("id", "calculated_at", "created_at", "updated_at")
    actions = ["action_sync_to_gradebook"]

    @admin.action(description="مزامنة درجات المواظبة المحددة مع سجل الدرجات GradeBook")
    def action_sync_to_gradebook(self, request, queryset):
        count = 0
        for entry in queryset:
            sync_score_to_gradebook(entry, teacher=None)
            count += 1
        self.message_user(request, f"تمت مزامنة {count} درجة مواظبة مع سجل الدرجات بنجاح.")


@admin.register(AttendanceAuditLog, site=school_admin_site)
class SchoolAttendanceAuditLogAdmin(SchoolScopedAdmin):
    list_display = ("action", "register", "student_record", "performed_by", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("register__section__name", "reason")
    autocomplete_fields = ("register", "student_record")
    readonly_fields = ("id", "register", "student_record", "action", "performed_by", "timestamp", "old_value", "new_value", "reason", "ip_address", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DailyAttendance, site=school_admin_site)
class SchoolDailyAttendanceAdmin(SchoolScopedAdmin):
    list_display = ("student", "date", "status", "late_minutes")
    list_filter = ("status", "date")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number")
    autocomplete_fields = ("student",)
    raw_id_fields = ("recorded_by",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PeriodAttendance, site=school_admin_site)
class SchoolPeriodAttendanceAdmin(SchoolScopedAdmin):
    list_display = ("student", "schedule", "date", "status")
    list_filter = ("status", "date")
    search_fields = ("student__first_name", "student__last_name", "schedule__subject__name")
    autocomplete_fields = ("schedule", "student")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FeeCategory, site=school_admin_site)
class SchoolFeeCategoryAdmin(SchoolScopedAdmin):
    list_display = ("name", "code", "is_mandatory")
    list_filter = ("is_mandatory",)
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FeeStructure, site=school_admin_site)
class SchoolFeeStructureAdmin(SchoolScopedAdmin):
    list_display = ("grade_level", "fee_category", "academic_year", "amount", "due_date")
    list_filter = ("academic_year", "grade_level")
    search_fields = ("grade_level__name", "fee_category__name")
    autocomplete_fields = ("academic_year", "grade_level", "fee_category")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentInvoice, site=school_admin_site)
class SchoolStudentInvoiceAdmin(SchoolScopedAdmin):
    list_display = ("invoice_number", "student", "total_amount", "discount_amount", "paid_amount", "status", "due_date")
    list_filter = ("status", "academic_year")
    search_fields = ("invoice_number", "student__first_name", "student__last_name")
    autocomplete_fields = ("student", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentReceipt, site=school_admin_site)
class SchoolPaymentReceiptAdmin(SchoolScopedAdmin):
    list_display = ("receipt_number", "student", "amount", "payment_method", "paid_at")
    list_filter = ("payment_method", "paid_at")
    search_fields = ("receipt_number", "reference_number", "student__first_name", "student__last_name")
    autocomplete_fields = ("student", "invoice")
    raw_id_fields = ("received_by",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FiscalYear, site=school_admin_site)
class SchoolFiscalYearAdmin(SchoolScopedAdmin):
    list_display = ("name", "start_date", "end_date", "is_closed")
    list_filter = ("is_closed",)
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Account, site=school_admin_site)
class SchoolAccountAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "account_type", "parent", "is_leaf")
    list_filter = ("account_type", "is_leaf")
    search_fields = ("code", "name")
    autocomplete_fields = ("parent",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CostCenter, site=school_admin_site)
class SchoolCostCenterAdmin(SchoolScopedAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(JournalEntry, site=school_admin_site)
class SchoolJournalEntryAdmin(SchoolScopedAdmin):
    list_display = ("entry_number", "date", "status", "source_module", "posted_at")
    list_filter = ("status", "source_module", "date")
    search_fields = ("entry_number", "description", "source_reference")
    raw_id_fields = ("posted_by", "fiscal_period")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Accounting Vouchers & Expenses in School Admin
# -----------------------------------------------------------------------------
from apps.accounting.models import ExpenseCategory, PaymentVoucher, ReceiptVoucher


@admin.register(ExpenseCategory, site=school_admin_site)
class SchoolExpenseCategoryAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "default_account")
    search_fields = ("code", "name")
    raw_id_fields = ("default_account",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentVoucher, site=school_admin_site)
class SchoolPaymentVoucherAdmin(SchoolScopedAdmin):
    list_display = ("voucher_number", "date", "paid_to", "amount", "payment_method", "credit_account", "debit_account", "status")
    list_filter = ("status", "payment_method", "date")
    search_fields = ("voucher_number", "paid_to", "description")
    raw_id_fields = ("credit_account", "debit_account", "cost_center", "journal_entry")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ReceiptVoucher, site=school_admin_site)
class SchoolReceiptVoucherAdmin(SchoolScopedAdmin):
    list_display = ("voucher_number", "date", "received_from", "amount", "payment_method", "debit_account", "credit_account", "status")
    list_filter = ("status", "payment_method", "date")
    search_fields = ("voucher_number", "received_from", "description")
    raw_id_fields = ("debit_account", "credit_account", "cost_center", "journal_entry")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Payroll & Human Resources in School Admin
# -----------------------------------------------------------------------------
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun, Payslip


@admin.register(EmployeeContract, site=school_admin_site)
class SchoolEmployeeContractAdmin(SchoolScopedAdmin):
    list_display = ("contract_number", "teacher", "staff_member", "contract_type", "basic_salary", "gross_salary", "net_salary", "is_active")
    list_filter = ("contract_type", "is_active")
    search_fields = ("contract_number", "teacher__user__first_name", "staff_member__user__first_name")
    raw_id_fields = ("teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(EmployeeLoanAdvance, site=school_admin_site)
class SchoolEmployeeLoanAdvanceAdmin(SchoolScopedAdmin):
    list_display = ("loan_number", "teacher", "staff_member", "amount", "monthly_installment", "repaid_amount", "remaining_amount", "status")
    list_filter = ("status",)
    search_fields = ("loan_number", "teacher__user__first_name", "staff_member__user__first_name")
    raw_id_fields = ("teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PayrollRun, site=school_admin_site)
class SchoolPayrollRunAdmin(SchoolScopedAdmin):
    list_display = ("name", "year", "month", "total_basic", "total_allowances", "total_deductions", "total_net", "status")
    list_filter = ("status", "year")
    search_fields = ("name",)
    raw_id_fields = ("approved_by", "journal_entry")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Payslip, site=school_admin_site)
class SchoolPayslipAdmin(SchoolScopedAdmin):
    list_display = ("teacher", "staff_member", "payroll_run", "basic_salary", "total_earnings", "total_deductions", "net_salary", "is_paid")
    list_filter = ("is_paid", "payroll_run__year")
    search_fields = ("teacher__user__first_name", "staff_member__user__first_name", "payroll_run__name")
    raw_id_fields = ("payroll_run", "teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Fixed Assets in School Admin
# -----------------------------------------------------------------------------
from apps.assets.models import AssetCategory, AssetDepreciationEntry, FixedAsset


@admin.register(AssetCategory, site=school_admin_site)
class SchoolAssetCategoryAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "annual_depreciation_rate", "useful_life_years")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FixedAsset, site=school_admin_site)
class SchoolFixedAssetAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "category", "purchase_date", "purchase_cost", "accumulated_depreciation", "current_book_value", "status")
    list_filter = ("category", "status")
    search_fields = ("code", "name", "location_room")
    raw_id_fields = ("category", "custodian")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AssetDepreciationEntry, site=school_admin_site)
class SchoolAssetDepreciationEntryAdmin(SchoolScopedAdmin):
    list_display = ("asset", "fiscal_year", "depreciation_amount", "date")
    list_filter = ("fiscal_year",)
    search_fields = ("asset__name", "asset__code")
    raw_id_fields = ("asset", "fiscal_year")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Procurement & Inventory in School Admin
# -----------------------------------------------------------------------------
from apps.inventory.models import InventoryItem, PurchaseOrder, StockMovement, Supplier, Warehouse


@admin.register(Supplier, site=school_admin_site)
class SchoolSupplierAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "contact_person", "phone", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "contact_person", "phone")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Warehouse, site=school_admin_site)
class SchoolWarehouseAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "manager", "location")
    search_fields = ("code", "name", "location")
    raw_id_fields = ("manager", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(InventoryItem, site=school_admin_site)
class SchoolInventoryItemAdmin(SchoolScopedAdmin):
    list_display = ("code", "name", "warehouse", "category", "unit", "current_stock", "unit_cost", "reorder_level")
    list_filter = ("category", "warehouse")
    search_fields = ("code", "name", "category")
    raw_id_fields = ("warehouse",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StockMovement, site=school_admin_site)
class SchoolStockMovementAdmin(SchoolScopedAdmin):
    list_display = ("date", "movement_type", "item", "quantity", "unit_cost", "reference", "recipient_name")
    list_filter = ("movement_type", "date")
    search_fields = ("item__name", "item__code", "reference", "recipient_name")
    raw_id_fields = ("item",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PurchaseOrder, site=school_admin_site)
class SchoolPurchaseOrderAdmin(SchoolScopedAdmin):
    list_display = ("order_number", "supplier", "warehouse", "order_date", "total_amount", "status")
    list_filter = ("status", "order_date")
    search_fields = ("order_number", "supplier__name")
    raw_id_fields = ("supplier", "warehouse", "approved_by")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# School Services (Buses, Library, Clinic) in School Admin
# -----------------------------------------------------------------------------
from apps.school_services.models import (
    BookLoan,
    BookRequisitionItem,
    BookRequisitionOrder,
    BusFinancialSettlement,
    BusRoute,
    ClinicVisit,
    LibraryBook,
    StudentBookDistribution,
    StudentBusSubscription,
    StudentHealthProfile,
)


@admin.register(BusRoute, site=school_admin_site)
class SchoolBusRouteAdmin(SchoolScopedAdmin):
    list_display = ("route_code", "route_name", "bus_number", "driver_name", "driver_phone", "compensation_type", "contract_amount", "contractor_type", "monthly_fee", "is_active")
    list_filter = ("is_active", "compensation_type", "contractor_type")
    search_fields = ("route_code", "route_name", "bus_number", "driver_name", "destination_area")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BusFinancialSettlement, site=school_admin_site)
class SchoolBusFinancialSettlementAdmin(SchoolScopedAdmin):
    list_display = ("bus_route", "month", "year", "student_count", "rate_applied", "gross_due", "advances_withdrawn", "net_payable", "status")
    list_filter = ("status", "year", "month")
    search_fields = ("bus_route__bus_number", "bus_route__driver_name", "notes")
    raw_id_fields = ("bus_route", "academic_year", "approved_by", "payment_voucher")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentBookDistribution, site=school_admin_site)
class SchoolStudentBookDistributionAdmin(SchoolScopedAdmin):
    list_display = ("student", "book_title", "fee_amount", "delivery_status", "delivered_at", "delivered_by")
    list_filter = ("delivery_status", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "book_title")
    raw_id_fields = ("student", "academic_year", "delivered_by", "invoice")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentBusSubscription, site=school_admin_site)
class SchoolStudentBusSubscriptionAdmin(SchoolScopedAdmin):
    list_display = ("student", "bus_route", "academic_year", "subscription_type", "status")
    list_filter = ("status", "subscription_type", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "bus_route__route_name")
    raw_id_fields = ("student", "bus_route", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LibraryBook, site=school_admin_site)
class SchoolLibraryBookAdmin(SchoolScopedAdmin):
    list_display = ("isbn", "title", "author", "category", "total_copies", "available_copies", "shelf_location")
    list_filter = ("category",)
    search_fields = ("isbn", "title", "author", "publisher")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BookLoan, site=school_admin_site)
class SchoolBookLoanAdmin(SchoolScopedAdmin):
    list_display = ("book", "student", "teacher", "borrow_date", "due_date", "return_date", "status", "fine_amount")
    list_filter = ("status", "borrow_date")
    search_fields = ("book__title", "student__first_name", "teacher__user__first_name")
    raw_id_fields = ("book", "student", "teacher")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentHealthProfile, site=school_admin_site)
class SchoolStudentHealthProfileAdmin(SchoolScopedAdmin):
    list_display = ("student", "blood_type", "emergency_contact_name", "emergency_contact_phone")
    list_filter = ("blood_type",)
    search_fields = ("student__first_name", "student__last_name", "emergency_contact_name")
    raw_id_fields = ("student",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ClinicVisit, site=school_admin_site)
class SchoolClinicVisitAdmin(SchoolScopedAdmin):
    list_display = ("student", "visit_date", "symptoms", "temperature", "sent_home", "parent_notified", "attended_by")
    list_filter = ("sent_home", "parent_notified", "visit_date")
    search_fields = ("student__first_name", "student__last_name", "diagnosis")
    raw_id_fields = ("student",)
    readonly_fields = ("id", "created_at", "updated_at")


from unfold.admin import TabularInline


class SchoolBookRequisitionItemInline(TabularInline):
    model = BookRequisitionItem
    extra = 1


@admin.register(BookRequisitionOrder, site=school_admin_site)
class SchoolBookRequisitionOrderAdmin(SchoolScopedAdmin):
    list_display = ("order_number", "requested_by", "academic_year", "grade_level", "section", "status", "approved_by", "fulfilled_by", "created_at")
    list_filter = ("status", "academic_year")
    search_fields = ("order_number", "requested_by__phone", "notes")
    raw_id_fields = ("requested_by", "approved_by", "fulfilled_by", "academic_year", "grade_level", "section")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at", "fulfilled_at")
    inlines = (SchoolBookRequisitionItemInline,)


@admin.register(BookRequisitionItem, site=school_admin_site)
class SchoolBookRequisitionItemAdmin(SchoolScopedAdmin):
    list_display = ("requisition", "book_title", "quantity_requested", "quantity_approved", "quantity_dispatched")
    search_fields = ("book_title", "requisition__order_number")
    raw_id_fields = ("requisition",)
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Fee Installment Plans in School Admin
# -----------------------------------------------------------------------------
from apps.student_fees.models import (
    FeeInstallment,
    FeeInstallmentPlan,
    PaymentAllocation,
    StudentCreditTransaction,
)


@admin.register(FeeInstallmentPlan, site=school_admin_site)
class SchoolFeeInstallmentPlanAdmin(SchoolScopedAdmin):
    list_display = ("plan_name", "student", "invoice", "total_amount", "number_of_installments")
    search_fields = ("plan_name", "student__first_name", "student__last_name", "invoice__invoice_number")
    raw_id_fields = ("student", "invoice")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FeeInstallment, site=school_admin_site)
class SchoolFeeInstallmentAdmin(SchoolScopedAdmin):
    list_display = ("installment_number", "title", "plan", "amount", "due_date", "paid_date", "status")
    list_filter = ("status", "due_date")
    search_fields = ("title", "plan__student__first_name", "plan__student__last_name")
    raw_id_fields = ("plan", "receipt")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentAllocation, site=school_admin_site)
class SchoolPaymentAllocationAdmin(SchoolScopedAdmin):
    list_display = ("receipt", "invoice", "installment", "allocated_amount", "status", "allocated_at")
    list_filter = ("status", "allocated_at")
    search_fields = ("receipt__receipt_number", "invoice__invoice_number", "notes")
    raw_id_fields = ("receipt", "invoice", "installment", "allocated_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentCreditTransaction, site=school_admin_site)
class SchoolStudentCreditTransactionAdmin(SchoolScopedAdmin):
    list_display = ("transaction_type", "student", "amount", "invoice", "receipt", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("student__first_name", "student__last_name", "notes")
    raw_id_fields = ("student", "invoice", "receipt")
    readonly_fields = ("id", "created_at", "updated_at")


# -----------------------------------------------------------------------------
# Exam Control Room & Committees in School Admin
# -----------------------------------------------------------------------------
from apps.assessments.models import (
    ExamCommittee,
    ExamSeating,
    OnlineExam,
    QuestionBank,
    StudentOnlineExamSubmission,
)


@admin.register(ExamCommittee, site=school_admin_site)
class SchoolExamCommitteeAdmin(SchoolScopedAdmin):
    list_display = ("committee_number", "name", "location_room", "capacity", "head_supervisor")
    search_fields = ("committee_number", "name", "location_room")
    raw_id_fields = ("head_supervisor",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ExamSeating, site=school_admin_site)
class SchoolExamSeatingAdmin(SchoolScopedAdmin):
    list_display = ("seating_number", "student", "committee", "academic_year", "secret_code")
    list_filter = ("academic_year", "committee")
    search_fields = ("seating_number", "secret_code", "student__first_name", "student__last_name")
    raw_id_fields = ("student", "committee", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(QuestionBank, site=school_admin_site)
class SchoolQuestionBankAdmin(SchoolScopedAdmin):
    list_display = ("question_text_short", "subject", "grade_level", "unit_name", "question_type", "difficulty", "default_marks")
    list_filter = ("question_type", "difficulty", "subject", "grade_level")
    search_fields = ("question_text", "unit_name", "topic", "subject__name")
    raw_id_fields = ("subject", "grade_level", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")

    def question_text_short(self, obj):
        return obj.question_text[:50] + ("..." if len(obj.question_text) > 50 else "")
    question_text_short.short_description = "نص السؤال"


@admin.register(OnlineExam, site=school_admin_site)
class SchoolOnlineExamAdmin(SchoolScopedAdmin):
    list_display = ("title", "subject", "academic_term", "grade_level", "exam_type", "duration_minutes", "total_marks", "passing_marks", "is_published")
    list_filter = ("is_published", "exam_type", "subject")
    search_fields = ("title", "subject__name", "instructions")
    raw_id_fields = ("subject", "academic_term", "grade_level", "section", "created_by")
    filter_horizontal = ("questions",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentOnlineExamSubmission, site=school_admin_site)
class SchoolStudentOnlineExamSubmissionAdmin(SchoolScopedAdmin):
    list_display = ("exam", "student", "final_score", "auto_score", "status", "submitted_at")
    list_filter = ("status", "exam")
    search_fields = ("student__first_name", "student__last_name", "exam__title")
    raw_id_fields = ("exam", "student", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "submitted_at")


# -----------------------------------------------------------------------------
# Messaging Gateways (WhatsApp / SMS) in School Admin
# -----------------------------------------------------------------------------
from apps.notifications.models import SchoolMessagingGateway


@admin.register(SchoolMessagingGateway, site=school_admin_site)
class SchoolMessagingGatewayAdmin(SchoolScopedAdmin):
    list_display = ("name", "channel", "provider", "sender_id", "auto_ai_reply", "is_active")
    list_filter = ("channel", "provider", "auto_ai_reply", "is_active")
    search_fields = ("name", "sender_id", "api_endpoint_url")
    readonly_fields = ("id", "created_at", "updated_at")
