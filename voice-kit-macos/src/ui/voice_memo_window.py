from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl
from PyQt6.QtCore import QMetaObject
import os
import json
import soundfile as sf
import sounddevice as sd
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QLineEdit,
    QStackedWidget, QTextEdit, QScrollArea, QFrame, QMenu, QToolButton,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, pyqtSlot
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath

class WaveformWidget(QWidget):
    signal_seek = pyqtSignal(float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.amplitudes = []
        self.play_progress = 0.0 # 0.0 to 1.0
        self.setMinimumHeight(150)
        self.setStyleSheet("background-color: transparent;")

    def add_amplitude(self, amp):
        self.amplitudes.append(amp)
        self.update()

    def set_amplitudes(self, amps):
        self.amplitudes = amps
        self.update()

    def set_progress(self, progress):
        self.play_progress = max(0.0, min(1.0, progress))
        self.update()

    def mousePressEvent(self, event):
        width = self.width()
        x = event.position().x()
        progress = max(0.0, min(1.0, x / width))
        self.signal_seek.emit(progress)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        mid_y = height / 2

        painter.setPen(QPen(QColor(100, 100, 100, 100), 1))
        painter.drawLine(0, int(mid_y), width, int(mid_y))

        if not self.amplitudes:
            return

        bar_width = 3
        spacing = 2
        total_bars = width // (bar_width + spacing)

        # Resample amplitudes to fit exactly into total_bars
        import numpy as np
        
        if len(self.amplitudes) <= total_bars:
            amps = self.amplitudes
            # Left align it and stretch it? No, if it's less than total bars, we still map 0-1 across the actual drawn area
            # But the user expects the scrubber to span the whole width!
            # So if it's less than total bars, let's just pad it or resample it to fill the whole width!
        
        # Always resample to total_bars so it spans exactly 0 to width
        amps = np.interp(np.linspace(0, len(self.amplitudes)-1, total_bars), np.arange(len(self.amplitudes)), self.amplitudes)
        
        play_x = width * self.play_progress
        
        path_played = QPainterPath()
        path_unplayed = QPainterPath()
        
        for i, amp in enumerate(amps):
            x = i * (bar_width + spacing)
            h = int(amp * height * 0.9)
            h = max(2, h)
            
            rect = QRectF(float(x), float(mid_y - h/2), float(bar_width), float(h))
            if x <= play_x:
                path_played.addRoundedRect(rect, 1.5, 1.5)
            else:
                path_unplayed.addRoundedRect(rect, 1.5, 1.5)
                
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0a84ff"))
        painter.drawPath(path_played)
        
        painter.setBrush(QColor("#f1f2f6"))
        painter.drawPath(path_unplayed)

class TranscriptWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #f1f2f6;
                font-size: 16px;
                border: none;
                line-height: 1.5;
            }
        """)
        self.transcript_data = None
        self.current_time = 0.0

    def set_transcript(self, transcript_data):
        self.transcript_data = transcript_data
        self._render_text()
        
    def _render_text(self):
        if not self.transcript_data:
            self.setHtml("<p style='color:#888;'>No transcript available.</p>")
            return
            
        # If it's a string (Voice-Editor format)
        if isinstance(self.transcript_data, str):
            self.setPlainText(self.transcript_data)
            return
            
        # If it's verbose_json format (timestamped)
        html = "<p>"
        words = self.transcript_data.get("words", [])
        for i, word_obj in enumerate(words):
            word = word_obj.get("word", "")
            start = word_obj.get("start", 0.0)
            end = word_obj.get("end", 0.0)
            
            color = "#f1f2f6"
            if start <= self.current_time <= end:
                color = "#0a84ff"
                
            html += f"<span style='color:{color};'>{word}</span> "
        html += "</p>"
        self.setHtml(html)

    def update_time(self, current_time):
        self.current_time = current_time
        # Re-render only if timestamped
        if isinstance(self.transcript_data, dict) and "words" in self.transcript_data:
            self._render_text()


class VoiceMemoWindow(QMainWindow):
    def __init__(self, memo_manager, recorder, ai_client, parent=None):
        super().__init__(parent)
        self.memo_manager = memo_manager
        self.recorder = recorder
        self.ai_client = ai_client
        self.current_memo = None
        self.audio_data = None
        self.audio_sr = 16000
        self.play_pos = 0
        self.is_playing = False
        self.play_stream = None
        
        self.setWindowTitle("Voice Memos")
        self.resize(1000, 600)
        self.setStyleSheet("background-color: #1e1e24; color: #f1f2f6;")
        
        self._init_ui()
        self.load_memos()
        
        self.recorder.signal_amplitude.connect(self._on_amplitude)
        self.recorder.signal_state_changed.connect(self._on_record_state)
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._on_player_position)
        self.player.playbackStateChanged.connect(self._on_player_state)
        
        # self.playback_timer is no longer needed for QMediaPlayer

    def _init_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        
        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search")
        self.search_bar.setStyleSheet("background-color: #2c2c34; border: none; padding: 8px; margin: 10px; border-radius: 6px;")
        left_layout.addWidget(self.search_bar)
        
        self.memo_list = QListWidget()
        self.memo_list.setStyleSheet("""
            QListWidget { border: none; background-color: #1e1e24; outline: none; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #2c2c34; }
            QListWidget::item:selected { background-color: #0a84ff; }
        """)
        self.memo_list.itemClicked.connect(self._on_memo_selected)
        left_layout.addWidget(self.memo_list)
        
        # New Memo button area
        new_memo_area = QWidget()
        new_memo_area.setStyleSheet("background-color: #1a1a20; border-top: 1px solid #2c2c34;")
        nma_layout = QHBoxLayout(new_memo_area)
        
        self.btn_new = QPushButton("➕ New Memo")
        self.btn_new.setStyleSheet("font-weight: bold; background-color: #3a3a44; border-radius: 6px; padding: 10px 20px; font-size: 14px;")
        self.btn_new.clicked.connect(self._on_new_memo)
        
        nma_layout.addStretch()
        nma_layout.addWidget(self.btn_new)
        nma_layout.addStretch()
        left_layout.addWidget(new_memo_area)
        
        splitter.addWidget(left_panel)
        
        # Right Panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #232329;")
        right_layout = QVBoxLayout(right_panel)
        
        # Top toolbar
        toolbar = QHBoxLayout()
        self.title_edit = QLineEdit("New Recording")
        self.title_edit.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent; border: none;")
        self.title_edit.editingFinished.connect(self._rename_memo)
        toolbar.addWidget(self.title_edit)
        
        self.btn_transcribe = QToolButton()
        self.btn_transcribe.setText("✨ Transcribe")
        self.btn_transcribe.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.update_transcribe_menu()
        toolbar.addWidget(self.btn_transcribe)
        
        self.btn_delete = QToolButton()
        self.btn_delete.setText("🗑️")
        self.btn_delete.clicked.connect(self.delete_current_memo)
        toolbar.addWidget(self.btn_delete)
        
        right_layout.addLayout(toolbar)
        
        self.transcript_view = TranscriptWidget()
        self.waveform_view = WaveformWidget()
        self.waveform_view.setFixedHeight(120)
        self.waveform_view.signal_seek.connect(self._on_seek)
        
        right_layout.addWidget(self.transcript_view, 1)
        right_layout.addWidget(self.waveform_view, 0)
        
        # Bottom controls
        bottom_area = QWidget()
        bottom_layout = QVBoxLayout(bottom_area)
        
        self.lbl_time = QLabel("00:00.00")
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setStyleSheet("font-size: 32px; font-weight: 300;")
        bottom_layout.addWidget(self.lbl_time)
        
        controls = QHBoxLayout()
        
        self.btn_record = QPushButton("🔴")
        self.btn_record.setFixedSize(50, 50)
        self.btn_record.setStyleSheet("border-radius: 25px; background-color: #ff4757; font-size: 20px;")
        self.btn_record.clicked.connect(self.toggle_recording)
        
        self.btn_play = QPushButton("▶️")
        self.btn_play.setFixedSize(50, 50)
        self.btn_play.setStyleSheet("border-radius: 25px; background-color: #333; font-size: 20px; margin-left: 10px; margin-right: 10px;")
        self.btn_play.clicked.connect(self.toggle_playback)
        
        self.btn_done = QPushButton("Done")
        self.btn_done.setStyleSheet("padding: 8px 16px; font-weight: bold; background-color: #333; border-radius: 6px; color: white;")
        self.btn_done.setVisible(False)
        self.btn_done.clicked.connect(self.finish_recording)
        
        controls.addStretch()
        controls.addWidget(self.btn_record)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_done)
        controls.addStretch()
        bottom_layout.addLayout(controls)
        right_layout.addWidget(bottom_area)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])

    @pyqtSlot()
    def load_memos(self):
        current_id = self.current_memo["id"] if hasattr(self, 'current_memo') and self.current_memo else None
        
        self.memo_list.clear()
        memos = self.memo_manager.list_memos()
        for m in memos:
            dur_str = f"{int(m['duration']//60):02d}:{int(m['duration']%60):02d}"
            
            icons = []
            if m["has_refined"]: icons.append("📝")
            if m["has_timestamped"]: icons.append("⏱️")
            if hasattr(self, 'transcribing_ids') and m["id"] in self.transcribing_ids:
                icons.append("⏳")
                
            icon_str = " ".join(icons)
            title = f"{m['title']} {icon_str}".strip()
            
            item = QListWidgetItem(f"{title}\n{dur_str}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.memo_list.addItem(item)
            
            if current_id == m["id"]:
                self.memo_list.setCurrentItem(item)
                self.current_memo = m
            
    def toggle_recording(self):
        if self.recorder.is_recording and not self.recorder.is_paused:
            self.recorder.pause_recording()
        else:
            if self.is_playing:
                self.stop_playback()
            if not self.recorder.is_recording:
                if hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("id") != "preview":
                    self.recorder.preload_audio(self.current_memo["file_path"])
                else:
                    self.waveform_view.amplitudes.clear()
            self.recorder.start_recording()

    def finish_recording(self):
        if self.is_playing:
            self.stop_playback()
            
        real = getattr(self, 'real_title', None)
        if real and real not in ["Paused", "Recording..."]:
            self.title_edit.setText(real)
        self.real_title = None
            
        if self.recorder.is_recording:
            temp_path = self.recorder.stop_recording()
            if temp_path:
                if hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("id") != "preview":
                    new_title = self.memo_manager.update_memo_audio(self.current_memo["id"], temp_path)
                else:
                    t = self.title_edit.text()
                    new_title = self.memo_manager.save_new_memo(temp_path, t if t != "New Recording" else None)
                self.load_memos()
                for i in range(self.memo_list.count()):
                    item = self.memo_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)["title"] == new_title:
                        self.memo_list.setCurrentItem(item)
                        self._on_memo_selected(item)
                        break
            
    def _on_record_state(self, state):
        if state == "recording":
            self.btn_record.setText("⏸️")
            self.btn_record.setStyleSheet("border-radius: 25px; background-color: #f39c12; font-size: 20px;")
            self.btn_done.setVisible(True)
            if not getattr(self, 'real_title', None): self.real_title = self.title_edit.text()
            self.title_edit.setText("Recording...")
            self.memo_list.setEnabled(False)
            if self.is_playing:
                self.stop_playback()
        elif state == "paused":
            self.btn_record.setText("🔴")
            self.btn_record.setStyleSheet("border-radius: 25px; background-color: #ff4757; font-size: 20px;")
            self.btn_done.setVisible(True)
            if not getattr(self, 'real_title', None): self.real_title = self.title_edit.text()
            self.title_edit.setText("Paused")
            
            # Create a preview
            preview_file = self.recorder.get_preview_file()
            if preview_file:
                import soundfile as sf
                try:
                    self.audio_data, self.audio_sr = sf.read(preview_file, dtype="float32")
                    dur = len(self.audio_data) / self.audio_sr
                except:
                    dur = 0
                    
                self.current_memo = {
                    "file_path": preview_file,
                    "duration": dur,
                    "id": "preview",
                    "title": "Preview",
                    "has_timestamped": False,
                    "has_refined": False
                }
                
                from PyQt6.QtCore import QUrl
                file_url = QUrl.fromLocalFile(preview_file)
                self.player.setSource(file_url)
                self.play_pos = 0
                self.lbl_time.setText(f"00:00.00 / {int(dur//60):02d}:{dur%60:05.2f}")
                self.waveform_view.set_progress(0)
                
        else:
            self.btn_record.setText("🔴")
            self.btn_record.setStyleSheet("border-radius: 25px; background-color: #ff4757; font-size: 20px;")
            self.btn_done.setVisible(False)
            self.memo_list.setEnabled(True)
            
    def _on_amplitude(self, amp):
        self.waveform_view.add_amplitude(amp)
        
    def _on_new_memo(self):
        self.memo_list.clearSelection()
        self.current_memo = None
        self.title_edit.setText("New Recording")
        self.transcript_view.set_transcript(None)
        self.waveform_view.amplitudes.clear()
        self.waveform_view.set_progress(0)
        self.lbl_time.setText("00:00.00 / 00:00.00")
        if self.is_playing:
            self.stop_playback()

    def _on_memo_selected(self, item):
        self.current_memo = item.data(Qt.ItemDataRole.UserRole)
        self.title_edit.setText(self.current_memo["title"])
        self.stop_playback()
        self.play_pos = 0
        
        file_url = QUrl.fromLocalFile(self.current_memo["file_path"])
        self.player.setSource(file_url)
        
        # Load audio data to generate waveform and prepare playback
        try:
            self.audio_data, self.audio_sr = sf.read(self.current_memo["file_path"], dtype="float32")
            # Generate coarse amplitudes for waveform
            step = max(1, len(self.audio_data) // 200)
            if len(self.audio_data.shape) > 1:
                mono = self.audio_data[:, 0]
            else:
                mono = self.audio_data
            amps = [np.max(np.abs(mono[i:i+step])) for i in range(0, len(mono), step)]
            self.waveform_view.set_amplitudes(amps)
            self.waveform_view.set_progress(0.0)
            dur = self.current_memo["duration"]
            self.lbl_time.setText(f"00:00.00 / {int(dur//60):02d}:{dur%60:05.2f}")
        except Exception as e:
            print(f"Error loading audio: {e}")
            
        self._reload_transcript_view()
        self.update_transcribe_menu()


    def _rename_memo(self):
        if not self.current_memo: return
        new_title = self.title_edit.text().strip()
        if new_title and new_title != self.current_memo["title"]:
            if self.memo_manager.rename_memo(self.current_memo["id"], new_title):
                self.load_memos()

    def delete_current_memo(self):
        if not self.current_memo: return
        self.stop_playback()
        self.memo_manager.delete_memo(self.current_memo["id"])
        self.current_memo = None
        self.load_memos()
        self.waveform_view.amplitudes.clear()
        


    @pyqtSlot(float)
    def _on_seek(self, progress):
        if not self.current_memo: return
        dur = self.current_memo["duration"]
        if dur <= 0: return
        
        pos_ms = int(progress * dur * 1000)
        self.player.setPosition(pos_ms)
        self.waveform_view.set_progress(progress)
        self.transcript_view.update_time(progress * dur)
        
        if not self.is_playing and hasattr(self, 'audio_sr'):
            self.play_pos = int((pos_ms / 1000.0) * self.audio_sr)
            
    def toggle_playback(self):
        if not self.audio_data is not None: return
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if not self.current_memo: return
        self.is_playing = True
        self.btn_play.setText("⏸️")
        self.player.play()

    def stop_playback(self):
        self.is_playing = False
        self.btn_play.setText("▶️")
        self.player.pause()

    def _on_player_position(self, pos_ms):
        if not self.current_memo: return
        curr_time = pos_ms / 1000.0
        dur = self.current_memo["duration"]
        
        if dur > 0:
            self.lbl_time.setText(f"{int(curr_time//60):02d}:{curr_time%60:05.2f} / {int(dur//60):02d}:{dur%60:05.2f}")
            self.waveform_view.set_progress(curr_time / dur)
            self.transcript_view.update_time(curr_time)

    def _on_player_state(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.is_playing = False
            self.play_pos = 0
            self.btn_play.setText("▶️")
            self.waveform_view.set_progress(0)
            if self.current_memo:
                dur = self.current_memo["duration"]
                self.lbl_time.setText(f"00:00.00 / {int(dur//60):02d}:{dur%60:05.2f}")

    def _update_playback(self):
        pass # Deprecated, kept to avoid attr errors if called anywhere else


    @pyqtSlot()
    def _on_transcription_done(self):
        self.load_memos()
        self.btn_transcribe.setEnabled(True)
        self.btn_transcribe.setText("✨ Transcribe")
        if self.current_memo:
            self._reload_transcript_view()
            self.update_transcribe_menu()
        self.update_transcribe_menu()

    def update_transcribe_menu(self):
        from PyQt6.QtWidgets import QMenu
        if not hasattr(self, 'btn_transcribe'): return
        menu = QMenu(self)
        
        m = self.current_memo
        if not m:
            self.btn_transcribe.setMenu(menu)
            return
            
        if m.get("has_refined"):
            a = menu.addAction("📝 View Refined")
            a.triggered.connect(lambda: self.switch_transcript_view("refined"))
            a = menu.addAction("🔄 Regenerate Refined")
            a.triggered.connect(lambda: self.start_transcription("refined"))
        else:
            a = menu.addAction("✨ Generate Refined")
            a.triggered.connect(lambda: self.start_transcription("refined"))
            
        if m.get("has_timestamped"):
            a = menu.addAction("⏱️ View Timestamped")
            a.triggered.connect(lambda: self.switch_transcript_view("timestamped"))
            a = menu.addAction("🔄 Regenerate Timestamped")
            a.triggered.connect(lambda: self.start_transcription("timestamped"))
        else:
            a = menu.addAction("✨ Generate Timestamped")
            a.triggered.connect(lambda: self.start_transcription("timestamped"))
            
        self.btn_transcribe.setMenu(menu)

    def switch_transcript_view(self, mode):
        if not self.current_memo: return
        self.active_transcript_mode = mode
        self._reload_transcript_view()
        self.update_transcribe_menu()

    def _reload_transcript_view(self):
        transcript = None
        import json
        mode = getattr(self, 'active_transcript_mode', 'timestamped' if self.current_memo.get("has_timestamped") else 'refined')
        
        if mode == "timestamped" and self.current_memo.get("has_timestamped"):
            try:
                with open(self.current_memo["json_path"], "r") as f:
                    transcript = json.load(f)
            except: pass
        elif mode == "refined" and self.current_memo.get("has_refined"):
            try:
                with open(self.current_memo["txt_path"], "r") as f:
                    transcript = f.read()
            except: pass
        self.transcript_view.set_transcript(transcript)

    def start_transcription(self, mode):
        if not self.current_memo: return
        
        file_path = self.current_memo["file_path"]
        base_name = self.current_memo["id"]
        folder_path = self.memo_manager.folder_path
        
        if not hasattr(self, 'transcribing_ids'):
            self.transcribing_ids = set()
        self.transcribing_ids.add(base_name)
        
        self.load_memos()
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.setText("⏳ Transcribing...")
        
        def worker():
            try:
                if mode == "refined":
                    text = self.ai_client.transcribe(file_path)
                    import os
                    txt_path = os.path.join(folder_path, f"{base_name}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(text)
                elif mode == "timestamped":
                    from openai import OpenAI
                    import os
                    base_url = "https://whisper.minipc.na/v1"
                    client = OpenAI(base_url=base_url, api_key="sk-local")
                    with open(file_path, "rb") as f:
                        transcript = client.audio.transcriptions.create(
                            model="deepdml/faster-whisper-large-v3-turbo-ct2",
                            file=f,
                            response_format="verbose_json",
                            timestamp_granularities=["word"]
                        )
                        json_path = os.path.join(folder_path, f"{base_name}.json")
                        with open(json_path, "w", encoding="utf-8") as out_f:
                            out_f.write(transcript.model_dump_json())
            except Exception as e:
                print(f"Transcription error: {e}")
            finally:
                if base_name in self.transcribing_ids:
                    self.transcribing_ids.remove(base_name)
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self, "_on_transcription_done", Qt.ConnectionType.QueuedConnection)
                
        import threading
        t = threading.Thread(target=worker, daemon=True)
        t.start()
