from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QGuiApplication

class FloatingButton(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.ToolTip
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.size = 60
        self.setFixedSize(self.size, self.size)
        
        self.is_active = False
        self.dragging = False
        self.offset = QPoint()
        
        # Position it on the right edge initially
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(screen.width() - self.size - 20, screen.height() // 2)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw circular button
        color = QColor("#0984e3") if self.is_active else QColor("#636e72")
        color.setAlpha(180) # semi-transparent
        
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.size, self.size)
        
        # Draw icon (an arrow or scroll indicator)
        painter.setPen(QPen(Qt.GlobalColor.white, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = self.size // 2, self.size // 2
        
        # Up arrow
        painter.drawLine(cx - 8, cy - 5, cx, cy - 13)
        painter.drawLine(cx, cy - 13, cx + 8, cy - 5)
        painter.drawLine(cx, cy - 13, cx, cy + 13)
        
        # Down arrow
        painter.drawLine(cx - 8, cy + 5, cx, cy + 13)
        painter.drawLine(cx, cy + 13, cx + 8, cy + 5)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.offset = event.pos()
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            # If they move more than a few pixels, it's a drag
            if (event.pos() - self.offset).manhattanLength() > 5:
                self.dragging = True
                self.move(self.mapToGlobal(event.pos() - self.offset))
                
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.dragging:
            # It was a click, toggle state
            self.toggle_state()
            
    def toggle_state(self, force_state=None):
        if force_state is not None:
            self.is_active = force_state
        else:
            self.is_active = not self.is_active
            
        print(f"[FloatingButton] Scroll mode active: {self.is_active}")
        self.update()
        self.toggled.emit(self.is_active)
