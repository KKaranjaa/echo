from django.conf import settings
from faster_whisper import WhisperModel
from .base import BaseASREngine

class WhisperEngine(BaseASREngine):
    def __init__(self):
        # Use 'large-v3' in production, 'small' in development
        model_size = "large-v3" if not settings.DEBUG else "small"
        
        # Using auto device selection with default compute type for CTranslate2
        self.model = WhisperModel(model_size, device="auto", compute_type="default")

    def transcribe(self, audio_path: str) -> dict:
        segments, info = self.model.transcribe(audio_path, word_timestamps=True)
        
        text_parts = []
        words_list = []
        
        for segment in segments:
            text_parts.append(segment.text)
            if segment.words:
                for word in segment.words:
                    words_list.append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end
                    })
                
        return {
            "text": " ".join(text_parts).strip(),
            "word_timestamps": words_list,
            "language": info.language
        }
