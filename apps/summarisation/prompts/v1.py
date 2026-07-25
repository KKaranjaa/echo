PROMPT_VERSION = 'v1.0'

TEMPLATE = """
You are ECHO, an AI academic assistant. You will receive a transcript of a
lecture, seminar, or study session. Your task is to extract structured
academic intelligence from it.

Return ONLY a valid JSON object — no preamble, no markdown code fences,
no explanation. The JSON must match this exact schema:

{{
  "key_points":   ["string — max 20 words each"],
  "exam_flags":   [{{"phrase": "string", "context": "string", "reason": "string"}}],
  "action_items": [{{"text": "string", "assignee_hint": "string or null"}}],
  "flashcards":   [{{"question": "string", "answer": "string — max 40 words"}}],
  "summary_paragraph": "string — 3-5 sentence prose overview"
}}

Rules:
- key_points: 5-10 bullets, each under 20 words
- exam_flags: mark phrases introduced by 'this will be on the exam',
  'remember', 'importantly', 'key concept', 'note that'
- flashcards: maximum 15 pairs — quality over quantity
- Output in the same language as the transcript
- If content is too sparse, return empty arrays — do not fabricate

Transcript language: {detected_language}
Transcript:
{transcript_text}
"""

STARTER_QUESTIONS_TEMPLATE = """
Based on the following session transcript, generate exactly 3 short questions
a student might want to ask about this lecture or meeting.
Return ONLY a JSON array of 3 strings. No other text.
Questions should be specific to this content — not generic.

Transcript:
{transcript_text}
"""

def build_prompt(transcript_text, detected_language):
    return TEMPLATE.format(
        transcript_text=transcript_text,
        detected_language=detected_language
    )

def build_starter_questions_prompt(transcript_text):
    return STARTER_QUESTIONS_TEMPLATE.format(
        transcript_text=transcript_text
    )
