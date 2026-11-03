"""Budget reservation and auditable usage accounting for every paid AI call."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.copilot.models import AIUsageRecord, SchoolAIUsagePolicy


class AIUsageLimitExceeded(Exception):
    def __init__(self, message, *, code="quota_exceeded", http_status=429):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _estimate_tokens(value) -> int:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return max(1, math.ceil(len(text) / 4))


def _cost(input_tokens, output_tokens, policy):
    value = (
        Decimal(input_tokens) * policy.input_cost_per_1k_tokens
        + Decimal(output_tokens) * policy.output_cost_per_1k_tokens
    ) / Decimal(1000)
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _day_start():
    local_date = timezone.localdate()
    return timezone.make_aware(datetime.combine(local_date, time.min), timezone.get_current_timezone())


def _month_start():
    local_date = timezone.localdate()
    return timezone.make_aware(datetime(local_date.year, local_date.month, 1), timezone.get_current_timezone())


def _write_audit(record):
    from apps.auditlog.services import record_event
    record_event(
        action="copilot.ai_usage",
        description=f"استخدام أداة ذكاء اصطناعي: {record.tool}",
        actor=record.user,
        school=record.school,
        obj=record,
        metadata={
            "usage_id": str(record.pk),
            "tool": record.tool,
            "model": record.model_name,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "estimated_cost": str(record.estimated_cost),
            "currency": record.currency,
            "status": record.status,
            "sources": record.source_refs,
        },
    )


def run_budgeted_ai_call(
    *,
    school,
    user,
    tool: str,
    input_text,
    source_refs: dict | None,
    call,
    max_output_tokens: int = 2000,
):
    """Reserve quota/cost first, call provider, then persist estimated actual usage.

    Prompts, answers, phone numbers and student content are deliberately not copied
    into the usage ledger; only bounded source identifiers are stored.
    """
    estimated_input_tokens = _estimate_tokens(input_text)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    with transaction.atomic():
        try:
            SchoolAIUsagePolicy.objects.get_or_create(school=school)
        except Exception:
            raise
        policy = SchoolAIUsagePolicy.objects.select_for_update().get(school=school)
        if not policy.enabled:
            raise AIUsageLimitExceeded(
                "خدمة الذكاء الاصطناعي غير مفعلة لهذه المدرسة أو لم تضبط ميزانيتها وأسعارها.",
                code="ai_not_configured", http_status=503,
            )
        if (
            policy.monthly_budget_amount <= 0
            or (policy.input_cost_per_1k_tokens <= 0 and policy.output_cost_per_1k_tokens <= 0)
            or policy.daily_request_limit < 1
            or policy.daily_token_limit < 1
        ):
            raise AIUsageLimitExceeded(
                "سياسة ميزانية الذكاء الاصطناعي غير مكتملة؛ راجع إعدادات المدرسة.",
                code="ai_policy_invalid", http_status=503,
            )

        day_records = AIUsageRecord.objects.filter(school=school, created_at__gte=_day_start())
        day_requests = day_records.count()
        day_totals = day_records.aggregate(input_sum=Sum("input_tokens"), output_sum=Sum("output_tokens"))
        day_tokens = (day_totals["input_sum"] or 0) + (day_totals["output_sum"] or 0)

        output_reservation = min(max(1, int(max_output_tokens)), policy.max_output_tokens)
        if day_requests >= policy.daily_request_limit:
            raise AIUsageLimitExceeded("تم بلوغ الحد اليومي لعدد طلبات الذكاء الاصطناعي.")
        if day_tokens + estimated_input_tokens + output_reservation > policy.daily_token_limit:
            raise AIUsageLimitExceeded("الطلب يتجاوز حصة التوكنز اليومية المتبقية.")

        month_cost = AIUsageRecord.objects.filter(
            school=school, created_at__gte=_month_start(),
        ).aggregate(total=Sum("estimated_cost"))["total"] or Decimal("0")
        reserved_cost = _cost(estimated_input_tokens, output_reservation, policy)
        if month_cost + reserved_cost > policy.monthly_budget_amount:
            raise AIUsageLimitExceeded("الطلب يتجاوز الميزانية الشهرية المتبقية.", code="ai_budget_exceeded")

        safe_sources = source_refs or {}
        if not isinstance(safe_sources, dict):
            safe_sources = {}
        safe_sources = {
            str(key)[:60]: str(value)[:120]
            for key, value in list(safe_sources.items())[:20]
            if value is not None
        }
        record = AIUsageRecord.objects.create(
            school=school,
            user=user,
            tool=tool[:80],
            model_name=model_name[:100],
            source_refs=safe_sources,
            input_tokens=estimated_input_tokens,
            output_tokens=output_reservation,
            estimated_cost=reserved_cost,
            currency=policy.currency,
            status=AIUsageRecord.Status.STARTED,
        )

    try:
        result = call()
    except Exception as exc:
        actual_cost = _cost(estimated_input_tokens, 0, policy)
        AIUsageRecord.objects.filter(pk=record.pk).update(
            output_tokens=0,
            estimated_cost=actual_cost,
            status=AIUsageRecord.Status.FAILED,
            failure_code=type(exc).__name__[:80],
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        record.refresh_from_db()
        _write_audit(record)
        raise

    output_tokens = min(_estimate_tokens(result), output_reservation)
    actual_cost = _cost(estimated_input_tokens, output_tokens, policy)
    AIUsageRecord.objects.filter(pk=record.pk).update(
        output_tokens=output_tokens,
        estimated_cost=actual_cost,
        status=AIUsageRecord.Status.SUCCEEDED,
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )
    record.refresh_from_db()
    _write_audit(record)
    return result
