from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QCheckBox, QFormLayout, QListWidget, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal

class VisionPromptsConfigDialog(QDialog):
    def __init__(self, prompts, parent=None):
        super().__init__(parent)
        self.prompts = prompts.copy() if prompts else {}
        self.setWindowTitle("Configure Vision Prompts")
        self.resize(700, 450)
        
        layout = QVBoxLayout(self)
        
        # Splitter for Master-Detail view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: List of categories
        left_widget = QListWidget()
        self.list_widget = left_widget
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        splitter.addWidget(left_widget)
        
        # Right side: Editor
        right_widget = QVBoxLayout()
        right_container = QDialog() # Dummy container for layout
        right_container.setLayout(right_widget)
        
        right_widget.addWidget(QLabel("Category Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        right_widget.addWidget(self.name_edit)
        
        right_widget.addWidget(QLabel("Prompt Text:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.textChanged.connect(self._on_prompt_changed)
        right_widget.addWidget(self.prompt_edit)
        
        splitter.addWidget(right_container)
        splitter.setSizes([200, 500])
        layout.addWidget(splitter)
        
        # Populate list
        self.ignore_changes = True
        for name, text in self.prompts.items():
            self.list_widget.addItem(name)
        self.ignore_changes = False
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Prompt")
        self.btn_add.clicked.connect(self._add_prompt)
        
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._remove_prompt)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
    def _on_row_changed(self, row):
        if row < 0 or self.ignore_changes:
            return
        
        self.ignore_changes = True
        name = self.list_widget.item(row).text()
        self.name_edit.setText(name)
        self.prompt_edit.setPlainText(self.prompts.get(name, ""))
        self.ignore_changes = False
        
    def _on_name_changed(self, new_name):
        if self.ignore_changes: return
        row = self.list_widget.currentRow()
        if row < 0: return
        
        item = self.list_widget.item(row)
        old_name = item.text()
        if old_name != new_name:
            # Update dictionary key
            val = self.prompts.pop(old_name, "")
            self.prompts[new_name] = val
            
            self.ignore_changes = True
            item.setText(new_name)
            self.ignore_changes = False
            
    def _on_prompt_changed(self):
        if self.ignore_changes: return
        row = self.list_widget.currentRow()
        if row < 0: return
        
        name = self.list_widget.item(row).text()
        self.prompts[name] = self.prompt_edit.toPlainText()
        
    def _add_prompt(self):
        base_name = "New Category"
        name = base_name
        counter = 1
        while name in self.prompts:
            name = f"{base_name} {counter}"
            counter += 1
            
        self.prompts[name] = "Enter prompt here..."
        
        self.ignore_changes = True
        self.list_widget.addItem(name)
        self.ignore_changes = False
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        
    def _remove_prompt(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            name = self.list_widget.item(row).text()
            self.prompts.pop(name, None)
            
            self.ignore_changes = True
            self.list_widget.takeItem(row)
            self.ignore_changes = False
            
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))
            else:
                self.name_edit.clear()
                self.prompt_edit.clear()
            
    def _save(self):
        self.accept()

class SettingsDialog(QDialog):
    signal_key_recorded = pyqtSignal(str)
    
    def __init__(self, config_manager, hotkey_listener=None):
        super().__init__()
        self.config = config_manager
        self.hotkey_listener = hotkey_listener
        self.signal_key_recorded.connect(self._apply_recorded_key)
        self.current_vision_prompts = self.config.get("vision_prompts", {}).copy()
        
        self.setWindowTitle("ImageKit Settings")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Hotkey UI ported from VoiceKit
        hotkey_box = QHBoxLayout()
        self.hotkey_input = QLineEdit(self.config.get("hotkey"))
        self.hotkey_input.setPlaceholderText("cmd+shift+2")
        hotkey_box.addWidget(self.hotkey_input)
        
        self.btn_record_hotkey = QPushButton("🎯 Record Shortcut")
        self.btn_record_hotkey.clicked.connect(self._on_record_hotkey_clicked)
        hotkey_box.addWidget(self.btn_record_hotkey)
        
        form_layout.addRow("Global Hotkey:", hotkey_box)
        
        # OCR API
        self.api_input = QLineEdit(self.config.get("api_url"))
        form_layout.addRow("OCR API URL:", self.api_input)
        
        self.model_input = QLineEdit(self.config.get("model"))
        form_layout.addRow("OCR Model:", self.model_input)
        
        self.vision_api_input = QLineEdit(self.config.get("vision_api_url", self.config.get("ai_api_url")))
        form_layout.addRow("Vision / Ask AI API URL:", self.vision_api_input)
        
        self.vision_model_input = QLineEdit(self.config.get("vision_model"))
        form_layout.addRow("Vision OCR Model:", self.vision_model_input)
        
        self.general_vision_model_input = QLineEdit(self.config.get("general_vision_model", "qwen2.5vl:3b"))
        form_layout.addRow("General Vision Model:", self.general_vision_model_input)
        
        self.chat_model_input = QLineEdit(self.config.get("chat_model"))
        form_layout.addRow("Ask AI Chat Model:", self.chat_model_input)
        
        self.ai_api_input = QLineEdit(self.config.get("ai_api_url"))
        form_layout.addRow("Ask AI Chat API URL:", self.ai_api_input)
        
        layout.addLayout(form_layout)
        
        # Checkboxes
        self.cb_clipboard = QCheckBox("Copy OCR result to clipboard automatically")
        self.cb_clipboard.setChecked(self.config.get("copy_to_clipboard", True))
        layout.addWidget(self.cb_clipboard)
        
        self.cb_editor = QCheckBox("Show editor window after OCR / Vision")
        self.cb_editor.setChecked(self.config.get("show_editor", True))
        layout.addWidget(self.cb_editor)
        
        # Prompts Config
        self.btn_config_prompts = QPushButton("Configure Vision Prompts...")
        self.btn_config_prompts.clicked.connect(self._open_prompts_config)
        layout.addWidget(self.btn_config_prompts)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def _open_prompts_config(self):
        dialog = VisionPromptsConfigDialog(self.current_vision_prompts, self)
        if dialog.exec():
            self.current_vision_prompts = dialog.prompts

    def _on_record_hotkey_clicked(self):
        from src.ui.permissions_dialog import check_accessibility, PermissionsDialog
        if not check_accessibility():
            dialog = PermissionsDialog(self)
            dialog.exec()
            if not check_accessibility():
                return
                
        self.btn_record_hotkey.setText("⏳ Press any key...")
        self.btn_record_hotkey.setEnabled(False)

        def _on_recorded(res: str):
            self.signal_key_recorded.emit(res)

        if self.hotkey_listener and hasattr(self.hotkey_listener, 'on_record_key_callback'):
            self.hotkey_listener.on_record_key_callback = _on_recorded
        else:
            from pynput import keyboard
            listener_ref = [None]

            def _on_press(key):
                name = getattr(key, 'name', None)
                vk = getattr(key, 'vk', None)
                key_str = str(key).replace('key.', '').replace('Key.', '').lower()
                if name:
                    res = name
                elif vk is not None:
                    res = f"<{vk}>"
                else:
                    res = key_str.strip("'")
                
                _on_recorded(res)
                if listener_ref[0]:
                    listener_ref[0].stop()
                return False

            listener_ref[0] = keyboard.Listener(on_press=_on_press)
            listener_ref[0].start()

    def _apply_recorded_key(self, key_str: str):
        self.hotkey_input.setText(key_str)
        self.btn_record_hotkey.setText("🎯 Record Shortcut")
        self.btn_record_hotkey.setEnabled(True)

    def save_settings(self):
        old_hotkey = self.config.get("hotkey")
        new_hotkey = self.hotkey_input.text().strip()
        
        self.config.set("hotkey", new_hotkey)
        self.config.set("api_url", self.api_input.text().strip())
        self.config.set("model", self.model_input.text().strip())
        self.config.set("ai_api_url", self.ai_api_input.text().strip())
        self.config.set("vision_api_url", self.vision_api_input.text().strip())
        self.config.set("vision_model", self.vision_model_input.text().strip())
        self.config.set("general_vision_model", self.general_vision_model_input.text().strip())
        self.config.set("chat_model", self.chat_model_input.text().strip())
        self.config.set("copy_to_clipboard", self.cb_clipboard.isChecked())
        self.config.set("show_editor", self.cb_editor.isChecked())
        self.config.set("vision_prompts", self.current_vision_prompts)
        
        # Fix Crash: Only update hotkey listener if it actually changed
        if self.hotkey_listener and new_hotkey and new_hotkey != old_hotkey:
            self.hotkey_listener.update_hotkey(new_hotkey)
            
        self.accept()
