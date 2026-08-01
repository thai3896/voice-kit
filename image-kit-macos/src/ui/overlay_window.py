from PyQt6.QtWidgets import QMainWindow, QRubberBand, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from .action_toolbar import ActionToolbar

class OverlayWindow(QMainWindow):
    selection_made = pyqtSignal(QRect)
    ai_selection_made = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self, pixmap, screen_geometry):
        super().__init__()
        self.pixmap = pixmap
        self.screen_geometry = screen_geometry
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Position window exactly over the targeted screen
        self.setGeometry(screen_geometry)
        
        self.origin = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)
        
        self.is_selecting = False
        self.selection_rect = QRect()
        
        self.toolbar = ActionToolbar(self)
        self.toolbar.hide()
        
        # Connect toolbar signals
        self.toolbar.ocr_requested.connect(self.on_ocr)
        self.toolbar.ai_requested.connect(self.on_ai)
        self.toolbar.cancel_requested.connect(self.on_cancel)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 1. Draw the captured screen pixmap opaquely
        painter.drawPixmap(0, 0, self.pixmap)
        
        # 2. Draw dim overlay on the unselected areas
        overlay_color = QColor(0, 0, 0, 120)
        
        if self.selection_rect.isNull():
            painter.fillRect(self.rect(), overlay_color)
            
            # Draw instructions
            painter.setPen(QPen(Qt.GlobalColor.white))
            from PyQt6.QtGui import QFont
            font = QFont("Arial", 18, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Drag to select an area  •  Press ESC to abort")
        else:
            from PyQt6.QtGui import QRegion
            dim_region = QRegion(self.rect()) - QRegion(self.selection_rect)
            painter.setClipRegion(dim_region)
            painter.fillRect(self.rect(), overlay_color)
            
            # Reset clipping so we can draw the border
            painter.setClipping(False)
            
            # Draw border around selection
            pen = QPen(QColor("#0984e3"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(self.selection_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toolbar.hide()
            self.origin = event.pos()
            self.selection_rect = QRect(self.origin, self.origin)
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.selection_rect = QRect(self.origin, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            self.selection_rect = QRect(self.origin, event.pos()).normalized()
            self.update()
            
            if self.selection_rect.width() > 10 and self.selection_rect.height() > 10:
                self.show_toolbar()
            else:
                self.selection_rect = QRect()
                self.update()
                self.cancelled.emit()
                
        elif event.button() == Qt.MouseButton.RightButton:
            self.on_cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.on_cancel()

    def show_toolbar(self):
        # Position toolbar near the bottom right of the selection
        tb_x = self.selection_rect.right() - self.toolbar.width()
        tb_y = self.selection_rect.bottom() + 10
        
        # Keep toolbar within screen bounds
        if tb_x < 0: tb_x = self.selection_rect.left()
        if tb_y + self.toolbar.height() > self.height():
            tb_y = self.selection_rect.top() - self.toolbar.height() - 10
            
        # Convert local window coordinates to global screen coordinates
        global_pos = self.mapToGlobal(QPoint(tb_x, tb_y))
        self.toolbar.move(global_pos)
        self.toolbar.show()

    def on_ocr(self):
        self.toolbar.hide()
        self.selection_made.emit(self.selection_rect)

    def on_ai(self):
        self.toolbar.hide()
        self.ai_selection_made.emit(self.selection_rect)

    def on_cancel(self):
        self.cancelled.emit()
