import sys
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QWidget, QGraphicsDropShadowEffect, QApplication, QComboBox
)
import pyperclip
from ..history_manager import HistoryManager


class EditorWindow(QDialog):
    signal_show_recording = pyqtSignal(bool)
    signal_update_partial = pyqtSignal(str)
    signal_show_transcribing = pyqtSignal(str)
    signal_show_finished = pyqtSignal(str)
    signal_append_text = pyqtSignal(str)
    signal_cut_speech = pyqtSignal()
    signal_close = pyqtSignal()
    signal_show_idle = pyqtSignal()

    def __init__(self, on_done_callback=None, on_cut_callback=None, on_stop_callback=None,
                 on_continue_callback=None, on_new_callback=None, on_settings_callback=None,
                 on_start_recording_callback=None, on_sessions_callback=None, on_recordings_callback=None, parent=None):
        super().__init__(parent)
        self.on_done_callback = on_done_callback
        self.on_cut_callback = on_cut_callback
        self.on_stop_callback = on_stop_callback
        self.on_continue_callback = on_continue_callback
        self.on_new_callback = on_new_callback
        self.on_settings_callback = on_settings_callback
        self.on_start_recording_callback = on_start_recording_callback
        self.on_sessions_callback = on_sessions_callback
        self.on_recordings_callback = on_recordings_callback
        self.history_mgr = HistoryManager()
        # For drag support
        self._drag_pos: QPoint | None = None
        self._init_ui()
        self._connect_signals()
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(self._reset_copy_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _init_ui(self):
        self.setWindowTitle("VoiceKit Editor")
        self.resize(640, 560)
        self.setWindowFlags(Qt.WindowType.Window)

        # Main glassmorphism container
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("QDialog { background-color: #1e1e24; }")
        self.container = QWidget(self)
        self.container.setObjectName("editorContainer")
        self.container.setStyleSheet("""
            QWidget#editorContainer {
                background-color: #1e1e24;
                border: none;
            }
            QLabel {
                color: #f1f2f6;
                font-family: '.AppleSystemUIFont', -apple-system, 'Helvetica Neue', sans-serif;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#dragHint {
                color: rgba(255,255,255,0.25);
                font-size: 11px;
                font-weight: 400;
            }
            QPlainTextEdit {
                background-color: rgba(18, 18, 22, 0.85);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 10px;
                font-family: '.AppleSystemUIFont', -apple-system, 'Helvetica Neue', sans-serif;
                font-size: 15px;
                line-height: 1.4;
            }
            QPlainTextEdit:focus {
                border: 1px solid #70a1ff;
            }
            QPlainTextEdit#liveTextBox {
                background-color: rgba(15, 15, 20, 0.6);
                color: #a4b0be;
                font-style: italic;
                font-size: 13px;
                border: 1px dashed rgba(255, 255, 255, 0.15);
            }
            QComboBox {
                background-color: rgba(45, 52, 54, 0.9);
                color: #f1f2f6;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 13px;
                min-width: 180px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2f3542;
                color: #ffffff;
                selection-background-color: #70a1ff;
                selection-color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
            }
            QPushButton {
                font-family: '.AppleSystemUIFont', -apple-system, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 14px;
                border-radius: 8px;
                border: none;
            }
            QPushButton#btnCancel {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ced6e0;
            }
            QPushButton#btnCancel:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton#btnCloseHeader {
                background-color: rgba(255, 255, 255, 0.08);
                color: #a4b0be;
                font-size: 14px;
                font-weight: 700;
                border-radius: 14px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
            }
            QPushButton#btnCloseHeader:hover {
                background-color: #ff4757;
                color: #ffffff;
            }
            QPushButton#btnCopy {
                background-color: rgba(112, 161, 255, 0.2);
                color: #70a1ff;
                border: 1px solid rgba(112, 161, 255, 0.4);
            }
            QPushButton#btnCopy:hover {
                background-color: rgba(112, 161, 255, 0.35);
            }
            QPushButton#btnContinue {
                background-color: #3742fa;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#btnContinue:hover {
                background-color: #5352ed;
            }
            QPushButton#btnNew {
                background-color: rgba(255, 255, 255, 0.12);
                color: #f1f2f6;
                font-weight: 600;
            }
            QPushButton#btnNew:hover {
                background-color: rgba(255, 255, 255, 0.22);
            }
            QPushButton#btnDone {
                background-color: #2ed573;
                color: #1e272e;
                font-weight: 700;
            }
            QPushButton#btnDone:hover {
                background-color: #26af5f;
            }
            QPushButton#btnCut {
                background-color: #ff4757;
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 14px;
            }
            QPushButton#btnCut:hover {
                background-color: #ff6b81;
            }
            QPushButton#btnStopRecord {
                background-color: #eccc68;
                color: #2f3542;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 14px;
            }
            QPushButton#btnStopRecord:hover {
                background-color: #ffa502;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                color: #747d8c;
                border: none;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(18, 18, 18, 18)
        container_layout.setSpacing(10)

        # Header bar with Status and History ComboBox
        header_layout = QHBoxLayout()
        self.lbl_status = QLabel("🔴 Recording Audio...")
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch()
        self.btn_open_sessions_header = QPushButton("📂 Sessions")
        self.btn_open_sessions_header.setObjectName("btnCancel")
        self.btn_open_sessions_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_sessions_header.setToolTip("Open Sessions History & Search")
        self.btn_open_sessions_header.clicked.connect(self._on_sessions_clicked)
        header_layout.addWidget(self.btn_open_sessions_header)

        self.btn_open_recordings_header = QPushButton("🎧 History")
        self.btn_open_recordings_header.setObjectName("btnCancel")
        self.btn_open_recordings_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_recordings_header.setToolTip("Open Recordings & Audio Preview History")
        self.btn_open_recordings_header.clicked.connect(self._on_recordings_clicked)
        header_layout.addWidget(self.btn_open_recordings_header)

        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.setObjectName("btnCancel")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setToolTip("Open Settings")
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        header_layout.addWidget(self.btn_settings)

        container_layout.addLayout(header_layout)

        # Main text editor area (placed at top so appearing/disappearing live preview doesn't shift it)
        self.lbl_main = QLabel("📝 Document:")
        container_layout.addWidget(self.lbl_main)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("AI-processed speech will be inserted here after each Cut or Stop. You can edit freely...")
        container_layout.addWidget(self.text_edit)

        # Live transcription preview area (placed below main document editor, hidden by default)
        self.lbl_live = QLabel("🎙️ Live Speech Preview:")
        self.lbl_live.setVisible(False)
        container_layout.addWidget(self.lbl_live)
        self.live_text_edit = QPlainTextEdit()
        self.live_text_edit.setObjectName("liveTextBox")
        self.live_text_edit.setReadOnly(True)
        self.live_text_edit.setMaximumHeight(85)
        self.live_text_edit.setPlaceholderText("Live real-time transcription will appear here as you speak...")
        self.live_text_edit.setVisible(False)
        container_layout.addWidget(self.live_text_edit)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setObjectName("btnCopy")
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        btn_layout.addWidget(self.btn_copy)

        self.btn_start_recording = QPushButton("🎙️ Start Recording")
        self.btn_start_recording.setObjectName("btnContinue")
        self.btn_start_recording.clicked.connect(self._on_start_recording_clicked)
        self.btn_start_recording.setVisible(False)
        btn_layout.addWidget(self.btn_start_recording)

        self.btn_continue = QPushButton("🎙️ Continue Session")
        self.btn_continue.setObjectName("btnContinue")
        self.btn_continue.clicked.connect(self._on_continue_clicked)
        btn_layout.addWidget(self.btn_continue)

        self.btn_new = QPushButton("🔄 New Session")
        self.btn_new.setObjectName("btnNew")
        self.btn_new.clicked.connect(self._on_new_clicked)
        btn_layout.addWidget(self.btn_new)

        btn_layout.addStretch()

        # Cut Speech button (visible during recording)
        self.btn_cut = QPushButton("✂️ Cut & Process")
        self.btn_cut.setObjectName("btnCut")
        self.btn_cut.clicked.connect(self._on_cut_clicked)
        btn_layout.addWidget(self.btn_cut)

        # Stop Recording button (visible during recording)
        self.btn_stop_recording = QPushButton("⏹ Stop Recording")
        self.btn_stop_recording.setObjectName("btnStopRecord")
        self.btn_stop_recording.clicked.connect(self._on_stop_recording_clicked)
        btn_layout.addWidget(self.btn_stop_recording)

        # Done button (close the editor, save session to history, no auto-paste)
        self.btn_done = QPushButton("✅ Done")
        self.btn_done.setObjectName("btnDone")
        self.btn_done.setDefault(True)
        self.btn_done.clicked.connect(self._on_done_clicked)
        btn_layout.addWidget(self.btn_done)

        container_layout.addLayout(btn_layout)

        main_layout.addWidget(self.container)

    def _connect_signals(self):
        self.signal_show_recording.connect(self._handle_show_recording, Qt.ConnectionType.QueuedConnection)
        self.signal_update_partial.connect(self._handle_update_partial, Qt.ConnectionType.QueuedConnection)
        self.signal_show_transcribing.connect(self._handle_show_transcribing, Qt.ConnectionType.QueuedConnection)
        self.signal_show_finished.connect(self._handle_show_finished, Qt.ConnectionType.QueuedConnection)
        self.signal_append_text.connect(self._handle_append_text, Qt.ConnectionType.QueuedConnection)
        self.signal_close.connect(self.accept, Qt.ConnectionType.QueuedConnection)
        self.signal_show_idle.connect(self._handle_show_idle, Qt.ConnectionType.QueuedConnection)

    def _handle_show_idle(self):
        """Called when opening the app from the tray icon — no recording in progress."""
        self.lbl_status.setText("🎙️ VoiceKit — Press Start Recording or use the hotkey")
        self.lbl_live.setVisible(False)
        self.live_text_edit.setVisible(False)
        self.btn_cut.setVisible(False)
        self.btn_stop_recording.setVisible(False)
        has_text = bool(self.text_edit.toPlainText().strip())
        self.btn_continue.setVisible(has_text)
        self.btn_new.setVisible(has_text)
        self.btn_done.setVisible(has_text)
        self.btn_cancel.setVisible(False)
        self.btn_start_recording.setVisible(not has_text)
        self.text_edit.setReadOnly(False)

    def _handle_show_recording(self, clear_main: bool = True):
        self.lbl_status.setText("🔴 Recording... (Click ✂️ Cut to process segment or ⏹ Stop when done)")
        self.btn_start_recording.setVisible(False)
        self.btn_cancel.setVisible(True)
        # Live preview shown only when partial updates arrive
        self.lbl_live.setVisible(False)
        self.live_text_edit.setVisible(False)
        self.live_text_edit.clear()
        if clear_main:
            self.text_edit.clear()
        self.text_edit.setReadOnly(False)
        self.btn_copy.setEnabled(True)
        self.btn_continue.setVisible(False)
        self.btn_new.setVisible(False)
        self.btn_done.setVisible(False)
        self.btn_cut.setVisible(True)
        self.btn_cut.setEnabled(True)
        self.btn_stop_recording.setVisible(True)
        self.btn_stop_recording.setEnabled(True)
        self.show()
        self.raise_()
        self.activateWindow()

    def _handle_update_partial(self, partial_text: str):
        if partial_text:
            # Show live box on first partial
            if not self.lbl_live.isVisible():
                self.lbl_live.setVisible(True)
                self.live_text_edit.setVisible(True)
            self.live_text_edit.setPlainText(partial_text)
            scrollbar = self.live_text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _handle_show_transcribing(self, provider_name: str):
        self.lbl_status.setText(f"⏳ Processing with {provider_name}...")
        self.btn_cut.setVisible(False)
        self.btn_stop_recording.setVisible(False)
        self.btn_continue.setVisible(False)
        self.btn_new.setVisible(False)
        self.btn_done.setVisible(True)
        self.btn_done.setEnabled(False)

    def _handle_show_finished(self, final_text: str):
        self.lbl_status.setText("✨ Done! Review text, continue speaking, or start a new session:")
        self.live_text_edit.clear()
        self.lbl_live.setVisible(False)
        self.live_text_edit.setVisible(False)
        self.text_edit.setReadOnly(False)
        if final_text:
            current = self.text_edit.toPlainText().strip()
            if current and not current.endswith("\n\n"):
                combined = f"{current}\n\n{final_text}"
            elif current:
                combined = f"{current}{final_text}"
            else:
                combined = final_text
            self.text_edit.setPlainText(combined)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.setFocus()

        self.btn_cut.setVisible(False)
        self.btn_stop_recording.setVisible(False)
        self.btn_start_recording.setVisible(False)
        self.btn_continue.setVisible(True)
        self.btn_continue.setEnabled(True)
        self.btn_new.setVisible(True)
        self.btn_new.setEnabled(True)
        self.btn_done.setVisible(True)
        self.btn_copy.setEnabled(True)
        self.btn_done.setEnabled(True)

    def _handle_append_text(self, new_text: str):
        if not new_text:
            return
        self.live_text_edit.clear()
        current = self.text_edit.toPlainText().strip()
        if current and not current.endswith("\n\n"):
            combined = f"{current}\n\n{new_text}"
        elif current:
            combined = f"{current}{new_text}"
        else:
            combined = new_text
        self.text_edit.setPlainText(combined)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.lbl_status.setText("🔴 Recording... (Segment processed & inserted! Keep talking or click Stop)")

    def _on_copy_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            pyperclip.copy(text)
            self.btn_copy.setText("✓ Copied!")
            self._copy_timer.start(2000)

    def _reset_copy_btn(self):
        self.btn_copy.setText("Copy")

    def _on_continue_clicked(self):
        self.lbl_status.setText("🔴 Continuing Recording... (appending to current text)")
        self.lbl_live.setVisible(True)
        self.live_text_edit.setVisible(True)
        self.live_text_edit.clear()
        self.btn_cut.setVisible(True)
        self.btn_cut.setEnabled(True)
        self.btn_stop_recording.setVisible(True)
        self.btn_stop_recording.setEnabled(True)
        self.btn_continue.setVisible(False)
        self.btn_new.setVisible(False)
        self.btn_done.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.text_edit.setReadOnly(True)
        if self.on_continue_callback:
            self.on_continue_callback()

    def _on_new_clicked(self):
        self.text_edit.clear()
        self.lbl_status.setText("⏳ Starting new session...")
        if self.on_new_callback:
            self.on_new_callback()

    def _on_start_recording_clicked(self):
        self.btn_start_recording.setVisible(False)
        if self.on_start_recording_callback:
            self.on_start_recording_callback()

    def _on_settings_clicked(self):
        if self.on_settings_callback:
            self.on_settings_callback()

    def _on_sessions_clicked(self):
        if self.on_sessions_callback:
            self.on_sessions_callback()

    def _on_recordings_clicked(self):
        if self.on_recordings_callback:
            self.on_recordings_callback()

    def _on_cut_clicked(self):
        self.live_text_edit.clear()
        self.lbl_status.setText("⏳ Processing speech segment... (Microphone is STILL RECORDING!)")
        if self.on_cut_callback:
            self.on_cut_callback()

    def _on_stop_recording_clicked(self):
        self.btn_stop_recording.setEnabled(False)
        self.btn_cut.setEnabled(False)
        self.lbl_status.setText("⏳ Stopping audio & processing final transcript...")
        if self.on_stop_callback:
            self.on_stop_callback()

    def _on_done_clicked(self):
        """Close editor. If text was modified, update the latest session."""
        text = self.text_edit.toPlainText().strip()
        if text:
            try:
                recent = self.history_mgr.get_recent(limit=1)
                if recent:
                    self.history_mgr.update_session_text(recent[0]["id"], text)
            except Exception as e:
                print(f"Failed to update session on Done: {e}")
        self.accept()
        # No pasting — editor Done just closes the window. Paste is handled by Copy button.
