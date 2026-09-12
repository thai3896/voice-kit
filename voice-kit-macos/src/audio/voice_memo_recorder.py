import tempfile
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
from PyQt6.QtCore import QObject, pyqtSignal

class VoiceMemoRecorder(QObject):
    signal_amplitude = pyqtSignal(float)
    signal_state_changed = pyqtSignal(str) # "recording", "paused", "stopped"
    
    def __init__(self, device=None, sample_rate=16000, channels=1):
        super().__init__()
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        
        self.is_recording = False
        self.is_paused = False
        
        self._stream = None
        self._frames = []
        self._lock = threading.RLock()

    def start_recording(self):
        with self._lock:
            if self.is_recording and not self.is_paused:
                return
                
            if not self.is_recording:
                if not getattr(self, '_preloaded', False):
                    self._frames = []
                self.is_recording = True
                self._preloaded = False
                pass # print(f"[VoiceMemoRecorder] Starting fresh recording. Device: {self.device}, SR: {self.sample_rate}, Channels: {self.channels}")
                
            self.is_paused = False
            self.signal_state_changed.emit("recording")
            
            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    device=self.device,
                    callback=self._audio_callback
                )
                self._stream.start()
            except sd.PortAudioError as e:
                pass # print(f"[VoiceMemoRecorder] Error with device {self.device}: {e}. Falling back to default.")
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception:
                    pass
                self.device = None
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    device=None,
                    callback=self._audio_callback
                )
                self._stream.start()

    def pause_recording(self):
        with self._lock:
            if self.is_recording and not self.is_paused:
                self.is_paused = True
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                self.signal_state_changed.emit("paused")
                pass # print(f"[VoiceMemoRecorder] Paused recording. Collected {len(self._frames)} chunks so far.")

    def stop_recording(self):
        with self._lock:
            self.is_recording = False
            self.is_paused = False
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                
            if not self._frames:
                pass # print("[VoiceMemoRecorder] Stopped, but no frames collected.")
                return None
                
            audio_data = np.concatenate(self._frames, axis=0)
            pass # print(f"[VoiceMemoRecorder] Stopped. Total frames: {audio_data.shape}. Saving to temp file...")
            
            fd, temp_file_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            
            sf.write(temp_file_path, audio_data, self.sample_rate, subtype='PCM_16')
            pass # print(f"[VoiceMemoRecorder] Saved wav to {temp_file_path}")
                
            self.signal_state_changed.emit("stopped")
            return temp_file_path

    def preload_audio(self, wav_path):
        import soundfile as sf
        with self._lock:
            try:
                data, sr = sf.read(wav_path, dtype='int16')
                # data shape could be (N,) or (N, channels)
                if len(data.shape) == 1:
                    data = data.reshape(-1, 1)
                self._frames = [data]
                self._preloaded = True
            except Exception as e:
                pass # print(f"Failed to preload: {e}")

    def get_preview_file(self):
        with self._lock:
            if not self._frames: return None
            audio_data = np.concatenate(self._frames, axis=0)
            fd, temp_file_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            sf.write(temp_file_path, audio_data, self.sample_rate, subtype='PCM_16')
            return temp_file_path

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass # print(f"[VoiceMemoRecorder] Status: {status}")
        if not self.is_recording or self.is_paused:
            return
            
        with self._lock:
            self._frames.append(indata.copy())
            
        try:
            float_data = indata.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(float_data ** 2))
            level = min(1.0, float(rms * 5.0))
            self.signal_amplitude.emit(level)
        except Exception:
            pass
