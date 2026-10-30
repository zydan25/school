from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin import AuditedAdminMixin
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun, Payslip


class PayslipInline(TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = ("teacher", "basic_salary", "housing_allowance", "transport_allowance", "loan_deduction", "insurance_deduction", "net_salary", "is_paid")
    can_delete = False


@admin.register(EmployeeContract)
class EmployeeContractAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("contract_number", "teacher", "staff_member", "contract_type", "basic_salary", "gross_salary", "net_salary", "start_date", "is_active", "school")
    list_filter = ("contract_type", "is_active", "school")
    search_fields = ("contract_number", "teacher__user__first_name", "staff_member__user__first_name", "school__name")
    raw_id_fields = ("school", "branch", "teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(EmployeeLoanAdvance)
class EmployeeLoanAdvanceAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("loan_number", "teacher", "staff_member", "amount", "monthly_installment", "repaid_amount", "remaining_amount", "status", "school")
    list_filter = ("status", "school")
    search_fields = ("loan_number", "teacher__user__first_name", "staff_member__user__first_name", "school__name")
    raw_id_fields = ("school", "branch", "teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PayrollRun)
class PayrollRunAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("name", "year", "month", "total_basic", "total_allowances", "total_deductions", "total_net", "status", "school")
    list_filter = ("status", "year", "school")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school", "branch", "journal_entry")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PayslipInline,)


@admin.register(Payslip)
class PayslipAdmin(AuditedAdminMixin, ModelAdmin):
    list_display = ("teacher", "staff_member", "payroll_run", "basic_salary", "total_earnings", "total_deductions", "net_salary", "is_paid", "school")
    list_filter = ("is_paid", "payroll_run__year", "school")
    search_fields = ("teacher__user__first_name", "staff_member__user__first_name", "payroll_run__name", "school__name")
    raw_id_fields = ("school", "branch", "payroll_run", "teacher", "staff_member")
    readonly_fields = ("id", "created_at", "updated_at")
