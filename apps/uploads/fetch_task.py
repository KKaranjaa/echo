"""
Celery task for fetching external media via yt-dlp and handing it off
to the existing transcription pipeline.

yt-dlp is imported INSIDE this module only, so a missing installation
cannot prevent Django startup or the direct upload feature from working.
"""
import os
import uuid
import logging
import tempfile
import shutil

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Limits (sourced from the authoritative locations) ────────────────────────
# Size limit: imported from uploads.views (single source of truth)
from apps.uploads.views import MAX_UPLOAD_SIZE  # 1 GB

# Duration limit: same value used in transcription/tasks.py line 35
MAX_DURATION_SECONDS = 12000  # 200 minutes

# ── Output format ────────────────────────────────────────────────────────────
# Media is downloaded in its best original format (video/audio).


def _set_failed(session, message):
    """Helper: mark session as failed with a human-readable message."""
    session.status = 'failed'
    session.error_detail = message
    session.save()


@shared_task(bind=True, max_retries=0)
def fetch_external_audio(self, session_id, url):
    """
    Stage 1: fetch metadata → validate limits
    Stage 2: download audio → save to pipeline storage path
    Stage 3: trigger transcribe_session (existing pipeline, unchanged)
    """
    from apps.uploads.models import Session

    try:
        session = Session.objects.get(id=session_id)
    except Session.DoesNotExist:
        logger.error(f"fetch_external_audio: session {session_id} not found")
        return

    try:
        _run_fetch(session, url)
    except Exception as exc:
        logger.exception(f"Unhandled error in fetch_external_audio for session {session_id}")
        try:
            session.refresh_from_db()
            if session.status not in ('failed', 'complete'):
                _set_failed(session, "Something went wrong while fetching this link. Please try again or upload the file directly.")
        except Exception:
            pass


def _is_direct_url(url):
    """Return True if the URL is a direct media file link (no yt-dlp extraction needed)."""
    from apps.uploads.url_validator import DIRECT_MEDIA_EXTENSIONS
    from urllib.parse import urlparse
    path = urlparse(url).path.lower()
    ext = '.' + path.rsplit('.', 1)[-1] if '.' in path else ''
    return ext in DIRECT_MEDIA_EXTENSIONS


