import numpy as np
import sounddevice as sd
import threading
import time
from typing import Callable, Optional

class VADListener:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: Optional[int] = None, silence_duration: float = 1.5, min_speech_duration: float = 0.5):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._listening = False
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.RLock()
        
        # Callbacks
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[bytes], None]] = None
        self.on_volume_update: Optional[Callable[[float], None]] = None
        
        # VAD Parameters
        self.energy_threshold = 0.01  # Adjust based on mic sensitivity
        self.silence_duration_limit = silence_duration  # Seconds of silence before speech ends
        self.min_speech_duration = min_speech_duration  # Min seconds of speech to keep
        self.speech_duration_limit = 0.05   # Seconds of speech before speech starts
        
        # State
        self._is_speaking = False
        self._frames = []
        self._silence_start_time = None
        self._speech_start_time = None

    def start(self):
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._is_speaking = False
            self._frames = []
            
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
                self._listening = False
                print(f"Error starting VAD stream: {e}")

    def stop(self):
        with self._lock:
            if not self._listening:
                return
            self._listening = False
            
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            finally:
                self._stream = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if not self._listening:
            return

        with self._lock:
            data_copy = indata.copy()
            float_data = data_copy.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(float_data ** 2)))
            
            is_active = rms > self.energy_threshold
            
            if self.on_volume_update:
                self.on_volume_update(rms)

            if self._is_speaking:
                self._frames.append(data_copy)
                
                if not is_active:
                    if self._silence_start_time is None:
                        self._silence_start_time = time.time()
                    elif time.time() - self._silence_start_time > self.silence_duration_limit:
                        # End of speech
                        self._is_speaking = False
                        self._silence_start_time = None
                        audio_data = np.concatenate(self._frames, axis=0)
                        self._frames = []
                        
                        # Calculate actual speech duration (total minus trailing silence)
                        total_duration = len(audio_data) / self.sample_rate
                        actual_speech_duration = total_duration - self.silence_duration_limit
                        
                        if actual_speech_duration >= self.min_speech_duration:
                            if self.on_speech_end:
                                # Run callback in thread to not block stream
                                threading.Thread(target=self.on_speech_end, args=(audio_data.tobytes(),), daemon=True).start()
                        else:
                            print(f"VAD: Ignored short sound ({actual_speech_duration:.2f}s < {self.min_speech_duration}s)")
                else:
                    self._silence_start_time = None
            else:
                if is_active:
                    if self._speech_start_time is None:
                        self._speech_start_time = time.time()
                        self._frames = [data_copy]
                    else:
                        self._frames.append(data_copy)
                        if time.time() - self._speech_start_time > self.speech_duration_limit:
                            # Start of speech
                            self._is_speaking = True
                            self._speech_start_time = None
                            if self.on_speech_start:
                                threading.Thread(target=self.on_speech_start, daemon=True).start()
                else:
                    self._speech_start_time = None
                    self._frames = []
