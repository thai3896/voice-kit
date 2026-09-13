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
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, pyqtSignal as pyqtSignal_dup, QRectF, pyqtSlot

class FFmpegWorker(QThread):
    finished_signal = pyqtSignal(str, str, str) # title, merged_mp4, merged_wav
    
    def __init__(self, chunks, memo_manager, current_memo):
        super().__init__()
        self.chunks = chunks
        self.memo_manager = memo_manager
        self.current_memo = current_memo
        
    def run(self):
        import os, tempfile, subprocess, shutil
        fd, merged_mp4 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        
        ffmpeg_exe = shutil.which("ffmpeg")
        if not ffmpeg_exe:
            if os.path.exists("/opt/homebrew/bin/ffmpeg"):
                ffmpeg_exe = "/opt/homebrew/bin/ffmpeg"
            elif os.path.exists("/usr/local/bin/ffmpeg"):
                ffmpeg_exe = "/usr/local/bin/ffmpeg"
            else:
                ffmpeg_exe = "ffmpeg"
        
        try:
            cmd = [ffmpeg_exe, '-y']
            for chunk_path, chunk_zoom in self.chunks:
                cmd.extend(['-i', chunk_path])
            
            filter_str = ""
            for i, (chunk_path, chunk_zoom) in enumerate(self.chunks):
                if chunk_zoom > 1.0:
                    filter_str += f"[{i}:v:0]crop=iw/{chunk_zoom}:ih/{chunk_zoom}:(iw-iw/{chunk_zoom})/2:(ih-ih/{chunk_zoom})/2,scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1[v{i}];"
                else:
                    filter_str += f"[{i}:v:0]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1[v{i}];"
                filter_str += f"[{i}:a:0]aformat=sample_rates=16000:channel_layouts=mono[a{i}];"
            
            for i in range(len(self.chunks)):
                filter_str += f"[v{i}][a{i}]"
            filter_str += f"concat=n={len(self.chunks)}:v=1:a=1[outv][outa]"
            
            cmd.extend(['-filter_complex', filter_str, 
                        '-map', '[outv]', '-map', '[outa]', 
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', 
                        merged_mp4])
                        
            log_path = os.path.expanduser("~/Desktop/ffmpeg_error.log")
            with open(log_path, "w") as log_file:
                log_file.write(f"--- FFMPEG VIDEO MERGE LOG ---\nFFmpeg Exe: {ffmpeg_exe}\nCommand: {' '.join(cmd)}\n")
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=log_file, check=False)
            
            fd, merged_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            
            with open(log_path, "a") as log_file:
                log_file.write(f"\n--- FFMPEG AUDIO EXTRACTION LOG ---\n")
                subprocess.run([ffmpeg_exe, '-y', '-i', merged_mp4, '-vn', '-ar', '16000', '-ac', '1', merged_wav], stdout=subprocess.DEVNULL, stderr=log_file, check=False)
        except Exception as e:
            print(f"FFmpeg Merge Error: {e}")
            # Ensure we don't hang if it crashes
            merged_mp4 = self.chunks[0][0] if self.chunks else ""
            merged_wav = ""
        
        new_title = ""
        if self.current_memo and self.current_memo.get("id") != "preview":
            new_title = self.memo_manager.update_memo_audio(self.current_memo["id"], merged_wav)
            self.memo_manager.update_memo_mp4(self.current_memo["id"], merged_mp4)
        else:
            new_title = self.memo_manager.save_new_memo(merged_wav, temp_mp4_path=merged_mp4)
            
        self.finished_signal.emit(new_title, merged_mp4, merged_wav)
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
    text_saved = pyqtSignal(str)
    
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

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if not self.isReadOnly():
            self.text_saved.emit(self.toPlainText())

    def set_transcript(self, transcript_data):
        self.transcript_data = transcript_data
        self._render_text()
        
    def _render_text(self):
        if not self.transcript_data:
            self.setReadOnly(True)
            self.setHtml("""
                <div style='color:#888; text-align:center; padding-top: 100px; font-family: -apple-system, system-ui;'>
                    <h3 style='color:#a0a0a5;'>No transcript</h3>
                    <p style='color:#666; margin-top: 10px;'>Click 'Transcribe' to generate text.</p>
                    <br><br>
                    <p style='color:#555;'><i>Tip: You can drag & drop any video or audio file<br>directly into this window to import it as a memo.</i></p>
                </div>
            """)
            return
            
        # If it's a string (Voice-Editor format or Refined text)
        if isinstance(self.transcript_data, str):
            self.setReadOnly(False)
            html_text = self.transcript_data.replace('\n', '<br>')
            self.setHtml(f"<p style='color:#f1f2f6;'>{html_text}</p>")
            # Auto-scroll to bottom
            from PyQt6.QtGui import QTextCursor
            self.moveCursor(QTextCursor.MoveOperation.End)
            return
            
        # If it's verbose_json format (timestamped)
        self.setReadOnly(True)
        html = "<p style='color:#f1f2f6;'>"
        words = self.transcript_data.get("words", [])
        has_active = False
        for i, word_obj in enumerate(words):
            word = word_obj.get("word", "")
            start = word_obj.get("start", 0.0)
            end = word_obj.get("end", 0.0)
            
            color = "#f1f2f6"
            if start <= self.current_time <= end:
                color = "#0a84ff"
                html += f"<a name='active'></a><span style='color:{color};'>{word}</span> "
                has_active = True
            else:
                html += f"<span style='color:{color};'>{word}</span> "
        html += "</p>"
        self.setHtml(html)
        if has_active:
            self.scrollToAnchor("active")

    def update_time(self, current_time):
        self.current_time = current_time
        # Re-render only if timestamped
        if isinstance(self.transcript_data, dict) and "words" in self.transcript_data:
            self._render_text()


