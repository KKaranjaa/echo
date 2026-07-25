import os
import logging
from django.conf import settings
from celery import shared_task
import anthropic
from google import genai
from groq import Groq
from apps.uploads.models import Session
from apps.transcription.models import Transcript
from .models import Summary
from .prompts.v2 import build_prompt, PROMPT_VERSION
from .parsers import parse_summary, SummaryParseError
import json
import re

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"  # Free tier: 200k TPM, 131k context

def _get_api_keys(prefix):
    keys = []
    primary = os.environ.get(prefix)
    if primary:
        keys.append(primary)
    i = 2
    while True:
        backup = os.environ.get(f"{prefix}_{i}")
        if backup:
            keys.append(backup)
            i += 1
        else:
            break
    return keys

def _generate_text_waterfall(prompt, max_tokens, temperature=1.0):
    """
    Attempts to generate JSON text using Groq first, then Anthropic, then Gemini.
    """
    # 1. TRY GROQ
    for api_key in _get_api_keys('GROQ_API_KEY'):
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Groq API failed with key: {e}. Trying next...")
            continue
            
    logger.warning("All Groq keys failed. Falling back to Anthropic...")

    # 2. FALLBACK TO ANTHROPIC
    for api_key in _get_api_keys('ANTHROPIC_API_KEY'):
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"} # prefill to force JSON
                ]
            )
            return "{" + response.content[0].text
        except Exception as e:
            logger.warning(f"Anthropic API failed with key: {e}. Trying next...")
            continue

    logger.warning("All Anthropic keys failed. Falling back to Gemini...")

    # 3. FALLBACK TO GEMINI
    for api_key in _get_api_keys('GEMINI_API_KEY'):
        try:
            from google.genai import types
            client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini API failed with key: {e}. Trying next...")
            continue

    raise RuntimeError("All AI providers and backup keys failed or no API keys configured.")


@shared_task
def summarise_session(session_id):
    try:
        session = Session.objects.get(id=session_id)
        transcript = Transcript.objects.get(session=session)
        
        current_prompt = build_prompt(transcript.raw_text, session.detected_language)
        max_attempts = 2
        summary_data = None
        
        for attempt in range(max_attempts):
            try:
                # 6000 max tokens to accommodate all 6 fields in a single JSON
                raw_response = _generate_text_waterfall(current_prompt, max_tokens=6000)
                summary_data = parse_summary(raw_response)
                break
            except SummaryParseError:
                if attempt == max_attempts - 1:
                    logger.error(f"Failed to parse consolidated JSON for session {session_id}")
                    summary_data = {}
                else:
                    current_prompt += "\n\nYou returned invalid JSON. Return ONLY the JSON object. No text before or after."

        if not summary_data:
            summary_data = {}
            
        # Post-process strict flags to find approximate timestamps via substring search
        strict_flags = summary_data.get('strict_exam_flags', [])
        if isinstance(strict_flags, list):
            raw_lower = transcript.raw_text.lower()
            total_chars = len(raw_lower)
            duration = getattr(session, 'duration_seconds', 0)
            
            for flag in strict_flags:
                quote = flag.get('quote', '')
                if quote and total_chars > 0 and duration > 0:
                    idx = raw_lower.find(quote.lower()[:50])
                    if idx != -1:
                        timestamp_seconds = int((idx / total_chars) * duration)
                        flag['timestamp'] = timestamp_seconds
                        
        # Save Summary to DB
        Summary.objects.create(
            session=session,
            key_points=summary_data.get('key_points', []),
            exam_flags=summary_data.get('exam_flags', []),
            action_items=summary_data.get('action_items', []),
            flashcards=summary_data.get('flashcards', []),
            summary_paragraph=summary_data.get('summary_paragraph', ''),
            prompt_version=PROMPT_VERSION,
            starter_questions=summary_data.get('starter_questions', []),
            strict_exam_flags=strict_flags
        )
        
        session.status = 'complete'
        session.save()
        
    except Exception as e:
        logger.exception(f"Summarisation failed for session {session_id}")
        session = Session.objects.get(id=session_id)
        session.status = 'failed'
        session.save()
