import os
import re
import uuid
import mimetypes
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, StreamingHttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.core.files.storage import FileSystemStorage
from .models import Session
from apps.transcription.tasks import transcribe_session

def file_iterator(file_path, offset=0, length=None, chunk_size=8192):
    with open(file_path, 'rb') as f:
        f.seek(offset)
        remaining = length if length is not None else os.path.getsize(file_path)
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

def serve_media_with_range(request, path):
    """Custom media view that supports HTTP 206 Range requests for seeking audio/video."""
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(file_path):
        raise Http404()

    size = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'

    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)

    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else size - 1
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1

        response = StreamingHttpResponse(
            file_iterator(file_path, offset=first_byte, length=length),
            status=206,
            content_type=content_type
        )
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{size}'
    else:
        response = StreamingHttpResponse(
            file_iterator(file_path),
            content_type=content_type
        )
        response['Content-Length'] = str(size)

    response['Accept-Ranges'] = 'bytes'
    return response

ALLOWED_EXTENSIONS = {
    '.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', 
    '.ogg', '.oga', '.flac', '.mov', '.avi', '.mkv'
}
MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1 GB

@ensure_csrf_cookie
@require_GET
def home(request):
    """Render the main upload page."""
    return render(request, 'uploads/upload_zone.html')


@require_POST
def upload_file(request):
    """Handle multipart/form-data audio/video uploads via HTMX."""
    if 'audio_file' not in request.FILES:
        return HttpResponseBadRequest("No file uploaded.")

    uploaded_file = request.FILES['audio_file']
    
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return HttpResponseBadRequest("File size exceeds 1 GB limit.")

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return HttpResponseBadRequest(f"Unsupported file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}")

    session_id = uuid.uuid4()
    
    # Save file with a safe physical name to avoid Windows MAX_PATH limits
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', str(session_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    fs = FileSystemStorage(location=upload_dir)
    safe_filename = f"original_audio{ext}"
    filename = fs.save(safe_filename, uploaded_file)
    file_path = os.path.join(upload_dir, filename)

    # Create session
    session = Session.objects.create(
        id=session_id,
        original_filename=uploaded_file.name,
        status='uploading'
    )

    # Run the full pipeline (eager/synchronous in dev — blocks until complete)
    transcribe_session.delay(session_id=str(session.id))

    # Reload session to get updated status after eager execution
    session.refresh_from_db()

    # Redirect to results page — HTMX will follow this redirect
    response = redirect('session-result', session_id=str(session.id))
    # Tell HTMX to do a full redirect (not a partial swap)
    response['HX-Redirect'] = f'/results/{session.id}/'
    return response
#add the effect to these sections.
#Ask ECHO
#AI assistant for this session section, summary, keypoints, flashcards holder, action items, ask about this, full transcript.  and ensure uniformity


# ── NEW: External URL ingestion endpoints ────────────────────────────────────
# These are purely additive. The existing upload_file view above is untouched.

@require_POST
def submit_url(request):
    """Accept a pasted media URL and kick off the async fetch pipeline."""
    import json
    from .url_validator import validate_and_identify_url
    from .fetch_task import fetch_external_audio

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    url = (body.get('url') or '').strip()
    title = (body.get('title') or '').strip()

    if not url:
        return JsonResponse({'error': 'Please provide a URL.'}, status=400)

    platform, error = validate_and_identify_url(url)
    if error:
        return JsonResponse({'error': error}, status=400)

    session_id = uuid.uuid4()

    session = Session.objects.create(
        id=session_id,
        original_filename=title or 'url_import',
        status='initiated',
        source_url=url,
        source_platform=platform,
    )

    fetch_external_audio.delay(session_id=str(session.id), url=url)

    return JsonResponse({'session_id': str(session.id)}, status=202)


@require_GET
def session_status(request, session_id):
    """Lightweight polling endpoint used by the Paste Link frontend."""
    try:
        session = Session.objects.get(id=session_id)
    except Session.DoesNotExist:
        return JsonResponse({'error': 'Session not found.'}, status=404)

    payload = {
        'status': session.status,
        'error': session.error_detail or None,
        'platform': session.source_platform or None,
    }
    if session.status == 'complete':
        payload['result_url'] = f'/results/{session.id}/'

    return JsonResponse(payload)