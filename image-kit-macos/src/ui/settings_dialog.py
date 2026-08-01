from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QCheckBox, QFormLayout)
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsDialog(QDialog):
    signal_key_recorded = pyqtSignal(str)
    
    def __init__(self, config_manager, hotkey_listener=None):
        super().__init__()
        self.config = config_manager
        self.hotkey_listener = hotkey_listener
        self.signal_key_recorded.connect(self._apply_recorded_key)
        
        self.setWindowTitle("ImageKit Settings")
        self.setMinimumWidth(400)
        
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
        form_layout.addRow("Ask AI Vision API URL:", self.vision_api_input)
        
        self.vision_model_input = QLineEdit(self.config.get("vision_model"))
        form_layout.addRow("Ask AI Vision Model:", self.vision_model_input)
        
        self.ai_api_input = QLineEdit(self.config.get("ai_api_url"))
        form_layout.addRow("Ask AI Chat API URL:", self.ai_api_input)
        
        self.chat_model_input = QLineEdit(self.config.get("chat_model"))
        form_layout.addRow("Ask AI Chat Model:", self.chat_model_input)
        
        layout.addLayout(form_layout)
        
        # Checkboxes
        self.cb_clipboard = QCheckBox("Copy OCR result to clipboard automatically")
        self.cb_clipboard.setChecked(self.config.get("copy_to_clipboard", True))
        layout.addWidget(self.cb_clipboard)
        
        self.cb_editor = QCheckBox("Show editor window after OCR")
        self.cb_editor.setChecked(self.config.get("show_editor", True))
        layout.addWidget(self.cb_editor)
        
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
        self.config.set("chat_model", self.chat_model_input.text().strip())
        self.config.set("copy_to_clipboard", self.cb_clipboard.isChecked())
        self.config.set("show_editor", self.cb_editor.isChecked())
        
        # Fix Crash: Only update hotkey listener if it actually changed
        if self.hotkey_listener and new_hotkey and new_hotkey != old_hotkey:
            self.hotkey_listener.update_hotkey(new_hotkey)
            
        self.accept()
