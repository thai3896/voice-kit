from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QListWidgetItem, QPushButton, QLabel, 
                             QMessageBox, QApplication)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from datetime import datetime
import os

class SessionsWindow(QMainWindow):
    def __init__(self, history_manager, on_session_selected_callback):
        super().__init__()
        self.history_manager = history_manager
        self.on_session_selected_callback = on_session_selected_callback
        
        self.setWindowTitle("ImageKit - Chat History")
        self.setMinimumSize(400, 500)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.setGeometry(x, y, self.width(), self.height())
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        header = QLabel("Past AI Chats")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0A84FF;
                color: white;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setStyleSheet("color: red;")
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        
        self.btn_open = QPushButton("Open Chat")
        self.btn_open.clicked.connect(self.open_selected)
        btn_layout.addWidget(self.btn_open)
        
        layout.addLayout(btn_layout)
        
        self.refresh_list()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_list)
        self.timer.start(5000)
        
    def refresh_list(self):
        self.list_widget.clear()
        sessions = self.history_manager.get_all_sessions()
        for session in sessions:
            title = session['title']
            if not title: title = "New Chat"
            
            # Formatting date
            date_str = session['created_at']
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
                display_date = dt.strftime("%b %d, %H:%M")
            except:
                display_date = date_str[:16]
                
            display_text = f"{title}\n{display_date}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, session['session_id'])
            
            img_path = session.get('preview_image')
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(pixmap))
                
            self.list_widget.addItem(item)
            
    def open_selected(self):
        item = self.list_widget.currentItem()
        if item:
            session_id = item.data(Qt.ItemDataRole.UserRole)
            self.on_session_selected_callback(session_id)
    def on_item_double_clicked(self, item):
        self.open_selected()
        
    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        
        session_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Delete Chat", 
                                     "Are you sure you want to delete this chat and its images?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.delete_session(session_id)
            self.refresh_list()
