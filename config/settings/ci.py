"""CI settings using PostgreSQL service and fast password hashing."""
import os

import dj_database_url

from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", "postgresql://school:school@127.0.0.1:5432/school"),
        conn_max_age=0,
        conn_health_checks=True,
    )
}
