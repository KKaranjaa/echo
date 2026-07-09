import json
from pathlib import Path
from django.http import HttpResponse, FileResponse, HttpResponseNotFound
from django.conf import settings

# ── Static asset helper ───────────────────────────────────────────────────────
_STATIC_CORE = Path(__file__).resolve().parent / "static" / "core"


from django.db import OperationalError
from django.core.cache import cache
from apps.uploads.models import Session

def health_check(request):
    """GET /health/ returns JSON: {status: 'ok', db: 'ok', redis: 'ok', version: '1.0.0'}"""
    db_status = 'ok'
    redis_status = 'ok'
    status_code = 200

    try:
        Session.objects.exists()
    except OperationalError:
        db_status = 'error'
        status_code = 503
    except Exception:
        db_status = 'error'
        status_code = 503

    try:
        cache.set('health_ping', 'pong', timeout=5)
        if cache.get('health_ping') != 'pong':
            redis_status = 'error'
            status_code = 503
    except Exception:
        redis_status = 'error'
        status_code = 503

    overall_status = 'ok' if status_code == 200 else 'error'

    payload = json.dumps({
        "status": overall_status,
        "db": db_status,
        "redis": redis_status,
        "version": "1.0.0"
    })
    return HttpResponse(payload, content_type="application/json", status=status_code)


def manifest(request):
    """GET /manifest.json → PWA web app manifest"""
    manifest_path = _STATIC_CORE / "manifest.json"
    return FileResponse(
        open(manifest_path, "rb"),
        content_type="application/manifest+json",
    )


def favicon_svg(request):
    """GET /favicon.ico → serve the SVG favicon with correct MIME type.

    Browsers that support SVG favicons (Chrome 80+, Firefox, Safari 14+) will
    render the vector at any resolution.  The path /favicon.ico is kept for
    compatibility; the Content-Type overrides the .ico assumption.
    """
    svg_path = _STATIC_CORE / "favicon.svg"
    return FileResponse(
        open(svg_path, "rb"),
        content_type="image/svg+xml",
    )


def favicon_32(request):
    """Fallback raster favicon."""
    path = Path(settings.STATIC_ROOT) / "core/img/favicon-32x32.png"
    if not path.exists():
        return HttpResponseNotFound()
    return FileResponse(open(path, "rb"), content_type="image/png")

from django.shortcuts import redirect

def confirm_email_manual(request):
    if request.method == 'POST':
        key = request.POST.get('key', '').strip()
        if key:
            # Redirect to allauth's built-in confirm view
            return redirect('account_confirm_email', key=key)
    # If GET or no key, just redirect to login
    return redirect('account_login')
