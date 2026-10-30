"""
apps/accounting/services/financial_reports.py
محرك التقارير المالية المدرسية: ميزان المراجعة، الأرباح والخسائر، الميزانية، ودفتر الأستاذ.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.tenants.models import School


def get_trial_balance(
    school: School,
    as_of_date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
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
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
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

    revenues: Dict[str, Decimal] = {}
    expenses: Dict[str, Decimal] = {}

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
    as_of_date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
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
