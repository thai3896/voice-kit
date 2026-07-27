import io
import os
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Callable, Optional


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: Optional[int] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._recording = False
        self._stream: Optional[sd.InputStream] = None
        self._frames = []
        self._lock = threading.RLock()
        self.on_level_callback: Optional[Callable[[float], None]] = None
        self.on_chunk_callback: Optional[Callable[[bytes], None]] = None

    def start(self, on_level: Optional[Callable[[float], None]] = None, on_chunk: Optional[Callable[[bytes], None]] = None) -> None:
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._recording = True
            self.on_level_callback = on_level
            self.on_chunk_callback = on_chunk

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    device=self.device,
                    dtype="int16",
                    callback=self._audio_callback
                )
                self._stream.start()
            except Exception as e:
                self._recording = False
                print(f"Error starting audio stream: {e}")
                raise e

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print(f"Audio status: {status}")
        if not self._recording:
            return

        with self._lock:
            data_copy = indata.copy()
            self._frames.append(data_copy)

        # Calculate RMS level for UI visualization (normalized 0.0 to 1.0 roughly)
        if self.on_level_callback:
            try:
                # int16 ranges from -32768 to 32767
                float_data = indata.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(float_data ** 2))
                # Scale up a bit so normal speaking shows visible pulse
                level = min(1.0, float(rms * 5.0))
                self.on_level_callback(level)
            except Exception as e:
                pass

        # If real-time streaming callback is registered, send PCM bytes
        if self.on_chunk_callback:
            try:
                self.on_chunk_callback(indata.tobytes())
            except Exception:
                pass

    def stop(self) -> str:
        with self._lock:
            if not self._recording:
                return ""
            self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                print(f"Error stopping stream: {e}")
            finally:
                self._stream = None

        with self._lock:
            if not self._frames:
                return ""
            audio_data = np.concatenate(self._frames, axis=0)

        # Save to permanent recording file
        import datetime
        rec_dir = os.path.expanduser("~/.voicekit/recordings")
        os.makedirs(rec_dir, exist_ok=True)
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = os.path.join(rec_dir, f"rec_{ts_str}.wav")
        try:
            sf.write(file_path, audio_data, self.sample_rate)
            return file_path
        except Exception as e:
            print(f"Error writing audio file: {e}")
            return ""

    def get_wav_bytes(self) -> bytes:
        return self.get_audio_bytes()

    def get_audio_bytes(self) -> bytes:
        with self._lock:
            if not self._frames:
                return b""
            audio_data = np.concatenate(self._frames, axis=0)
        
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, self.sample_rate, format="WAV")
        return buffer.getvalue()

    def clear_buffer(self) -> None:
        with self._lock:
            self._frames = []

    @property
    def is_recording(self) -> bool:
        return self._recording
