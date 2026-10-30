from apps.core.admin import AuditedAdminMixin
"""Dedicated per-school admin site with mandatory tenant scoping at queryset level."""
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.sites import UnfoldAdminSite

from apps.accounts.models import MembershipRole, SchoolInvitation, SchoolMembership, SchoolRole, User
from apps.accounts.services import has_school_permission, is_platform_operator
from apps.academics.models import (
    AcademicTerm, AcademicYear, Classroom, EducationalStage, GradeLevel,
    PeriodDefinition, SchoolWorkingDay, Section, Subject,
)
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
    list_display = ("name", "code", "grade", "academic_year", "homeroom_classroom", "capacity", "is_active")
    list_filter = ("academic_year", "grade", "is_active")
    search_fields = ("name", "code", "grade__name")
    readonly_fields = ("id", "created_at", "updated_at")


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
from apps.staff.models import Teacher, TeacherAssignment
from apps.students.models import Student, Guardian, StudentGuardianRelation
from apps.timetable.models import ClassSchedule, DailyLessonLog
from apps.assignments.models import Homework, HomeworkSubmission
from apps.assessments.models import AssessmentType, GradeBook
from apps.copilot.models import CurriculumDocument, AIChatSession


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


@admin.register(Student, site=school_admin_site)
class SchoolStudentAdmin(SchoolScopedAdmin):
    list_display = ("get_full_name", "student_id_number", "grade_level", "section", "status")
    list_filter = ("status", "grade_level", "academic_year")
    search_fields = ("student_id_number", "first_name", "last_name", "national_id")
    autocomplete_fields = ("grade_level", "section", "academic_year")
    raw_id_fields = ("user",)
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


@admin.register(ClassSchedule, site=school_admin_site)
class SchoolClassScheduleAdmin(SchoolScopedAdmin):
    list_display = ("get_day_of_week_display", "period_number", "subject", "section", "teacher", "classroom")
    list_filter = ("day_of_week", "academic_year", "subject")
    search_fields = ("subject__name", "section__name", "teacher__user__first_name")
    autocomplete_fields = ("academic_year", "academic_term", "section", "subject", "teacher", "classroom")
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
from apps.attendance.models import DailyAttendance, PeriodAttendance
from apps.student_fees.models import FeeCategory, FeeStructure, StudentInvoice, PaymentReceipt
from apps.accounting.models import FiscalYear, Account, CostCenter, JournalEntry


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
