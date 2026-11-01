"""Treasury transfers and bank statement reconciliation services."""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import (
    BankReconciliation,
    BankStatementLine,
    JournalEntry,
    JournalEntryLine,
    TreasuryAccount,
    TreasuryTransfer,
)
from apps.accounting.services.auto_posting import (
    _get_active_fiscal_period,
    reverse_journal_entry,
)


ZERO = Decimal("0.00")


@transaction.atomic
def create_treasury_transfer(
    *,
    source_account: TreasuryAccount,
    destination_account: TreasuryAccount,
    amount: Decimal,
    transfer_number: str,
    idempotency_key: str,
    transfer_date=None,
    description: str = "",
    user=None,
) -> TreasuryTransfer:
    """تنفيذ تحويل خزينة بقيد مزدوج واحد، مع قفل المدرسة ومنع تكرار المفتاح."""
    from apps.tenants.models import School

    school_id = source_account.school_id
    School.objects.select_for_update().get(pk=school_id)
    if destination_account.school_id != school_id:
        raise ValidationError("لا يمكن التحويل بين مدرستين مختلفتين.")

    existing = TreasuryTransfer.objects.filter(
        school_id=school_id,
        idempotency_key=idempotency_key,
        is_archived=False,
    ).first()
    if existing:
        same_data = (
            existing.source_account_id == source_account.pk
            and existing.destination_account_id == destination_account.pk
            and existing.amount == amount
            and existing.transfer_number == transfer_number
            and (transfer_date is None or existing.transfer_date == transfer_date)
        )
        if not same_data:
            raise ValidationError("مفتاح منع التكرار مستخدم لتحويل ببيانات مختلفة.")
        if existing.status == TreasuryTransfer.Status.POSTED:
            return existing
        if existing.status == TreasuryTransfer.Status.REVERSED:
            raise ValidationError("تم عكس التحويل السابق ولا يمكن إعادة استخدام مفتاحه.")
        transfer = existing
    else:
        account_ids = sorted((source_account.pk, destination_account.pk), key=str)
        locked_accounts = {
            item.pk: item
            for item in TreasuryAccount.objects.select_for_update().filter(
                pk__in=account_ids,
                school_id=school_id,
                is_active=True,
                is_archived=False,
            )
        }
        if len(locked_accounts) != 2:
            raise ValidationError("يجب أن يكون حسابا التحويل نشطين ويتبعان المدرسة نفسها.")
        source = locked_accounts[source_account.pk]
        destination = locked_accounts[destination_account.pk]
        transfer = TreasuryTransfer.objects.create(
            school_id=school_id,
            branch_id=source.branch_id if source.branch_id == destination.branch_id else None,
            transfer_number=transfer_number,
            transfer_date=transfer_date or timezone.localdate(),
            source_account=source,
            destination_account=destination,
            amount=amount,
            description=description,
            idempotency_key=idempotency_key,
            status=TreasuryTransfer.Status.DRAFT,
        )

    if transfer.journal_entry_id:
        if transfer.journal_entry.status == JournalEntry.Status.POSTED:
            transfer.status = TreasuryTransfer.Status.POSTED
            transfer.save(update_fields=["status", "updated_at"])
            return transfer
        raise ValidationError("يوجد قيد تحويل سابق غير مرحل؛ يجب مراجعته قبل المتابعة.")

    source = transfer.source_account
    destination = transfer.destination_account
    period = _get_active_fiscal_period(transfer.school, transfer.transfer_date)
    same_branch = source.branch_id == destination.branch_id
    entry = JournalEntry.objects.create(
        school=transfer.school,
        branch=source.branch if same_branch else None,
        fiscal_period=period,
        entry_number=f"TR-{transfer.transfer_number}",
        date=transfer.transfer_date,
        description=f"تحويل خزينة {source.name} إلى {destination.name}: {transfer.description}",
        status=JournalEntry.Status.DRAFT,
        source_module="treasury_transfer",
        source_reference=str(transfer.pk),
    )
    JournalEntryLine.objects.create(
        school=transfer.school,
        branch=destination.branch,
        journal_entry=entry,
        account=destination.account,
        debit=transfer.amount,
        credit=ZERO,
        description=f"إيداع تحويل وارد إلى {destination.name}",
    )
    JournalEntryLine.objects.create(
        school=transfer.school,
        branch=source.branch,
        journal_entry=entry,
        account=source.account,
        debit=ZERO,
        credit=transfer.amount,
        description=f"تحويل صادر من {source.name}",
    )
    entry.post(user=user)
    transfer.journal_entry = entry
    transfer.status = TreasuryTransfer.Status.POSTED
    transfer.save(update_fields=["journal_entry", "status", "updated_at"])
    return transfer


