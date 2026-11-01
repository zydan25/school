"""
apps/accounting/services/financial_reports.py
محرك التقارير المالية المدرسية: ميزان المراجعة، الأرباح والخسائر، الميزانية، ودفتر الأستاذ.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.tenants.models import School


def get_trial_balance(
    school: School,
    as_of_date: datetime.date | None = None,
) -> dict[str, Any]:
    """
    ميزان المراجعة بالأرصدة والمجاميع لمدرسة محددة.
    """
    if as_of_date is None:
        as_of_date = timezone.localdate()

    # Query posted journal lines up to the date
    lines = JournalEntryLine.objects.filter(
        school=school,
        journal_entry__status=JournalEntry.Status.POSTED,
        journal_entry__date__lte=as_of_date,
        is_archived=False,
    ).values("account_id", "account__code", "account__name", "account__account_type").annotate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    ).order_by("account__code")

    records = []
    grand_total_debit = Decimal("0.00")
    grand_total_credit = Decimal("0.00")

    for row in lines:
        t_debit = row["total_debit"] or Decimal("0.00")
        t_credit = row["total_credit"] or Decimal("0.00")
        grand_total_debit += t_debit
        grand_total_credit += t_credit

        net_balance = t_debit - t_credit
        records.append({
            "account_id": str(row["account_id"]),
            "account_code": row["account__code"],
            "account_name": row["account__name"],
            "account_type": row["account__account_type"],
            "total_debit": float(t_debit),
            "total_credit": float(t_credit),
            "net_debit": float(net_balance) if net_balance > 0 else 0.0,
            "net_credit": float(abs(net_balance)) if net_balance < 0 else 0.0,
        })

    is_balanced = (grand_total_debit == grand_total_credit)

    return {
        "school": school.name,
        "as_of_date": str(as_of_date),
        "is_balanced": is_balanced,
        "total_debit": float(grand_total_debit),
        "total_credit": float(grand_total_credit),
        "accounts": records,
    }


def get_income_statement(
    school: School,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> dict[str, Any]:
    """
    قائمة الدخل وتقرير الأرباح والخسائر: الإيرادات - المصروفات = صافي الدخل / الخسارة.
    """
    if end_date is None:
        end_date = timezone.localdate()
    if start_date is None:
        start_date = datetime.date(end_date.year, 1, 1)

    # Posted lines within date range
    lines = JournalEntryLine.objects.filter(
        school=school,
        journal_entry__status=JournalEntry.Status.POSTED,
        journal_entry__date__gte=start_date,
        journal_entry__date__lte=end_date,
        is_archived=False,
    ).select_related("account")

    revenues: dict[str, Decimal] = {}
    expenses: dict[str, Decimal] = {}

    total_revenues = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for line in lines:
        acc = line.account
        if acc.account_type == Account.AccountType.REVENUE:
            # Net revenue is credit - debit
            amount = line.credit - line.debit
            revenues[acc.name] = revenues.get(acc.name, Decimal("0.00")) + amount
            total_revenues += amount
        elif acc.account_type == Account.AccountType.EXPENSE:
            # Net expense is debit - credit
            amount = line.debit - line.credit
            expenses[acc.name] = expenses.get(acc.name, Decimal("0.00")) + amount
            total_expenses += amount

    net_income = total_revenues - total_expenses

    return {
        "school": school.name,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_revenues": float(total_revenues),
        "total_expenses": float(total_expenses),
        "net_income": float(net_income),
        "is_profit": (net_income >= 0),
        "revenues_breakdown": [{"name": k, "amount": float(v)} for k, v in revenues.items()],
        "expenses_breakdown": [{"name": k, "amount": float(v)} for k, v in expenses.items()],
    }


def get_balance_sheet(
    school: School,
    as_of_date: datetime.date | None = None,
) -> dict[str, Any]:
    """
    الميزانية العمومية وقائمة المركز المالي: الأصول = الالتزامات + حقوق الملكية.
    """
    if as_of_date is None:
        as_of_date = timezone.localdate()

    lines = JournalEntryLine.objects.filter(
        school=school,
        journal_entry__status=JournalEntry.Status.POSTED,
        journal_entry__date__lte=as_of_date,
        is_archived=False,
    ).select_related("account")

    assets = Decimal("0.00")
    liabilities = Decimal("0.00")
    equity = Decimal("0.00")

    assets_breakdown = {}
    liabilities_breakdown = {}
    equity_breakdown = {}

    for line in lines:
        acc = line.account
        if acc.account_type == Account.AccountType.ASSET:
            amt = line.debit - line.credit
            assets += amt
            assets_breakdown[acc.name] = assets_breakdown.get(acc.name, Decimal("0.00")) + amt
        elif acc.account_type == Account.AccountType.LIABILITY:
            amt = line.credit - line.debit
            liabilities += amt
            liabilities_breakdown[acc.name] = liabilities_breakdown.get(acc.name, Decimal("0.00")) + amt
        elif acc.account_type == Account.AccountType.EQUITY:
            amt = line.credit - line.debit
            equity += amt
            equity_breakdown[acc.name] = equity_breakdown.get(acc.name, Decimal("0.00")) + amt

    # Net result from revenues & expenses contributes to equity as retained earnings
    inc_statement = get_income_statement(school, end_date=as_of_date)
    period_earnings = Decimal(str(inc_statement["net_income"]))
    equity += period_earnings
    equity_breakdown["أرباح / (خسائر) الفترة الحالية"] = float(period_earnings)

    return {
        "school": school.name,
        "as_of_date": str(as_of_date),
        "total_assets": float(assets),
        "total_liabilities": float(liabilities),
        "total_equity": float(equity),
        "total_liabilities_and_equity": float(liabilities + equity),
        "difference": float(assets - (liabilities + equity)),
        "assets_breakdown": [{"name": k, "amount": float(v)} for k, v in assets_breakdown.items()],
        "liabilities_breakdown": [{"name": k, "amount": float(v)} for k, v in liabilities_breakdown.items()],
        "equity_breakdown": [{"name": k, "amount": float(v)} for k, v in equity_breakdown.items()],
    }


def get_general_ledger(
    account: Account,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> dict[str, Any]:
    """كشف حركة حساب تفصيلي مع رصيد افتتاحي ورصيد متحرك لكل حركة."""
    if account.is_archived:
        raise ValueError("لا يمكن عرض دفتر أستاذ لحساب مؤرشف.")
    if not account.is_leaf:
        raise ValueError("يجب اختيار حساب تفصيلي لعرض دفتر الأستاذ.")

    if end_date is None:
        end_date = timezone.localdate()
    if start_date is None:
        start_date = datetime.date(end_date.year, 1, 1)
    if start_date > end_date:
        raise ValueError("تاريخ بداية التقرير يجب ألا يتجاوز تاريخ نهايته.")

    base_lines = JournalEntryLine.objects.filter(
        school=account.school,
        account=account,
        journal_entry__school=account.school,
        journal_entry__status=JournalEntry.Status.POSTED,
        is_archived=False,
    )
    opening_totals = base_lines.filter(
        journal_entry__date__lt=start_date,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    opening_debit = opening_totals["debit"] or Decimal("0.00")
    opening_credit = opening_totals["credit"] or Decimal("0.00")
    opening_balance = opening_debit - opening_credit
    running_balance = opening_balance

    lines = base_lines.filter(
        journal_entry__date__range=(start_date, end_date),
    ).select_related(
        "journal_entry", "branch", "cost_center",
    ).order_by(
        "journal_entry__date", "journal_entry__created_at", "journal_entry_id", "created_at", "pk",
    )

    movements = []
    period_debit = Decimal("0.00")
    period_credit = Decimal("0.00")
    for line in lines:
        period_debit += line.debit
        period_credit += line.credit
        running_balance += line.debit - line.credit
        movements.append({
            "line_id": str(line.pk),
            "date": line.journal_entry.date.isoformat(),
            "entry_number": line.journal_entry.entry_number,
            "description": line.description or line.journal_entry.description,
            "source_module": line.journal_entry.source_module,
            "source_reference": line.journal_entry.source_reference,
            "branch_id": str(line.branch_id) if line.branch_id else None,
            "cost_center_id": str(line.cost_center_id) if line.cost_center_id else None,
            "debit": float(line.debit),
            "credit": float(line.credit),
            "running_debit_balance": float(max(running_balance, Decimal("0.00"))),
            "running_credit_balance": float(max(-running_balance, Decimal("0.00"))),
            "running_signed_balance": float(running_balance),
        })

    closing_balance = running_balance
    return {
        "school": {"id": str(account.school_id), "name": account.school.name},
        "account": {
            "id": str(account.pk),
            "code": account.code,
            "name": account.name,
            "type": account.account_type,
        },
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening": {
            "debit": float(max(opening_balance, Decimal("0.00"))),
            "credit": float(max(-opening_balance, Decimal("0.00"))),
            "signed_balance": float(opening_balance),
        },
        "period": {
            "debit": float(period_debit),
            "credit": float(period_credit),
        },
        "closing": {
            "debit": float(max(closing_balance, Decimal("0.00"))),
            "credit": float(max(-closing_balance, Decimal("0.00"))),
            "signed_balance": float(closing_balance),
        },
        "movements": movements,
    }
