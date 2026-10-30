"""Production settings. All secrets and hosts must come from the environment."""
import os
from .base import *  # noqa: F403

DEBUG = False
if SECRET_KEY == "unsafe-development-key-change-before-deploy":  # noqa: F405
    raise RuntimeError("SECRET_KEY must be configured in production")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("ALLOWED_HOSTS must contain explicit production hosts")

SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if v.strip()]
