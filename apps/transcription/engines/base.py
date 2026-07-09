import abc

class BaseASREngine(abc.ABC):
    @abc.abstractmethod
    def transcribe(self, audio_path: str) -> dict:
        """
        Returns: {
            'text': str,
            'word_timestamps': [{'word': str, 'start': float, 'end': float}],
            'language': str
        }
        """
        pass
