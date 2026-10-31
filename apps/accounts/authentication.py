"""
Unified Token/Bearer authentication.
New sessions are independent per device; legacy DRF tokens remain accepted during migration.
"""
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from apps.accounts.session_services import authenticate_api_credential


class BearerOrTokenAuthentication(BaseAuthentication):
    """Authenticate device-session Bearer tokens and legacy Token/Bearer credentials."""

    keyword_map = {b"token", b"bearer"}

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None

        prefix = parts[0].lower()
        if prefix not in self.keyword_map:
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed(
                "ترويسة المصادقة غير صالحة؛ استخدم Bearer أو Token متبوعاً بمفتاح واحد."
            )
        try:
            raw_token = parts[1].decode("utf-8")
        except UnicodeError as exc:
            raise exceptions.AuthenticationFailed("مفتاح المصادقة يحتوي على محارف غير صالحة.") from exc

        authenticated = authenticate_api_credential(raw_token)
        if authenticated is None:
            raise exceptions.AuthenticationFailed("رمز المصادقة غير صالح أو منتهي الصلاحية.")
        user, auth_object = authenticated
        if not user.is_active:
            raise exceptions.AuthenticationFailed("الحساب غير نشط.")
        return user, auth_object
