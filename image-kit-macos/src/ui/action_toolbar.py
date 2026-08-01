from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class ActionToolbar(QWidget):
    ocr_requested = pyqtSignal()
    ai_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Style
        button_style = """
            QPushButton {
                background-color: #2d3436;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                border: 1px solid #636e72;
            }
            QPushButton:hover {
                background-color: #636e72;
            }
        """

        self.btn_ocr = QPushButton("OCR")
        self.btn_ocr.setStyleSheet(button_style)
        self.btn_ocr.clicked.connect(self.ocr_requested.emit)

        self.btn_ai = QPushButton("Ask AI")
        self.btn_ai.setStyleSheet(button_style)
        self.btn_ai.clicked.connect(self.ai_requested.emit)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(button_style)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)

        layout.addWidget(self.btn_ocr)
        layout.addWidget(self.btn_ai)
        layout.addWidget(self.btn_cancel)

        # Add drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