@transaction.atomic
def reverse_treasury_transfer(
    transfer: TreasuryTransfer,
    *,
    reason: str,
    reversed_by=None,
) -> TreasuryTransfer:
    locked = TreasuryTransfer.objects.select_for_update().select_related(
        "journal_entry",
    ).get(pk=transfer.pk)
    if locked.status == TreasuryTransfer.Status.REVERSED:
        return locked
    if locked.status != TreasuryTransfer.Status.POSTED or not locked.journal_entry_id:
        raise ValidationError("لا يمكن عكس تحويل غير مرحل.")
    reversal = reverse_journal_entry(
        locked.journal_entry,
        reason=reason,
        reversed_by=reversed_by,
    )
    locked.status = TreasuryTransfer.Status.REVERSED
    locked.reversed_by_entry = reversal
    locked.save(update_fields=["status", "reversed_by_entry", "updated_at"])
    return locked


def complete_bank_reconciliation(
    reconciliation: BankReconciliation,
    *,
    reconciled_by,
) -> BankReconciliation:
    """مطابقة كشف البنك مع حفظ فروقات المحاولة الفاشلة لأغراض المراجعة."""
    result, error = _complete_bank_reconciliation(
        reconciliation,
        reconciled_by=reconciled_by,
    )
    if error:
        raise ValidationError(error)
    return result


@transaction.atomic
def _complete_bank_reconciliation(
    reconciliation: BankReconciliation,
    *,
    reconciled_by,
) -> tuple[BankReconciliation, str | None]:
    """الجزء الذري: احسب واحفظ نتائج المطابقة قبل إبلاغ المستدعي بالفرق."""
    locked = BankReconciliation.objects.select_for_update().select_related(
        "treasury_account__account",
    ).get(pk=reconciliation.pk)
    if locked.status == BankReconciliation.Status.RECONCILED:
        return locked, None

    lines = list(
        BankStatementLine.objects.select_for_update().filter(
            reconciliation=locked,
            is_archived=False,
        ).select_related("journal_line__journal_entry")
    )
    statement_net = sum((line.amount for line in lines), ZERO)
    expected_statement_close = locked.statement_opening_balance + statement_net
    if expected_statement_close != locked.statement_closing_balance:
        raise ValidationError(
            "مجموع حركات كشف البنك لا يساوي الفرق بين الرصيد الافتتاحي والختامي."
        )

    matched_ids = set()
    for statement_line in lines:
        if not statement_line.journal_line_id:
            raise ValidationError(
                f"حركة البنك {statement_line.external_reference} لم تطابق مع قيد في دفتر الأستاذ."
            )
        statement_line.full_clean()
        matched_ids.add(statement_line.journal_line_id)

    account_lines = JournalEntryLine.objects.filter(
        school=locked.school,
        account=locked.treasury_account.account,
        journal_entry__school=locked.school,
        journal_entry__status=JournalEntry.Status.POSTED,
        is_archived=False,
    )
    before = account_lines.filter(
        journal_entry__date__lt=locked.start_date,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    within = account_lines.filter(
        journal_entry__date__range=(locked.start_date, locked.end_date),
    )
    through = account_lines.filter(
        journal_entry__date__lte=locked.end_date,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    book_opening = (before["debit"] or ZERO) - (before["credit"] or ZERO)
    book_closing = (through["debit"] or ZERO) - (through["credit"] or ZERO)

    statement_opening_difference = book_opening - locked.statement_opening_balance
    if statement_opening_difference != ZERO:
        raise ValidationError(
            "الرصيد الافتتاحي في كشف البنك لا يطابق رصيد الأستاذ؛ يجب إقفال الفترة السابقة أو تسوية الفرق أولاً."
        )

    unmatched = within.exclude(pk__in=matched_ids).aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )
    outstanding = (unmatched["debit"] or ZERO) - (unmatched["credit"] or ZERO)
    adjusted_statement = locked.statement_closing_balance + outstanding
    difference = book_closing - adjusted_statement

    locked.book_opening_balance = book_opening
    locked.book_closing_balance = book_closing
    locked.outstanding_ledger_amount = outstanding
    locked.difference = difference
    if difference != ZERO:
        locked.save(update_fields=[
            "book_opening_balance", "book_closing_balance",
            "outstanding_ledger_amount", "difference", "updated_at",
        ])
        return locked, (
            f"كشف البنك غير مطابق لدفتر الأستاذ. الفرق المتبقي: {difference}."
        )

    locked.status = BankReconciliation.Status.RECONCILED
    locked.reconciled_at = timezone.now()
    locked.reconciled_by = reconciled_by
    locked.save(update_fields=[
        "book_opening_balance", "book_closing_balance",
        "outstanding_ledger_amount", "difference",
        "status", "reconciled_at", "reconciled_by", "updated_at",
    ])
    return locked, None
