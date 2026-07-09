"""
Development settings – SQLite, DEBUG on, relaxed security.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Database – SQLite for local iteration without Docker
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# ---------------------------------------------------------------------------
# Email — SMTP via Gmail (using .env credentials)
# ---------------------------------------------------------------------------
import os
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = f'ECHO <{EMAIL_HOST_USER}>'

# ---------------------------------------------------------------------------
# Celery - Eager Mode (Bypass Redis locally)
# ---------------------------------------------------------------------------
# This runs tasks immediately instead of sending them to a background queue.
# It means the web browser will "spin" for a few seconds during upload,
# but it completely removes the need to install Redis on Windows!
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_STORE_EAGER_RESULT = False
CELERY_RESULT_BACKEND = None
# Use in-memory transport so Celery never tries to connect to Redis locally
CELERY_BROKER_URL = 'memory://'
CELERY_BROKER_TRANSPORT_OPTIONS = {'max_retries': 1}
