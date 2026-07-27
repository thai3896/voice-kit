from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication


class TrayIcon(QSystemTrayIcon):
    signal_open_app = pyqtSignal()
    signal_open_sessions = pyqtSignal()
    signal_open_recordings = pyqtSignal()
    signal_quit = pyqtSignal()

    # Keep these for backward-compat with main.py connections
    signal_toggle_recording = pyqtSignal()
    signal_open_settings = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(self._create_default_icon(is_recording=False))
        self.setToolTip("VoiceKit — Click to open")
        self._create_menu()
        # Single left-click opens the app
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.signal_open_app.emit()

    def _create_default_icon(self, is_recording: bool) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if is_recording:
            color = QColor("#ff4757")  # Red dot when recording
        else:
            color = QColor("#f1f2f6")  # White/light dot for macOS dark menu bar

        # Draw a sleek circle representing microphone/status
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(6, 6, 20, 20)
        painter.end()

        return QIcon(pixmap)

    def set_recording_state(self, is_recording: bool):
        self.setIcon(self._create_default_icon(is_recording))
        if is_recording:
            self.setToolTip("VoiceKit — Recording 🔴")
        else:
            self.setToolTip("VoiceKit — Click to open")

    def _create_menu(self):
        self.menu = QMenu()

        self.status_action = QAction("VoiceKit: Ready", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        self.open_action = QAction("Open VoiceKit...", self.menu)
        self.open_action.triggered.connect(self.signal_open_app.emit)
        self.menu.addAction(self.open_action)

        self.sessions_action = QAction("📂 Sessions History & Search...", self.menu)
        self.sessions_action.triggered.connect(self.signal_open_sessions.emit)
        self.menu.addAction(self.sessions_action)

        self.recordings_action = QAction("🎧 Preview Recordings...", self.menu)
        self.recordings_action.triggered.connect(self.signal_open_recordings.emit)
        self.menu.addAction(self.recordings_action)

        self.menu.addSeparator()

        self.quit_action = QAction("Quit VoiceKit", self.menu)
        self.quit_action.triggered.connect(self.signal_quit.emit)
        self.menu.addAction(self.quit_action)

        self.setContextMenu(self.menu)
