from django.urls import path
from . import views
from .views import health_check, confirm_email_manual

# Mounted at /health/ from root urls.py; manifest + favicon mounted at root.
# See echo/urls.py for top-level wiring.
urlpatterns = [
    path('', health_check, name='health_check'),
    path('confirm-email-manual/', confirm_email_manual, name='confirm_email_manual'),
]

# ── Standalone routes (registered in echo/urls.py directly) ──────────────────
# /manifest.json, /favicon.ico, /favicon-32x32.png
# Kept here as named imports for the root URLconf to reference.
manifest_view   = views.manifest
favicon_ico     = views.favicon_svg
favicon_png     = views.favicon_32
