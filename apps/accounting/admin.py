from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.accounting.models import (
    Account,
    CostCenter,
    ExpenseCategory,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
    PaymentVoucher,
    ReceiptVoucher,
)
from apps.core.admin import AuditedAdminMixin


class FiscalPeriodInline(TabularInline):
    model = FiscalPeriod
    extra = 0


class JournalEntryLineInline(TabularInline):
    model = JournalEntryLine
    extra = 2
    autocomplete_fields = ("account", "cost_center")


@admin.register(FiscalYear)
class FiscalYearAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_closed", "school")
    list_filter = ("is_closed", "school")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (FiscalPeriodInline,)


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "fiscal_year", "period_number", "start_date", "end_date", "is_closed", "school")
    list_filter = ("is_closed", "fiscal_year", "school")
    search_fields = ("name", "fiscal_year__name", "school__name")
    autocomplete_fields = ("school", "branch", "fiscal_year")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Account)
class AccountAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "account_type", "parent", "is_leaf", "school")
    list_filter = ("account_type", "is_leaf", "school")
    search_fields = ("code", "name", "school__name")
    autocomplete_fields = ("school", "branch", "parent")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CostCenter)
class CostCenterAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "school")
    list_filter = ("school",)
    search_fields = ("code", "name", "school__name")
    autocomplete_fields = ("school", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(JournalEntry)
class JournalEntryAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("entry_number", "date", "status", "source_module", "posted_at", "posted_by", "school")
    list_filter = ("status", "source_module", "date", "school")
    search_fields = ("entry_number", "description", "source_reference", "school__name")
    autocomplete_fields = ("school", "branch", "fiscal_period")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (JournalEntryLineInline,)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "default_account", "school")
    list_filter = ("school",)
    search_fields = ("code", "name")
    raw_id_fields = ("default_account", "school", "branch")


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("voucher_number", "date", "paid_to", "amount", "payment_method", "credit_account", "debit_account", "status", "school")
    list_filter = ("school", "status", "payment_method", "date")
    search_fields = ("voucher_number", "paid_to", "description")
    raw_id_fields = ("credit_account", "debit_account", "cost_center", "journal_entry", "school", "branch")


@admin.register(ReceiptVoucher)
class ReceiptVoucherAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("voucher_number", "date", "received_from", "amount", "payment_method", "debit_account", "credit_account", "status", "school")
    list_filter = ("school", "status", "payment_method", "date")
    search_fields = ("voucher_number", "received_from", "description")
    raw_id_fields = ("debit_account", "credit_account", "cost_center", "journal_entry", "school", "branch")

