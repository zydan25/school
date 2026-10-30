"""Payroll generation and accounting posting services."""
from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.payroll.models import EmployeeContract, EmployeeLoanAdvance, PayrollRun, Payslip
from apps.tenants.models import School


def generate_monthly_payroll(
    school: School,
    year: int,
    month: int,
    name: str = "",
) -> PayrollRun:
    """
    توليد مسير الرواتب الشهري المجمع للمدرسة استناداً لعقود العمل النشطة والسلف القائمة.
    """
    if not name:
        name = f"مسير رواتب شهر {month:02d} / {year}"

    with transaction.atomic():
        run, created = PayrollRun.objects.get_or_create(
            school=school,
            year=year,
            month=month,
            defaults={
                "name": name,
                "status": PayrollRun.Status.DRAFT,
            },
        )
        if not created:
            # Delete previous draft payslips to regenerate fresh
            if run.status != PayrollRun.Status.DRAFT:
                raise ValueError("لا يمكن إعادة توليد مسير رواتب معتمد أو مدفوع.")
            run.payslips.all().delete()

        # Fetch all active contracts for this school
        contracts = EmployeeContract.objects.filter(
            school=school,
            is_active=True,
            is_archived=False,
        ).select_related("teacher")

        t_basic = Decimal("0.00")
        t_allowances = Decimal("0.00")
        t_deductions = Decimal("0.00")
        t_net = Decimal("0.00")

        for c in contracts:
            teacher = c.teacher
            basic = c.basic_salary
            housing = c.housing_allowance
            transport = c.transport_allowance
            other_all = c.other_allowances
            insurance = c.insurance_deduction

            # Check for active loan advance to deduct
            loan = EmployeeLoanAdvance.objects.filter(
                school=school,
                teacher=teacher,
                status=EmployeeLoanAdvance.Status.ACTIVE,
                is_archived=False,
            ).first()

            loan_ded = Decimal("0.00")
            if loan:
                loan_ded = min(loan.monthly_installment, loan.remaining_amount)

            earnings = basic + housing + transport + other_all
            deductions = insurance + loan_ded
            net = max(Decimal("0.00"), earnings - deductions)

            Payslip.objects.create(
                school=school,
                payroll_run=run,
                teacher=teacher,
                basic_salary=basic,
                housing_allowance=housing,
                transport_allowance=transport,
                other_allowances=other_all,
                insurance_deduction=insurance,
                loan_deduction=loan_ded,
                net_salary=net,
            )

            t_basic += basic
            t_allowances += (housing + transport + other_all)
            t_deductions += deductions
            t_net += net

        run.total_basic = t_basic
        run.total_allowances = t_allowances
        run.total_deductions = t_deductions
        run.total_net = t_net
        run.save()

        return run


def post_payroll_to_accounting(
    payroll_run: PayrollRun,
    expense_account: Account,
    payable_account: Account,
    posted_by=None,
) -> JournalEntry:
    """
    ترحيل مسير الرواتب المعتمد إلى دفتر الأستاذ العام وإنشاء القيد المزدوج:
    مدين: مصروف الرواتب والأجور (Gross Salary)
    دائن: الرواتب المستحقة للموظفين (Net) + أمانات واستقطاعات التأمينات والسلف (Deductions).
    """
    if payroll_run.status == PayrollRun.Status.PAID and payroll_run.journal_entry:
        return payroll_run.journal_entry

    with transaction.atomic():
        entry_number = f"PAY-{payroll_run.year}{payroll_run.month:02d}-{payroll_run.id.hex[:6].upper()}"
        
        entry = JournalEntry.objects.create(
            school=payroll_run.school,
            entry_number=entry_number,
            date=timezone.localdate(),
            description=f"إثبات استحقاق {payroll_run.name}",
            status=JournalEntry.Status.POSTED,
            posted_by=posted_by,
            posted_at=timezone.now(),
            source_module="payroll",
            source_reference=str(payroll_run.id),
        )

        gross_total = payroll_run.total_basic + payroll_run.total_allowances
        
        # Debit: Salaries & Wages Expense
        JournalEntryLine.objects.create(
            school=payroll_run.school,
            journal_entry=entry,
            account=expense_account,
            debit=gross_total,
            credit=Decimal("0.00"),
            description=f"إجمالي استحقاقات {payroll_run.name}",
        )

        # Credit: Accrued Salaries Payable
        JournalEntryLine.objects.create(
            school=payroll_run.school,
            journal_entry=entry,
            account=payable_account,
            debit=Decimal("0.00"),
            credit=payroll_run.total_net,
            description="صافي الرواتب المستحقة للصرف",
        )

        # Credit: Deductions if any (difference to balance)
        diff = gross_total - payroll_run.total_net
        if diff > Decimal("0.00"):
            # Use payable account or liabilities account for deductions
            JournalEntryLine.objects.create(
                school=payroll_run.school,
                journal_entry=entry,
                account=payable_account,
                debit=Decimal("0.00"),
                credit=diff,
                description="استقطاعات التأمينات والسلف المستردة",
            )

        payroll_run.journal_entry = entry
        payroll_run.status = PayrollRun.Status.PAID
        payroll_run.save()

        # Update loans
        for p in payroll_run.payslips.filter(loan_deduction__gt=0):
            loan = EmployeeLoanAdvance.objects.filter(
                school=payroll_run.school,
                teacher=p.teacher,
                status=EmployeeLoanAdvance.Status.ACTIVE,
            ).first()
            if loan:
                loan.repaid_amount += p.loan_deduction
                if loan.repaid_amount >= loan.amount:
                    loan.status = EmployeeLoanAdvance.Status.FULLY_REPAID
                loan.save()

        return entry
