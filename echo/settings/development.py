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
# Email – console backend during development
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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
