from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.student_fees.models import (
    FeeCategory,
    FeeDiscountPolicy,
    FeeDiscountRequest,
    FeeInstallment,
    FeeInstallmentPlan,
    FeeStructure,
    PaymentAllocation,
    PaymentReceipt,
    StudentCreditTransaction,
    StudentInvoice,
    StudentInvoiceItem,
)


class StudentInvoiceItemInline(TabularInline):
    model = StudentInvoiceItem
    extra = 0
    can_delete = False
    readonly_fields = ("school", "branch", "invoice", "fee_category", "description", "amount", "discount_amount")

    def has_add_permission(self, request, obj=None):
        return False


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
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch",
        "invoice_number", "student", "academic_year", "total_amount",
        "discount_amount", "paid_amount", "status", "issue_date",
        "due_date", "notes", "journal_entry", "idempotency_key",
    )
    inlines = (StudentInvoiceItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("receipt_number", "student", "amount", "payment_method", "paid_at", "received_by", "school")
    list_filter = ("payment_method", "paid_at", "school")
    search_fields = ("receipt_number", "reference_number", "student__first_name", "student__last_name", "school__name")
    autocomplete_fields = ("school", "branch", "student", "invoice")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch",
        "receipt_number", "student", "invoice", "amount", "payment_method",
        "reference_number", "paid_at", "received_by", "journal_entry",
        "idempotency_key", "is_cancelled",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FeeInstallmentInline(TabularInline):
    model = FeeInstallment
    extra = 0
    can_delete = False
    raw_id_fields = ("receipt",)
    readonly_fields = (
        "school", "branch", "plan", "installment_number", "title",
        "amount", "paid_amount", "due_date", "paid_date", "status", "receipt",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FeeInstallmentPlan)
class FeeInstallmentPlanAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("plan_name", "student", "invoice", "total_amount", "number_of_installments", "school")
    list_filter = ("school",)
    search_fields = ("plan_name", "student__first_name", "student__last_name", "invoice__invoice_number")
    raw_id_fields = ("student", "invoice", "school", "branch")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch",
        "student", "invoice", "plan_name", "total_amount",
        "number_of_installments", "notes",
    )
    inlines = (FeeInstallmentInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FeeInstallment)
class FeeInstallmentAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("installment_number", "title", "plan", "amount", "due_date", "paid_date", "status", "school")
    list_filter = ("status", "due_date", "school")
    search_fields = ("title", "plan__student__first_name", "plan__student__last_name")
    raw_id_fields = ("plan", "receipt", "school", "branch")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch", "plan",
        "installment_number", "title", "amount", "paid_amount",
        "due_date", "status", "paid_date", "receipt",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("receipt", "invoice", "installment", "allocated_amount", "status", "allocated_at", "school")
    list_filter = ("status", "allocated_at", "school")
    search_fields = ("receipt__receipt_number", "invoice__invoice_number", "notes")
    raw_id_fields = ("receipt", "invoice", "installment", "allocated_by", "school", "branch")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch",
        "receipt", "credit_transaction", "invoice", "installment",
        "allocated_amount", "allocated_at", "allocated_by", "status", "notes",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentCreditTransaction)
class StudentCreditTransactionAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("transaction_type", "student", "amount", "invoice", "receipt", "created_at", "school")
    list_filter = ("transaction_type", "school", "created_at")
    search_fields = ("student__first_name", "student__last_name", "notes")
    raw_id_fields = ("student", "invoice", "receipt", "school", "branch")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch", "student",
        "transaction_type", "amount", "balance_before", "balance_after",
        "invoice", "receipt", "source_receipt", "is_reversed",
        "reversed_by_transaction", "created_by", "notes",
        "refund_payment_method", "refund_reference", "idempotency_key",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FeeDiscountPolicy)
class FeeDiscountPolicyAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("school", "max_discount_percent", "auto_approval_limit", "allow_full_exemption")
    list_filter = ("allow_full_exemption", "school")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FeeDiscountRequest)
class FeeDiscountRequestAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("invoice", "amount", "status", "requested_by", "approved_by", "decided_at", "school")
    list_filter = ("status", "school", "created_at")
    search_fields = ("invoice__invoice_number", "invoice__student__first_name", "reason")
    autocomplete_fields = ("school", "branch", "invoice", "requested_by", "approved_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "school", "branch", "invoice",
        "idempotency_key", "amount", "reason", "status", "requested_by",
        "approved_by", "decided_at", "decision_notes",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
