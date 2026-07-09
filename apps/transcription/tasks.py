import os
import logging
from django.conf import settings
from celery import shared_task
from apps.uploads.models import Session
from .models import Transcript
from .preprocessor import extract_audio, apply_vad, get_duration, chunk_audio
from .engines import get_engine

logger = logging.getLogger(__name__)

@shared_task
def transcribe_session(session_id):
    try:
        session = Session.objects.get(id=session_id)
        session.status = 'transcribing'
        session.save()

        # Reconstruct paths
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', str(session.id))
        ext = os.path.splitext(session.original_filename)[1].lower()
        original_file_path = os.path.join(upload_dir, f"original_audio{ext}")
        audio_path = os.path.join(upload_dir, 'extracted_audio.wav')
        
        # 1. Preprocessor pipeline
        extract_audio(original_file_path, audio_path)
        # VAD skipped for local dev — uncomment for production
        # apply_vad(audio_path)
        
        duration = get_duration(audio_path)
        session.duration_seconds = int(duration)
        session.save()
        
        # Validate duration <= 12000s (200 min)
        if duration > 12000:
            raise ValueError(f"Duration {duration}s exceeds 200 minutes limit.")

        # 2. Transcribe chunks
        chunks = chunk_audio(audio_path, chunk_min=10)
        engine = get_engine()
        
        import concurrent.futures
        
        all_text = [None] * len(chunks)
        all_words = [None] * len(chunks)
        detected_language = None
        
        time_offsets = [0.0] * len(chunks)
        current_offset = 0.0
        for i, chunk_path in enumerate(chunks):
            time_offsets[i] = current_offset
            current_offset += get_duration(chunk_path)
            
        def process_chunk(idx, chunk_path):
            return idx, engine.transcribe(chunk_path)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_chunk, i, cp) for i, cp in enumerate(chunks)]
            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                all_text[idx] = result['text']
                
                chunk_words = []
                offset = time_offsets[idx]
                for word in result['word_timestamps']:
                    chunk_words.append({
                        'word': word['word'],
                        'start': word['start'] + offset,
                        'end': word['end'] + offset
                    })
                all_words[idx] = chunk_words
                
                if not detected_language:
                    detected_language = result['language']
                    
        flattened_words = []
        for word_list in all_words:
            if word_list:
                flattened_words.extend(word_list)
        
        # 3. Save Transcript to DB
        Transcript.objects.create(
            session=session,
            raw_text=" ".join(filter(None, all_text)).strip(),
            word_timestamps=flattened_words
        )
        
        session.detected_language = detected_language or ''
        session.status = 'summarising'
        session.save()
        
        # 4. Trigger summarise_session — import here to avoid circular imports
        from apps.summarisation.tasks import summarise_session
        summarise_session.delay(session_id=session_id)
        
    except Exception as e:
        logger.exception(f"Transcription failed for session {session_id}")
        session = Session.objects.get(id=session_id)
        session.status = 'failed'
        session.save()
