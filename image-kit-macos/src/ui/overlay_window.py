from PyQt6.QtWidgets import QMainWindow, QRubberBand, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from .action_toolbar import ActionToolbar
from .vision_prompt_menu import VisionPromptMenu

class OverlayWindow(QMainWindow):
    selection_made = pyqtSignal(QRect)
    ai_selection_made = pyqtSignal(QRect)
    vision_selection_made = pyqtSignal(QRect, str)
    ask_vision_selection_made = pyqtSignal(QRect, str)
    cancelled = pyqtSignal()

    def __init__(self, pixmap, screen_geometry, config):
        super().__init__()
        self.pixmap = pixmap
        self.screen_geometry = screen_geometry
        self.config = config
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # Position window exactly over the targeted screen
        self.setGeometry(screen_geometry)
        
        self.origin = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)
        
        self.is_selecting = False
        self._is_closing = False
        self.selection_rect = QRect()
        
        self.toolbar = ActionToolbar(self)
        self.toolbar.hide()
        
        # Connect toolbar signals
        self.toolbar.ocr_requested.connect(self.on_ocr)
        self.toolbar.ai_requested.connect(self.on_ai)
        self.toolbar.vision_requested.connect(self.on_vision)
        self.toolbar.ask_vision_requested.connect(self.on_ask_vision)
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
        self.toolbar.adjustSize()
        # Position toolbar near the bottom right of the selection
        tb_x = self.selection_rect.right() - self.toolbar.width()
        tb_y = self.selection_rect.bottom() + 10
        
        # Keep toolbar within screen bounds
        if tb_x < 0: tb_x = 0
        if tb_x + self.toolbar.width() > self.width(): 
            tb_x = self.width() - self.toolbar.width()
            
        if tb_y + self.toolbar.height() > self.height():
            tb_y = self.selection_rect.top() - self.toolbar.height() - 10
        if tb_y < 0: 
            tb_y = 0
            
        # Convert local window coordinates to global screen coordinates
        global_pos = self.mapToGlobal(QPoint(int(tb_x), int(tb_y)))
        self.toolbar.move(global_pos)
        self.toolbar.show()

    def on_ocr(self):
        self.toolbar.hide()
        self.selection_made.emit(self.selection_rect)

    def on_ai(self):
        self.toolbar.hide()
        self.ai_selection_made.emit(self.selection_rect)

    def on_vision(self):
        self._show_vision_menu(is_ask=False)

    def on_ask_vision(self):
        self._show_vision_menu(is_ask=True)

    def _show_vision_menu(self, is_ask):
        self.toolbar.hide()
        
        prompts = self.config.get("vision_prompts", {})
        if not prompts:
            # Fallback if config is missing
            prompts = {"General Description": "Analyze this image in detail."}
            
        self.menu = VisionPromptMenu(prompts, self)
        
        def handle_prompt(prompt_text):
            if is_ask:
                self.ask_vision_selection_made.emit(self.selection_rect, prompt_text)
            else:
                self.vision_selection_made.emit(self.selection_rect, prompt_text)
                
        self.menu.prompt_selected.connect(handle_prompt)
        
        def on_menu_closed():
            # If the overlay wasn't closed by a selection, bring the toolbar back
            if not self._is_closing and not self.selection_rect.isNull() and self.isVisible():
                self.show_toolbar()
                
        self.menu.finished.connect(on_menu_closed)
        
        self.menu.adjustSize()
        # Position menu near the selection rect
        menu_x = self.selection_rect.right() - self.menu.width()
        menu_y = self.selection_rect.bottom() + 10
        
        # Clamp menu within screen bounds
        if menu_x < 0: menu_x = 0
        if menu_x + self.menu.width() > self.width(): 
            menu_x = self.width() - self.menu.width()
            
        if menu_y + self.menu.height() > self.height():
            menu_y = self.selection_rect.top() - self.menu.height() - 10
        if menu_y < 0: 
            menu_y = 0
        
        global_pos = self.mapToGlobal(QPoint(int(menu_x), int(menu_y)))
        self.menu.move(global_pos)
        self.menu.show()

    def on_cancel(self):
        self.cancelled.emit()

    def closeEvent(self, event):
        self._is_closing = True
        if hasattr(self, 'toolbar') and self.toolbar:
            self.toolbar.close()
        if hasattr(self, 'menu') and self.menu:
            self.menu.close()
        super().closeEvent(event)
