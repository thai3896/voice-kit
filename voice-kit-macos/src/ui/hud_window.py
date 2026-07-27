from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPainter, QBrush, QFont, QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QApplication
from PyQt6.QtGui import QGuiApplication


class PulsingDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.level = 0.0
        self.color = QColor("#ff4757")  # Red for recording
        # Pulse animation timer
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_dir = 1
        self._pulse_val = 0.2

    def start_pulse(self):
        self._pulse_timer.start(60)

    def stop_pulse(self):
        self._pulse_timer.stop()
        self.level = 0.5
        self.update()

    def _pulse_tick(self):
        self._pulse_val += self._pulse_dir * 0.06
        if self._pulse_val >= 1.0:
            self._pulse_val = 1.0
            self._pulse_dir = -1
        elif self._pulse_val <= 0.1:
            self._pulse_val = 0.1
            self._pulse_dir = 1
        self.set_level(self._pulse_val)

    def set_level(self, level: float):
        self.level = max(0.1, min(1.0, level))
        self.update()

    def set_color(self, hex_color: str):
        self.color = QColor(hex_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()
        base_radius = 5.0
        pulse_radius = base_radius + (self.level * 6.0)

        # Outer pulse glow
        glow_color = QColor(self.color)
        glow_color.setAlphaF(min(1.0, 0.3 + self.level * 0.5))
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, int(pulse_radius), int(pulse_radius))

        # Inner solid dot
        painter.setBrush(QBrush(self.color))
        painter.drawEllipse(center, int(base_radius), int(base_radius))
        painter.end()


class HudWindow(QWidget):
    signal_show_recording = pyqtSignal()
    signal_update_level = pyqtSignal(float)
    signal_show_transcribing = pyqtSignal(str)
    signal_show_done = pyqtSignal()
    signal_hide = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        # On macOS: FramelessWindowHint + WindowStaysOnTopHint is the most reliable
        # combination for a floating pill. We skip Tool/WindowDoesNotAcceptFocus because
        # those flags silently hide the window on macOS when the app is running in background (Accessory mode).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Main pill container
        self.container = QWidget(self)
        self.container.setObjectName("hudContainer")
        self.container.setStyleSheet("""
            QWidget#hudContainer {
                background-color: rgba(22, 22, 26, 0.97);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 28px;
            }
            QLabel {
                color: #f1f2f6;
                font-family: '.AppleSystemUIFont', -apple-system, 'Helvetica Neue', sans-serif;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#partialText {
                color: #a4b0be;
                font-size: 12px;
                font-weight: 400;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(18, 12, 22, 12)
        layout.setSpacing(12)

        self.dot = PulsingDot(self.container)
        layout.addWidget(self.dot)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.status_label = QLabel("🔴 Recording...", self.container)
        self.status_label.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.Bold))
        text_layout.addWidget(self.status_label)

        self.partial_label = QLabel("", self.container)
        self.partial_label.setObjectName("partialText")
        self.partial_label.setVisible(False)
        text_layout.addWidget(self.partial_label)

        layout.addLayout(text_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.container)

        self.setMinimumWidth(220)

    def _position_near_cursor(self):
        """Position the HUD pill just above and to the right of the current mouse cursor."""
        cursor_pos = QCursor.pos()

        # Try to get the screen the cursor is on
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        self.adjustSize()
        geom = screen.availableGeometry()
        w = self.width()
        h = self.height()

        # Prefer: right of cursor, above cursor (like Superwhisper)
        x = cursor_pos.x() + 24
        y = cursor_pos.y() - h - 36

        # Clamp to screen bounds
        if x + w > geom.right() - 10:
            x = cursor_pos.x() - w - 24  # flip to left
        if x < geom.left() + 10:
            x = geom.left() + 10
        if y < geom.top() + 10:
            y = cursor_pos.y() + 30  # flip below
        if y + h > geom.bottom() - 10:
            y = geom.bottom() - h - 10

        self.move(x, y)

    def _connect_signals(self):
        self.signal_show_recording.connect(self._on_show_recording)
        self.signal_update_level.connect(self._on_update_level)
        self.signal_show_transcribing.connect(self._on_show_transcribing)
        self.signal_show_done.connect(self._on_show_done)
        self.signal_hide.connect(self.hide)

    def _make_non_activating(self):
        """Ensure the native NSWindow never steals key focus or activates the app."""
        import sys
        if sys.platform != "darwin":
            return
        try:
            import ctypes
            import ctypes.util
            ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
            objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))

            register_sel = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(("sel_registerName", objc))
            msg_send_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_send_void = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_send_int = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(("objc_msgSend", objc))

            ns_view = ctypes.c_void_p(int(self.winId()))
            sel_window = register_sel(b"window")
            ns_win = msg_send_ptr(ns_view, sel_window)

            if ns_win:
                # orderFrontRegardless: bring to front without activating or taking keyboard focus
                sel_order = register_sel(b"orderFrontRegardless")
                msg_send_void(ns_win, sel_order)

                # setLevel: 25 (NSStatusWindowLevel / floating pill)
                sel_level = register_sel(b"setLevel:")
                msg_send_int(ns_win, sel_level, 25)

                # setCollectionBehavior: 329 (CanJoinAllSpaces | Transient | IgnoresCycle | FullScreenAuxiliary)
                sel_cb = register_sel(b"setCollectionBehavior:")
                msg_send_ulong = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc))
                msg_send_ulong(ns_win, sel_cb, 329)
        except Exception as e:
            print(f"[HUD] Non-activating setup error: {e}")

    def _on_show_recording(self):
        self.dot.set_color("#ff4757")  # Red
        self.dot.start_pulse()
        self.status_label.setText("Recording...")
        self.partial_label.setText("")
        self.partial_label.setVisible(False)
        self._position_near_cursor()
        self.show()
        self._make_non_activating()

    def _on_update_level(self, level: float):
        self.dot.set_level(level)

    def _on_show_transcribing(self, partial: str):
        self.dot.set_color("#ffa502")  # Orange/Yellow
        self.dot.stop_pulse()
        self.dot.set_level(0.6)
        self.status_label.setText("Processing...")
        if partial:
            display_text = partial if len(partial) < 45 else "..." + partial[-42:]
            self.partial_label.setText(f'"{display_text}"')
            self.partial_label.setVisible(True)
        else:
            self.partial_label.setVisible(False)
        self.adjustSize()
        if not self.isVisible():
            self._position_near_cursor()
            self.show()
            self._make_non_activating()

    def _on_show_done(self):
        self.dot.set_color("#2ed573")  # Green
        self.dot.stop_pulse()
        self.dot.set_level(0.9)
        self.status_label.setText("Inserted!")
        self.partial_label.setVisible(False)
        self.adjustSize()

        # Hide after 1.5 seconds
        QTimer.singleShot(1500, self.hide)
