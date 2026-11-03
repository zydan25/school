"""School-scoped AI policy administration and usage summaries."""
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import has_school_roles
from apps.copilot.api.views import AI_TEACHER_ADMIN_ROLES, _resolve_school
from apps.copilot.models import AIUsageRecord, SchoolAIUsagePolicy


def _school_and_admin(request):
    school = _resolve_school(request)
    is_admin = school.owner_id == request.user.pk or has_school_roles(
        request.user, school, AI_TEACHER_ADMIN_ROLES,
    )
    return school, is_admin


class SchoolAIUsagePolicyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school, is_admin = _school_and_admin(request)
        if not is_admin:
            raise PermissionDenied("عرض سياسة ميزانية AI يتطلب صلاحية إدارة المدرسة.")
        policy, _ = SchoolAIUsagePolicy.objects.get_or_create(school=school)
        return Response(_policy_data(policy))

    def patch(self, request):
        school, is_admin = _school_and_admin(request)
        if not is_admin:
            raise PermissionDenied("تعديل سياسة ميزانية AI يتطلب صلاحية إدارة المدرسة.")
        allowed = {
            "enabled", "daily_request_limit", "daily_token_limit",
            "monthly_budget_amount", "input_cost_per_1k_tokens",
            "output_cost_per_1k_tokens", "currency", "max_output_tokens",
        }
        if set(request.data) - allowed:
            raise ValidationError("توجد حقول غير مسموح بتعديلها.")
        policy, _ = SchoolAIUsagePolicy.objects.get_or_create(school=school)
        for key, value in request.data.items():
            if key in {"monthly_budget_amount", "input_cost_per_1k_tokens", "output_cost_per_1k_tokens"}:
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValidationError({key: "قيمة رقمية غير صالحة."})
                if value < 0:
                    raise ValidationError({key: "لا تقبل القيم السالبة."})
            if key == "currency":
                value = str(value).upper()
                if len(value) != 3 or not value.isalpha():
                    raise ValidationError({key: "أدخل رمز عملة مكوناً من ثلاثة أحرف."})
            setattr(policy, key, value)
        policy.full_clean()
        policy.save()
        return Response(_policy_data(policy))


def _policy_data(policy):
    return {
        "enabled": policy.enabled,
        "daily_request_limit": policy.daily_request_limit,
        "daily_token_limit": policy.daily_token_limit,
        "monthly_budget_amount": str(policy.monthly_budget_amount),
        "input_cost_per_1k_tokens": str(policy.input_cost_per_1k_tokens),
        "output_cost_per_1k_tokens": str(policy.output_cost_per_1k_tokens),
        "currency": policy.currency,
        "max_output_tokens": policy.max_output_tokens,
    }


class AIUsageSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school, is_admin = _school_and_admin(request)
        qs = AIUsageRecord.objects.filter(school=school)
        if not is_admin:
            qs = qs.filter(user=request.user)
        today = timezone.localdate()
        month = today.replace(day=1)
        day_rows = qs.filter(created_at__date=today)
        month_rows = qs.filter(created_at__date__gte=month)
        daily_tokens = day_rows.aggregate(total_input=Sum("input_tokens"), total_output=Sum("output_tokens"))
        month_totals = month_rows.aggregate(total=Sum("estimated_cost"))
        policy = SchoolAIUsagePolicy.objects.filter(school=school).first()
        return Response({
            "scope": "school" if is_admin else "user",
            "daily_requests": day_rows.count(),
            "daily_input_tokens": daily_tokens["total_input"] or 0,
            "daily_output_tokens": daily_tokens["total_output"] or 0,
            "monthly_estimated_cost": str(month_totals["total"] or Decimal("0")),
            "currency": policy.currency if policy else "USD",
            "policy": _policy_data(policy) if is_admin and policy else None,
        })
