"""Financial and fee reports selectors for school administration."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import PaymentVoucher, ReceiptVoucher
from apps.student_fees.models import FeeInstallment, PaymentReceipt, StudentInvoice
from apps.students.models import Student


def get_student_statement_of_account(student: Student) -> dict[str, Any]:
    """توليد كشف حساب تفصيلي للطالب يوضح كافة المطالبات، الأقساط، والسندات المسددة باستبعاد السندات والفواتير الملغاة."""
    invoices = StudentInvoice.objects.filter(
        student=student,
        is_archived=False,
    ).exclude(status=StudentInvoice.Status.CANCELLED).order_by("issue_date")

    receipts = PaymentReceipt.objects.filter(
        student=student,
        is_archived=False,
        is_cancelled=False,
    ).order_by("paid_at")

    installments = FeeInstallment.objects.filter(plan__student=student, is_archived=False).order_by("due_date")

    invoice_list = []
    total_invoiced = Decimal("0.00")
    total_discounts = Decimal("0.00")

    for inv in invoices:
        total_invoiced += inv.total_amount
        total_discounts += inv.discount_amount
        invoice_list.append({
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "issue_date": inv.issue_date.isoformat(),
            "due_date": inv.due_date.isoformat(),
            "total_amount": float(inv.total_amount),
            "discount_amount": float(inv.discount_amount),
            "paid_amount": float(inv.paid_amount),
            "remaining_amount": float(inv.remaining_amount),
            "status": inv.status,
            "status_label": inv.get_status_display(),
        })

    receipt_list = []
    total_paid = Decimal("0.00")
    for rec in receipts:
        total_paid += rec.amount
        receipt_list.append({
            "id": str(rec.id),
            "receipt_number": rec.receipt_number,
            "paid_at": rec.paid_at.isoformat(),
            "amount": float(rec.amount),
            "payment_method": rec.payment_method,
            "payment_method_label": rec.get_payment_method_display(),
            "reference_number": rec.reference_number,
        })

    installment_list = []
    for inst in installments:
        installment_list.append({
            "id": str(inst.id),
            "installment_number": inst.installment_number,
            "title": inst.title,
            "amount": float(inst.amount),
            "due_date": inst.due_date.isoformat(),
            "paid_date": inst.paid_date.isoformat() if inst.paid_date else None,
            "status": inst.status,
            "status_label": inst.get_status_display(),
        })

    net_payable = max(Decimal("0.00"), total_invoiced - total_discounts)
    outstanding_balance = max(Decimal("0.00"), net_payable - total_paid)

    return {
        "student": {
            "id": str(student.id),
            "name": f"{student.first_name} {student.last_name}",
            "student_id_number": student.student_id_number,
            "section": str(student.section) if student.section else None,
            "school_id": str(student.school_id),
        },
        "summary": {
            "total_invoiced": float(total_invoiced),
            "total_discounts": float(total_discounts),
            "net_payable": float(net_payable),
            "total_paid": float(total_paid),
            "outstanding_balance": float(outstanding_balance),
            "credit_balance": float(student.credit_balance),
            "net_balance_due": float(max(Decimal("0.00"), outstanding_balance - student.credit_balance)),
            "has_overdue": any(inv.status != StudentInvoice.Status.PAID and inv.due_date < timezone.localdate() for inv in invoices),
        },
        "invoices": invoice_list,
        "receipts": receipt_list,
        "installments": installment_list,
    }


def get_aging_receivables_report(school) -> dict[str, Any]:
    """تقرير أعمار الديون والذمم المدينة للرسوم المدرسية (Aging of Receivables)."""
    today = timezone.localdate()
    invoices = StudentInvoice.objects.filter(
        school=school,
        is_archived=False,
    ).exclude(status__in=[StudentInvoice.Status.PAID, StudentInvoice.Status.CANCELLED]).select_related("student")

    buckets = {
        "current": Decimal("0.00"),     # لم تستحق بعد
        "days_1_30": Decimal("0.00"),   # متأخرة 1 إلى 30 يوماً
        "days_31_60": Decimal("0.00"),  # متأخرة 31 إلى 60 يوماً
        "days_61_90": Decimal("0.00"),  # متأخرة 61 إلى 90 يوماً
        "over_90": Decimal("0.00"),     # متأخرة أكثر من 90 يوماً
    }

    student_aging: dict[str, dict[str, Any]] = {}

    for inv in invoices:
        balance = inv.remaining_amount
        if balance <= 0:
            continue

        days_overdue = (today - inv.due_date).days
        student_key = str(inv.student_id)
        if student_key not in student_aging:
            student_aging[student_key] = {
                "student_id": student_key,
                "student_name": f"{inv.student.first_name} {inv.student.last_name}",
                "student_id_number": inv.student.student_id_number,
                "total_balance": Decimal("0.00"),
                "current": Decimal("0.00"),
                "days_1_30": Decimal("0.00"),
                "days_31_60": Decimal("0.00"),
                "days_61_90": Decimal("0.00"),
                "over_90": Decimal("0.00"),
            }

        student_aging[student_key]["total_balance"] += balance

        if days_overdue <= 0:
            buckets["current"] += balance
            student_aging[student_key]["current"] += balance
        elif 1 <= days_overdue <= 30:
            buckets["days_1_30"] += balance
            student_aging[student_key]["days_1_30"] += balance
        elif 31 <= days_overdue <= 60:
            buckets["days_31_60"] += balance
            student_aging[student_key]["days_31_60"] += balance
        elif 61 <= days_overdue <= 90:
            buckets["days_61_90"] += balance
            student_aging[student_key]["days_61_90"] += balance
        else:
            buckets["over_90"] += balance
            student_aging[student_key]["over_90"] += balance

    total_outstanding = sum(buckets.values(), Decimal("0.00"))

    aging_details = []
    for s_data in student_aging.values():
        aging_details.append({
            "student_id": s_data["student_id"],
            "student_name": s_data["student_name"],
            "student_id_number": s_data["student_id_number"],
            "total_balance": float(s_data["total_balance"]),
            "current": float(s_data["current"]),
            "days_1_30": float(s_data["days_1_30"]),
            "days_31_60": float(s_data["days_31_60"]),
            "days_61_90": float(s_data["days_61_90"]),
            "over_90": float(s_data["over_90"]),
        })

    return {
        "as_of_date": today.isoformat(),
        "total_outstanding": float(total_outstanding),
        "buckets": {k: float(v) for k, v in buckets.items()},
        "students_count": len(aging_details),
        "details": aging_details,
    }


def get_daily_cash_register_report(school, target_date=None) -> dict[str, Any]:
    """تقرير اليومية وحركة الصناديق والمقبوضات والمصروفات النقدية والبنكية."""
    if target_date is None:
        target_date = timezone.localdate()

    student_receipts = PaymentReceipt.objects.filter(
        school=school,
        is_archived=False,
        is_cancelled=False,
        paid_at__date=target_date,
    ).select_related("student")

    receipt_vouchers = ReceiptVoucher.objects.filter(
        school=school,
        is_archived=False,
        date=target_date,
        status=ReceiptVoucher.Status.POSTED,
    )

    payment_vouchers = PaymentVoucher.objects.filter(
        school=school,
        is_archived=False,
        date=target_date,
        status=PaymentVoucher.Status.POSTED,
    )

    inflow_items = []
    total_inflow = Decimal("0.00")

    for sr in student_receipts:
        total_inflow += sr.amount
        inflow_items.append({
            "type": "student_fee",
            "reference": sr.receipt_number,
            "party": f"{sr.student.first_name} {sr.student.last_name}",
            "amount": float(sr.amount),
            "payment_method": sr.get_payment_method_display(),
            "notes": sr.notes or "تحصيل رسوم دراسية",
        })

    for rv in receipt_vouchers:
        total_inflow += rv.amount
        inflow_items.append({
            "type": "general_receipt",
            "reference": rv.voucher_number,
            "party": rv.received_from,
            "amount": float(rv.amount),
            "payment_method": rv.get_payment_method_display(),
            "notes": rv.description,
        })

    outflow_items = []
    total_outflow = Decimal("0.00")

    for pv in payment_vouchers:
        total_outflow += pv.amount
        outflow_items.append({
            "type": "payment_voucher",
            "reference": pv.voucher_number,
            "party": pv.paid_to,
            "amount": float(pv.amount),
            "payment_method": pv.get_payment_method_display(),
            "notes": pv.description,
        })

    net_cash_movement = total_inflow - total_outflow

    return {
        "date": target_date.isoformat(),
        "total_inflow": float(total_inflow),
        "total_outflow": float(total_outflow),
        "net_movement": float(net_cash_movement),
        "inflows": inflow_items,
        "outflows": outflow_items,
    }


def get_billing_ledger_reconciliation_report(school) -> dict[str, Any]:
    """
    تقرير المطابقة الدورية الشامل بين سجلات الفواتير والتحصيل التشغيلية ودفتر الأستاذ العام (حساب 1104).
    """
    from apps.accounting.models import Account, JournalEntryLine

    active_invoices = StudentInvoice.objects.filter(
        school=school,
        is_archived=False,
    ).exclude(status=StudentInvoice.Status.CANCELLED)

    total_billed = Decimal("0.00")
    total_discounts = Decimal("0.00")
    total_collected = Decimal("0.00")

    for inv in active_invoices:
        total_billed += inv.total_amount
        total_discounts += inv.discount_amount
        total_collected += inv.paid_amount

    net_billed = max(Decimal("0.00"), total_billed - total_discounts)
    operational_receivable = max(Decimal("0.00"), net_billed - total_collected)

    acc_1104 = Account.objects.filter(school=school, code="1104", is_leaf=True).first()
    gl_debit = Decimal("0.00")
    gl_credit = Decimal("0.00")
    if acc_1104:
        lines = JournalEntryLine.objects.filter(
            school=school,
            account=acc_1104,
            journal_entry__status="posted",
            is_archived=False,
        )
        agg = lines.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        gl_debit = agg["total_debit"] or Decimal("0.00")
        gl_credit = agg["total_credit"] or Decimal("0.00")

    gl_receivable_balance = gl_debit - gl_credit
    variance = operational_receivable - gl_receivable_balance
    is_reconciled = (abs(variance) < Decimal("0.01"))

    return {
        "school": {
            "id": str(school.id),
            "name": school.name,
            "code": school.code,
        },
        "operational": {
            "total_billed": float(total_billed),
            "total_discounts": float(total_discounts),
            "net_billed": float(net_billed),
            "total_collected": float(total_collected),
            "operational_receivable": float(operational_receivable),
        },
        "ledger": {
            "account_code": "1104",
            "account_name": acc_1104.name if acc_1104 else "غير مهيأ",
            "gl_debit": float(gl_debit),
            "gl_credit": float(gl_credit),
            "gl_receivable_balance": float(gl_receivable_balance),
        },
        "reconciliation": {
            "variance": float(variance),
            "is_reconciled": is_reconciled,
            "status": "متطابق تماماً" if is_reconciled else "يوجد فروق تسوية",
        },
    }
