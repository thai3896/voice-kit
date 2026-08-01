from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLineEdit, QApplication, QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from src.capture.screen_grabber import ScreenGrabber
from src.ui.overlay_window import OverlayWindow
import os

class AIWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, ai_client, prompt, is_initial=False, base64_image=None):
        super().__init__()
        self.ai_client = ai_client
        self.prompt = prompt
        self.is_initial = is_initial
        self.base64_image = base64_image
        
    def run(self):
        if self.is_initial:
            result = self.ai_client.send_initial_request(self.prompt, self.base64_image)
        else:
            result = self.ai_client.send_followup_request(self.prompt, self.base64_image)
        self.finished.emit(result)

class ChatWindow(QMainWindow):
    def __init__(self, ai_client, history_manager=None, session_id=None):
        super().__init__()
        self.ai_client = ai_client
        self.history_manager = history_manager
        self.session_id = session_id
        self.pending_image = None
        self.last_user_prompt = ""
        self.last_base64_image = None
        self.overlay = None
        
        self.setWindowTitle("ImageKit - Ask AI")
        self.setMinimumSize(500, 600)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.setGeometry(x, y, self.width(), self.height())
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                font-size: 14px;
                padding: 10px;
                border: none;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.chat_history)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8E8E93; font-style: italic; font-size: 12px; margin-left: 10px;")
        layout.addWidget(self.status_label)
        
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(10, 5, 10, 10)
        
        self.btn_attach = QPushButton("📎")
        self.btn_attach.setToolTip("Add Screenshot")
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background-color: #E5E5EA;
                border-radius: 18px;
                padding: 8px 12px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #D1D1D6;
            }
        """)
        self.btn_attach.clicked.connect(self.start_attach_capture)
        input_layout.addWidget(self.btn_attach)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask a follow-up question...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #C7C7CC;
                border-radius: 18px;
                font-size: 14px;
            }
        """)
        self.input_field.returnPressed.connect(self.send_followup)
        input_layout.addWidget(self.input_field)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A84FF;
                color: white;
                border-radius: 18px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:disabled {
                background-color: #B0D4FF;
            }
        """)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_followup)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        self.worker = None
        
        if self.session_id and self.history_manager:
            self.load_session()
            
    def load_session(self):
        messages = self.history_manager.get_session_messages(self.session_id)
        self.ai_client.messages = []
        for msg in messages:
            role = msg['role']
            content = msg['text_content']
            img_path = msg.get('image_path')
            
            # Load into AI Client context
            self.ai_client.messages.append({"role": role, "content": content})
            
            # Load into UI
            display_name = "You" if role == "user" else "AI"
            
            # Since content for 'user' contains the huge OCR prompt context, 
            # we should clean it up for UI display if we can, or just display it.
            # A simple way to display it is just to show the raw text for now.
            display_text = content
            
            if img_path and os.path.exists(img_path):
                img_html = f"<br><img src='file://{img_path}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
                display_text += img_html
                
            self.append_message(display_name, display_text)

    def append_message(self, role, text):
        is_user = (role == "You")
        header_color = "#0A84FF" if is_user else "#34C759"
        
        formatted_text = text.replace(chr(10), '<br>')
        
        html = f"""
        <div style='margin-top: 12px; margin-bottom: 12px; font-family: system-ui, -apple-system, sans-serif;'>
            <div style='font-weight: 600; font-size: 13px; color: {header_color}; margin-bottom: 4px;'>{role}</div>
            <div style='font-size: 14px; line-height: 1.5;'>{formatted_text}</div>
        </div>
        """
        self.chat_history.append(html)

    def start_initial_request(self, prompt, base64_img):
        self.last_user_prompt = prompt
        self.last_base64_image = base64_img
        
        img_html = f"<br><img src='data:image/png;base64,{base64_img}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
        self.append_message("You", f"{prompt}{img_html}")
        
        self.status_label.setText("Analyzing image with Vision model...")
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.btn_attach.setEnabled(False)
        
        self.worker = AIWorker(self.ai_client, prompt, is_initial=True, base64_image=base64_img)
        self.worker.finished.connect(self.on_response)
        self.worker.start()

    def start_attach_capture(self):
        self.hide() # Hide chat window temporarily
        try:
            pixmap, screen = ScreenGrabber.capture_active_screen()
            if pixmap and not pixmap.isNull():
                self.overlay = OverlayWindow(pixmap, screen.geometry())
                self.overlay.selection_made.connect(self.on_attach_selected)
                self.overlay.ai_selection_made.connect(self.on_attach_selected)
                self.overlay.cancelled.connect(self.on_attach_cancelled)
                self.overlay.show()
                self.overlay.activateWindow()
                self.overlay.raise_()
            else:
                self.show()
        except Exception as e:
            print(f"Error capturing for attachment: {e}")
            self.show()

    def on_attach_selected(self, rect):
        if not self.overlay: return
        cropped = self.overlay.pixmap.copy(rect)
        self.overlay.close()
        self.overlay = None
        
        self.pending_image = ScreenGrabber.pixmap_to_base64(cropped)
        self.btn_attach.setText("✅")
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background-color: #34C759;
                color: white;
                border-radius: 18px;
                padding: 8px 12px;
                font-size: 18px;
            }
        """)
        self.show()
        self.activateWindow()

    def on_attach_cancelled(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        self.show()
        self.activateWindow()

    def send_followup(self):
        prompt = self.input_field.text().strip()
        if not prompt and not self.pending_image: return
        
        display_text = prompt
        if self.pending_image:
            img_html = f"<br><img src='data:image/png;base64,{self.pending_image}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
            display_text += img_html
            
        self.input_field.clear()
        self.append_message("You", display_text)
        self.status_label.setText("Thinking...")
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.btn_attach.setEnabled(False)
        
        # Reset attach button UI
        self.btn_attach.setText("📎")
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background-color: #E5E5EA;
                border-radius: 18px;
                padding: 8px 12px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #D1D1D6;
            }
        """)
        
        base64_img = self.pending_image
        self.pending_image = None
        
        self.last_user_prompt = prompt
        self.last_base64_image = base64_img
        
        self.worker = AIWorker(self.ai_client, prompt, is_initial=False, base64_image=base64_img)
        self.worker.finished.connect(self.on_response)
        self.worker.start()

    def on_response(self, text):
        if self.history_manager:
            if not self.session_id:
                title = self.last_user_prompt[:30] if self.last_user_prompt else "New Chat"
                self.session_id = self.history_manager.create_session(title=title)
                
            if len(self.ai_client.messages) >= 2:
                user_content = self.ai_client.messages[-2]['content']
                self.history_manager.add_message(self.session_id, "user", user_content, self.last_base64_image)
            self.history_manager.add_message(self.session_id, "assistant", text)
            
        self.last_base64_image = None
        
        self.status_label.setText("")
        self.append_message("AI", text)
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.btn_attach.setEnabled(True)
        self.input_field.setFocus()
