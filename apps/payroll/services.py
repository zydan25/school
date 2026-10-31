"""Payroll generation and accounting posting services."""
from __future__ import annotations

import calendar
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.payroll.models import (
    EmployeeContract,
    EmployeeLoanAdvance,
    EmployeeLoanRepayment,
    PayrollRun,
    Payslip,
)
from apps.tenants.models import School


def generate_monthly_payroll(
    school: School,
    year: int,
    month: int,
    name: str = "",
    created_by=None,
) -> PayrollRun:
    """
    توليد مسير الرواتب الشهري المجمع للمدرسة استناداً لعقود العمل النشطة والسلف القائمة وسجلات الحضور والغياب.
    """
    if not name:
        name = f"مسير رواتب شهر {month:02d} / {year}"

    month_start = datetime.date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    month_end = datetime.date(year, month, last_day_num)

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

        # Fetch contracts active during this payroll month
        contracts = EmployeeContract.objects.filter(
            school=school,
            is_active=True,
            is_archived=False,
            start_date__lte=month_end,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        ).select_related("teacher", "staff_member")

        t_basic = Decimal("0.00")
        t_allowances = Decimal("0.00")
        t_deductions = Decimal("0.00")
        t_net = Decimal("0.00")

        from apps.staff.models import StaffAttendance

        for c in contracts:
            teacher = c.teacher
            staff_member = c.staff_member
            basic = c.basic_salary
            housing = c.housing_allowance
            transport = c.transport_allowance
            other_all = c.other_allowances
            insurance = c.insurance_deduction

            # Calculate total loan deductions across all active loans for this employee whose start date has arrived
            loans_qs = EmployeeLoanAdvance.objects.filter(
                school=school,
                status=EmployeeLoanAdvance.Status.ACTIVE,
                start_date__lte=month_end,
                is_archived=False,
            )
            if teacher:
                loans_qs = loans_qs.filter(teacher=teacher)
            elif staff_member:
                loans_qs = loans_qs.filter(staff_member=staff_member)
            else:
                loans_qs = loans_qs.none()

            loan_ded = Decimal("0.00")
            for loan in loans_qs:
                loan_ded += min(loan.monthly_installment, loan.remaining_amount)

            # Calculate absence deduction from StaffAttendance
            att_qs = StaffAttendance.objects.filter(
                school=school,
                date__range=(month_start, month_end),
                status=StaffAttendance.Status.UNEXCUSED,
                is_archived=False,
            )
            if teacher:
                att_qs = att_qs.filter(teacher=teacher)
            elif staff_member:
                att_qs = att_qs.filter(staff_member=staff_member)
            else:
                att_qs = att_qs.none()

            absent_count = att_qs.count()
            daily_rate = (basic / Decimal("30")).quantize(Decimal("0.01"))
            absence_ded = (Decimal(absent_count) * daily_rate).quantize(Decimal("0.01"))

            earnings = basic + housing + transport + other_all
            deductions = insurance + loan_ded + absence_ded
            net = max(Decimal("0.00"), earnings - deductions)

            Payslip.objects.create(
                school=school,
                payroll_run=run,
                teacher=teacher,
                staff_member=staff_member,
                basic_salary=basic,
                housing_allowance=housing,
                transport_allowance=transport,
                other_allowances=other_all,
                insurance_deduction=insurance,
                loan_deduction=loan_ded,
                absence_deduction=absence_ded,
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


def approve_payroll_run(payroll_run: PayrollRun, approved_by=None) -> PayrollRun:
    """
    اعتماد مسير الرواتب رسمياً بعد مراجعة قسائم الموظفين وقبل ترحيله محاسبياً.
    """
    if payroll_run.status != PayrollRun.Status.DRAFT:
        raise ValidationError("يمكن اعتماد مسير الرواتب فقط عندما يكون في حالة مسودة.")
    if not payroll_run.payslips.exists():
        raise ValidationError("لا يمكن اعتماد مسير رواتب فارغ لا يحتوي على قسائم رواتب.")

    payroll_run.status = PayrollRun.Status.APPROVED
    payroll_run.approved_by = approved_by
    payroll_run.save(update_fields=["status", "approved_by", "updated_at"])
    return payroll_run


def post_payroll_to_accounting(
    payroll_run: PayrollRun,
    expense_account: Account = None,
    payable_account: Account = None,
    posted_by=None,
    user=None,
) -> JournalEntry:
    """
    ترحيل مسير الرواتب المعتمد إلى دفتر الأستاذ العام وإنشاء قيد الاستحقاق المزدوج:
    مدين: مصروف الرواتب والأجور (Gross Salary 5101)
    دائن: الرواتب المستحقة للموظفين (Net 2101) + أمانات التأمينات (2103) والسلف (1105) وجزاءات الغياب (4201).
    """
    if user is not None and posted_by is None:
        posted_by = user
    if payroll_run.journal_entry:
        return payroll_run.journal_entry

    if payroll_run.status != PayrollRun.Status.APPROVED:
        raise ValidationError("لا يمكن ترحيل مسير رواتب محاسبياً قبل اعتماده رسمياً من الإدارة.")

    from apps.accounting.services.auto_posting import (
        _get_account_or_seed,
        _get_active_fiscal_period,
    )
    school = payroll_run.school

    with transaction.atomic():
        locked_run = PayrollRun.objects.select_for_update().get(pk=payroll_run.pk)
        if locked_run.journal_entry:
            return locked_run.journal_entry
        if locked_run.status != PayrollRun.Status.APPROVED:
            raise ValidationError("لا يمكن ترحيل مسير رواتب محاسبياً قبل اعتماده رسمياً من الإدارة.")

        if expense_account is None:
            expense_account = _get_account_or_seed(school, "5101", "رواتب وأجور الكادر والموظفين")
        elif expense_account.school_id != school.pk:
            raise ValidationError("حساب مصروف الرواتب لا يتبع نفس المدرسة.")

        if payable_account is None:
            payable_account = _get_account_or_seed(school, "2101", "الرواتب والأجور المستحقة")
        elif payable_account.school_id != school.pk:
            raise ValidationError("حساب مستحقات الرواتب لا يتبع نفس المدرسة.")

        loans_acc = _get_account_or_seed(school, "1105", "سلف وقروض الموظفين")
        insurance_acc = _get_account_or_seed(school, "2103", "أمانات التأمينات الاجتماعية")
        absence_acc = _get_account_or_seed(school, "4201", "إيرادات جزاءات واستقطاعات غياب الموظفين")

        last_day_num = calendar.monthrange(locked_run.year, locked_run.month)[1]
        post_date = datetime.date(locked_run.year, locked_run.month, last_day_num)
        period = _get_active_fiscal_period(school, post_date)

        entry_number = f"PAY-{locked_run.year}{locked_run.month:02d}-{locked_run.id.hex[:6].upper()}"
        
        entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=entry_number,
            date=post_date,
            description=f"إثبات استحقاق مسير الرواتب: {locked_run.name}",
            status=JournalEntry.Status.DRAFT,
            source_module="payroll",
            source_reference=str(locked_run.id),
        )

        gross_total = locked_run.total_basic + locked_run.total_allowances
        
        # 1. Debit: Salaries & Wages Expense
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=expense_account,
            debit=gross_total,
            credit=Decimal("0.00"),
            description=f"إجمالي استحقاقات {locked_run.name}",
        )

        # 2. Credit: Accrued Salaries Payable (Net)
        JournalEntryLine.objects.create(
            school=school,
            journal_entry=entry,
            account=payable_account,
            debit=Decimal("0.00"),
            credit=locked_run.total_net,
            description="صافي الرواتب المستحقة للصرف",
        )

        # 3. Credit: Total Loans Deductions
        total_loans_ded = sum(p.loan_deduction for p in locked_run.payslips.all())
        if total_loans_ded > Decimal("0.00"):
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=loans_acc,
                debit=Decimal("0.00"),
                credit=total_loans_ded,
                description="استقطاعات سلف الموظفين المحصلة من الرواتب",
            )

        # 4. Credit: Total Insurance deductions
        total_insurance_ded = sum(p.insurance_deduction for p in locked_run.payslips.all())
        if total_insurance_ded > Decimal("0.00"):
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=insurance_acc,
                debit=Decimal("0.00"),
                credit=total_insurance_ded,
                description="أمانات التأمينات الاجتماعية المستقطعة من الرواتب",
            )

        # 5. Credit: Total Absence Deductions
        total_absence_ded = sum(p.absence_deduction for p in locked_run.payslips.all())
        if total_absence_ded > Decimal("0.00"):
            JournalEntryLine.objects.create(
                school=school,
                journal_entry=entry,
                account=absence_acc,
                debit=Decimal("0.00"),
                credit=total_absence_ded,
                description="استقطاعات وجزاءات الغياب من الرواتب",
            )

        entry.post(user=posted_by)

        # Update specific active loans for each employee and record EmployeeLoanRepayment
        for p in locked_run.payslips.filter(loan_deduction__gt=0):
            needed_ded = p.loan_deduction
            loans_qs = EmployeeLoanAdvance.objects.filter(
                school=school,
                status=EmployeeLoanAdvance.Status.ACTIVE,
                is_archived=False,
            )
            if p.teacher_id:
                loans_qs = loans_qs.filter(teacher_id=p.teacher_id)
            elif p.staff_member_id:
                loans_qs = loans_qs.filter(staff_member_id=p.staff_member_id)
            else:
                loans_qs = loans_qs.none()

            for loan in loans_qs.order_by("start_date", "created_at"):
                if needed_ded <= Decimal("0.00"):
                    break
                pay_installment = min(needed_ded, min(loan.monthly_installment, loan.remaining_amount))
                bal_before = loan.remaining_amount
                loan.repaid_amount += pay_installment
                bal_after = loan.remaining_amount
                needed_ded -= pay_installment
                if loan.repaid_amount >= loan.amount:
                    loan.status = EmployeeLoanAdvance.Status.FULLY_REPAID
                loan.save(update_fields=["repaid_amount", "status", "updated_at"])

                EmployeeLoanRepayment.objects.create(
                    school=school,
                    loan=loan,
                    payslip=p,
                    payroll_run=locked_run,
                    amount=pay_installment,
                    balance_before=bal_before,
                    balance_after=bal_after,
                    repaid_at=post_date,
                )

        locked_run.journal_entry = entry
        locked_run.status = PayrollRun.Status.POSTED
        locked_run.save(update_fields=["journal_entry", "status", "updated_at"])

        return entry


