from django.contrib import admin
from django.db import transaction
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from apps.auditlog.services import record_event
from apps.core.admin import AuditedAdminMixin
from apps.tenants.models import Branch, School, SchoolDomain, SchoolSettings


class BranchInline(TabularInline):
    model = Branch
    extra = 0
    fields = ("code", "name", "is_main", "status", "phone", "capacity")
    show_change_link = True


class DomainInline(TabularInline):
    model = SchoolDomain
    extra = 0
    fields = ("domain", "is_primary", "status", "verified_at")
    readonly_fields = ("verified_at",)
    show_change_link = True


class SchoolSettingsInline(TabularInline):
    model = SchoolSettings
    extra = 0
    max_num = 1
    can_delete = False
    fields = (
        "allow_guardian_multiple_children", "require_student_photo",
        "require_admission_approval", "attendance_lock_after_days",
        "default_lesson_minutes", "library_default_loan_days",
        "library_max_renewals", "library_overdue_fine_per_day",
        "library_max_overdue_fine", "library_lost_book_fine",
    )


@admin.register(School)
class SchoolAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "owner", "school_type", "status_badge", "city", "country_code", "created_at")
    list_filter = ("status", "school_type", "country_code", "city", "is_archived")
    search_fields = ("name", "code", "legal_name", "email", "phone", "city", "owner__full_name", "owner__phone")
    readonly_fields = ("id", "slug", "activated_at", "suspended_at", "created_at", "updated_at")
    list_per_page = 30
    date_hierarchy = "created_at"
    inlines = (BranchInline, DomainInline, SchoolSettingsInline)
    autocomplete_fields = ("owner",)
    actions = ("activate_schools", "suspend_schools", "archive_schools")
    list_select_related = False
    fieldsets = (
        ("الهوية والتصنيف", {"fields": (("name", "code"), ("owner", "slug", "school_type"), ("legal_name", "status"))}),
        ("العلامة التجارية", {"fields": (("logo",), ("brand_primary", "brand_secondary"))}),
        ("بيانات التواصل والموقع", {"fields": (("country_code", "city"), ("phone", "email"), ("website",), ("address",))}),
        ("الإعدادات الإقليمية", {"fields": (("timezone", "language_code", "currency_code"), ("established_on",))}),
        ("إدارة المنصة", {"classes": ("collapse",), "fields": (("activated_at", "suspended_at"), ("platform_notes",))}),
        ("الأرشفة والتواريخ", {"classes": ("collapse",), "fields": (("is_archived", "archived_at", "archived_by"), ("archive_reason",), ("created_at", "updated_at"))}),
    )

    @display(description="الحالة", ordering="status", label={"active": "success", "draft": "info", "suspended": "warning", "archived": "danger"})
    def status_badge(self, obj):
        return obj.get_status_display()

    @admin.action(description="تفعيل المدارس المحددة")
    def activate_schools(self, request, queryset):
        from django.core.exceptions import ValidationError

        from apps.tenants.services import activate_school
        count = 0
        errors = []
        for school in queryset.select_related("owner"):
            try:
                activate_school(school, actor=request.user)
                record_event(action="school.activated", description="تفعيل مدرسة من الإدارة المركزية", actor=request.user, school=school, obj=school, request=request)
                count += 1
            except ValidationError as exc:
                errors.append(f"{school.code}: {exc}")
        self.message_user(request, f"تم تفعيل {count} مدرسة. " + ("؛ ".join(errors) if errors else ""))

    @admin.action(description="إيقاف المدارس المحددة")
    def suspend_schools(self, request, queryset):
        from django.utils import timezone
        count = 0
        for school in queryset:
            school.status = School.Status.SUSPENDED
            school.suspended_at = timezone.now()
            school.save(update_fields=["status", "suspended_at", "updated_at"])
            record_event(action="school.suspended", description="إيقاف مدرسة من الإدارة المركزية", actor=request.user, school=school, obj=school, request=request)
            count += 1
        self.message_user(request, f"تم إيقاف {count} مدرسة.")

    @admin.action(description="أرشفة المدارس المحددة")
    def archive_schools(self, request, queryset):
        count = 0
        for school in queryset:
            school.archive(actor=request.user, reason="أرشفة من الإدارة المركزية")
            school.status = School.Status.ARCHIVED
            school.save(update_fields=["status", "updated_at"])
            record_event(action="school.archived", description="أرشفة مدرسة", actor=request.user, school=school, obj=school, request=request)
            count += 1
        self.message_user(request, f"تمت أرشفة {count} مدرسة.")

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.owner and obj.status == School.Status.ACTIVE:
            from apps.tenants.services import provision_school
            provision_school(obj, actor=request.user)


@admin.register(Branch)
class BranchAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "school", "is_main", "status", "capacity", "is_archived")
    list_filter = ("status", "is_main", "school", "is_archived")
    search_fields = ("name", "code", "school__name", "school__code", "manager_name")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at", "archived_at", "archived_by")
    list_select_related = ("school",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SchoolDomain)
class SchoolDomainAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("domain", "school", "is_primary", "status", "verified_at")
    list_filter = ("status", "is_primary")
    search_fields = ("domain", "school__name", "school__code")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "verification_token", "verified_at", "created_at", "updated_at")


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("school", "require_admission_approval", "require_student_photo", "attendance_lock_after_days", "default_lesson_minutes")
    search_fields = ("school__name", "school__code")
    autocomplete_fields = ("school",)
    readonly_fields = ("id", "created_at", "updated_at")
