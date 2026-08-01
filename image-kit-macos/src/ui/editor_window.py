from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt
import pyperclip

class EditorWindow(QMainWindow):
    def __init__(self, text, config_manager=None):
        super().__init__()
        self.config = config_manager
        self.setWindowTitle("ImageKit OCR Result")
        self.setMinimumSize(400, 300)
        
        # Keep window on top so user sees it immediately
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Center on current screen where cursor is
        from PyQt6.QtGui import QCursor, QGuiApplication
        cursor_pos = QCursor.pos()
        screen_obj = QGuiApplication.screenAt(cursor_pos)
        if not screen_obj:
            screen_obj = QApplication.primaryScreen()
            
        screen = screen_obj.geometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.setGeometry(x, y, self.width(), self.height())
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
                font-size: 14px;
                padding: 10px;
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                background-color: #ffffff;
                color: #2d3436;
            }
        """)
        
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #0984e3;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74b9ff;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_text)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #636e72;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b2bec3;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)

    def copy_text(self):
        text = self.text_edit.toPlainText()
        pyperclip.copy(text)
        self.copy_btn.setText("Copied!")
        
    def closeEvent(self, event):
        super().closeEvent(event)
