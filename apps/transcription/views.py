import json
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from apps.transcription.models import Transcript

@csrf_exempt
@require_http_methods(["POST"])
def edit_transcript_segment(request, session_id, segment_idx):
    try:
        transcript = Transcript.objects.get(session__id=session_id)
        
        if not (0 <= segment_idx < len(transcript.word_timestamps)):
            return HttpResponseBadRequest("Invalid segment index")

        segment = transcript.word_timestamps[segment_idx]
        
        # Check if reverting
        if request.POST.get('action') == 'revert':
            if segment.get('is_edited'):
                segment['word'] = segment.get('original_text', segment['word'])
                segment['is_edited'] = False
                # Keep original_text in case we need it, or delete it
        else:
            new_text = request.POST.get('text', '').strip()
            
            if not segment.get('is_edited'):
                segment['original_text'] = segment['word']
            
            segment['word'] = new_text
            segment['is_edited'] = True

        transcript.has_edits = True
        transcript.save(update_fields=['word_timestamps', 'has_edits'])

        # Render the updated segment HTML for HTMX to swap
        html = render_to_string('sessions/partials/_transcript_word.html', {
            'word': segment,
            'index': segment_idx,
            'session': transcript.session
        })
        return HttpResponse(html)

    except Transcript.DoesNotExist:
        return HttpResponseBadRequest("Transcript not found")
    except Exception as e:
        return HttpResponseBadRequest(str(e))
