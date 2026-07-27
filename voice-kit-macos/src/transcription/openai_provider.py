import os
import io
from typing import Callable, Optional
from openai import OpenAI
from .base import BaseTranscriptionProvider


class OpenAIProvider(BaseTranscriptionProvider):
    def __init__(self, api_key: str = "", model: str = "whisper-1", prompt: str = ""):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.prompt = prompt
        self._client = None
        if self.api_key:
            self._client = OpenAI(api_key=self.api_key)

    def transcribe(self, audio_file_path: str, on_partial: Optional[Callable[[str], None]] = None) -> str:
        if not self._client:
            return "[Error: OPENAI_API_KEY not set]"
        
        try:
            with open(audio_file_path, "rb") as audio_file:
                kwargs = {"model": self.model, "file": audio_file}
                if self.prompt:
                    kwargs["prompt"] = self.prompt
                transcript = self._client.audio.transcriptions.create(**kwargs)
                text = transcript.text.strip()
                if on_partial:
                    on_partial(text)
                return text
        except Exception as e:
            print(f"OpenAI Whisper error: {e}")
            return f"[OpenAI Error: {e}]"

    def transcribe_bytes(self, audio_bytes: bytes, on_partial: Optional[Callable[[str], None]] = None) -> str:
        if not self._client:
            return "[Error: OPENAI_API_KEY not set]"
        
        try:
            buffer = io.BytesIO(audio_bytes)
            buffer.name = "audio.wav"
            kwargs = {"model": self.model, "file": buffer}
            if self.prompt:
                kwargs["prompt"] = self.prompt
            transcript = self._client.audio.transcriptions.create(**kwargs)
            text = transcript.text.strip()
            if on_partial:
                on_partial(text)
            return text
        except Exception as e:
            print(f"OpenAI Whisper error: {e}")
            return f"[OpenAI Error: {e}]"
