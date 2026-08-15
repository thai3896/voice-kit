import os
import threading
import pyperclip
import soundfile as sf
import sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFrame, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, Q_ARG, pyqtSlot
from PyQt6.QtGui import QColor

from src.history_manager import HistoryManager


class RecordingCardWidget(QFrame):
    def __init__(self, session_data: dict, history_mgr: HistoryManager, on_delete_callback, on_regenerate_callback, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.history_mgr = history_mgr
        self.on_delete_callback = on_delete_callback
        self.on_regenerate_callback = on_regenerate_callback
        self.is_playing = False
        self._play_thread = None

        self._init_ui()

    def _init_ui(self):
        self.setObjectName("recordingCard")
        self.setStyleSheet("""
            QFrame#recordingCard {
                background-color: #1e1e24;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QLabel#cardText {
                color: #f1f2f6;
                font-size: 14px;
                font-weight: 500;
                line-height: 1.4;
            }
            QLabel#cardTime {
                color: #747d8c;
                font-size: 12px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #ced6e0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
            QPushButton#btnPlay {
                background-color: #007aff;
                color: #ffffff;
                border: none;
                border-radius: 14px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
                font-size: 12px;
            }
            QPushButton#btnPlay:hover {
                background-color: #2b95ff;
            }
            QPushButton#btnPlay[playing="true"] {
                background-color: #ff3b30;
            }
            QPushButton#btnDelete:hover {
                background-color: #ff3b30;
                color: #ffffff;
                border-color: #ff3b30;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Transcribed text
        self.lbl_text = QLabel(self.session_data.get("text", ""))
        self.lbl_text.setObjectName("cardText")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lbl_text)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.08); background-color: rgba(255, 255, 255, 0.08); border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Footer row
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        # Timestamp
        date_str = self.session_data.get("date", "")
        time_str = self.session_data.get("timestamp", "")
        self.lbl_time = QLabel(f"{date_str} {time_str}")
        self.lbl_time.setObjectName("cardTime")
        footer_layout.addWidget(self.lbl_time)
        footer_layout.addStretch()

        # Action Buttons
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("btnPlay")
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setToolTip("Play Audio")
        self.btn_play.clicked.connect(self._toggle_playback)
        footer_layout.addWidget(self.btn_play)

        # Disable play button if no audio file exists
        audio_path = self.session_data.get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            self.btn_play.setEnabled(False)
            self.btn_play.setToolTip("No audio file recorded for this session")
            self.btn_play.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color: #747d8c;")

        self.btn_copy = QPushButton("📋")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setToolTip("Copy Transcription")
        self.btn_copy.clicked.connect(self._on_copy)
        footer_layout.addWidget(self.btn_copy)

        self.btn_regen = QPushButton("🔄")
        self.btn_regen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_regen.setToolTip("Regenerate Transcription")
        self.btn_regen.clicked.connect(self._on_regenerate)
        footer_layout.addWidget(self.btn_regen)

        if not audio_path or not os.path.exists(audio_path):
            self.btn_regen.setEnabled(False)
            self.btn_regen.setToolTip("Cannot regenerate without saved audio file")
            self.btn_regen.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color: #747d8c;")

        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setToolTip("Delete Recording")
        self.btn_delete.clicked.connect(self._on_delete)
        footer_layout.addWidget(self.btn_delete)

        layout.addLayout(footer_layout)

    def _toggle_playback(self):
        if self.is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        audio_path = self.session_data.get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            return

        self.is_playing = True
        self.btn_play.setText("■")
        self.btn_play.setProperty("playing", "true")
        self.btn_play.style().unpolish(self.btn_play)
        self.btn_play.style().polish(self.btn_play)

        def _play_worker():
            try:
                data, fs = sf.read(audio_path)
                sd.play(data, fs)
                sd.wait()
            except Exception as e:
                print(f"Error playing audio {audio_path}: {e}")
            finally:
                QMetaObject.invokeMethod(self, "_on_play_finished", Qt.ConnectionType.QueuedConnection)

        self._play_thread = threading.Thread(target=_play_worker, daemon=True)
        self._play_thread.start()

    def _stop_playback(self):
        try:
            sd.stop()
        except Exception:
            pass
        self._on_play_finished()

    @pyqtSlot()
    def _on_play_finished(self):
        self.is_playing = False
        self.btn_play.setText("▶")
        self.btn_play.setProperty("playing", "false")
        self.btn_play.style().unpolish(self.btn_play)
        self.btn_play.style().polish(self.btn_play)

    def _on_copy(self):
        text = self.lbl_text.text()
        if text:
            pyperclip.copy(text)
            old_text = self.btn_copy.text()
            self.btn_copy.setText("✔")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText(old_text))

    def _on_regenerate(self):
        audio_path = self.session_data.get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            return
        self.btn_regen.setEnabled(False)
        self.btn_regen.setText("⌛")
        self.on_regenerate_callback(self.session_data.get("id"), audio_path, self._on_regen_complete)

    def _on_regen_complete(self, new_text: str):
        self.btn_regen.setEnabled(True)
        self.btn_regen.setText("🔄")
        if new_text and not new_text.startswith("[Error") and not new_text.startswith("[Transcrib"):
            self.lbl_text.setText(new_text)
            self.session_data["text"] = new_text
            self.history_mgr.update_session_text(self.session_data.get("id"), new_text)

    def _on_delete(self):
        self._stop_playback()
        self.on_delete_callback(self)


class RecordingsWindow(QDialog):
    signal_refresh = pyqtSignal()

    def __init__(self, history_mgr: HistoryManager, regenerate_handler, parent=None):
        super().__init__(parent)
        self.history_mgr = history_mgr
        self.regenerate_handler = regenerate_handler
        self.cards = []
        self._init_ui()
        self.refresh_recordings()
        self.signal_refresh.connect(self.refresh_recordings)

    def _init_ui(self):
        self.setWindowTitle("Recordings Preview — VoiceKit")
        self.setMinimumSize(540, 680)
        self.resize(580, 740)
        self.setWindowFlags(Qt.WindowType.Window)

        self.setStyleSheet("""
            QDialog {
                background-color: #121216;
            }
            QLineEdit {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #007aff;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search in transcriptions...")
        self.search_input.textChanged.connect(self._filter_recordings)
        main_layout.addWidget(self.search_input)

        # Scroll Area for Cards Feed
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.feed_container = QWidget()
        self.feed_container.setStyleSheet("background-color: transparent;")
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_layout.setSpacing(12)
        self.feed_layout.addStretch()

        self.scroll_area.setWidget(self.feed_container)
        main_layout.addWidget(self.scroll_area)

    def refresh_recordings(self):
        # Clear existing cards
        while self.feed_layout.count() > 1:
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = []

        sessions = self.history_mgr.get_recent(limit=self.history_mgr.get_max_limit())
        for s in sessions:
            card = RecordingCardWidget(
                session_data=s,
                history_mgr=self.history_mgr,
                on_delete_callback=self._delete_card,
                on_regenerate_callback=self.regenerate_handler
            )
            self.feed_layout.insertWidget(self.feed_layout.count() - 1, card)
            self.cards.append(card)

        self._filter_recordings(self.search_input.text())

    def _filter_recordings(self, query: str):
        q = query.strip().lower()
        for card in self.cards:
            text = card.session_data.get("text", "").lower()
            date_time = f"{card.session_data.get('date', '')} {card.session_data.get('timestamp', '')}".lower()
            if not q or q in text or q in date_time:
                card.setVisible(True)
            else:
                card.setVisible(False)

    def _delete_card(self, card_widget: RecordingCardWidget):
        session_id = card_widget.session_data.get("id")
        if session_id:
            self.history_mgr.delete_session(session_id)
        if card_widget in self.cards:
            self.cards.remove(card_widget)
        self.feed_layout.removeWidget(card_widget)
        card_widget.deleteLater()

    def closeEvent(self, event):
        # Stop any playing audio when closing window
        for card in self.cards:
            if card.is_playing:
                card._stop_playback()
        super().closeEvent(event)
