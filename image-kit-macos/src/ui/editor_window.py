from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QApplication, QTextEdit
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
import pyperclip
import markdown
import re

class EditorWindow(QMainWindow):
    ask_ai_requested = pyqtSignal(str)
    
    def __init__(self, text, config_manager=None):
        super().__init__()
        self.config = config_manager
        self.raw_text = text
        self.setWindowTitle("ImageKit OCR Result")
        self.setMinimumSize(700, 500)
        
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
        
        # WebView for rendered HTML
        self.web_view = QWebEngineView()
        
        # TextEdit for raw Markdown editing (hidden by default)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.raw_text)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
                font-size: 14px;
                padding: 10px;
                background-color: #f1f2f6;
                color: #2d3436;
                border: 1px solid #dfe6e9;
                border-radius: 4px;
            }
        """)
        self.text_edit.hide()
        
        layout.addWidget(self.web_view)
        layout.addWidget(self.text_edit)
        
        self._render_preview()
        
        btn_layout = QHBoxLayout()
        
        self.toggle_btn = QPushButton("Edit Raw Markdown")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #00b894;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #55efc4;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_mode)
        
        self.copy_btn = QPushButton("Copy Raw Markdown")
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
        
        self.ask_ai_btn = QPushButton("Ask AI")
        self.ask_ai_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c5ce7;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a29bfe;
            }
        """)
        self.ask_ai_btn.clicked.connect(self.trigger_ask_ai)
        
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
        btn_layout.addWidget(self.ask_ai_btn)
        btn_layout.addWidget(self.toggle_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        self.is_editing = False

    def set_text(self, text):
        self.raw_text = text
        if self.is_editing:
            self.text_edit.setPlainText(text)
        else:
            self._render_preview()

    def trigger_ask_ai(self):
        # Always use the most up-to-date raw text
        if self.is_editing:
            self.raw_text = self.text_edit.toPlainText()
        self.ask_ai_requested.emit(self.raw_text)
        self.close()

    def toggle_mode(self):
        if self.is_editing:
            # Switch to Preview Mode
            self.raw_text = self.text_edit.toPlainText()
            self._render_preview()
            self.text_edit.hide()
            self.web_view.show()
            self.toggle_btn.setText("Edit Raw Markdown")
            self.is_editing = False
        else:
            # Switch to Edit Mode
            self.web_view.hide()
            self.text_edit.setPlainText(self.raw_text)
            self.text_edit.show()
            self.toggle_btn.setText("Preview HTML")
            self.is_editing = True

    def _render_preview(self):
        # Protect math blocks from markdown parser mangling
        math_blocks = []
        def math_repl(match):
            math_blocks.append(match.group(0))
            return f"@@MATH_{len(math_blocks)-1}@@"
            
        # Match $$ ... $$ (non-greedy, including newlines)
        text_safe = re.sub(r'\$\$.*?\$\$', math_repl, self.raw_text, flags=re.DOTALL)
        # Match \[ ... \] (non-greedy, including newlines)
        text_safe = re.sub(r'\\\[.*?\\\]', math_repl, text_safe, flags=re.DOTALL)
        # Match $ ... $ (non-greedy, inline)
        text_safe = re.sub(r'\$.*?\$', math_repl, text_safe)
        # Match \( ... \) (non-greedy, inline)
        text_safe = re.sub(r'\\\(.*?\\\)', math_repl, text_safe)
        
        # Parse markdown to HTML (enable tables)
        html_body = markdown.markdown(text_safe, extensions=['tables'])
        
        # Restore math blocks
        for i, block in enumerate(math_blocks):
            html_body = html_body.replace(f"@@MATH_{i}@@", block)
        
        # Wrap in basic HTML structure with CSS for tables and MathJax for formulas
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script>
                MathJax = {{
                  tex: {{
                    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
                  }}
                }};
            </script>
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    color: #2d3436;
                    background-color: #ffffff;
                    padding: 10px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin-bottom: 20px;
                }}
                th, td {{
                    border: 1px solid #dfe6e9;
                    padding: 8px 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f5f6fa;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                code {{
                    background-color: #f1f2f6;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
                }}
                pre {{
                    background-color: #f1f2f6;
                    padding: 10px;
                    border-radius: 4px;
                    overflow-x: auto;
                }}
                /* Make mathjax elements scrollable if they are too wide */
                .mjx-chtml {{
                    overflow-x: auto;
                    overflow-y: hidden;
                }}
            </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)

    def copy_text(self):
        # Always copy the most up-to-date raw text
        if self.is_editing:
            self.raw_text = self.text_edit.toPlainText()
        pyperclip.copy(self.raw_text)
        self.copy_btn.setText("Copied!")
        
    def closeEvent(self, event):
        super().closeEvent(event)
