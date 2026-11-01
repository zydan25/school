from django.contrib import admin, messages
from django.core.exceptions import ValidationError
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
    TreasuryAccount,
    TreasuryTransfer,
    BankReconciliation,
    BankStatementLine,
)
from apps.accounting.services.period_closing import close_fiscal_period, close_fiscal_year, open_fiscal_year
from apps.accounting.services.treasury import (
    complete_bank_reconciliation,
    create_treasury_transfer,
    reverse_treasury_transfer,
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
    readonly_fields = (
        "id", "created_at", "updated_at", "is_closed",
        "closed_at", "closed_by", "closing_entry", "opening_entry",
    )
    inlines = (FiscalPeriodInline,)
    actions = ("close_selected_fiscal_years", "open_selected_fiscal_years")

    @admin.action(description="ترحيل الأرصدة الافتتاحية من السنة السابقة")
    def open_selected_fiscal_years(self, request, queryset):
        opened = 0
        failures = []
        for year in queryset:
            previous = FiscalYear.objects.filter(
                school=year.school,
                is_closed=True,
                end_date__lt=year.start_date,
                is_archived=False,
            ).order_by("-end_date").first()
            if not previous:
                failures.append(f"{year.name}: لا توجد سنة سابقة مقفلة.")
                continue
            try:
                open_fiscal_year(year, previous, user=request.user)
                opened += 1
            except ValidationError as exc:
                failures.append(f"{year.name}: {exc}")
        if opened:
            self.message_user(request, f"تم ترحيل الأرصدة الافتتاحية لـ {opened} سنة.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)

    @admin.action(description="إقفال السنوات المالية المحددة")
    def close_selected_fiscal_years(self, request, queryset):
        closed = 0
        failures = []
        for year in queryset:
            try:
                close_fiscal_year(year, request.user)
                closed += 1
            except ValidationError as exc:
                failures.append(f"{year.name}: {exc}")
        if closed:
            self.message_user(request, f"تم إقفال {closed} سنة مالية.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "fiscal_year", "period_number", "start_date", "end_date", "is_closed", "school")
    list_filter = ("is_closed", "fiscal_year", "school")
    search_fields = ("name", "fiscal_year__name", "school__name")
    autocomplete_fields = ("school", "branch", "fiscal_year")
    readonly_fields = (
        "id", "created_at", "updated_at", "is_closed", "closed_at", "closed_by",
    )
    actions = ("close_selected_periods",)

    @admin.action(description="إقفال الفترات المالية المحددة")
    def close_selected_periods(self, request, queryset):
        closed = 0
        failures = []
        for period in queryset:
            try:
                close_fiscal_period(period, request.user)
                closed += 1
            except ValidationError as exc:
                failures.append(f"{period.name}: {exc}")
        if closed:
            self.message_user(request, f"تم إقفال {closed} فترة مالية.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)


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




class BankStatementLineInline(TabularInline):
    model = BankStatementLine
    extra = 0
    raw_id_fields = ("journal_line",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(TreasuryAccount)
class TreasuryAccountAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("code", "name", "kind", "account", "bank_name", "currency", "is_default", "is_active", "school")
    list_filter = ("kind", "is_active", "is_default", "school", "branch")
    search_fields = ("code", "name", "bank_name", "bank_account_number", "account__code", "account__name")
    autocomplete_fields = ("school", "branch", "account")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TreasuryTransfer)
class TreasuryTransferAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("transfer_number", "transfer_date", "source_account", "destination_account", "amount", "status", "school")
    list_filter = ("status", "transfer_date", "school", "branch")
    search_fields = ("transfer_number", "idempotency_key", "description")
    autocomplete_fields = ("school", "branch", "source_account", "destination_account", "journal_entry", "reversed_by_entry")
    readonly_fields = ("id", "created_at", "updated_at", "journal_entry", "reversed_by_entry", "status")
    actions = ("post_selected_transfers", "reverse_selected_transfers")

    @admin.action(description="ترحيل التحويلات المسودة")
    def post_selected_transfers(self, request, queryset):
        posted = 0
        failures = []
        for transfer in queryset:
            try:
                create_treasury_transfer(
                    source_account=transfer.source_account,
                    destination_account=transfer.destination_account,
                    amount=transfer.amount,
                    transfer_number=transfer.transfer_number,
                    idempotency_key=transfer.idempotency_key,
                    transfer_date=transfer.transfer_date,
                    description=transfer.description,
                    user=request.user,
                )
                posted += 1
            except ValidationError as exc:
                failures.append(f"{transfer.transfer_number}: {exc}")
        if posted:
            self.message_user(request, f"تم ترحيل {posted} تحويل.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)

    @admin.action(description="عكس التحويلات المحددة")
    def reverse_selected_transfers(self, request, queryset):
        reversed_count = 0
        failures = []
        for transfer in queryset:
            try:
                reverse_treasury_transfer(
                    transfer,
                    reason="عكس إداري من سجل تحويلات الخزينة",
                    reversed_by=request.user,
                )
                reversed_count += 1
            except ValidationError as exc:
                failures.append(f"{transfer.transfer_number}: {exc}")
        if reversed_count:
            self.message_user(request, f"تم عكس {reversed_count} تحويل.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BankReconciliation)
class BankReconciliationAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("treasury_account", "start_date", "end_date", "statement_closing_balance", "book_closing_balance", "difference", "status", "school")
    list_filter = ("status", "treasury_account", "school")
    search_fields = ("treasury_account__name", "treasury_account__bank_name")
    autocomplete_fields = ("school", "branch", "treasury_account", "reconciled_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "book_opening_balance",
        "book_closing_balance", "outstanding_ledger_amount", "difference",
        "status", "reconciled_at", "reconciled_by",
    )
    inlines = (BankStatementLineInline,)
    actions = ("reconcile_selected_statements",)

    @admin.action(description="مطابقة كشوف البنك المحددة")
    def reconcile_selected_statements(self, request, queryset):
        reconciled_count = 0
        failures = []
        for reconciliation in queryset:
            try:
                complete_bank_reconciliation(
                    reconciliation,
                    reconciled_by=request.user,
                )
                reconciled_count += 1
            except ValidationError as exc:
                failures.append(f"{reconciliation}: {exc}")
        if reconciled_count:
            self.message_user(request, f"تم اعتماد {reconciled_count} مطابقة بنكية.", messages.SUCCESS)
        for failure in failures:
            self.message_user(request, failure, messages.ERROR)


@admin.register(BankStatementLine)
class BankStatementLineAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("external_reference", "transaction_date", "reconciliation", "amount", "journal_line", "school")
    list_filter = ("transaction_date", "school")
    search_fields = ("external_reference", "description", "reconciliation__treasury_account__name")
    autocomplete_fields = ("school", "branch", "reconciliation")
    raw_id_fields = ("journal_line",)
    readonly_fields = ("id", "created_at", "updated_at")
