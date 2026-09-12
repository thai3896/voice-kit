import time
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen

class ScrollOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # This window is 100% invisible to the macOS Window Server hit-testing
        # It exists purely to draw on the screen. It can never steal focus.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        # Force transparency to mouse events at the Qt level as well
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.start_pos = None
        self.current_pos = None
        
    def update_ui(self, start_pos_global, current_pos_global):
        if start_pos_global is None:
            self.start_pos = None
            self.current_pos = None
        else:
            # Convert the global screen coordinates from pynput to this window's local coordinates
            self.start_pos = self.mapFromGlobal(start_pos_global)
            self.current_pos = self.mapFromGlobal(current_pos_global)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # We do not draw a background at all anymore! It is completely invisible.
        
        if self.start_pos:
            try:
                # Start circle
                painter.setPen(QPen(QColor("#0984e3"), 6, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(9, 132, 227, 80))
                center = QPoint(int(self.start_pos.x()), int(self.start_pos.y()))
                painter.drawEllipse(center, 40, 40)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(center, 5, 5)
                
                # Dynamic Joystick line
                if self.current_pos and (self.current_pos - self.start_pos).manhattanLength() > 10:
                    pen = QPen(QColor("#74b9ff"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                    painter.setPen(pen)
                    curr = QPoint(int(self.current_pos.x()), int(self.current_pos.y()))
                    painter.drawLine(center, curr)
            except Exception as e:
                pass
