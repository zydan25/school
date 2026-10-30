from apps.core.admin import AuditedAdminMixin
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.platform.models import Feature, Plan, PlanFeature, PlatformInvoice, PlatformPayment, SchoolFeatureOverride, Subscription


class PlanFeatureInline(TabularInline):
    model = PlanFeature
    extra = 0
    autocomplete_fields = ("feature",)
    fields = ("feature", "is_included", "limit_value", "configuration")


@admin.register(Feature)
class FeatureAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "module_key", "is_addon", "is_active")
    list_filter = ("module_key", "is_addon", "is_active")
    search_fields = ("name", "code", "description")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Plan)
class PlanAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "billing_cycle", "price", "currency_code", "max_students", "max_branches", "is_public", "is_active")
    list_filter = ("billing_cycle", "is_public", "is_active", "currency_code")
    search_fields = ("name", "code", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PlanFeatureInline,)
    fieldsets = (
        ("تعريف الباقة", {"fields": (("name", "code"), ("description",), ("is_public", "is_active", "display_order"))}),
        ("التسعير", {"fields": (("billing_cycle", "price", "currency_code"), ("trial_days",))}),
        ("حدود الاستخدام", {"fields": (("max_students", "max_staff"), ("max_branches", "storage_limit_mb"), ("limits",))}),
    )


@admin.register(PlanFeature)
class PlanFeatureAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("plan", "feature", "is_included", "limit_value")
    list_filter = ("is_included", "plan", "feature__module_key")
    search_fields = ("plan__name", "feature__name", "feature__code")
    autocomplete_fields = ("plan", "feature")


@admin.register(Subscription)
class SubscriptionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("school", "plan", "status", "starts_at", "ends_at", "auto_renew", "price_locked")
    list_filter = ("status", "plan", "auto_renew", "currency_code")
    search_fields = ("school__name", "school__code", "external_reference")
    autocomplete_fields = ("school", "plan")
    readonly_fields = ("id", "created_at", "updated_at", "cancelled_at", "suspended_at")
    date_hierarchy = "starts_at"
    list_select_related = ("school", "plan")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SchoolFeatureOverride)
class SchoolFeatureOverrideAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("school", "feature", "is_enabled", "limit_value", "starts_at", "ends_at", "granted_by")
    list_filter = ("is_enabled", "feature__module_key")
    search_fields = ("school__name", "school__code", "feature__name", "reason")
    autocomplete_fields = ("school", "feature", "granted_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PlatformInvoice)
class PlatformInvoiceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("number", "school", "subscription", "status", "issue_date", "due_date", "total", "paid_amount", "currency_code")
    list_filter = ("status", "currency_code", "issue_date")
    search_fields = ("number", "school__name", "school__code", "subscription__plan__name")
    autocomplete_fields = ("school", "subscription")
    readonly_fields = ("id", "issued_at", "created_at", "updated_at")
    date_hierarchy = "issue_date"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlatformPayment)
class PlatformPaymentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("invoice", "amount", "currency_code", "status", "method", "provider", "paid_at")
    list_filter = ("status", "method", "provider", "currency_code")
    search_fields = ("invoice__number", "invoice__school__name", "provider_reference")
    autocomplete_fields = ("invoice",)
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False
