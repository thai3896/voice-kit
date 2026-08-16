import json
import urllib.request
import ssl
import os
import tempfile
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, QObject, pyqtSignal

ssl._create_default_https_context = ssl._create_unverified_context

class KokoroTTS(QObject):
    started_playing = pyqtSignal()
    finished = pyqtSignal()
    _signal_play_file = pyqtSignal(str)
    
    def __init__(self, url: str, voice: str = "af_bella"):
        super().__init__()
        self.url = url
        self.voice = voice
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self._temp_file = None
        self._signal_play_file.connect(self._play_on_main_thread)

    def speak(self, text: str):
        if not text.strip():
            self.finished.emit()
            return
            
        import threading
        threading.Thread(target=self._download_and_play, args=(text,), daemon=True).start()
        
    def _download_and_play(self, text: str):
            
        data = json.dumps({
            "model": "kokoro",
            "input": text,
            "voice": self.voice,
            "response_format": "mp3"
        }).encode("utf-8")

        req = urllib.request.Request(self.url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                audio_bytes = response.read()
                
            if self._temp_file and os.path.exists(self._temp_file):
                try:
                    os.remove(self._temp_file)
                except:
                    pass

            fd, self._temp_file = tempfile.mkstemp(suffix=".mp3")
            with os.fdopen(fd, 'wb') as f:
                f.write(audio_bytes)

            self._signal_play_file.emit(self._temp_file)
        except Exception as e:
            print(f"Kokoro TTS Error: {e}")
            self.finished.emit()

    def _play_on_main_thread(self, file_path: str):
        self.started_playing.emit()
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        
    def stop(self):
        self.player.stop()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.finished.emit()
