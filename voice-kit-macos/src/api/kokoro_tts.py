import json
import urllib.request
import ssl
import os
import tempfile
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, QObject, pyqtSignal

ssl._create_default_https_context = ssl._create_unverified_context

class KokoroTTS(QObject):
    finished = pyqtSignal()
    
    def __init__(self, url: str, voice: str = "af_bella"):
        super().__init__()
        self.url = url
        self.voice = voice
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self._temp_file = None

    def speak(self, text: str):
        if not text.strip():
            self.finished.emit()
            return
            
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

            self.player.setSource(QUrl.fromLocalFile(self._temp_file))
            self.player.play()
        except Exception as e:
            print(f"Kokoro TTS Error: {e}")
            self.finished.emit()
            
    def stop(self):
        self.player.stop()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.finished.emit()
