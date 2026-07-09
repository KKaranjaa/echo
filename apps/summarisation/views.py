from django.shortcuts import render, get_object_or_404
from apps.uploads.models import Session


def session_result(request, session_id):
    """Render the full results page for a processed session."""
    session = get_object_or_404(Session, id=session_id)

    transcript = getattr(session, 'transcript', None)
    summary = getattr(session, 'summary', None)

    context = {
        'session': session,
        'transcript': transcript,
        'summary': summary,
    }
    return render(request, 'summarisation/result.html', context)
