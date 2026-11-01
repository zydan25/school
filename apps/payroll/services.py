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
    """ترحيل مسير الرواتب بعد مطابقة الإجماليات وتخصيص كل استقطاع سلفة فعلياً."""
    if user is not None and posted_by is None:
        posted_by = user
    from apps.accounting.services.auto_posting import (
        _get_account_or_seed,
        _get_active_fiscal_period,
    )

    with transaction.atomic():
        locked_run = PayrollRun.objects.select_for_update(of=("self",)).get(pk=payroll_run.pk)
        if locked_run.journal_entry_id:
            if (
                locked_run.journal_entry.status == JournalEntry.Status.POSTED
                and locked_run.status in (PayrollRun.Status.POSTED, PayrollRun.Status.PAID)
            ):
                payroll_run.journal_entry = locked_run.journal_entry
                return locked_run.journal_entry
            raise ValidationError("مسير الرواتب مرتبط بقيد غير مرحّل أو بحالة غير متوافقة؛ يجب مراجعته.")
        if locked_run.status != PayrollRun.Status.APPROVED:
            raise ValidationError("لا يمكن ترحيل مسير رواتب محاسبياً قبل اعتماده رسمياً من الإدارة.")

        school = locked_run.school
        last_day_num = calendar.monthrange(locked_run.year, locked_run.month)[1]
        post_date = datetime.date(locked_run.year, locked_run.month, last_day_num)
        period = _get_active_fiscal_period(school, post_date)
        payslips = list(
            locked_run.payslips.select_for_update(of=("self",))
            .filter(is_archived=False).order_by("pk")
        )
        if not payslips:
            raise ValidationError("لا يمكن ترحيل مسير رواتب بلا قسائم رواتب.")

        gross_total = sum((slip.total_earnings for slip in payslips), Decimal("0.00"))
        net_total = sum((slip.net_salary for slip in payslips), Decimal("0.00"))
        loans_total = sum((slip.loan_deduction for slip in payslips), Decimal("0.00"))
        insurance_total = sum((slip.insurance_deduction for slip in payslips), Decimal("0.00"))
        absence_total = sum((slip.absence_deduction for slip in payslips), Decimal("0.00"))
        deductions_total = loans_total + insurance_total + absence_total
        run_gross = locked_run.total_basic + locked_run.total_allowances
        if gross_total != run_gross:
            raise ValidationError(
                f"إجمالي استحقاقات القسائم ({gross_total}) لا يطابق إجمالي المسير ({run_gross})."
            )
        if deductions_total != locked_run.total_deductions:
            raise ValidationError("إجمالي الاستقطاعات في القسائم لا يطابق إجمالي الاستقطاعات في المسير.")
        if net_total != locked_run.total_net:
            raise ValidationError("صافي القسائم لا يطابق صافي المسير المسجل.")
        if gross_total - deductions_total != net_total:
            raise ValidationError("مسير الرواتب غير متوازن: الاستحقاقات ناقص الاستقطاعات لا يساوي الصافي.")
        if any(value < Decimal("0.00") for value in (
            gross_total, net_total, loans_total, insurance_total, absence_total,
        )):
            raise ValidationError("لا تقبل المحاسبة مبالغ رواتب أو استقطاعات سالبة.")

        if expense_account is None:
            expense_account = _get_account_or_seed(
                school, "5101", "رواتب وأجور الكادر والموظفين",
            )
        if payable_account is None:
            payable_account = _get_account_or_seed(
                school, "2103", "الرواتب والأجور المستحقة",
            )
        for account in (expense_account, payable_account):
            if account.school_id != school.pk or not account.is_leaf or account.is_archived:
                raise ValidationError("حساب مصروف الرواتب أو المستحقات غير صالح لهذه المدرسة.")
        if expense_account.account_type != Account.AccountType.EXPENSE:
            raise ValidationError("حساب مصروف الرواتب يجب أن يكون من نوع المصروفات.")
        if payable_account.account_type != Account.AccountType.LIABILITY:
            raise ValidationError("حساب مستحقات الرواتب يجب أن يكون من نوع الالتزامات.")
        loans_acc = _get_account_or_seed(school, "1105", "سلف وقروض الموظفين")
        insurance_acc = _get_account_or_seed(school, "2104", "أمانات التأمينات الاجتماعية")
        absence_acc = _get_account_or_seed(
            school, "4201", "إيرادات جزاءات واستقطاعات غياب الموظفين",
        )

        repayment_plan = []
        for payslip in payslips:
            remaining = payslip.loan_deduction
            if remaining <= Decimal("0.00"):
                continue
            if bool(payslip.teacher_id) == bool(payslip.staff_member_id):
                raise ValidationError("قسيمة استقطاع السلفة يجب أن ترتبط بمعلم أو موظف إداري واحد فقط.")
            loans_qs = EmployeeLoanAdvance.objects.select_for_update(of=("self",)).filter(
                school=school,
                status=EmployeeLoanAdvance.Status.ACTIVE,
                start_date__lte=post_date,
                is_archived=False,
            )
            if payslip.teacher_id:
                loans_qs = loans_qs.filter(teacher_id=payslip.teacher_id)
            else:
                loans_qs = loans_qs.filter(staff_member_id=payslip.staff_member_id)
            if payslip.branch_id:
                loans_qs = loans_qs.filter(
                    Q(branch_id=payslip.branch_id) | Q(branch__isnull=True)
                )
            for loan in loans_qs.order_by("start_date", "created_at", "pk"):
                if remaining <= Decimal("0.00"):
                    break
                installment = min(
                    remaining, loan.monthly_installment, loan.remaining_amount,
                )
                if installment <= Decimal("0.00"):
                    continue
                repayment_plan.append((payslip, loan, installment))
                remaining -= installment
            if remaining > Decimal("0.00"):
                raise ValidationError(
                    f"استقطاع السلفة في قسيمة {payslip.pk} يتجاوز الأقساط المتاحة للسلف النشطة بمبلغ {remaining}."
                )

        source_reference = str(locked_run.pk)
        if JournalEntry.objects.filter(
            school=school, source_module="payroll",
            source_reference=source_reference, is_archived=False,
        ).exists():
            raise ValidationError("يوجد قيد رواتب سابق غير مرتبط بمسير الرواتب؛ راجع سجل التدقيق.")

        entry = JournalEntry.objects.create(
            school=school,
            fiscal_period=period,
            entry_number=f"PAY-{locked_run.year}{locked_run.month:02d}-{locked_run.pk.hex[:6].upper()}",
            date=post_date,
            description=f"إثبات استحقاق مسير الرواتب: {locked_run.name}",
            status=JournalEntry.Status.DRAFT,
            source_module="payroll",
            source_reference=source_reference,
        )
        JournalEntryLine.objects.create(
            school=school, journal_entry=entry, account=expense_account,
            debit=gross_total, credit=Decimal("0.00"),
            description=f"إجمالي استحقاقات {locked_run.name}",
        )
        for amount, account, description in (
            (net_total, payable_account, "صافي الرواتب المستحقة للصرف"),
            (loans_total, loans_acc, "استقطاعات سلف الموظفين المحصلة من الرواتب"),
            (insurance_total, insurance_acc, "أمانات التأمينات الاجتماعية المستقطعة من الرواتب"),
            (absence_total, absence_acc, "استقطاعات وجزاءات الغياب من الرواتب"),
        ):
            if amount > Decimal("0.00"):
                JournalEntryLine.objects.create(
                    school=school, journal_entry=entry, account=account,
                    debit=Decimal("0.00"), credit=amount, description=description,
                )
        entry.post(user=posted_by)

        for payslip, loan, installment in repayment_plan:
            balance_before = loan.remaining_amount
            loan.repaid_amount += installment
            balance_after = loan.remaining_amount
            if loan.repaid_amount >= loan.amount:
                loan.status = EmployeeLoanAdvance.Status.FULLY_REPAID
            loan.save(update_fields=["repaid_amount", "status", "updated_at"])
            EmployeeLoanRepayment.objects.create(
                school=school, branch=payslip.branch, loan=loan,
                payslip=payslip, payroll_run=locked_run,
                amount=installment, balance_before=balance_before,
                balance_after=balance_after, repaid_at=post_date,
            )

        locked_run.journal_entry = entry
        locked_run.status = PayrollRun.Status.POSTED
        locked_run.save(update_fields=["journal_entry", "status", "updated_at"])
        payroll_run.journal_entry = entry
        payroll_run.status = PayrollRun.Status.POSTED
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
        from apps.accounting.models import PaymentVoucher

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
