import numpy as np
import sounddevice as sd
import threading
import time
from typing import Callable, Optional

class VADListener:
    def __init__(self, mode: str = "energy", sample_rate: int = 16000, channels: int = 1, device: Optional[int] = None, energy_threshold: float = 0.006, silence_duration: float = 1.5, min_speech_duration: float = 0.5):
        self.mode = mode
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        
        self._silero_model = None
        self._torch = None
        self._listening = False
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.RLock()
        
        # Callbacks
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[bytes], None]] = None
        self.on_volume_update: Optional[Callable[[float], None]] = None
        
        # VAD Parameters
        self.energy_threshold = energy_threshold  # Tuned: above ambient noise (~0.003) but below speech (~0.008+)
        self.silence_duration_limit = silence_duration  # Seconds of silence before speech ends
        self.min_speech_duration = min_speech_duration  # Min seconds of speech to keep
        self.speech_duration_limit = 0.05   # Seconds of speech before speech starts
        self.hold_mode = False
        
        # State
        self._is_speaking = False
        self._frames = []
        self._silence_start_time = None
        self._speech_start_time = None
        self._paused = False
        self._active_frames_count = 0

    def pause(self):
        with self._lock:
            self._paused = True
            self._is_speaking = False
            self._frames = []
            self._active_frames_count = 0

    def resume(self):
        with self._lock:
            self._paused = False
            self._is_speaking = False
            self._frames = []
            self._active_frames_count = 0

    def start(self):
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._is_speaking = False
            self._frames = []
            self._active_frames_count = 0
            
            try:
                # Lazy load Silero if needed
                if self.mode == "silero":
                    print("[VAD] Initializing Silero AI VAD...")
                    if self._silero_model is None:
                        import torch
                        from silero_vad import load_silero_vad
                        self._torch = torch
                        self._silero_model = load_silero_vad()
                    print("[VAD] Silero AI VAD ready.")
                else:
                    print(f"[VAD] Initializing Energy VAD (threshold={self.energy_threshold})")
                    
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    device=self.device,
                    dtype="int16",
                    blocksize=512, # Force 512 blocksize for Silero compatibility
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
                self._stream = None
            except Exception:
                pass

    def set_hold_mode(self, enabled: bool):
        with self._lock:
            self.hold_mode = enabled
            if not enabled and self._is_speaking:
                # Force flush if disabled while speaking
                self._is_speaking = False
                self._silence_start_time = None
                if not self._frames:
                    return
                audio_data = np.concatenate(self._frames, axis=0)
                self._frames = []
                if self.on_speech_end:
                    threading.Thread(target=self.on_speech_end, args=(audio_data.tobytes(),), daemon=True).start()

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._listening or self._paused:
            return

        with self._lock:
            data_copy = indata.copy()
            float_data = data_copy.astype(np.float32) / 32768.0
            
            # Compute RMS for volume meter
            rms = float(np.sqrt(np.mean(float_data ** 2)))
            
            if self.mode == "silero" and self._silero_model is not None:
                # Silero expects (batch, samples)
                tensor_chunk = self._torch.from_numpy(float_data).squeeze()
                if tensor_chunk.dim() == 1:
                    tensor_chunk = tensor_chunk.unsqueeze(0)
                prob = self._silero_model(tensor_chunk, self.sample_rate).item()
                is_active = prob > 0.5
            else:
                is_active = rms > self.energy_threshold
            
            if self.on_volume_update:
                self.on_volume_update(rms)

            if self._is_speaking:
                self._frames.append(data_copy)
                
                if not is_active:
                    if self.hold_mode:
                        self._silence_start_time = None
                    elif self._silence_start_time is None:
                        self._silence_start_time = time.time()
                    elif time.time() - self._silence_start_time > self.silence_duration_limit:
                        # End of speech
                        self._is_speaking = False
                        self._silence_start_time = None
                        audio_data = np.concatenate(self._frames, axis=0)
                        
                        # Calculate actual speech duration by active frames
                        if len(self._frames) > 0:
                            frame_dur = len(self._frames[0]) / self.sample_rate
                            actual_speech_duration = self._active_frames_count * frame_dur
                        else:
                            actual_speech_duration = 0.0

                        self._frames = []
                        self._active_frames_count = 0
                        
                        if actual_speech_duration >= self.min_speech_duration:
                            print(f"[VAD] Speech ENDED (Mode: {self.mode}, duration: {actual_speech_duration:.2f}s)")
                            if self.on_speech_end:
                                # Run callback in thread to not block stream
                                threading.Thread(target=self.on_speech_end, args=(audio_data.tobytes(),), daemon=True).start()
                        else:
                            print(f"[VAD] Speech DISCARDED (too short: {actual_speech_duration:.2f}s < {self.min_speech_duration}s)")
                else:
                    self._silence_start_time = None
            else:
                if is_active:
                    self._is_speaking = True
                    self._speech_start_time = None
                    self._frames.append(data_copy)
                    self._active_frames_count = 1
                    print(f"[VAD] Speech STARTED (Mode: {self.mode})")
                    if self.on_speech_start:
                        threading.Thread(target=self.on_speech_start, daemon=True).start()
                else:
                    self._speech_start_time = None
                    self._frames.append(data_copy)
                    # Keep only last 0.5s of frames as pre-roll buffer
                    max_preroll_frames = int(0.5 * self.sample_rate / len(data_copy))
                    if max_preroll_frames > 0:
                        self._frames = self._frames[-max_preroll_frames:]
                        self._active_frames_count = 0

            # Count active frames while speaking
            if self._is_speaking and is_active:
                self._active_frames_count += 1