def reverse_payroll_run(payroll_run: PayrollRun, reason: str, reversed_by=None) -> PayrollRun:
    """
    عكس مسير رواتب مرحل محاسبياً وإلغاء أثره على دفاتر المحاسبة وأرصدة سلف الموظفين.
    لا يمكن عكس مسير تم صرفه نقدياً/بنكياً بالفعل (PAID) إلا بعد عكس سند الصرف.
    """
    if payroll_run.status == PayrollRun.Status.PAID:
        raise ValidationError("لا يمكن عكس مسير رواتب تم صرفه فعلياً؛ يرجى إلغاء سند الصرف المالي أولاً.")
    if payroll_run.status != PayrollRun.Status.POSTED or not payroll_run.journal_entry:
        raise ValidationError("لا يمكن عكس مسير رواتب غير مرحل محاسبياً.")

    from apps.accounting.services.auto_posting import reverse_journal_entry

    with transaction.atomic():
        locked_run = PayrollRun.objects.select_for_update().get(pk=payroll_run.pk)
        if locked_run.status == PayrollRun.Status.PAID:
            raise ValidationError("لا يمكن عكس مسير رواتب تم صرفه فعلياً.")
        
        # 1. Reverse EmployeeLoanRepayment records and restore loan balances
        repayments = list(locked_run.loan_repayments.filter(is_reversed=False))
        for rep in repayments:
            loan = EmployeeLoanAdvance.objects.select_for_update().get(pk=rep.loan_id)
            loan.repaid_amount = max(Decimal("0.00"), loan.repaid_amount - rep.amount)
            loan.status = EmployeeLoanAdvance.Status.ACTIVE
            loan.save(update_fields=["repaid_amount", "status", "updated_at"])
            rep.is_reversed = True
            rep.save(update_fields=["is_reversed", "updated_at"])

        # 2. Reverse the journal entry
        if locked_run.journal_entry:
            reverse_journal_entry(
                locked_run.journal_entry,
                reason=f"عكس مسير الرواتب {locked_run.name}: {reason}",
                reversed_by=reversed_by,
            )

        locked_run.status = PayrollRun.Status.DRAFT
        locked_run.journal_entry = None
        locked_run.save(update_fields=["status", "journal_entry", "updated_at"])
        return locked_run


