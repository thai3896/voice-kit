from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QSizeGrip, QCheckBox, QApplication, QScrollArea
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QFont, QColor, QMouseEvent, QPainter, QPixmap
import math

class ThumbnailWidget(QWidget):
    def __init__(self, data: str, is_image: bool, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_image = is_image
        self.setFixedSize(64, 64)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); border-radius: 8px;")
        
        if is_image:
            b64 = data.split(",")[1]
            ba = QByteArray.fromBase64(b64.encode())
            pixmap = QPixmap()
            pixmap.loadFromData(ba)
            self.lbl.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.lbl.setText("📄")
            self.lbl.setToolTip(data[:100])
            self.lbl.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; font-size: 24px;")
            
        layout.addWidget(self.lbl)
        
        self.btn_close = QPushButton("×", self)
        self.btn_close.setFixedSize(16, 16)
        self.btn_close.move(48, 0)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.6);
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 0.8);
            }
        """)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.deleteLater)

class AudioMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 20)
        self.history = [(0.0, 0.0)] * 15
        self.active_threshold = 0.006
        
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
    signal_append_user_msg_with_images = pyqtSignal(str, list)
    signal_append_ai_msg = pyqtSignal(str)
    signal_toggle_vad = pyqtSignal()
    signal_close = pyqtSignal()
    signal_update_volume = pyqtSignal(float)
    signal_toggle_hold = pyqtSignal()
    signal_send_message = pyqtSignal(str)
    signal_update_input = pyqtSignal(str)
    signal_stop_tts = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VoiceKit Active Listening")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(380, 500)
        
        # Buffers for pasted content
        self.buffered_images = []
        self.buffered_texts = []
        
        # For dragging
        self._drag_pos = None
        # Connect signals to slots to ensure thread safety
        self.signal_append_user_msg.connect(self.append_user_msg)
        self.signal_append_user_msg_with_images.connect(self.append_user_msg_with_images)
        self.signal_append_ai_msg.connect(self.append_ai_msg)
        self.signal_update_volume.connect(self._on_volume_update)
        self.signal_update_input.connect(self._on_update_input)

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
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        
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
        
        self.btn_hold = QPushButton("⏸")
        self.btn_hold.setToolTip("Toggle Hold/Think Mode")
        self.btn_hold.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hold.clicked.connect(self.signal_toggle_hold.emit)
        header_layout.addWidget(self.btn_hold)
        
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
        
        self.btn_stop_tts = QPushButton("⏹️")
        self.btn_stop_tts.setToolTip("Stop Speaking (Esc)")
        self.btn_stop_tts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_tts.clicked.connect(self.signal_stop_tts.emit)
        self.btn_stop_tts.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        self.btn_stop_tts.hide()
        header_layout.addWidget(self.btn_stop_tts)
        
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
        
        # Input Container
        input_container = QVBoxLayout()
        input_container.setSpacing(4)
        input_container.setContentsMargins(0, 0, 0, 0)
        
        # Attachments Preview Area
        self.attachments_scroll = QScrollArea()
        self.attachments_scroll.setFixedHeight(75)
        self.attachments_scroll.setWidgetResizable(True)
        self.attachments_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget#AttachmentsContainer { background: transparent; }")
        self.attachments_scroll.hide()
        
        self.attachments_container = QWidget()
        self.attachments_container.setObjectName("AttachmentsContainer")
        self.attachments_layout = QHBoxLayout(self.attachments_container)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.attachments_scroll.setWidget(self.attachments_container)
        
        input_container.insertWidget(0, self.attachments_scroll)
        
        # Attachments and Auto-Send row
        top_input_layout = QHBoxLayout()
        top_input_layout.setContentsMargins(0, 0, 0, 0)
        
        top_input_layout.addStretch()

        self.chk_auto_send = QCheckBox("Auto-Send")
        self.chk_auto_send.setChecked(True)
        self.chk_auto_send.setStyleSheet("color: #aaa; font-size: 11px;")
        top_input_layout.addWidget(self.chk_auto_send)
        
        input_container.addLayout(top_input_layout)

        # Input Area (Preview / Manual Send)
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        self.input_text = QTextEdit()
        self.input_text.setFixedHeight(45)
        self.input_text.textChanged.connect(self._adjust_input_height)
        self.input_text.setPlaceholderText("Type, paste (Cmd+V), or speak...")
        self.input_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid #444;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                padding: 6px;
            }
        """)
        self.input_text.installEventFilter(self)
        input_layout.addWidget(self.input_text)
        
        self.btn_send = QPushButton("🚀")
        self.btn_send.setToolTip("Send (Enter)")
        self.btn_send.setFixedSize(45, 45)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self._on_send_clicked)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        input_layout.addWidget(self.btn_send)
        input_container.addLayout(input_layout)
        
        container_layout.addLayout(input_container)
        
        # Size Grip for resizing
        grip = QSizeGrip(self.container)
        grip.setStyleSheet("background: transparent;")
        
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

    def append_user_msg_with_images(self, text: str, images: list):
        html = f"<b style='color:#0077ee;'>You:</b> {text}"
        if images:
            html += "<br>"
            for img_data in images:
                # img_data is like "data:image/png;base64,..."
                html += f"<img src='{img_data}' width='120' style='border-radius:8px; margin:4px 4px 4px 0;'>"
        html += "<br>"
        self.log_text.append(html)
        self._scroll_to_bottom()

    def _on_update_input(self, text: str):
        current = self.input_text.toPlainText()
        if current:
            self.input_text.setPlainText(current + " " + text)
        else:
            self.input_text.setPlainText(text)

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

    def eventFilter(self, obj, event):
        if obj == self.input_text and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_V and (event.modifiers() & Qt.KeyboardModifier.ControlModifier or event.modifiers() & Qt.KeyboardModifier.MetaModifier):
                clipboard = QApplication.clipboard()
                mime = clipboard.mimeData()
                if mime.hasImage():
                    image = clipboard.image()
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    image.save(buffer, "PNG")
                    b64 = ba.toBase64().data().decode()
                    self.buffered_images.append(f"data:image/png;base64,{b64}")
                    self._update_attachments_ui()
                    return True
            elif event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._on_send_clicked()
                return True
        return super().eventFilter(obj, event)

    def _adjust_input_height(self):
        doc = self.input_text.document()
        # Add some padding to the document height
        target_height = int(doc.size().height()) + 14
        if target_height < 45:
            target_height = 45
        elif target_height > 150:
            target_height = 150
            
        if self.input_text.height() != target_height:
            self.input_text.setFixedHeight(target_height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if not self.btn_stop_tts.isHidden():
                self.signal_stop_tts.emit()
            return
            
        # Handle Cmd+V / Ctrl+V for paste
        if event.key() == Qt.Key.Key_V and (event.modifiers() & Qt.KeyboardModifier.ControlModifier or event.modifiers() & Qt.KeyboardModifier.MetaModifier):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            
            if mime.hasImage():
                image = clipboard.image()
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buffer, "PNG")
                b64 = ba.toBase64().data().decode()
                self.buffered_images.append(f"data:image/png;base64,{b64}")
                self._update_attachments_ui()
            elif mime.hasText():
                # Allow default text paste into input_text if it has focus
                if self.input_text.hasFocus():
                    super().keyPressEvent(event)
                    return
                text = clipboard.text()
                self.buffered_texts.append(text)
                self._update_attachments_ui()
            return
            
        super().keyPressEvent(event)

    def _update_attachments_ui(self):
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        count = len(self.buffered_images) + len(self.buffered_texts)
        if count == 0:
            self.attachments_scroll.hide()
            return
            
        self.attachments_scroll.show()
        
        for idx, img in enumerate(self.buffered_images):
            thumb = ThumbnailWidget(img, True)
            thumb.btn_close.clicked.connect(lambda checked, i=idx: self._remove_image(i))
            self.attachments_layout.addWidget(thumb)
            
        for idx, txt in enumerate(self.buffered_texts):
            thumb = ThumbnailWidget(txt, False)
            thumb.btn_close.clicked.connect(lambda checked, i=idx: self._remove_text(i))
            self.attachments_layout.addWidget(thumb)

    def _remove_image(self, index):
        if 0 <= index < len(self.buffered_images):
            self.buffered_images.pop(index)
            self._update_attachments_ui()
            
    def _remove_text(self, index):
        if 0 <= index < len(self.buffered_texts):
            self.buffered_texts.pop(index)
            self._update_attachments_ui()

    def get_buffered_data(self):
        return self.buffered_images, self.buffered_texts
        
    def clear_buffered_data(self):
        self.buffered_images = []
        self.buffered_texts = []
        self._update_attachments_ui()

    def _on_send_clicked(self):
        text = self.input_text.toPlainText().strip()
        self.input_text.clear()
        self.signal_send_message.emit(text)

