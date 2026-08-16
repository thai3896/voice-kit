from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QSizeGrip
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QMouseEvent, QPainter
import math

class AudioMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 20)
        self.history = [(0.0, 0.0)] * 15
        self.active_threshold = 0.01
        
    def set_volume(self, rms: float):
        # Scale rms. It's usually very small. We cap at 0.1 for max height.
        val = min(rms * 10.0, 1.0)
        self.history.append((val, rms))
        if len(self.history) > 15:
            self.history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bar_width = 2
        spacing = 2
        for i, (val, raw_rms) in enumerate(self.history):
            h = int(val * self.height())
            if h < 2: h = 2
            
            # Color: green if above threshold, grey otherwise
            if raw_rms > self.active_threshold:
                color = QColor("#00ff00")
            else:
                color = QColor("#555555")
                
            x = i * (bar_width + spacing)
            y = (self.height() - h) // 2
            painter.fillRect(x, y, bar_width, h, color)

class AssistantWindow(QWidget):
    signal_new_session = pyqtSignal()
    signal_open_sessions = pyqtSignal()
    signal_append_user_msg = pyqtSignal(str)
    signal_append_ai_msg = pyqtSignal(str)
    signal_toggle_vad = pyqtSignal()
    signal_close = pyqtSignal()
    signal_update_volume = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VoiceKit Active Listening")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(350, 450)
        
        # For dragging
        self._drag_pos = None
        # Connect signals to slots to ensure thread safety
        self.signal_append_user_msg.connect(self.append_user_msg)
        self.signal_append_ai_msg.connect(self.append_ai_msg)
        self.signal_update_volume.connect(self._on_volume_update)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Main container for styling
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget#MainContainer {
                background-color: rgba(30, 30, 36, 0.95);
                border-radius: 12px;
                border: 1px solid #3d3d4e;
            }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        
        # Header (draggable) with buttons
        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("Active Listening: ON")
        self.status_label.setStyleSheet("""
            color: #00ff00;
            font-weight: bold;
            font-size: 14px;
            background: transparent;
        """)
        header_layout.addWidget(self.status_label)
        
        self.audio_meter = AudioMeter()
        header_layout.addWidget(self.audio_meter)
        
        header_layout.addStretch()
        
        self.btn_toggle_vad = QPushButton("🎙️")
        self.btn_toggle_vad.setToolTip("Toggle Active Listening")
        self.btn_toggle_vad.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_vad.clicked.connect(self.signal_toggle_vad.emit)
        header_layout.addWidget(self.btn_toggle_vad)
        
        self.btn_history = QPushButton("📜")
        self.btn_history.setToolTip("Session History")
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.clicked.connect(self.signal_open_sessions.emit)
        header_layout.addWidget(self.btn_history)
        
        self.btn_new = QPushButton("✨")
        self.btn_new.setToolTip("New Session")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self.clear_session)
        self.btn_new.clicked.connect(self.signal_new_session.emit)
        header_layout.addWidget(self.btn_new)
        
        self.btn_close = QPushButton("✖")
        self.btn_close.setToolTip("Close")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.signal_close.emit)
        header_layout.addWidget(self.btn_close)
        
        container_layout.addWidget(self.header)
        
        # Chat log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-size: 14px;
            }
        """)
        container_layout.addWidget(self.log_text)
        
        # Size Grip for resizing
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        grip = QSizeGrip(self)
        grip.setStyleSheet("background: transparent;")
        grip_layout.addWidget(grip)
        container_layout.addLayout(grip_layout)
        
        layout.addWidget(self.container)
        
        # Position bottom right
        self._position_window()

    def _position_window(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 40
        y = screen.height() - self.height() - 60
        self.move(x, y)

    def set_status(self, text: str, color: str = "#00ff00"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            color: {color};
            font-weight: bold;
            font-size: 14px;
            background: transparent;
        """)

    def _on_volume_update(self, rms: float):
        self.audio_meter.set_volume(rms)

    def append_user_msg(self, text: str):
        self.log_text.append(f"<b style='color:#0077ee;'>You:</b> {text}<br>")
        self._scroll_to_bottom()

    def append_ai_msg(self, text: str):
        self.log_text.append(f"<b style='color:#ffaa00;'>OpenClaw:</b> {text}<br><br>")
        self._scroll_to_bottom()
        
    def clear_session(self):
        self.log_text.clear()

    def load_session_text(self, text: str):
        self.clear_session()
        # Parse the raw text (e.g. "User: hi\n\nOpenClaw: hello\n\n")
        parts = text.split('\n\n')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith("User:"):
                self.append_user_msg(part[len("User:"):].strip())
            elif part.startswith("OpenClaw:"):
                self.append_ai_msg(part[len("OpenClaw:"):].strip())
            else:
                self.log_text.append(part)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # --- Dragging Implementation ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only allow drag from the top header area
            if event.position().y() < 50:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
