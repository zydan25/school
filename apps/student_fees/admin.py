from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.student_fees.models import (
    FeeCategory,
    FeeInstallment,
    FeeInstallmentPlan,
    FeeStructure,
    PaymentAllocation,
    PaymentReceipt,
    StudentInvoice,
    StudentInvoiceItem,
)


class StudentInvoiceItemInline(TabularInline):
    model = StudentInvoiceItem
    extra = 1


@admin.register(FeeCategory)
class FeeCategoryAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "code", "is_mandatory", "school")
    list_filter = ("is_mandatory", "school")
    search_fields = ("name", "code", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FeeStructure)
class FeeStructureAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("grade_level", "fee_category", "academic_year", "amount", "due_date", "school")
    list_filter = ("academic_year", "grade_level", "school")
    search_fields = ("grade_level__name", "fee_category__name", "school__name")
    autocomplete_fields = ("school", "branch", "academic_year", "grade_level", "fee_category")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("invoice_number", "student", "total_amount", "discount_amount", "paid_amount", "remaining_amount", "status", "due_date", "school")
    list_filter = ("status", "academic_year", "school")
    search_fields = ("invoice_number", "student__first_name", "student__last_name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "academic_year")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (StudentInvoiceItemInline,)


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("receipt_number", "student", "amount", "payment_method", "paid_at", "received_by", "school")
    list_filter = ("payment_method", "paid_at", "school")
    search_fields = ("receipt_number", "reference_number", "student__first_name", "student__last_name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "invoice")
    readonly_fields = ("id", "created_at", "updated_at")


class FeeInstallmentInline(TabularInline):
    model = FeeInstallment
    extra = 1
    raw_id_fields = ("receipt",)


@admin.register(FeeInstallmentPlan)
class FeeInstallmentPlanAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("plan_name", "student", "invoice", "total_amount", "number_of_installments", "school")
    list_filter = ("school",)
    search_fields = ("plan_name", "student__first_name", "student__last_name", "invoice__invoice_number")
    raw_id_fields = ("student", "invoice", "school", "branch")
    inlines = (FeeInstallmentInline,)


@admin.register(FeeInstallment)
class FeeInstallmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("installment_number", "title", "plan", "amount", "due_date", "paid_date", "status", "school")
    list_filter = ("status", "due_date", "school")
    search_fields = ("title", "plan__student__first_name", "plan__student__last_name")
    raw_id_fields = ("plan", "receipt", "school", "branch")


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("receipt", "invoice", "installment", "allocated_amount", "status", "allocated_at", "school")
    list_filter = ("status", "allocated_at", "school")
    search_fields = ("receipt__receipt_number", "invoice__invoice_number", "notes")
    raw_id_fields = ("receipt", "invoice", "installment", "allocated_by", "school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
