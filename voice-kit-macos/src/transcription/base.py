from abc import ABC, abstractmethod
from typing import Callable, Optional


class BaseTranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_file_path: str, on_partial: Optional[Callable[[str], None]] = None) -> str:
        """
        Transcribe an audio file and return the text string.
        Optional on_partial callback can be invoked when streaming text chunks.
        """
        pass

    @abstractmethod
    def transcribe_bytes(self, audio_bytes: bytes, on_partial: Optional[Callable[[str], None]] = None) -> str:
        """
        Transcribe audio bytes directly and return the text string.
        """
        pass

    def reset_live_stream(self) -> None:
        """
        Reset live stream state (e.g. after cut or clear buffer).
        """
        pass
