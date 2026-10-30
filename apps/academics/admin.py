from apps.core.admin import AuditedAdminMixin
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.academics.models import (
    AcademicTerm, AcademicYear, Classroom, EducationalStage, GradeLevel,
    PeriodDefinition, SchoolWorkingDay, Section, Subject,
)


class AcademicTermInline(TabularInline):
    model = AcademicTerm
    extra = 0
    fields = ("name", "number", "starts_on", "ends_on", "is_current", "is_closed")
    show_change_link = True


@admin.register(AcademicYear)
class AcademicYearAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "starts_on", "ends_on", "status", "is_current")
    list_filter = ("status", "is_current", "school")
    search_fields = ("name", "code", "school__name", "school__code")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (AcademicTermInline,)
    date_hierarchy = "starts_on"
    list_select_related = ("school", "branch")
    fieldsets = (
        ("تعريف السنة", {"fields": (("school", "branch"), ("name", "code"), ("starts_on", "ends_on"), ("status", "is_current"))}),
        ("الإغلاق والمتابعة", {"fields": (("opened_at", "closed_at"), ("notes",))}),
        ("التواريخ", {"classes": ("collapse",), "fields": (("created_at", "updated_at"),)}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AcademicTerm)
class AcademicTermAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "academic_year", "school", "number", "starts_on", "ends_on", "is_current", "is_closed")
    list_filter = ("is_current", "is_closed", "school", "academic_year")
    search_fields = ("name", "academic_year__name", "school__name")
    autocomplete_fields = ("school", "branch", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(EducationalStage)
class EducationalStageAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "sequence", "is_active", "is_archived")
    list_filter = ("is_active", "school", "is_archived")
    search_fields = ("name", "code", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
    list_editable = ("sequence", "is_active")


@admin.register(GradeLevel)
class GradeLevelAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "stage", "school", "sequence", "age_from", "age_to", "is_active")
    list_filter = ("is_active", "stage", "school")
    search_fields = ("name", "code", "stage__name", "school__name")
    autocomplete_fields = ("school", "branch", "stage")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("school", "stage")


@admin.register(Classroom)
class ClassroomAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "classroom_type", "capacity", "building", "is_active")
    list_filter = ("classroom_type", "is_active", "school")
    search_fields = ("name", "code", "building", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Section)
class SectionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "grade", "academic_year", "school", "homeroom_classroom", "capacity", "is_active")
    list_filter = ("is_active", "school", "academic_year", "grade")
    search_fields = ("name", "code", "grade__name", "academic_year__name", "school__name")
    autocomplete_fields = ("school", "branch", "academic_year", "grade", "homeroom_classroom")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("school", "academic_year", "grade", "homeroom_classroom")


@admin.register(Subject)
class SubjectAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "is_core", "default_weekly_periods", "max_score", "is_active")
    list_filter = ("is_core", "is_active", "school")
    search_fields = ("name", "short_name", "code", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PeriodDefinition)
class PeriodDefinitionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("period_number", "name", "school", "starts_at", "ends_at", "kind", "is_active")
    list_filter = ("kind", "is_active", "school")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SchoolWorkingDay)
class SchoolWorkingDayAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("weekday", "school", "is_working", "sequence", "first_period", "last_period")
    list_filter = ("is_working", "school")
    search_fields = ("school__name",)
    autocomplete_fields = ("school", "branch", "first_period", "last_period")
    readonly_fields = ("id", "created_at", "updated_at")
