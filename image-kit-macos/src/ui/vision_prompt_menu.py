from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QApplication
from PyQt6.QtCore import Qt, pyqtSignal

class VisionPromptMenu(QDialog):
    prompt_selected = pyqtSignal(str)
    
    def __init__(self, prompts_dict, parent=None):
        super().__init__(parent)
        self.prompts_dict = prompts_dict
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d3436;
                color: white;
                border: 1px solid #636e72;
                border-radius: 6px;
                font-size: 14px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #636e72;
            }
            QListWidget::item:selected {
                background-color: #0984e3;
            }
        """)
        
        for name in self.prompts_dict.keys():
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
            
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)
        
        # Calculate size based on items
        self.setFixedWidth(200)
        self.setFixedHeight(min(300, (len(self.prompts_dict) * 45) + 12))
        
    def on_item_clicked(self, item):
        prompt_name = item.text()
        prompt_text = self.prompts_dict.get(prompt_name)
        if prompt_text:
            self.prompt_selected.emit(prompt_text)
        self.close()
