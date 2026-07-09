"""
Root URL configuration for the echo project.
"""
from django.contrib import admin
from django.urls import path, include
from apps.core.views import health_check, manifest, favicon_svg, favicon_32

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # ── Core: health check ────────────────────────────────────────────────────
    path("health/", include("apps.core.urls")),

    # ── PWA / browser integration ─────────────────────────────────────────────
    # /manifest.json — served with application/manifest+json
    path("manifest.json", manifest, name="manifest"),

    # /favicon.ico — SVG lettermark (Chrome 80+, Firefox, Safari 14+)
    path("favicon.ico", favicon_svg, name="favicon-ico"),

    # /favicon-32x32.png — raster fallback for older tooling / meta tags
    path("favicon-32x32.png", favicon_32, name="favicon-png"),

    # ── Uploads ───────────────────────────────────────────────────────────────
    path("", include("apps.uploads.urls")),

    # ── Chat ──────────────────────────────────────────────────────────────────
    path("chat/", include("apps.chat.urls")),

    # ── Transcription API ─────────────────────────────────────────────────────
    path("api/sessions/", include("apps.transcription.urls")),
]

from django.conf import settings
from apps.uploads.views import serve_media_with_range
from django.urls import re_path

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media_with_range),
    ]
