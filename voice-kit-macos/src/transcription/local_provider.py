import os
import tempfile
from typing import Callable, Optional
from .base import BaseTranscriptionProvider

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False


class LocalProvider(BaseTranscriptionProvider):
    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _get_model(self):
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper package is not installed.")
        
        if self._model is None:
            device = self.device
            compute_type = "default"
            if device == "auto":
                device = "cpu"  # faster-whisper on macOS M1/M2 runs great on CPU with Accelerate
                compute_type = "int8"
            
            print(f"Loading local Whisper model '{self.model_size}' on {device}...")
            self._model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        return self._model

    def transcribe(self, audio_file_path: str, on_partial: Optional[Callable[[str], None]] = None) -> str:
        try:
            model = self._get_model()
            segments, info = model.transcribe(audio_file_path, beam_size=5)
            text_chunks = []
            for segment in segments:
                text_chunks.append(segment.text)
                if on_partial:
                    on_partial("".join(text_chunks).strip())
            return "".join(text_chunks).strip()
        except Exception as e:
            print(f"Local Whisper error: {e}")
            return f"[Local Whisper Error: {e}]"

    def transcribe_bytes(self, audio_bytes: bytes, on_partial: Optional[Callable[[str], None]] = None) -> str:
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "voice_kit_local_temp.wav")
        try:
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            return self.transcribe(temp_file, on_partial)
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
