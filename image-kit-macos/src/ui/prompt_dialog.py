from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class PromptDialog(QDialog):
    def __init__(self, pixmap=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ask AI")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                border: 1px solid #3d3d4e;
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            QLabel#image_preview {
                border: 1px solid #3d3d4e;
                border-radius: 6px;
                background-color: #1a1a20;
            }
            QLineEdit {
                background-color: #2a2a35;
                color: #ffffff;
                border: 1px solid #3d3d4e;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #0077ee;
                background-color: #323242;
            }
            QPushButton {
                background-color: #3d3d4e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4f4f66;
            }
            QPushButton#submit_btn {
                background-color: #0066cc;
            }
            QPushButton#submit_btn:hover {
                background-color: #0077ee;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        label = QLabel("✨ What would you like to ask about this region?")
        layout.addWidget(label)
        
        if pixmap and not pixmap.isNull():
            self.image_label = QLabel()
            self.image_label.setObjectName("image_preview")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Scale down if it's too big, e.g. max height 300, max width 500
            scaled_pixmap = pixmap.scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            # Add some margins inside the label
            self.image_label.setContentsMargins(8, 8, 8, 8)
            layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("e.g. Extract the text, explain this chart, etc.")
        self.input_field.returnPressed.connect(self.accept)
        layout.addWidget(self.input_field)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_submit = QPushButton("Ask")
        self.btn_submit.setObjectName("submit_btn")
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_submit)
        layout.addLayout(btn_layout)
        
        # Adjust size to fit contents before centering
        self.adjustSize()
        
        # Center on screen where cursor is
        from PyQt6.QtGui import QCursor, QGuiApplication
        cursor_pos = QCursor.pos()
        screen_obj = QGuiApplication.screenAt(cursor_pos)
        if not screen_obj:
            screen_obj = QApplication.primaryScreen()
            
        if screen_obj:
            screen = screen_obj.geometry()
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + (screen.height() - self.height()) // 2
            self.setGeometry(x, y, self.width(), self.height())

    def get_prompt(self):
        return self.input_field.text().strip()
