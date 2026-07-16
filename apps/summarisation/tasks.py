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
from .prompts.v1 import build_prompt, build_starter_questions_prompt, PROMPT_VERSION
from .prompts.strict_flags import build_strict_flags_prompt
from .parsers import parse_summary, parse_starter_questions, SummaryParseError
import json

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"  # Free tier, 32k context

def _generate_text_waterfall(prompt, max_tokens, temperature=1.0):
    """
    Attempts to generate text using Groq first, then Anthropic, then Gemini.
    Returns the raw string response. Raises Exception if all fail.
    """
    # 1. TRY GROQ
    groq_api_key = os.environ.get('GROQ_API_KEY')
    if groq_api_key:
        client = Groq(api_key=groq_api_key)
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Groq API failed: {e}. Falling back to Anthropic...")

    # 2. FALLBACK TO ANTHROPIC
    anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
    if anthropic_api_key:
        try:
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.warning(f"Anthropic API failed: {e}. Falling back to Gemini...")

    # 3. FALLBACK TO GEMINI
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if gemini_api_key:
        try:
            client = genai.Client(api_key=gemini_api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=dict(temperature=temperature)
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini API failed: {e}.")

    raise RuntimeError("All AI providers failed or no API keys configured.")


@shared_task
def summarise_session(session_id):
    try:
        session = Session.objects.get(id=session_id)
        transcript = Transcript.objects.get(session=session)
        
        import concurrent.futures
        
        def generate_summary():
            current_prompt = build_prompt(transcript.raw_text, session.detected_language)
            max_attempts = 2
            
            for attempt in range(max_attempts):
                try:
                    raw_response = _generate_text_waterfall(current_prompt, max_tokens=2000)
                    return parse_summary(raw_response)
                except SummaryParseError:
                    if attempt == max_attempts - 1:
                        return {
                            "key_points": [],
                            "exam_flags": [],
                            "action_items": [],
                            "flashcards": [],
                            "summary_paragraph": raw_response if 'raw_response' in locals() else "Failed to parse summary."
                        }
                    else:
                        current_prompt += "\n\nYou returned invalid JSON. Return ONLY the JSON object. No text before or after."
            return None

        def generate_sq():
            sq_prompt = build_starter_questions_prompt(transcript.raw_text)
            try:
                raw_response = _generate_text_waterfall(sq_prompt, max_tokens=300)
                return parse_starter_questions(raw_response)
            except Exception as e:
                logger.error(f"Failed to generate starter questions: {e}")
                return []

                
        def generate_strict_exam_flags():
            flags_prompt = build_strict_flags_prompt(transcript.raw_text)
            try:
                raw_response = _generate_text_waterfall(flags_prompt, max_tokens=1500, temperature=0.0)
                
                # Try parsing JSON safely
                import re
                json_str = raw_response
                # Clean up if markdown fences were added despite instructions
                if "```" in raw_response:
                    m = re.search(r'```(?:json)?(.*?)```', raw_response, re.DOTALL)
                    if m:
                        json_str = m.group(1)
                        
                flags = json.loads(json_str.strip())
                if not isinstance(flags, list):
                    return []
                    
                # Post-process to find approximate timestamps via substring search
                raw_lower = transcript.raw_text.lower()
                total_chars = len(raw_lower)
                duration = getattr(session, 'duration_seconds', 0)
                
                for flag in flags:
                    quote = flag.get('quote', '')
                    if quote and total_chars > 0 and duration > 0:
                        idx = raw_lower.find(quote.lower()[:50]) # match first 50 chars to be safe against slight LLM changes
                        if idx != -1:
                            # approximate timestamp assuming uniform speaking rate
                            timestamp_seconds = int((idx / total_chars) * duration)
                            flag['timestamp'] = timestamp_seconds
                return flags
            except Exception as e:
                logger.error(f"Failed to generate strict exam flags: {e}")
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            summary_future = executor.submit(generate_summary)
            sq_future = executor.submit(generate_sq)
            flags_future = executor.submit(generate_strict_exam_flags)
            
            summary_data = summary_future.result()
            starter_questions = sq_future.result()
            strict_exam_flags = flags_future.result()
            
        if not summary_data:
            summary_data = {}
            
        # 3. Save Summary to DB
        Summary.objects.create(
            session=session,
            key_points=summary_data.get('key_points', []),
            exam_flags=summary_data.get('exam_flags', []),
            action_items=summary_data.get('action_items', []),
            flashcards=summary_data.get('flashcards', []),
            summary_paragraph=summary_data.get('summary_paragraph', ''),
            prompt_version=PROMPT_VERSION,
            starter_questions=starter_questions,
            strict_exam_flags=strict_exam_flags
        )
        
        # 4. Update session status
        session.status = 'complete'
        session.save()
        
    except Exception as e:
        logger.exception(f"Summarisation failed for session {session_id}")
        session = Session.objects.get(id=session_id)
        session.status = 'failed'
        session.save()
