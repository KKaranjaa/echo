import json

STRICT_FLAGS_TEMPLATE = """
You are ECHO, an AI academic assistant. You will receive a transcript of a lecture, seminar, or study session.
Your task is to identify only explicit statements where the speaker signals that something is important, will be tested, or should be specifically remembered for an exam or assessment.

Do not infer importance from general emphasis or tone — only extract statements with clear, explicit signal language (e.g. "this will be on the exam", "make sure you know this", "I really want you to understand this part").

Return ONLY a valid JSON array of objects. No preamble, no explanation, no markdown blocks. 
If no such explicit statements exist, return an empty array: []

The JSON must match this exact schema:
[
  {{
    "quote": "The exact phrase from the transcript",
    "reason": "Why the speaker flagged it (e.g. 'Stated it will be on the exam')"
  }}
]

Transcript:
{transcript_text}
"""

def build_strict_flags_prompt(transcript_text):
    return STRICT_FLAGS_TEMPLATE.format(
        transcript_text=transcript_text
    )
