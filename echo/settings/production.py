"""
Production settings – PostgreSQL, Redis, strict security.
"""
import os
import dj_database_url  # type: ignore

from .base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-for-build")

ALLOWED_HOSTS = [os.environ.get("RENDER_EXTERNAL_HOSTNAME", "localhost")]
CSRF_TRUSTED_ORIGINS = [f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}"]

# ---------------------------------------------------------------------------
# Database – PostgreSQL via DATABASE_URL
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ---------------------------------------------------------------------------
# Cache & Celery – Redis
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-sessions': {
        'task': 'apps.uploads.tasks.cleanup_expired_sessions',
        'schedule': crontab(minute=0),  # every hour
    },
}

# ---------------------------------------------------------------------------
# Media & Static
# ---------------------------------------------------------------------------
MEDIA_ROOT = '/var/data/media'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_HOST_USER")