def _run_fetch(session, url):
    from apps.uploads.models import Session
    from apps.transcription.tasks import transcribe_session

    # ── STAGE 1: Metadata ────────────────────────────────────────────────────
    session.status = 'fetching_metadata'
    session.save()

    is_direct = _is_direct_url(url)

    if is_direct:
        # For direct file URLs, use a HEAD request to get Content-Length
        import requests
        try:
            resp = requests.head(url, allow_redirects=True, timeout=15)
            content_length = int(resp.headers.get('Content-Length', 0))
            if content_length and content_length > MAX_UPLOAD_SIZE:
                size_gb = content_length / (1024 ** 3)
                _set_failed(session, f"This file is {size_gb:.1f} GB, which exceeds the 1 GB limit.")
                return
            # Can't determine duration from a HEAD request for direct links.
            # Duration will be validated by the transcription pipeline.
            if not session.original_filename or session.original_filename == 'url_import':
                from urllib.parse import urlparse
                fname = urlparse(url).path.split('/')[-1] or 'audio'
                session.original_filename = fname
                session.save()
        except requests.RequestException as e:
            logger.exception(f"Direct download HEAD request failed for {url}")
            _set_failed(session, "Could not reach the file URL. Please check it is publicly accessible.")
            return
    else:
        # Use yt-dlp to fetch metadata without downloading
        import yt_dlp

        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'color': 'no_color',
            'socket_timeout': 120,       # seconds before connection attempt times out
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            err_str = str(e).lower()
            if 'private' in err_str or 'sign in' in err_str or 'login' in err_str:
                _set_failed(session, "This video is private or requires sign-in. Please use a publicly accessible link.")
            elif 'unavailable' in err_str or 'removed' in err_str or 'deleted' in err_str:
                _set_failed(session, "This video has been removed or is no longer available.")
            elif 'not available' in err_str and 'region' in err_str:
                _set_failed(session, "This video is not available in the server's region.")
            elif 'age' in err_str:
                _set_failed(session, "This video is age-restricted and cannot be downloaded without sign-in.")
            else:
                logger.error("yt-dlp DownloadError (metadata stage): %s", str(e), exc_info=True)
                _set_failed(session, "Could not access this video — check that it is publicly available.")
            return
        except Exception as e:
            logger.exception("Unhandled error reading video information with yt-dlp")
            _set_failed(session, "Could not read video information.")
            return

        # Duration check
        duration = info.get('duration')
        if duration and duration > MAX_DURATION_SECONDS:
            mins = int(duration // 60)
            _set_failed(session, f"This video is {mins} minutes long, which exceeds the 200-minute limit. Please use a shorter recording.")
            return

        # Estimated file size check (if available)
        filesize_approx = info.get('filesize') or info.get('filesize_approx')
        if filesize_approx and filesize_approx > MAX_UPLOAD_SIZE:
            size_gb = filesize_approx / (1024 ** 3)
            _set_failed(session, f"The estimated audio size ({size_gb:.1f} GB) exceeds the 1 GB limit.")
            return

        # Populate title if user didn't provide one
        if not session.original_filename or session.original_filename == 'url_import':
            title = info.get('title') or info.get('id') or 'video'
            session.original_filename = title
        
        session.save()

    # ── STAGE 2: Download ────────────────────────────────────────────────────
    session.status = 'downloading'
    session.save()

    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', str(session.id))
    os.makedirs(upload_dir, exist_ok=True)
    tmp_dir = tempfile.mkdtemp()
    downloaded_ext = '.mp3'
    try:
        if is_direct:
            downloaded_ext = _download_direct(url, tmp_dir, upload_dir, session)
        else:
            downloaded_ext = _download_yt_dlp(url, tmp_dir, upload_dir, session)
        
        if session.status == 'failed':
            return  # download helper set failure; bail out

    except Exception as e:
        logger.exception("Download failed")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        _set_failed(session, "Download failed.")
        return
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Ensure original_filename has the correct extension for the pipeline
    base_name = os.path.splitext(session.original_filename or 'media')[0]
    session.original_filename = f"{base_name}{downloaded_ext}"
    session.save()

    # ── STAGE 3: Hand off to existing pipeline (unchanged) ───────────────────
    transcribe_session.delay(session_id=str(session.id))


def _download_direct(url, tmp_dir, upload_dir, session):
    """Stream-download a direct media URL using requests."""
    import requests
    from urllib.parse import urlparse

    ext = os.path.splitext(urlparse(url).path)[1].lower() or '.mp3'
    tmp_file = os.path.join(tmp_dir, f'download{ext}')
    try:
        with requests.get(url, stream=True, timeout=(30, 300)) as r:
            r.raise_for_status()
            written = 0
            with open(tmp_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    written += len(chunk)
                    if written > MAX_UPLOAD_SIZE:
                        _set_failed(session, "The file exceeds the 1 GB size limit.")
                        return ext
        
        final_path = os.path.join(upload_dir, f'original_audio{ext}')
        shutil.move(tmp_file, final_path)
    except requests.HTTPError as e:
        logger.error("HTTP error downloading file: %s", str(e), exc_info=True)
        _set_failed(session, "Could not download file. Please check the URL is publicly accessible.")
    except requests.RequestException as e:
        logger.error("Network error downloading file: %s", str(e), exc_info=True)
        _set_failed(session, "Network error during download.")
        
    return ext


def _download_yt_dlp(url, tmp_dir, upload_dir, session):
    """Download media via yt-dlp."""
    import yt_dlp

    # yt-dlp writes to tmp_dir, then we move the result to upload_dir
    tmp_output_template = os.path.join(tmp_dir, 'media.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio/best',      # prefer audio-only — much smaller than video+audio
        'outtmpl': tmp_output_template,
        'quiet': True,
        'no_warnings': True,
        'color': 'no_color',
        'socket_timeout': 120,           # seconds before a connection attempt times out
        'retries': 10,                   # retry the full download up to 10 times
        'fragment_retries': 10,          # retry individual timed-out chunks up to 10 times
        'buffersize': 1024 * 256,        # 256 KB read buffer (helps on slow connections)
        'http_chunk_size': 1024 * 1024,  # request 1 MB chunks at a time
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
    }

    ext = '.mp4'  # Fallback
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        logger.error("yt-dlp DownloadError (download stage): %s", str(e), exc_info=True)
        _set_failed(session, "Media download failed.")
        return ext

    # Find the output file and determine its actual extension
    downloaded = None
    for fname in os.listdir(tmp_dir):
        if fname.startswith('media.'):
            downloaded = os.path.join(tmp_dir, fname)
            ext = os.path.splitext(fname)[1]
            break

    if not downloaded or not os.path.exists(downloaded):
        _set_failed(session, "Download completed but the file could not be located. Please try again.")
        return ext

    # Final size check (in case estimate was unavailable at metadata stage)
    actual_size = os.path.getsize(downloaded)
    if actual_size > MAX_UPLOAD_SIZE:
        size_gb = actual_size / (1024 ** 3)
        os.remove(downloaded)
        _set_failed(session, f"The downloaded file ({size_gb:.1f} GB) exceeds the 1 GB limit.")
        return ext

    final_path = os.path.join(upload_dir, f'original_audio{ext}')
    shutil.move(downloaded, final_path)
    return ext
