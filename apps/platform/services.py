"""Subscription entitlement and platform-only payment services."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.auditlog.services import record_event
from apps.platform.models import PlatformInvoice, PlatformPayment, SchoolFeatureOverride, Subscription


def active_subscription_for(school, *, at=None):
    at = at or timezone.now()
    return Subscription.objects.filter(
        school=school,
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIAL],
        starts_at__lte=at,
        ends_at__gt=at,
    ).select_related("plan").order_by("-starts_at").first()


def school_has_feature(school, feature_code: str, *, at=None) -> bool:
    """Overrides intentionally take precedence; otherwise evaluate the current plan."""
    at = at or timezone.now()
    override = SchoolFeatureOverride.objects.filter(
        school=school,
        feature__code=feature_code,
        feature__is_active=True,
    ).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=at)).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=at)
    ).first()
    if override is not None:
        return override.is_enabled
    subscription = active_subscription_for(school, at=at)
    if subscription is None:
        return False
    return subscription.plan.feature_links.filter(
        feature__code=feature_code,
        feature__is_active=True,
        is_included=True,
    ).exists()


def check_plan_limit(school, limit_name: str, current_value: int) -> None:
    subscription = active_subscription_for(school)
    if subscription is None:
        raise ValidationError("لا يوجد اشتراك نشط لهذه المدرسة.")
    field_map = {
        "students": subscription.plan.max_students,
        "staff": subscription.plan.max_staff,
        "branches": subscription.plan.max_branches,
    }
    if limit_name not in field_map:
        raise ValueError(f"Unsupported plan limit: {limit_name}")
    limit = field_map[limit_name]
    if limit is not None and current_value >= limit:
        raise ValidationError(f"تم بلوغ الحد المسموح في باقة المدرسة: {limit}.")


@transaction.atomic
def record_successful_platform_payment(*, invoice_id, amount, method, provider="", provider_reference="", actor=None):
    """Record a confirmed subscription payment and update only the platform invoice."""
    invoice = PlatformInvoice.objects.select_for_update().select_related("school", "subscription").get(pk=invoice_id)
    amount = Decimal(str(amount))
    if invoice.status in [PlatformInvoice.Status.DRAFT, PlatformInvoice.Status.VOID]:
        raise ValidationError("لا يمكن تحصيل فاتورة مسودة أو ملغاة.")
    if amount <= 0 or invoice.paid_amount + amount > invoice.total:
        raise ValidationError("مبلغ التحصيل غير صالح أو يتجاوز الرصيد المستحق.")
    payment = PlatformPayment.objects.create(
        invoice=invoice, amount=amount, currency_code=invoice.currency_code,
        status=PlatformPayment.Status.SUCCEEDED, method=method,
        provider=provider, provider_reference=provider_reference,
        paid_at=timezone.now(),
    )
    invoice.paid_amount += amount
    invoice.status = PlatformInvoice.Status.PAID if invoice.paid_amount == invoice.total else PlatformInvoice.Status.PARTIAL
    invoice.save(update_fields=["paid_amount", "status", "updated_at"])
    record_event(
        action="platform.subscription_payment.received",
        description=f"استلام دفعة اشتراك للفاتورة {invoice.number}",
        actor=actor, school=invoice.school, obj=payment,
        metadata={"invoice_id": str(invoice.pk), "amount": str(amount), "currency": invoice.currency_code},
    )
    from apps.notifications.services import enqueue_event
    enqueue_event(
        event_name="platform.subscription_payment.received",
        aggregate_type="platform.PlatformPayment",
        aggregate_id=str(payment.pk),
        school=invoice.school,
        payload={"invoice_number": invoice.number, "amount": str(amount), "currency": invoice.currency_code},
        idempotency_key=f"platform-payment:{payment.pk}",
    )
    return payment
