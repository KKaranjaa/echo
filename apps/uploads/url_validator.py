"""
Structural URL validator for ECHO's external link ingestion.
No network requests are made here — this is purely pattern-based.
"""
import re
from urllib.parse import urlparse, parse_qs


# Audio/video file extensions we treat as direct downloads (no yt-dlp extraction needed)
DIRECT_MEDIA_EXTENSIONS = {
    '.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.webm',
    '.flac', '.opus', '.mkv', '.mov', '.avi',
}


def validate_and_identify_url(url):
    """
    Structurally validate and identify a media URL.

    Returns:
        (platform_label: str, error: str | None)

    On success: (platform_label, None)
    On failure: (None, human-readable error message)
    """
    url = url.strip()

    # 1. Basic URL structure check
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None, "URL must start with http:// or https://. Please paste a valid link."
        if not parsed.netloc:
            return None, "That doesn't look like a valid URL. Please paste a full link including http:// or https://."
    except Exception:
        return None, "That doesn't look like a valid URL. Please paste a full link."

    host = parsed.netloc.lower().lstrip('www.')
    path = parsed.path.lower()
    qs   = parse_qs(parsed.query)

    # ── YOUTUBE ──────────────────────────────────────────────────────────────
    YT_HOSTS = {'youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com'}
    if host in YT_HOSTS:
        # Reject playlists
        if 'list' in qs and 'v' not in qs:
            return None, "Playlists are not supported — please paste a link to a single video."
        # Accept watch, shorts, live, youtu.be short links
        if (
            '/watch' in path
            or host == 'youtu.be'
            or '/shorts/' in path
            or '/live/' in path
            or 'v' in qs
        ):
            return 'YouTube', None
        # Reject channel pages, playlists etc.
        return None, "That YouTube link doesn't point to a single video. Please use a direct video link."

    # ── GOOGLE DRIVE ─────────────────────────────────────────────────────────
    # Note: only works if the file is set to "Anyone with the link can view".
    # Private files will fail at download time with a 403 error.
    if host in ('drive.google.com',):
        if '/file/d/' in path or 'id' in qs:
            return 'Google Drive', None
        return None, "Please paste a direct Google Drive file link (drive.google.com/file/d/...)."

    # ── DROPBOX ──────────────────────────────────────────────────────────────
    # yt-dlp handles direct Dropbox file downloads but not Dropbox folders.
    if host in ('dropbox.com', 'www.dropbox.com'):
        if path.startswith('/s/') or '/scl/' in path:
            # Reject folder links
            if path.endswith('/') and not re.search(r'\.\w{2,5}$', path.rstrip('/')):
                return None, "Dropbox folder links are not supported — please paste a link to a single file."
            return 'Dropbox', None
        return None, "Please paste a direct Dropbox shared file link."

    # ── VIMEO ────────────────────────────────────────────────────────────────
    # Note: password-protected Vimeo videos will fail at download time.
    if host in ('vimeo.com', 'player.vimeo.com'):
        if re.search(r'/video/\d+', path) or re.search(r'/\d+', path):
            return 'Vimeo', None
        return None, "Please paste a direct Vimeo video link (vimeo.com/<id>)."

    # ── TWITTER / X ──────────────────────────────────────────────────────────
    if host in ('twitter.com', 'x.com', 't.co'):
        return 'Twitter/X', None

    # ── FACEBOOK ─────────────────────────────────────────────────────────────
    if host in ('facebook.com', 'fb.com', 'fb.watch', 'www.facebook.com'):
        return 'Facebook', None

    # ── INSTAGRAM ────────────────────────────────────────────────────────────
    if host in ('instagram.com', 'www.instagram.com'):
        return 'Instagram', None

    # ── TIKTOK ───────────────────────────────────────────────────────────────
    if host in ('tiktok.com', 'www.tiktok.com', 'vm.tiktok.com'):
        return 'TikTok', None

    # ── DIRECT FILE LINK ─────────────────────────────────────────────────────
    path_no_qs = parsed.path.lower()
    ext = '.' + path_no_qs.rsplit('.', 1)[-1] if '.' in path_no_qs else ''
    if ext in DIRECT_MEDIA_EXTENSIONS:
        return 'Direct link', None

    # ── GENERIC YT-DLP PASS-THROUGH ──────────────────────────────────────────
    # yt-dlp supports thousands of platforms. We pass everything else through
    # and let the Celery task surface any errors at download time.
    return 'External link', None
