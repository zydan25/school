from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.student_fees.models import FeeCategory, FeeStructure, PaymentReceipt, StudentInvoice, StudentInvoiceItem


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
