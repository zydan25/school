"""Device session, phone challenge and account recovery services."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.module_loading import import_string

from apps.accounts.models import DeviceSession, PhoneVerificationChallenge, User


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def authenticate_api_credential(raw_token: str):
    """Return (user, auth_object) for a current device session or legacy DRF token."""
    if not raw_token or len(raw_token) > 256:
        return None
    digest = token_digest(raw_token)
    session = DeviceSession.objects.select_related("user").filter(
        token_digest=digest,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
        user__is_active=True,
        user__status=User.Status.ACTIVE,
    ).first()
    if session:
        now = timezone.now()
        if session.last_used_at is None or session.last_used_at < now - timedelta(minutes=5):
            session.last_used_at = now
            session.save(update_fields=["last_used_at", "updated_at"])
        return session.user, session

    # Backward compatibility for tokens issued before the device-session rollout.
    from rest_framework.authtoken.models import Token
    legacy_token = Token.objects.select_related("user").filter(key=raw_token).first()
    if legacy_token and legacy_token.user.is_active and legacy_token.user.status == User.Status.ACTIVE:
        return legacy_token.user, legacy_token
    return None


@transaction.atomic
def create_device_session(*, user, device_id="", device_name="", user_agent="", ip_address=None):
    raw_token = secrets.token_urlsafe(48)
    now = timezone.now()
    normalized_device_id = (device_id or "").strip()[:128] or secrets.token_urlsafe(18)
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if not locked_user.is_active or locked_user.status != User.Status.ACTIVE:
        raise ValidationError("الحساب غير نشط.")

    DeviceSession.objects.select_for_update().filter(
        user=locked_user,
        device_id=normalized_device_id,
        revoked_at__isnull=True,
    ).update(revoked_at=now, updated_at=now)

    session = DeviceSession.objects.create(
        user=locked_user,
        token_digest=token_digest(raw_token),
        device_id=normalized_device_id,
        device_name=(device_name or "")[:120],
        user_agent=(user_agent or "")[:512],
        ip_address=ip_address,
        expires_at=now + timedelta(days=getattr(settings, "API_SESSION_LIFETIME_DAYS", 30)),
        last_used_at=now,
    )
    return session, raw_token


@transaction.atomic
def rotate_device_session(session: DeviceSession):
    locked = DeviceSession.objects.select_for_update().select_related("user").get(pk=session.pk)
    if not locked.is_active:
        raise ValidationError("انتهت الجلسة أو تم إبطالها؛ سجل الدخول مجدداً.")
    raw_token = secrets.token_urlsafe(48)
    locked.token_digest = token_digest(raw_token)
    locked.expires_at = timezone.now() + timedelta(
        days=getattr(settings, "API_SESSION_LIFETIME_DAYS", 30)
    )
    locked.last_used_at = timezone.now()
    locked.save(update_fields=["token_digest", "expires_at", "last_used_at", "updated_at"])
    return locked, raw_token


def revoke_device_session(*, user, session_id=None):
    now = timezone.now()
    qs = DeviceSession.objects.filter(user=user, revoked_at__isnull=True)
    if session_id is not None:
        qs = qs.filter(pk=session_id)
    return qs.update(revoked_at=now, updated_at=now)


def _challenge_digest(*, purpose: str, phone: str, code: str) -> str:
    return salted_hmac(
        "school-phone-otp",
        f"{purpose}:{phone}:{code}",
        secret=settings.SECRET_KEY,
    ).hexdigest()


def send_phone_message(*, phone: str, message: str, purpose: str) -> None:
    """Use the configured SMS adapter; fail closed when no delivery provider is configured."""
    backend_path = getattr(settings, "PHONE_OTP_DELIVERY_BACKEND", "")
    if not backend_path:
        raise ImproperlyConfigured(
            "لم يتم إعداد مزود رسائل OTP؛ اضبط PHONE_OTP_DELIVERY_BACKEND قبل تفعيل التسجيل أو الاستعادة."
        )
    backend = import_string(backend_path)
    result = backend(phone=phone, message=message, purpose=purpose)
    if result is False:
        raise RuntimeError("تعذر تسليم رسالة التحقق إلى مزود الرسائل.")


@transaction.atomic
def issue_phone_challenge(*, user, purpose: str, request_ip=None):
    now = timezone.now()
    recent = PhoneVerificationChallenge.objects.filter(
        user=user, purpose=purpose, created_at__gte=now - timedelta(hours=1),
    ).count()
    if recent >= 5:
        raise ValidationError("تجاوزت عدد طلبات رموز التحقق المسموح؛ حاول لاحقاً.")

    last = PhoneVerificationChallenge.objects.filter(
        user=user, purpose=purpose,
    ).order_by("-created_at").first()
    if last and last.created_at > now - timedelta(seconds=60):
        raise ValidationError("انتظر دقيقة قبل طلب رمز تحقق جديد.")

    # Only one unconsumed challenge per purpose remains usable.
    PhoneVerificationChallenge.objects.filter(
        user=user, purpose=purpose, consumed_at__isnull=True,
    ).update(consumed_at=now, updated_at=now)

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        phone=user.phone,
        purpose=purpose,
        code_digest=_challenge_digest(purpose=purpose, phone=user.phone, code=code),
        expires_at=now + timedelta(minutes=5),
        request_ip=request_ip,
    )
    message = f"رمز التحقق الخاص بمنصة سكول هو: {code}. صالح لمدة 5 دقائق ولا تشاركه مع أحد."
    try:
        send_phone_message(phone=user.phone, message=message, purpose=purpose)
    except Exception:
        challenge.delete()
        raise
    return challenge


def consume_phone_challenge(*, user, phone: str, purpose: str, code: str):
    now = timezone.now()
    invalid = False
    consumed = None
    with transaction.atomic():
        challenge = PhoneVerificationChallenge.objects.select_for_update().filter(
            user=user,
            phone=phone,
            purpose=purpose,
            consumed_at__isnull=True,
        ).order_by("-created_at").first()
        if challenge is None or challenge.expires_at <= now or challenge.attempts >= 5:
            invalid = True
        else:
            expected = challenge.code_digest
            actual = _challenge_digest(purpose=purpose, phone=phone, code=code)
            if not constant_time_compare(expected, actual):
                challenge.attempts += 1
                if challenge.attempts >= 5:
                    challenge.consumed_at = now
                challenge.save(update_fields=["attempts", "consumed_at", "updated_at"])
                invalid = True
            else:
                challenge.consumed_at = now
                challenge.save(update_fields=["consumed_at", "updated_at"])
                consumed = challenge

    # Raise outside the atomic block so the failed-attempt counter is committed.
    if invalid:
        raise ValidationError("رمز التحقق غير صحيح أو منتهي الصلاحية.")
    return consumed