def disburse_payroll_run(
    payroll_run: PayrollRun,
    payment_account: Account | None = None,
    credit_account: Account | None = None,
    payment_method: str = "bank_transfer",
    reference_number: str = "",
    disbursed_by=None,
    user=None,
) -> JournalEntry:
    """
    تنفيذ الصرف الفعلي لمسير الرواتب من حساب الصندوق أو البنك،
    وإنشاء قيد صرف مالي وسند صرف وتحديث قسائم الموظفين كـ مدفوعة.
    """
    disbursed_by = disbursed_by or user
    if payment_account is None and credit_account is not None:
        payment_account = credit_account

    if payment_account is None:
        raise ValueError("يجب تحديد حساب الصرف المالي (الصندوق أو البنك).")

    from apps.accounting.services.auto_posting import (
        _get_account_or_seed,
        _get_active_fiscal_period,
    )

    school = payroll_run.school
    if payment_account.school_id != school.pk:
        raise ValidationError("حساب الصرف المالي لا ينتمي إلى نفس المدرسة.")
    if not payment_account.is_leaf or payment_account.account_type != Account.AccountType.ASSET:
        raise ValidationError("حساب الصرف يجب أن يكون حساباً فرعياً من نوع أصول (نقدية أو بنك).")

    with transaction.atomic():
        locked_run = PayrollRun.objects.select_for_update().get(pk=payroll_run.pk)
        if locked_run.status == PayrollRun.Status.PAID:
            raise ValueError("مسير الرواتب هذا مصروف مسبقاً.")

        if not locked_run.journal_entry:
            post_payroll_to_accounting(locked_run, posted_by=disbursed_by)
            locked_run.refresh_from_db()

        payable_account = _get_account_or_seed(school, "2101", "الرواتب والأجور المستحقة")

        post_date = timezone.localdate()
        period = _get_active_fiscal_period(school, post_date)

        # Disbursement Journal Entry (Debit 2101, Credit 1101/1102)
        disb_entry_number = f"DISB-PAY-{locked_run.year}{locked_run.month:02d}-{locked_run.id.hex[:6].upper()}"
        disb_entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=disb_entry_number,
            date=post_date,
            description=f"صرف رواتب شهر {locked_run.month}/{locked_run.year} - مرجع: {reference_number}",
            status=JournalEntry.Status.DRAFT,
            source_module="payroll_disbursement",
            source_reference=str(locked_run.id),
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=disb_entry,
            account=payable_account,
            debit=locked_run.total_net,
            credit=Decimal("0.00"),
            description=f"إقفال مستحقات رواتب شهر {locked_run.month}/{locked_run.year}",
        )

        JournalEntryLine.objects.create(
            school=school,
            journal_entry=disb_entry,
            account=payment_account,
            debit=Decimal("0.00"),
            credit=locked_run.total_net,
            description=f"تحويل رواتب الموظفين عبر {payment_method}",
        )

        disb_entry.post(user=disbursed_by)

        # Create Payment Voucher with complete details
        v_num = f"PV-PAY-{locked_run.year}{locked_run.month:02d}"
        pv, _ = PaymentVoucher.objects.get_or_create(
            school=school,
            voucher_number=v_num,
            defaults={
                "date": post_date,
                "paid_to": f"كادر وموظفو المدرسة ({locked_run.name})",
                "amount": locked_run.total_net,
                "payment_method": payment_method if payment_method in [PaymentVoucher.PaymentMethod.CASH, PaymentVoucher.PaymentMethod.BANK_TRANSFER, PaymentVoucher.PaymentMethod.CHEQUE] else PaymentVoucher.PaymentMethod.BANK_TRANSFER,
                "reference_number": reference_number,
                "debit_account": payable_account,
                "credit_account": payment_account,
                "description": f"صرف مسير رواتب شهر {locked_run.month}/{locked_run.year}",
                "status": PaymentVoucher.Status.POSTED,
                "journal_entry": disb_entry,
            },
        )

        locked_run.status = PayrollRun.Status.PAID
        locked_run.save(update_fields=["status", "updated_at"])

        # Mark all payslips as paid with today's date
        locked_run.payslips.all().update(
            is_paid=True,
            payment_date=post_date,
            updated_at=timezone.now(),
        )

        return disb_entry
