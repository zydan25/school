"""Transactional HR workflows for employee loans and manual repayments."""
from __future__ import annotations

import hashlib
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Account, PaymentVoucher, ReceiptVoucher
from apps.accounting.services.auto_posting import (
    _get_account_or_seed,
    post_payment_voucher_to_journal,
    post_receipt_voucher_to_journal,
)
from apps.payroll.models import (
    EmployeeLoanAdvance,
    EmployeeLoanRepayment,
)


def approve_employee_loan(*, loan: EmployeeLoanAdvance, approved_by) -> EmployeeLoanAdvance:
    """Approve a pending employee advance without disbursing it."""
    with transaction.atomic():
        locked = EmployeeLoanAdvance.objects.select_for_update().get(pk=loan.pk)
        if locked.status != EmployeeLoanAdvance.Status.PENDING:
            raise ValidationError("لا يمكن اعتماد إلا طلب سلفة قيد المراجعة.")
        if locked.amount <= Decimal("0.00") or locked.monthly_installment <= Decimal("0.00"):
            raise ValidationError("بيانات مبلغ السلفة أو القسط غير صالحة.")
        locked.status = EmployeeLoanAdvance.Status.APPROVED
        locked.approved_by = approved_by
        locked.approved_at = timezone.now()
        locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return locked


def disburse_employee_loan(
    *,
    loan: EmployeeLoanAdvance,
    payment_account: Account,
    payment_method: str = PaymentVoucher.PaymentMethod.BANK_TRANSFER,
    reference_number: str = "",
    disbursed_by=None,
) -> PaymentVoucher:
    """Disburse an approved loan through an idempotent, posted accounting voucher."""
    with transaction.atomic():
        locked = EmployeeLoanAdvance.objects.select_for_update().get(pk=loan.pk)
        school = locked.school
        if locked.status == EmployeeLoanAdvance.Status.ACTIVE and locked.disbursement_voucher_id:
            voucher = locked.disbursement_voucher
            if voucher.status != PaymentVoucher.Status.POSTED or not voucher.journal_entry_id:
                raise ValidationError("السلفة مصروفة لكن سند الصرف غير مرحّل؛ يلزم التدقيق.")
            post_payment_voucher_to_journal(voucher)
            return voucher
        if locked.status != EmployeeLoanAdvance.Status.APPROVED:
            raise ValidationError("يجب اعتماد طلب السلفة قبل صرفه.")
        if payment_account.school_id != school.pk:
            raise ValidationError("حساب الصرف لا يتبع المدرسة نفسها.")
        if (
            payment_account.account_type != Account.AccountType.ASSET
            or not payment_account.is_leaf
            or payment_account.is_archived
        ):
            raise ValidationError("حساب الصرف يجب أن يكون حساب أصول تفصيلياً ونشطاً.")
        if locked.branch_id and payment_account.branch_id and locked.branch_id != payment_account.branch_id:
            raise ValidationError("حساب الصرف لا يتبع فرع السلفة.")

        loan_account = _get_account_or_seed(school, "1105", "سلف وقروض الموظفين")
        if (
            loan_account.school_id != school.pk
            or loan_account.account_type != Account.AccountType.ASSET
            or not loan_account.is_leaf
            or loan_account.is_archived
        ):
            raise ValidationError("حساب سلف الموظفين 1105 غير صالح.")

        voucher_key = f"employee-loan-disbursement-{locked.pk}"
        voucher_number = f"PV-LN-{locked.pk.hex[:16].upper()}"
        voucher, created = PaymentVoucher.objects.get_or_create(
            school=school,
            idempotency_key=voucher_key,
            defaults={
                "branch": locked.branch,
                "voucher_number": voucher_number,
                "date": timezone.localdate(),
                "paid_to": (
                    locked.teacher.user.get_full_name() or locked.teacher.user.phone
                    if locked.teacher else
                    locked.staff_member.user.get_full_name() or locked.staff_member.user.phone
                ),
                "amount": locked.amount,
                "payment_method": (
                    payment_method if payment_method in PaymentVoucher.PaymentMethod.values
                    else PaymentVoucher.PaymentMethod.BANK_TRANSFER
                ),
                "credit_account": payment_account,
                "debit_account": loan_account,
                "description": f"صرف سلفة موظف رقم {locked.loan_number}",
                "reference_number": reference_number,
                "status": PaymentVoucher.Status.DRAFT,
            },
        )
        if not created and (
            voucher.amount != locked.amount
            or voucher.debit_account_id != loan_account.pk
            or voucher.credit_account_id != payment_account.pk
            or voucher.status == PaymentVoucher.Status.CANCELLED
        ):
            raise ValidationError("يوجد سند صرف سابق للسلفة ببيانات مختلفة أو بحالة ملغاة.")
        post_payment_voucher_to_journal(voucher)
        voucher.refresh_from_db()
        locked.status = EmployeeLoanAdvance.Status.ACTIVE
        locked.disbursement_voucher = voucher
        locked.disbursed_by = disbursed_by
        locked.disbursed_at = timezone.now()
        locked.save(update_fields=[
            "status", "disbursement_voucher", "disbursed_by",
            "disbursed_at", "updated_at",
        ])
        return voucher


