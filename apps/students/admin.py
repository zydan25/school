from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.students.models import (
    AdministrativeSummon,
    Guardian,
    GuardianConsent,
    SchoolComplaint,
    StudentDocument,
    Student,
    StudentEnrollment,
    StudentGuardianRelation,
    StudentIncidentReport,
)


class StudentGuardianInline(TabularInline):
    model = StudentGuardianRelation
    extra = 1
    autocomplete_fields = ("guardian",)


@admin.register(Student)
class StudentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("get_full_name", "student_id_number", "grade_level", "section", "school", "status", "enrollment_date")
    list_filter = ("status", "grade_level", "school", "academic_year")
    search_fields = ("student_id_number", "first_name", "last_name", "national_id", "school__name")
    autocomplete_fields = ("school", "branch", "user", "grade_level", "section", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at", "credit_balance")
    inlines = (StudentGuardianInline,)


@admin.register(Guardian)
class GuardianAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("user", "relationship_type", "school", "national_id", "emergency_phone")
    list_filter = ("relationship_type", "school")
    search_fields = ("user__phone", "user__first_name", "user__last_name", "national_id", "school__name")
    autocomplete_fields = ("school", "branch", "user")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentGuardianRelation)
class StudentGuardianRelationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "guardian", "is_primary", "receives_notifications", "can_pickup", "school")
    list_filter = ("is_primary", "receives_notifications", "can_pickup", "school")
    search_fields = ("student__first_name", "student__last_name", "guardian__user__first_name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "guardian")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentIncidentReport)
class StudentIncidentReportAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("title", "student", "reporter", "severity", "incident_type", "date", "parent_notified", "is_resolved", "school")
    list_filter = ("severity", "incident_type", "parent_notified", "is_resolved", "school")
    search_fields = ("title", "student__first_name", "student__last_name", "reporter__phone", "details")
    raw_id_fields = ("school", "branch", "student", "reporter")
    readonly_fields = ("id", "created_at", "updated_at", "parent_seen_at")


@admin.register(AdministrativeSummon)
class AdministrativeSummonAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("summon_type", "target_user", "student", "appointment_date", "is_attended", "issued_by", "school")
    list_filter = ("summon_type", "is_attended", "school")
    search_fields = ("student__first_name", "student__last_name", "target_user__phone", "target_user__first_name", "reason")
    raw_id_fields = ("school", "branch", "student", "target_user", "issued_by")
    readonly_fields = ("id", "created_at", "updated_at", "attended_at")


@admin.register(SchoolComplaint)
class SchoolComplaintAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("subject", "category", "status", "submitter", "resolved_by", "resolved_at", "school")
    list_filter = ("category", "status", "school")
    search_fields = ("subject", "details", "submitter__phone")
    raw_id_fields = ("school", "branch", "submitter", "resolved_by")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at")


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("student", "academic_year", "grade_level", "section", "status", "enrollment_date", "school")
    list_filter = ("status", "academic_year", "grade_level", "school")
    search_fields = ("student__first_name", "student__last_name", "student__student_id_number", "notes")
    raw_id_fields = ("student", "academic_year", "grade_level", "section", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentDocument)
class StudentDocumentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "title", "student", "document_type", "visible_to_guardian",
        "uploaded_by", "created_at", "school",
    )
    list_filter = ("document_type", "visible_to_guardian", "school")
    search_fields = (
        "title", "student__first_name", "student__last_name",
        "student__student_id_number",
    )
    raw_id_fields = ("school", "branch", "student", "uploaded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GuardianConsent)
class GuardianConsentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = (
        "title", "student", "guardian", "consent_type",
        "status", "requested_at", "responded_at", "school",
    )
    list_filter = ("consent_type", "status", "school")
    search_fields = (
        "title", "student__first_name", "student__last_name",
        "guardian__user__phone", "guardian__user__full_name",
    )
    raw_id_fields = (
        "school", "branch", "student", "guardian", "requested_by", "responded_by",
    )
    readonly_fields = ("id", "created_at", "updated_at", "requested_at", "responded_at")
