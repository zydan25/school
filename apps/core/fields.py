"""Authenticated encryption for credentials stored in database text fields."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class EncryptedTextField(models.TextField):
    """Fernet-encrypted text field with a version marker and legacy plaintext reads."""

    marker = "enc:v1:"

    def _fernet(self):
        secret = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or settings.SECRET_KEY
        if not secret or secret == "unsafe-development-key-change-before-deploy":
            raise ImproperlyConfigured("Set FIELD_ENCRYPTION_KEY or a strong SECRET_KEY before storing credentials.")
        key = base64.urlsafe_b64encode(hashlib.sha256(("school-field-encryption:" + secret).encode()).digest())
        return Fernet(key)

    def _decrypt(self, value):
        if value is None or not isinstance(value, str) or not value.startswith(self.marker):
            return value
        try:
            token = value[len(self.marker):].encode("ascii")
            return self._fernet().decrypt(token).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
            raise ImproperlyConfigured("A stored credential cannot be decrypted; verify FIELD_ENCRYPTION_KEY.") from exc

    def from_db_value(self, value, expression, connection):
        return self._decrypt(value)

    def to_python(self, value):
        return self._decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, "") or (isinstance(value, str) and value.startswith(self.marker)):
            return value
        token = self._fernet().encrypt(str(value).encode("utf-8")).decode("ascii")
        return self.marker + token