def record_employee_loan_repayment(
    *,
    loan: EmployeeLoanAdvance,
    amount: Decimal,
    payment_account: Account,
    idempotency_key: str,
    payment_method: str = ReceiptVoucher.PaymentMethod.BANK_TRANSFER,
    reference_number: str = "",
    notes: str = "",
    recorded_by=None,
) -> EmployeeLoanRepayment:
    """Record a manual loan repayment and its receipt voucher as one atomic operation."""
    normalized_key = (idempotency_key or "").strip()
    if len(normalized_key) < 8 or len(normalized_key) > 70:
        raise ValidationError("مفتاح منع التكرار يجب أن يكون بين 8 و70 حرفاً.")
    amount = Decimal(amount)
    if amount <= Decimal("0.00"):
        raise ValidationError("مبلغ السداد يجب أن يكون أكبر من الصفر.")

    with transaction.atomic():
        locked_loan = EmployeeLoanAdvance.objects.select_for_update().get(pk=loan.pk)
        school = locked_loan.school
        existing = EmployeeLoanRepayment.objects.filter(
            school=school, idempotency_key=normalized_key, is_archived=False,
        ).first()
        if existing:
            if existing.loan_id != locked_loan.pk or existing.amount != amount:
                raise ValidationError("مفتاح منع التكرار مستخدم مسبقاً لعملية سداد مختلفة.")
            return existing
        if locked_loan.status != EmployeeLoanAdvance.Status.ACTIVE:
            raise ValidationError("لا يمكن تسجيل سداد يدوي إلا لسلفة مصروفة ونشطة.")
        if amount > locked_loan.remaining_amount:
            raise ValidationError("مبلغ السداد يتجاوز الرصيد المتبقي للسلفة.")
        if payment_account.school_id != school.pk:
            raise ValidationError("حساب التحصيل لا يتبع المدرسة نفسها.")
        if (
            locked_loan.branch_id
            and payment_account.branch_id
            and locked_loan.branch_id != payment_account.branch_id
        ):
            raise ValidationError("حساب التحصيل لا يتبع فرع السلفة.")
        if (
            payment_account.account_type != Account.AccountType.ASSET
            or not payment_account.is_leaf
            or payment_account.is_archived
        ):
            raise ValidationError("حساب التحصيل يجب أن يكون حساب أصول تفصيلياً ونشطاً.")

        loan_account = _get_account_or_seed(school, "1105", "سلف وقروض الموظفين")
        if (
            loan_account.school_id != school.pk
            or loan_account.account_type != Account.AccountType.ASSET
            or not loan_account.is_leaf
            or loan_account.is_archived
        ):
            raise ValidationError("حساب سلف الموظفين 1105 غير صالح.")

        voucher_key = f"loan-repayment-{normalized_key}"
        digest = hashlib.sha256(f"{school.pk}:{locked_loan.pk}:{normalized_key}".encode()).hexdigest()[:18].upper()
        voucher, created = ReceiptVoucher.objects.get_or_create(
            school=school,
            idempotency_key=voucher_key,
            defaults={
                "branch": locked_loan.branch,
                "voucher_number": f"RC-LN-{digest}",
                "date": timezone.localdate(),
                "received_from": (
                    locked_loan.teacher.user.get_full_name() or locked_loan.teacher.user.phone
                    if locked_loan.teacher else
                    locked_loan.staff_member.user.get_full_name() or locked_loan.staff_member.user.phone
                ),
                "amount": amount,
                "payment_method": (
                    payment_method if payment_method in ReceiptVoucher.PaymentMethod.values
                    else ReceiptVoucher.PaymentMethod.BANK_TRANSFER
                ),
                "debit_account": payment_account,
                "credit_account": loan_account,
                "description": f"تحصيل سداد من سلفة الموظف رقم {locked_loan.loan_number}",
                "reference_number": reference_number,
                "status": ReceiptVoucher.Status.DRAFT,
            },
        )
        if not created and (
            voucher.amount != amount
            or voucher.debit_account_id != payment_account.pk
            or voucher.credit_account_id != loan_account.pk
            or voucher.status == ReceiptVoucher.Status.CANCELLED
        ):
            raise ValidationError("يوجد سند تحصيل سابق بمفتاح منع التكرار نفسه وبيانات مختلفة.")
        post_receipt_voucher_to_journal(voucher)
        voucher.refresh_from_db()
        balance_before = locked_loan.remaining_amount
        locked_loan.repaid_amount += amount
        if locked_loan.repaid_amount >= locked_loan.amount:
            locked_loan.status = EmployeeLoanAdvance.Status.FULLY_REPAID
        locked_loan.save(update_fields=["repaid_amount", "status", "updated_at"])
        repayment = EmployeeLoanRepayment.objects.create(
            school=school,
            branch=locked_loan.branch,
            loan=locked_loan,
            amount=amount,
            balance_before=balance_before,
            balance_after=locked_loan.remaining_amount,
            repaid_at=timezone.localdate(),
            idempotency_key=normalized_key,
            receipt_voucher=voucher,
            recorded_by=recorded_by,
            notes=(notes or "")[:500],
        )
        return repayment