class ImportWorker(QThread):
    finished_signal = pyqtSignal(bool)
    
    def __init__(self, file_path, target_dir):
        super().__init__()
        self.file_path = file_path
        self.target_dir = target_dir
        
    def run(self):
        import os, shutil, subprocess
        from datetime import datetime
        
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        target_base = os.path.join(self.target_dir, base_name)
        idx = 1
        while os.path.exists(f"{target_base}.wav"):
            target_base = os.path.join(self.target_dir, f"{base_name}_{idx}")
            idx += 1
            
        out_wav = f"{target_base}.wav"
        out_mp4 = f"{target_base}.mp4"
        
        ffmpeg_exe = shutil.which("ffmpeg")
        if not ffmpeg_exe:
            if os.path.exists("/opt/homebrew/bin/ffmpeg"): ffmpeg_exe = "/opt/homebrew/bin/ffmpeg"
            elif os.path.exists("/usr/local/bin/ffmpeg"): ffmpeg_exe = "/usr/local/bin/ffmpeg"
            else: ffmpeg_exe = "ffmpeg"
            
        subprocess.run([ffmpeg_exe, '-y', '-i', self.file_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', out_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        probe_cmd = [ffmpeg_exe, '-i', self.file_path]
        result = subprocess.run(probe_cmd, stderr=subprocess.PIPE, text=True)
        if 'Video:' in result.stderr:
            if self.file_path.lower().endswith('.mp4'):
                shutil.copy(self.file_path, out_mp4)
            else:
                subprocess.run([ffmpeg_exe, '-y', '-i', self.file_path, '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', out_mp4], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        self.finished_signal.emit(True)

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
        self.setAcceptDrops(True)
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._on_player_position)
        self.player.playbackStateChanged.connect(self._on_player_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        
        self._init_ui()
        self.load_memos()
        
        self.recorder.signal_amplitude.connect(self._on_amplitude)
        self.recorder.signal_state_changed.connect(self._on_record_state)
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(100)
        self.record_timer.timeout.connect(self._update_record_time)
        self.record_duration = 0.0
        
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
        self.search_bar.textChanged.connect(self._on_search)
        left_layout.addWidget(self.search_bar)
        
        self.memo_list = QListWidget()
        self.memo_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.memo_list.setStyleSheet("""
            QListWidget { border: none; background-color: #1e1e24; outline: none; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #2c2c34; }
            QListWidget::item:selected { background-color: #0a84ff; }
        """)
        self.memo_list.itemSelectionChanged.connect(self._on_selection_changed)
        
        def _list_key_press(event):
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.delete_current_memo()
            else:
                QListWidget.keyPressEvent(self.memo_list, event)
        self.memo_list.keyPressEvent = _list_key_press
        
        left_layout.addWidget(self.memo_list)
        
        # New Memo button area
        new_memo_area = QWidget()
        new_memo_area.setStyleSheet("background-color: #1a1a20; border-top: 1px solid #2c2c34;")
        nma_layout = QHBoxLayout(new_memo_area)
        
        self.btn_new = QPushButton("➕ New Memo")
        self.btn_new.setStyleSheet("font-weight: bold; background-color: #3a3a44; border-radius: 6px; padding: 10px 20px; font-size: 14px;")
        self.btn_new.clicked.connect(self._on_new_memo)
        
        self.btn_camera = QPushButton("📷 Off")
        self.btn_camera.setCheckable(True)
        self.btn_camera.setStyleSheet("font-weight: bold; background-color: #3a3a44; border-radius: 6px; padding: 10px 20px; font-size: 14px;")
        self.btn_camera.toggled.connect(self._toggle_camera_mode)
        
        from PyQt6.QtWidgets import QSlider
         
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 50) # 1.0x to 5.0x
        self.zoom_slider.setValue(10)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setVisible(False)
        self.current_zoom = 1.0
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        
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
        self.transcript_view.text_saved.connect(self._on_transcript_edited)
        self.waveform_view = WaveformWidget()
        self.waveform_view.setFixedHeight(120)
        self.waveform_view.signal_seek.connect(self._on_seek)
        
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        from PyQt6.QtMultimedia import QMediaCaptureSession, QCamera, QMediaRecorder, QAudioInput, QMediaFormat
        from PyQt6.QtWidgets import QStackedWidget
        self.video_stack = QStackedWidget()
        self.video_stack.setVisible(False)
        self.video_stack.setFixedSize(533, 300)
        
        from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
        from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
        
        self.camera_item = QGraphicsVideoItem()
        self.camera_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.camera_scene = QGraphicsScene()
        self.camera_scene.addItem(self.camera_item)
        self.camera_view = QGraphicsView(self.camera_scene)
        self.camera_view.setStyleSheet("background: black; border: none;")
        self.camera_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.camera_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.camera_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        self.player_view = QVideoWidget()
        
        self.poster_label = QLabel()
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("background-color: black;")
        
        self.video_stack.addWidget(self.camera_view)
        self.video_stack.addWidget(self.player_view)
        self.video_stack.addWidget(self.poster_label)
        
        right_layout.addWidget(self.transcript_view, 1)
        right_layout.addWidget(self.video_stack, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.waveform_view, 0)
        
        self.camera = QCamera()
        self.audio_in = QAudioInput()
        self.capture_session = QMediaCaptureSession()
        self.capture_session.setCamera(self.camera)
        self.capture_session.setAudioInput(self.audio_in)
        
        # Force camera to 16:9 widescreen format to match the UI and output
        from PyQt6.QtMultimedia import QCameraFormat
        from PyQt6.QtCore import QSize
        best_format = None
        for fmt in self.camera.cameraDevice().videoFormats():
            res = fmt.resolution()
            if res.width() > 0 and res.height() > 0:
                ratio = res.width() / res.height()
                if abs(ratio - 16/9) < 0.1:  # 16:9 formats only
                    if best_format is None:
                        best_format = fmt
                    else:
                        # Prefer 1280x720
                        if res.width() == 1280:
                            best_format = fmt
        if best_format:
            self.camera.setCameraFormat(best_format)
        
        self.video_recorder = QMediaRecorder()
        fmt = QMediaFormat()
        fmt.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        self.video_recorder.setMediaFormat(fmt)
        
        self.capture_session.setRecorder(self.video_recorder)
        self.capture_session.setVideoOutput(self.camera_item)
        
        # Center the video item in the view when it resizes
        def resize_view(event):
            from PyQt6.QtCore import QSizeF
            size = self.camera_view.viewport().size()
            self.camera_item.setSize(QSizeF(size))
            self.camera_scene.setSceneRect(0, 0, size.width(), size.height())
            QGraphicsView.resizeEvent(self.camera_view, event)
        self.camera_view.resizeEvent = resize_view
        self.player.setVideoOutput(self.player_view)
        self.is_video_mode = False
        self.video_chunks = []
        # self.video_recorder.recorderStateChanged.connect(self._on_video_state_changed)
        
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
        controls.addWidget(self.btn_camera)
        controls.addWidget(self.zoom_slider)
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
            # Pre-cache search text
            search_text = m["title"].lower()
            if m.get("has_refined") and m.get("txt_path"):
                try:
                    with open(m["txt_path"], "r") as f:
                        search_text += " " + f.read().lower()
                except: pass
            if m.get("has_timestamped") and m.get("json_path"):
                try:
                    import json
                    with open(m["json_path"], "r") as f:
                        data = json.load(f)
                        search_text += " " + data.get("text", "").lower()
                except: pass
            m["search_text"] = search_text

            dur_str = f"{int(m['duration']//60):02d}:{int(m['duration']%60):02d}"
            
            icons = []
            if m["has_refined"]: icons.append("📝")
            if m["has_timestamped"]: icons.append("⏱️")
            if hasattr(self, 'transcribing_ids') and m["id"] in self.transcribing_ids:
                icons.append("⏳")
                
            icon_str = " ".join(icons)
            title = f"{m['title']} {icon_str}".strip()
            
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, m)
            
            widget = QWidget()
            main_layout = QHBoxLayout(widget)
            main_layout.setContentsMargins(5, 5, 5, 5)
            main_layout.setSpacing(10)
            
            # Thumbnail
            lbl_thumb = QLabel()
            lbl_thumb.setFixedSize(50, 50)
            lbl_thumb.setStyleSheet("background-color: #333; border-radius: 4px;")
            lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if m.get("mp4_path"):
                import os, shutil, subprocess
                thumb_path = m["mp4_path"].replace(".mp4", ".jpg")
                if not os.path.exists(thumb_path):
                    ffmpeg_exe = shutil.which("ffmpeg")
                    if not ffmpeg_exe:
                        if os.path.exists("/opt/homebrew/bin/ffmpeg"): ffmpeg_exe = "/opt/homebrew/bin/ffmpeg"
                        elif os.path.exists("/usr/local/bin/ffmpeg"): ffmpeg_exe = "/usr/local/bin/ffmpeg"
                        else: ffmpeg_exe = "ffmpeg"
                        
                    log_path = os.path.expanduser("~/Desktop/ffmpeg_error.log")
                    with open(log_path, "a") as log_file:
                        log_file.write(f"\n--- FFMPEG THUMBNAIL LOG ---\n")
                        subprocess.run([ffmpeg_exe, '-y', '-i', m['mp4_path'], '-vframes', '1', '-q:v', '2', '-vf', 'scale=50:50:force_original_aspect_ratio=increase,crop=50:50', thumb_path], stdout=subprocess.DEVNULL, stderr=log_file, check=False)
                
                if os.path.exists(thumb_path):
                    from PyQt6.QtGui import QPixmap
                    pix = QPixmap(thumb_path).scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    lbl_thumb.setPixmap(pix)
                else:
                    lbl_thumb.setText("🎥")
            else:
                lbl_thumb.setText("🎵")
                lbl_thumb.setStyleSheet("background-color: #333; border-radius: 4px; font-size: 24px;")
            
            main_layout.addWidget(lbl_thumb)
            
            # Text Area
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #f1f2f6; background: transparent;")
            
            lbl_snippet = QLabel("")
            lbl_snippet.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent;")
            lbl_snippet.setWordWrap(True)
            lbl_snippet.setVisible(False)
            
            text_layout.addWidget(lbl_title)
            text_layout.addWidget(lbl_snippet)
            text_layout.addStretch()
            
            main_layout.addLayout(text_layout)
            
            widget.setStyleSheet("background: transparent;")
            from PyQt6.QtCore import QSize
            item.setSizeHint(QSize(250, 60))
            
            self.memo_list.addItem(item)
            self.memo_list.setItemWidget(item, widget)
            
            m["lbl_title"] = lbl_title
            m["lbl_snippet"] = lbl_snippet
            m["list_item"] = item
            m["widget"] = widget
            
            if current_id == m["id"]:
                self.memo_list.setCurrentItem(item)
                self.current_memo = m
            

    def _on_zoom_changed(self, value):
        factor = value / 10.0
        self.current_zoom = factor
        if hasattr(self, 'camera_item'):
            from PyQt6.QtCore import QPointF
            w = self.camera_item.boundingRect().width()
            h = self.camera_item.boundingRect().height()
            self.camera_item.setTransformOriginPoint(QPointF(w / 2, h / 2))
            self.camera_item.setScale(factor)
        
        # If actively recording video, segment the current chunk so each
        # segment gets its own zoom value baked in by FFmpeg
        if self.is_video_mode and hasattr(self, 'video_recorder'):
            from PyQt6.QtMultimedia import QMediaRecorder
            if self.video_recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
                # Debounce: cancel any pending segment to avoid rapid-fire splits
                if hasattr(self, '_zoom_segment_timer') and self._zoom_segment_timer.isActive():
                    self._zoom_segment_timer.stop()
                
                def _do_segment():
                    # Stop current chunk — FFmpeg will apply the zoom at chunk start
                    self.video_recorder.stop()
                    # Wait for file to flush then start new chunk with updated zoom
                    def _poll_seg_stopped():
                        if self.video_recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState:
                            self._seg_poll_timer.stop()
                            QTimer.singleShot(300, self._start_video_recording_internal)
                    self._seg_poll_timer = QTimer(self)
                    self._seg_poll_timer.timeout.connect(_poll_seg_stopped)
                    self._seg_poll_timer.start(50)
                
                self._zoom_segment_timer = QTimer(self)
                self._zoom_segment_timer.setSingleShot(True)
                self._zoom_segment_timer.timeout.connect(_do_segment)
                self._zoom_segment_timer.start(400)  # wait 400ms after slider stops moving
                
    def _toggle_camera_mode(self, checked):
        self.is_video_mode = checked
        if checked:
            try:
                import ctypes, os, sys
                if getattr(sys, 'frozen', False):
                    dylib_path = os.path.join(sys._MEIPASS, 'librequestcam.dylib')
                else:
                    dylib_path = os.path.join(os.path.dirname(__file__), '..', '..', 'librequestcam.dylib')
                if os.path.exists(dylib_path):
                    cam_lib = ctypes.cdll.LoadLibrary(dylib_path)
                    cam_lib.trigger_camera_prompt()
            except Exception as e:
                print(f"Failed to trigger camera prompt: {e}")

            self.btn_camera.setText("📷 On")
            self.btn_camera.setStyleSheet("font-weight: bold; background-color: #0a84ff; border-radius: 6px; padding: 10px 20px; font-size: 14px;")
            
            # Re-initialize camera in case it was empty before permission
            from PyQt6.QtMultimedia import QCamera
            self.camera = QCamera()
            self.capture_session.setCamera(self.camera)

            self.capture_session.setVideoOutput(self.camera_item)
            
            self.video_stack.setCurrentWidget(self.camera_view)
            self.video_stack.setVisible(True)
            if hasattr(self, 'zoom_slider'): self.zoom_slider.setVisible(True)
            self.camera.start()
        else:
            self.btn_camera.setText("📷 Off")
            self.btn_camera.setStyleSheet("font-weight: bold; background-color: #3a3a44; border-radius: 6px; padding: 10px 20px; font-size: 14px;")
            self.video_stack.setVisible(False)
            if hasattr(self, 'zoom_slider'): self.zoom_slider.setVisible(False)
            self.camera.stop()

    def _on_video_state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaRecorder
        if state == QMediaRecorder.RecorderState.RecordingState:
            self._on_record_state("recording")
        elif state == QMediaRecorder.RecorderState.PausedState:
            self._on_record_state("paused")
        elif state == QMediaRecorder.RecorderState.StoppedState:
            self._on_record_state("idle")

    def _start_video_recording_internal(self):
        import tempfile, os
        from PyQt6.QtCore import QUrl
        if not hasattr(self, 'video_chunks') or not self.video_chunks:
            if hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("id") != "preview":
                self.record_duration = self.current_memo.get("duration", 0.0)
            else:
                self.record_duration = 0.0
        if self.is_playing:
            self.stop_playback()
        fd, temp_mp4 = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        if not hasattr(self, 'video_chunks'): self.video_chunks = []
        if not self.video_chunks and hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("id") != "preview":
            if self.current_memo.get("mp4_path"):
                self.video_chunks.append((self.current_memo["mp4_path"], 1.0))
        self.video_chunks.append((temp_mp4, self.current_zoom))
        self.video_recorder.setOutputLocation(QUrl.fromLocalFile(temp_mp4))
        self.video_recorder.record()
        self.is_video_recording_active = True
        self._on_record_state("recording")

    def toggle_recording(self):
        just_turned_on = False
        # Auto-enable camera if we are appending to a video memo
        if hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("mp4_path") and not self.is_video_mode:
            self.btn_camera.setChecked(True)
            self._toggle_camera_mode(True)
            just_turned_on = True
            
        if self.is_video_mode:
            from PyQt6.QtMultimedia import QMediaRecorder
            if getattr(self, 'is_video_recording_active', False):
                self.btn_record.setEnabled(False)  # lock button to prevent double-click corruption
                self.video_recorder.stop() # stop so it writes the chunk
                self.is_video_recording_active = False
                
                # Poll until truly stopped before enabling pause state
                def _poll_pause_stopped():
                    if self.video_recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState:
                        self._pause_timer.stop()
                        self._on_record_state("paused")
                        self.btn_record.setEnabled(True)
                        
                from PyQt6.QtCore import QTimer
                self._pause_timer = QTimer(self)
                self._pause_timer.timeout.connect(_poll_pause_stopped)
                self._pause_timer.start(50)
            else:
                if just_turned_on:
                    # Hard delay to guarantee AVFoundation camera initialization before recording
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(1500, self._start_video_recording_internal)
                else:
                    self._start_video_recording_internal()
        else:
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

    def _on_ffmpeg_done(self, new_title, merged_mp4, merged_wav):
        self.btn_done.setEnabled(True)
        self.btn_done.setVisible(False)
        self.btn_record.setEnabled(True)
        self.btn_play.setVisible(True)
        self.title_edit.setText(new_title)
        self.video_chunks = []
        self._on_record_state("idle")
        
        # Turn camera off FIRST so AVFoundation fully releases the hardware
        # before the player tries to load the new file
        if hasattr(self, 'btn_camera') and self.btn_camera.isChecked():
            self.btn_camera.setChecked(False)
        
        self.load_memos()
        
        def _select_after_camera_stop():
            for i in range(self.memo_list.count()):
                item = self.memo_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole)["title"] == new_title:
                    self.memo_list.setCurrentItem(item)
                    self._on_memo_selected(item)
                    break
        
        # 400ms delay lets camera hardware fully release before player loads
        QTimer.singleShot(400, _select_after_camera_stop)

    def finish_recording(self):
        if self.is_playing:
            self.stop_playback()
            
        real = getattr(self, 'real_title', None)
        if real and real not in ["Paused", "Recording..."]:
            self.title_edit.setText(real)
        self.real_title = None
            
        import os, tempfile, subprocess
        if self.is_video_mode:
            from PyQt6.QtMultimedia import QMediaRecorder
            already_stopped = self.video_recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState
            if not already_stopped:
                self.video_recorder.stop()
            
            if hasattr(self, 'video_chunks') and self.video_chunks:
                # Show processing UI immediately
                self.title_edit.setText("⏳ Processing video...")
                self.btn_done.setEnabled(False)
                self.btn_done.setVisible(True)
                self.btn_record.setEnabled(False)
                self.btn_play.setVisible(False)
                
                c_memo = None
                if hasattr(self, 'current_memo') and self.current_memo:
                    c_memo = self.current_memo
                
                def _start_ffmpeg():
                    self.worker = FFmpegWorker(self.video_chunks, self.memo_manager, c_memo)
                    self.worker.finished_signal.connect(self._on_ffmpeg_done)
                    self.worker.start()
                
                if already_stopped:
                    # Even if already stopped, give OS 500ms to flush the file to disk
                    QTimer.singleShot(500, _start_ffmpeg)
                else:
                    # Wait for StoppedState via polling, then flush delay
                    def _poll_recorder_stopped():
                        if self.video_recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState:
                            self._stop_poll_timer.stop()
                            QTimer.singleShot(500, _start_ffmpeg)
                    self._stop_poll_timer = QTimer(self)
                    self._stop_poll_timer.timeout.connect(_poll_recorder_stopped)
                    self._stop_poll_timer.start(50)
        else:
            temp_path = None
            if self.recorder.is_recording:
                temp_path = self.recorder.stop_recording()
                
            if temp_path and os.path.exists(temp_path):
                if hasattr(self, 'current_memo') and self.current_memo and self.current_memo.get("id") != "preview":
                    new_title = self.memo_manager.update_memo_audio(self.current_memo["id"], temp_path)
                else:
                    new_title = self.memo_manager.save_new_memo(temp_path)
                self._on_record_state("idle")
                self.load_memos()
                for i in range(self.memo_list.count()):
                    item = self.memo_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)["title"] == new_title:
                        self.memo_list.setCurrentItem(item)
                        self._on_memo_selected(item)
                        break


    def _on_record_state(self, state):
        if state == "recording":
            self.btn_play.setVisible(False)
            self.btn_camera.setEnabled(False)  # lock — can't switch type mid-recording
            self.record_timer.start()
            self.btn_record.setText("⏸️")
            self.btn_record.setStyleSheet("border-radius: 25px; background-color: #f39c12; font-size: 20px;")
            self.btn_done.setVisible(True)
            if not getattr(self, 'real_title', None): self.real_title = self.title_edit.text()
            self.title_edit.setText("Recording...")
            self.memo_list.setEnabled(False)
            if self.is_playing:
                self.stop_playback()
        elif state == "paused":
            # In video mode there's no merged preview to play yet — hide the button
            self.btn_play.setVisible(not self.is_video_mode)
            self.btn_camera.setEnabled(False)  # still locked during pause
            self.record_timer.stop()
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
            self.btn_play.setVisible(True)
            self.btn_camera.setEnabled(True)  # unlock — recording done
            self.record_timer.stop()
            self.btn_record.setText("🔴")
            self.btn_record.setStyleSheet("border-radius: 25px; background-color: #ff4757; font-size: 20px;")
            self.btn_done.setVisible(False)
            self.memo_list.setEnabled(True)
            
    def _update_record_time(self):
        self.record_duration += 0.1
        self.lbl_time.setText(f"{int(self.record_duration//60):02d}:{self.record_duration%60:05.2f}")

    def _on_amplitude(self, amp):
        if not self.recorder.is_recording: return
        self.waveform_view.add_amplitude(amp)
        
    def _on_new_memo(self):
        self.memo_list.clearSelection()
        self.current_memo = None
        self.title_edit.setText("New Recording")
        self.transcript_view.set_transcript(None)
        self.waveform_view.amplitudes.clear()
        self.waveform_view.update()
        self.waveform_view.set_progress(0)
        self.lbl_time.setText("00:00.00 / 00:00.00")
        if hasattr(self, 'video_stack'):
            self.video_stack.setVisible(False)
        if self.is_playing:
            self.stop_playback()
        # Explicitly turn camera off and reset state
        if hasattr(self, 'btn_camera') and self.btn_camera.isChecked():
            self.btn_camera.setChecked(False)  # toggled signal fires _toggle_camera_mode(False)
        # Reset zoom to 1.0x
        if hasattr(self, 'zoom_slider'):
            self.zoom_slider.setValue(10)

    def _on_search(self, text):
        text = text.lower()
        for i in range(self.memo_list.count()):
            item = self.memo_list.item(i)
            memo = item.data(Qt.ItemDataRole.UserRole)
            
            search_text = memo.get("search_text", "")
            match = text in search_text or text in memo["title"].lower()
            
            item.setHidden(not match)
            
            if not match:
                continue
                
            lbl_snippet = memo.get("lbl_snippet")
            widget = memo.get("widget")
            
            if not text:
                if lbl_snippet: lbl_snippet.setVisible(False)
                if widget:
                    from PyQt6.QtCore import QSize
                    item.setSizeHint(QSize(250, 45))
                continue
                
            if match and text in search_text:
                # Find snippet context
                idx = search_text.find(text)
                if idx != -1:
                    start = max(0, idx - 30)
                    end = min(len(search_text), idx + len(text) + 30)
                    snippet = search_text[start:end]
                    if start > 0: snippet = "..." + snippet
                    if end < len(search_text): snippet = snippet + "..."
                    
                    # Highlight the exact typed text
                    import re
                    highlighted = re.sub(f"({re.escape(text)})", r'<span style="background-color: #f1c40f; color: black;">\1</span>', snippet, flags=re.IGNORECASE)
                    
                    if lbl_snippet:
                        lbl_snippet.setText(highlighted)
                        lbl_snippet.setVisible(True)
                        if widget:
                            from PyQt6.QtCore import QSize
                            item.setSizeHint(QSize(250, 80))
            elif lbl_snippet:
                lbl_snippet.setVisible(False)
                if widget:
                    from PyQt6.QtCore import QSize
                    item.setSizeHint(QSize(250, 45))

    def _on_memo_selected(self, item):
        self.current_memo = item.data(Qt.ItemDataRole.UserRole)
        self.title_edit.setText(self.current_memo["title"])
        self.stop_playback()
        self.play_pos = 0
        
        import os
        # Ensure camera is off to prevent native overlay conflicts
        if hasattr(self, 'btn_camera') and self.btn_camera.isChecked():
            self.btn_camera.setChecked(False)
            
        mp4_path = self.current_memo["file_path"].replace('.wav', '.mp4')
        if os.path.exists(mp4_path):
            file_url = QUrl.fromLocalFile(mp4_path)
             
            self.video_stack.setCurrentWidget(self.poster_label)
            
            poster_path = mp4_path.replace(".mp4", "_poster.jpg")
            import os, shutil, subprocess
            if not os.path.exists(poster_path):
                ffmpeg_exe = shutil.which("ffmpeg")
                if not ffmpeg_exe:
                    if os.path.exists("/opt/homebrew/bin/ffmpeg"): ffmpeg_exe = "/opt/homebrew/bin/ffmpeg"
                    elif os.path.exists("/usr/local/bin/ffmpeg"): ffmpeg_exe = "/usr/local/bin/ffmpeg"
                    else: ffmpeg_exe = "ffmpeg"
                subprocess.run([ffmpeg_exe, '-y', '-i', mp4_path, '-vframes', '1', '-q:v', '2', '-vf', 'scale=533:300:force_original_aspect_ratio=increase,crop=533:300', poster_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                
            if os.path.exists(poster_path):
                from PyQt6.QtGui import QPixmap
                pix = QPixmap(poster_path)
                self.poster_label.setPixmap(pix)
            
            self.video_stack.setVisible(True)
        else:
            file_url = QUrl.fromLocalFile(self.current_memo["file_path"])
            self.video_stack.setVisible(False)
             
            
        # Clear first so Qt always triggers a fresh load even if it's the same file path
        self.player.setSource(QUrl())
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

    def _on_selection_changed(self):
        selected = self.memo_list.selectedItems()
        if len(selected) == 1:
            self._on_memo_selected(selected[0])
        # If 0 or >1 items selected, leave right panel as-is

    def delete_current_memo(self):
        selected = self.memo_list.selectedItems()
        if not selected: return
        
        # Collect IDs being deleted
        deleting_ids = set()
        for item in selected:
            memo = item.data(Qt.ItemDataRole.UserRole)
            if memo:
                deleting_ids.add(memo["id"])
                
        if len(selected) == 1:
            memo = selected[0].data(Qt.ItemDataRole.UserRole)
            title = memo.get("title", "this memo") if memo else "this memo"
            msg = f"Are you sure you want to delete '{title}'?"
        else:
            msg = f"Are you sure you want to delete {len(selected)} memos?"
            
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, 'Confirm Delete', msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        
        # If the currently previewed memo is one being deleted, stop and clear it
        if self.current_memo and self.current_memo.get("id") in deleting_ids:
            self.stop_playback()
            self.player.setSource(QUrl())
            self.video_stack.setVisible(False)
            self.waveform_view.amplitudes.clear()
            self.waveform_view.update()
            self.lbl_time.setText("00:00.00 / 00:00.00")
            self.title_edit.setText("New Recording")
            self.transcript_view.set_transcript(None)
            self.current_memo = None
        
        for item in selected:
            memo = item.data(Qt.ItemDataRole.UserRole)
            if memo:
                self.memo_manager.delete_memo(memo["id"])
        
        self.load_memos()
        


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
        
        if hasattr(self, 'btn_camera') and self.btn_camera.isChecked():
            self.btn_camera.setChecked(False)
            
        import os
        mp4_path = self.current_memo["file_path"].replace('.wav', '.mp4')
        if os.path.exists(mp4_path):
            self.video_stack.setCurrentWidget(self.player_view)
            self.video_stack.setVisible(True)
            
        if self.is_playing:
            self._play_requested = False
            self.stop_playback()
        else:
            from PyQt6.QtMultimedia import QMediaPlayer
            if self.player.mediaStatus() in (
                QMediaPlayer.MediaStatus.NoMedia,
                QMediaPlayer.MediaStatus.LoadingMedia,
            ):
                # Player not ready yet — queue the play command
                self._play_requested = True
                self.btn_play.setText("⏸️")  # show intent immediately
            else:
                self._play_requested = False
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
        if hasattr(self, 'current_memo') and self.current_memo:
            import os
            mp4_path = self.current_memo["file_path"].replace('.wav', '.mp4')
            if os.path.exists(mp4_path):
                self.video_stack.setCurrentWidget(self.poster_label)

    def _on_player_position(self, pos_ms):
        if not self.current_memo: return
        curr_time = pos_ms / 1000.0
        dur = self.current_memo["duration"]
        
        if dur > 0:
            self.lbl_time.setText(f"{int(curr_time//60):02d}:{curr_time%60:05.2f} / {int(dur//60):02d}:{dur%60:05.2f}")
            self.waveform_view.set_progress(curr_time / dur)
            self.transcript_view.update_time(curr_time)

    def _on_media_status(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        # Both LoadedMedia and BufferedMedia mean the player is ready
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if getattr(self, '_play_requested', False):
                self._play_requested = False
                self.start_playback()

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
    def _on_transcript_edited(self, new_text):
        if not self.current_memo or not self.current_memo.get("has_refined"):
            return
        mode = getattr(self, 'active_transcript_mode', 'timestamped' if self.current_memo.get("has_timestamped") else 'refined')
        if mode == "refined":
            try:
                with open(self.current_memo["txt_path"], "w") as f:
                    f.write(new_text)
            except Exception as e:
                print(f"Error saving transcript: {e}")

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
                            timestamp_granularities=["word"],
                            prompt="Hello, welcome to my audio memo. Please transcribe this correctly, including punctuation, commas, and periods."
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

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        
        file_path = urls[0].toLocalFile()
        if not file_path:
            return
            
        ext = file_path.lower().split('.')[-1]
        if ext not in ['mp4', 'mov', 'mkv', 'avi', 'wav', 'mp3', 'm4a', 'aac', 'flac', 'webm']:
            return
            
        self.btn_done.setText("Importing...")
        self.btn_done.setEnabled(False)
        self.import_worker = ImportWorker(file_path, self.memo_manager.folder_path)
        self.import_worker.finished_signal.connect(self._on_import_done)
        self.import_worker.start()

    def _on_import_done(self, success):
        self.btn_done.setText("Done")
        self.btn_done.setEnabled(True)
        self.load_memos()
