from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLineEdit, QApplication, QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src.capture.screen_grabber import ScreenGrabber
from src.ui.overlay_window import OverlayWindow
import os
import re
import json
import markdown

class AIWorker(QThread):
    finished = pyqtSignal(str)
    text_extracted = pyqtSignal(str)
    chunk_received = pyqtSignal(str)
    
    def __init__(self, ai_client, prompt, is_initial=False, base64_image=None, vision_task="ocr", vision_prompt=None):
        super().__init__()
        self.ai_client = ai_client
        self.prompt = prompt
        self.is_initial = is_initial
        self.base64_image = base64_image
        self.vision_task = vision_task
        self.vision_prompt = vision_prompt
        
    def run(self):
        if self.is_initial:
            result = self.ai_client.send_initial_request(
                self.prompt, 
                self.base64_image,
                on_text_extracted=self.text_extracted.emit,
                on_chunk=self.chunk_received.emit,
                vision_task=self.vision_task,
                vision_prompt=self.vision_prompt
            )
        else:
            result = self.ai_client.send_followup_request(
                self.prompt, 
                self.base64_image,
                on_text_extracted=self.text_extracted.emit,
                on_chunk=self.chunk_received.emit,
                vision_task=self.vision_task,
                vision_prompt=self.vision_prompt
            )
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
        self.is_page_loaded = False
        self.message_buffer = []
        
        self.setWindowTitle("ImageKit - Ask AI")
        self.setMinimumSize(500, 600)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
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
        
        central = QWidget()
        central.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                color: #ffffff;
            }
        """)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.chat_history = QWebEngineView()
        self.chat_history.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.chat_history.loadFinished.connect(self.on_page_loaded)
        
        # Setup base HTML for the web view
        base_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script>
                MathJax = {
                  tex: {
                    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
                  }
                };
            </script>
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            <style>
                html, body {
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    color: #e4e4e7;
                    background-color: #1e1e24;
                }
                #chat-container {
                    padding: 15px;
                    padding-bottom: 30px;
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin-bottom: 20px;
                }
                th, td {
                    border: 1px solid #3f3f46;
                    padding: 8px 12px;
                    text-align: left;
                }
                th {
                    background-color: #27272a;
                    font-weight: bold;
                }
                tr:nth-child(even) {
                    background-color: #18181b;
                }
                code {
                    background-color: #27272a;
                    color: #f472b6;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
                }
                pre {
                    background-color: #18181b;
                    border: 1px solid #3f3f46;
                    padding: 10px;
                    border-radius: 6px;
                    overflow-x: auto;
                }
                .mjx-chtml {
                    overflow-x: auto;
                    overflow-y: hidden;
                    color: #e4e4e7;
                }
                /* Customize scrollbar for dark theme */
                ::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                ::-webkit-scrollbar-track {
                    background: #1e1e24; 
                }
                ::-webkit-scrollbar-thumb {
                    background: #3f3f46; 
                    border-radius: 4px;
                }
                ::-webkit-scrollbar-thumb:hover {
                    background: #52525b; 
                }
            </style>
        </head>
        <body>
            <div id="chat-container"></div>
        </body>
        </html>
        """
        self.chat_history.setHtml(base_html)
        
        layout.addWidget(self.chat_history, 1) # stretch factor 1
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a1a1aa; font-style: italic; font-size: 12px; margin-left: 14px; margin-top: 5px;")
        # Fix label to have fixed small height so it doesn't take space when empty
        self.status_label.setFixedHeight(16)
        layout.addWidget(self.status_label)
        
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(14, 5, 14, 14)
        
        self.btn_attach = QPushButton("📎")
        self.btn_attach.setToolTip("Add Screenshot")
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setFixedHeight(40)
        self.btn_attach.setFixedWidth(46)
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                border-radius: 20px;
                font-size: 18px;
                border: 1px solid #3f3f46;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        self.btn_attach.clicked.connect(self.start_attach_capture)
        input_layout.addWidget(self.btn_attach)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask a follow-up question...")
        self.input_field.setFixedHeight(40)
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 0px 14px;
                border: 1px solid #3f3f46;
                border-radius: 20px;
                font-size: 14px;
                background-color: #27272a;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.input_field.returnPressed.connect(self.send_followup)
        input_layout.addWidget(self.input_field)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 20px;
                padding: 0px 20px;
                font-weight: 600;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #1d4ed8;
                color: #93c5fd;
            }
        """)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_followup)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        self.worker = None
        
        if self.session_id and self.history_manager:
            self.load_session()
            
    def on_page_loaded(self, ok):
        self.is_page_loaded = True
        for msg_html in self.message_buffer:
            self._inject_html(msg_html)
        self.message_buffer.clear()
        
    def _inject_html(self, html_str):
        js_safe_html = json.dumps(html_str)
        js = f"""
        var container = document.getElementById('chat-container');
        container.insertAdjacentHTML('beforeend', {js_safe_html});
        if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {{
            MathJax.typesetPromise().then(() => {{
                window.scrollTo(0, document.body.scrollHeight);
            }});
        }} else {{
            window.scrollTo(0, document.body.scrollHeight);
        }}
        """
        self.chat_history.page().runJavaScript(js)

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
            
            display_text = content
            if img_path and os.path.exists(img_path):
                img_html = f"<br><img src='file://{img_path}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
                display_text += img_html
                
            self.append_message(display_name, display_text)

    def append_message(self, role, text, stream_id=None):
        is_user = (role == "You")
        is_system = (role == "System")
        
        if is_user:
            header_color = "#0A84FF"
        elif is_system:
            header_color = "#8E8E93"
        else:
            header_color = "#34C759"
            
        html_body = self._parse_markdown(text, is_ai=(not is_user and not is_system))
        
        div_id = f"id='{stream_id}'" if stream_id else ""
        html = f"""
        <div style='margin-top: 24px; margin-bottom: 12px; font-family: system-ui, -apple-system, sans-serif;'>
            <div style='font-weight: 600; font-size: 13px; color: {header_color}; margin-bottom: 6px;'>{role}</div>
            <div {div_id} style='font-size: 14px; line-height: 1.5;'>{html_body}</div>
        </div>
        """
        
        if self.is_page_loaded:
            self._inject_html(html)
        else:
            self.message_buffer.append(html)

    def _parse_markdown(self, text, is_ai=False):
        if is_ai:
            math_blocks = []
            def math_repl(match):
                math_blocks.append(match.group(0))
                return f"@@MATH_{len(math_blocks)-1}@@"
                
            text_safe = re.sub(r'\$\$.*?\$\$', math_repl, text, flags=re.DOTALL)
            text_safe = re.sub(r'\\\[.*?\\\]', math_repl, text_safe, flags=re.DOTALL)
            text_safe = re.sub(r'\$.*?\$', math_repl, text_safe)
            text_safe = re.sub(r'\\\(.*?\\\)', math_repl, text_safe)
            
            html_body = markdown.markdown(text_safe, extensions=['tables'])
            
            for i, block in enumerate(math_blocks):
                html_body = html_body.replace(f"@@MATH_{i}@@", block)
            return html_body
        else:
            return text.replace(chr(10), '<br>')

    def on_text_extracted(self, text):
        html_text = f"<pre style='background-color: #F2F2F7; padding: 10px; border-radius: 6px; font-size: 13px; max-height: 200px; overflow-y: auto; white-space: pre-wrap; font-family: monospace;'>{text}</pre>"
        self.append_message("System", f"<i>Extracted text from image:</i><br>{html_text}")

    def on_chunk_received(self, chunk):
        if not hasattr(self, 'is_streaming'):
            self.is_streaming = False
            self.current_stream_text = ""
            
        if not self.is_streaming:
            self.is_streaming = True
            self.current_stream_text = chunk
            self.status_label.setText("Receiving response...")
            self.append_message("AI", self.current_stream_text, stream_id="current-stream")
        else:
            self.current_stream_text += chunk
            html_body = self._parse_markdown(self.current_stream_text, is_ai=True)
            js_safe_html = json.dumps(html_body)
            js = f"""
            var el = document.getElementById('current-stream');
            if (el) {{
                el.innerHTML = {js_safe_html};
                window.scrollTo(0, document.body.scrollHeight);
            }}
            """
            self.chat_history.page().runJavaScript(js)

    def start_initial_request(self, prompt, base64_img):
        self.last_user_prompt = prompt
        self.last_base64_image = base64_img
        self.is_streaming = False
        self.current_stream_text = ""
        
        display_text = prompt
        if base64_img:
            img_html = f"<br><img src='data:image/png;base64,{base64_img}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
            display_text += img_html
            
        self.append_message("You", display_text)
        
        if base64_img:
            self.status_label.setText("Analyzing image with Vision model...")
        else:
            self.status_label.setText("Thinking...")
            
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.btn_attach.setEnabled(False)
        
        self.worker = AIWorker(self.ai_client, prompt, is_initial=True, base64_image=base64_img)
        self.worker.finished.connect(self.on_response)
        self.worker.text_extracted.connect(self.on_text_extracted)
        self.worker.chunk_received.connect(self.on_chunk_received)
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
                border-radius: 20px;
                font-size: 18px;
                border: none;
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
        
        self.is_streaming = False
        self.current_stream_text = ""
        
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
                background-color: #27272a;
                color: #ffffff;
                border-radius: 20px;
                font-size: 18px;
                border: 1px solid #3f3f46;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        
        base64_img = self.pending_image
        self.pending_image = None
        
        self.last_user_prompt = prompt
        self.last_base64_image = base64_img
        
        # Preserve the vision task mode for follow-ups
        v_task = getattr(self, "current_vision_task", "ocr")
        v_prompt = getattr(self, "current_vision_prompt", None)
        
        self.worker = AIWorker(self.ai_client, prompt, is_initial=False, base64_image=base64_img, vision_task=v_task, vision_prompt=v_prompt)
        self.worker.finished.connect(self.on_response)
        self.worker.text_extracted.connect(self.on_text_extracted)
        self.worker.chunk_received.connect(self.on_chunk_received)
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
        
        if getattr(self, 'is_streaming', False):
            # Finalize stream: typeset mathjax
            html_body = self._parse_markdown(text, is_ai=True)
            js_safe_html = json.dumps(html_body)
            js = f"""
            var el = document.getElementById('current-stream');
            if (el) {{
                el.innerHTML = {js_safe_html};
                el.removeAttribute('id');
                if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {{
                    MathJax.typesetPromise([el]).then(() => {{
                        window.scrollTo(0, document.body.scrollHeight);
                    }});
                }}
            }}
            """
            self.chat_history.page().runJavaScript(js)
            self.is_streaming = False
        else:
            # Fallback if streaming didn't fire chunks
            self.append_message("AI", text)
            
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.btn_attach.setEnabled(True)
        self.input_field.setFocus()
