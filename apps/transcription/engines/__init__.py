"""
Engine factory for ASR backends.

Controlled by the TRANSCRIPTION_BACKEND env var (defaults to 'local'):

  TRANSCRIPTION_BACKEND=local   → faster-whisper running on this machine
  TRANSCRIPTION_BACKEND=groq    → Groq hosted Whisper large-v3 (free API)

Set TRANSCRIPTION_BACKEND=groq on Render and keep 'local' in your .env
for development so you never pay and never run out of minutes.
"""
import os
from django.conf import settings


def get_engine():
    backend = (
        getattr(settings, "TRANSCRIPTION_BACKEND", None)
        or os.environ.get("TRANSCRIPTION_BACKEND", "local")
    ).lower()

    if backend == "groq":
        from .groq import GroqEngine
        return GroqEngine()
    else:
        from .whisper import WhisperEngine
        return WhisperEngine()
