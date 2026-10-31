"""Additional identity throttles keyed by privacy-preserving phone/device identifiers."""
from __future__ import annotations

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class _IdentifierRateThrottle(SimpleRateThrottle):
    """Rate-limit a normalized identifier without storing it in the cache key."""

    identifier_name = ""

    def get_identifier(self, request):
        raise NotImplementedError

    def get_cache_key(self, request, view):
        identifier = self.get_identifier(request)
        if not identifier:
            return None
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class PhoneScopedRateThrottle(_IdentifierRateThrottle):
    """Apply a phone-wide limit in addition to the endpoint's IP throttle."""

    def get_identifier(self, request):
        from apps.accounts.models import normalize_phone

        raw_phone = (
            request.data.get("phone")
            or request.query_params.get("phone")
            or ""
        )
        return normalize_phone(str(raw_phone))


class DeviceScopedRateThrottle(_IdentifierRateThrottle):
    """Apply an additional login limit to a client-supplied device identifier."""

    def get_identifier(self, request):
        device_id = (
            request.headers.get("X-Device-ID")
            or request.data.get("device_id")
            or ""
        )
        return str(device_id).strip()[:128]


class LoginPhoneRateThrottle(PhoneScopedRateThrottle):
    scope = "login_phone"


class LoginDeviceRateThrottle(DeviceScopedRateThrottle):
    scope = "login_device"


class RegistrationPhoneRateThrottle(PhoneScopedRateThrottle):
    scope = "registration_phone"


class OTPRequestPhoneRateThrottle(PhoneScopedRateThrottle):
    scope = "otp_request_phone"


class OTPVerifyPhoneRateThrottle(PhoneScopedRateThrottle):
    scope = "otp_verify_phone"


class PasswordResetPhoneRateThrottle(PhoneScopedRateThrottle):
    scope = "password_reset_phone"
