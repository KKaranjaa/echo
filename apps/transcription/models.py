import uuid
from django.db import models
from apps.uploads.models import Session

class Transcript(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='transcript')
    raw_text = models.TextField()
    word_timestamps = models.JSONField(default=list)
    has_edits = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcript for Session {self.session_id}"

    def get_chunked_segments(self):
        import inspect
        import json
        from apps.transcription.preprocessor import chunk_audio
        
        # Extract default chunk_min from preprocessor.py to ensure they match exactly
        sig = inspect.signature(chunk_audio)
        chunk_min = sig.parameters['chunk_min'].default
        chunk_sec = chunk_min * 60

        if not self.word_timestamps:
            return []

        chunks = []
        current_chunk_idx = 0
        current_chunk_words = []

        for i, word in enumerate(self.word_timestamps):
            word_with_index = word.copy()
            word_with_index['original_index'] = i
            
            chunk_idx = int(word.get('start', 0) // chunk_sec)
            
            if chunk_idx != current_chunk_idx:
                if current_chunk_words:
                    chunks.append({
                        'index': current_chunk_idx,
                        'start': current_chunk_idx * chunk_sec,
                        'end': (current_chunk_idx + 1) * chunk_sec,
                        'words': current_chunk_words,
                        'words_json': json.dumps(current_chunk_words)
                    })
                current_chunk_idx = chunk_idx
                current_chunk_words = [word_with_index]
            else:
                current_chunk_words.append(word_with_index)

        if current_chunk_words:
            chunks.append({
                'index': current_chunk_idx,
                'start': current_chunk_idx * chunk_sec,
                'end': (current_chunk_idx + 1) * chunk_sec,
                'words': current_chunk_words,
                'words_json': json.dumps(current_chunk_words)
            })

        return chunks
