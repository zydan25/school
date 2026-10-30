"""
apps/accounts/authentication.py
Unified Bearer / Token Authentication for Django REST Framework.
Supports Authorization headers starting with either 'Token <key>' or 'Bearer <key>'.
"""
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication, get_authorization_header


class BearerOrTokenAuthentication(TokenAuthentication):
    """
    Accepts both standard Django 'Token <key>' and standard OAuth/mobile 'Bearer <key>'
    in the Authorization header.
    """
    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            return None

        prefix = auth[0].lower().decode("utf-8", errors="ignore")
        if prefix not in ["token", "bearer"]:
            return None

        if len(auth) == 1:
            msg = "رمز المصادقة غير صالح. لم يتم تزويد المفتاح."
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = "رمز المصادقة غير صالح. يجب ألا يحتوي مفتاح الرمز على مسافات."
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode("utf-8")
        except UnicodeError:
            msg = "رمز المصادقة غير صالح. يحتوي الرمز على محارف غير صحيحة."
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(token)
