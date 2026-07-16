import os
import logging
from django.conf import settings
from .base import BaseASREngine

logger = logging.getLogger(__name__)

# Groq's file size limit for the Whisper API endpoint
GROQ_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


class GroqEngine(BaseASREngine):
    """
    Transcription engine backed by Groq's hosted Whisper large-v3.

    Groq free tier: 7,200 audio minutes / day — essentially inexhaustible
    for normal use and perfect for Render deployments where local Whisper
    would require several GB of RAM.

    Docs: https://console.groq.com/docs/speech-text
    """

    def __init__(self):
        from groq import Groq  # lazy import so the package is optional

        api_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file or "
                "environment variables."
            )
        # Increase timeout drastically (e.g. 5 minutes) to handle large 20MB chunk uploads
        # on slower network connections without timing out during the SSL handshake or upload.
        self.client = Groq(api_key=api_key, timeout=300.0)

    def _get_api_keys(self):
        keys = []
        primary = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY")
        if primary:
            keys.append(primary)
        i = 2
        while True:
            backup = os.environ.get(f"GROQ_API_KEY_{i}")
            if backup:
                keys.append(backup)
                i += 1
            else:
                break
        return keys

    def transcribe(self, audio_path: str) -> dict:
        """
        Send the audio file to Groq's Whisper large-v3 endpoint.
        Rotates through backup API keys (e.g. GROQ_API_KEY_2) if one fails.
        """
        file_size = os.path.getsize(audio_path)
        if file_size > GROQ_MAX_FILE_BYTES:
            raise ValueError(
                f"Audio chunk {audio_path} is {file_size / 1e6:.1f} MB, "
                f"which exceeds Groq's 25 MB per-request limit. "
                f"Reduce chunk_min in tasks.py or re-encode to a lower bitrate."
            )

        import time
        from groq import Groq
        
        api_keys = self._get_api_keys()
        if not api_keys:
            raise RuntimeError("No GROQ_API_KEY configured.")
            
        transcription = None
        last_exception = None
        
        for api_key in api_keys:
            client = Groq(api_key=api_key, timeout=300.0)
            max_attempts = 4
            success = False
            
            for attempt in range(max_attempts):
                try:
                    with open(audio_path, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            file=(os.path.basename(audio_path), audio_file),
                            model="whisper-large-v3",
                            response_format="verbose_json",
                            timestamp_granularities=["word"],
                        )
                    success = True
                    break  # Success
                except Exception as e:
                    last_exception = e
                    # If it's a rate limit or auth error, don't wait for 4 attempts, just jump to the next key
                    if "429" in str(e) or "401" in str(e):
                        logger.warning(f"Groq API error on {audio_path} with key (ending in ...{api_key[-4:]}): {e}. Rotating to next API key...")
                        break 
                    
                    if attempt == max_attempts - 1:
                        logger.warning(f"Groq API error on {audio_path} with key (ending in ...{api_key[-4:]}) after {max_attempts} attempts: {e}. Rotating to next API key...")
                        break
                        
                    logger.warning(f"Groq API error on {audio_path} (attempt {attempt + 1}/{max_attempts}): {e}. Retrying same key in 5 seconds...")
                    time.sleep(5)
            
            if success:
                break
                
        if not transcription:
            raise RuntimeError(f"All Groq API keys failed. Last error: {last_exception}")

        # Parse word-level timestamps from Groq's response.
        # Groq may return words as plain dicts or as objects depending on SDK version.
        words_list = []
        if hasattr(transcription, "words") and transcription.words:
            for w in transcription.words:
                if isinstance(w, dict):
                    words_list.append({
                        "word": w.get("word", ""),
                        "start": float(w.get("start", 0)),
                        "end": float(w.get("end", 0)),
                    })
                else:
                    words_list.append({
                        "word": w.word,
                        "start": float(w.start),
                        "end": float(w.end),
                    })

        return {
            "text": transcription.text.strip(),
            "word_timestamps": words_list,
            "language": getattr(transcription, "language", "en"),
        }
