from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import Qt

class PromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ask AI")
        self.setMinimumWidth(300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        label = QLabel("What would you like to ask about this region?")
        layout.addWidget(label)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("e.g. Extract the text, explain this chart, etc.")
        self.input_field.returnPressed.connect(self.accept)
        layout.addWidget(self.input_field)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_submit = QPushButton("Ask")
        self.btn_submit.setStyleSheet("background-color: #0984e3; color: white; font-weight: bold;")
        self.btn_submit.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_submit)
        layout.addLayout(btn_layout)

    def get_prompt(self):
        return self.input_field.text().strip()
