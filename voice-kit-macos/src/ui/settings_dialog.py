from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QGroupBox, QFormLayout, QTabWidget, QWidget, QMessageBox, QSpinBox
)
from src.config_manager import ConfigManager
import sounddevice as sd


class SettingsDialog(QDialog):
    signal_config_changed = pyqtSignal()
    signal_key_recorded = pyqtSignal(str)

    def __init__(self, config_manager: ConfigManager, hotkey_listener=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.hotkey_listener = hotkey_listener
        self.signal_key_recorded.connect(self._apply_recorded_key)
        self.setWindowTitle("VoiceKit macOS Settings")
        self.resize(480, 400)
        self._init_ui()
        self._load_from_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget(self)

        # Tab 1: General & Hotkeys
        gen_tab = QWidget()
        gen_layout = QFormLayout(gen_tab)
        
        hotkey_box = QHBoxLayout()
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("right_fn")
        hotkey_box.addWidget(self.hotkey_input)

        self.btn_record_hotkey = QPushButton("🎯 Record Shortcut")
        self.btn_record_hotkey.clicked.connect(self._on_record_hotkey_clicked)
        hotkey_box.addWidget(self.btn_record_hotkey)
        gen_layout.addRow("Global Hotkey:", hotkey_box)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["toggle", "hold"])
        gen_layout.addRow("Recording Mode:", self.mode_combo)

        self.mic_combo = QComboBox()
        try:
            default_input = sd.default.device[0]
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    name = d["name"]
                    if i == default_input:
                        name += " (Default)"
                    self.mic_combo.addItem(name, userData=i)
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            self.mic_combo.addItem("Default Microphone", userData=None)
        gen_layout.addRow("Microphone:", self.mic_combo)

        self.max_rec_spin = QSpinBox()
        self.max_rec_spin.setRange(10, 5000)
        self.max_rec_spin.setSingleStep(50)
        gen_layout.addRow("Keep Recordings:", self.max_rec_spin)

        self.btn_check_perms = QPushButton("🔐 Check macOS Accessibility Permission...")
        self.btn_check_perms.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_perms.clicked.connect(self._check_mac_perms)
        gen_layout.addRow("", self.btn_check_perms)

        self.tabs.addTab(gen_tab, "General")

        # Tab 2: Transcription Provider
        trans_tab = QWidget()
        trans_layout = QVBoxLayout(trans_tab)

        provider_form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["voice_editor", "openai", "groq", "local"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_form.addRow("Provider:", self.provider_combo)

        # Voice Editor Settings
        self.grp_ve = QGroupBox("Voice Editor (Live Streaming)")
        ve_form = QFormLayout(self.grp_ve)
        self.ve_url_input = QLineEdit()
        self.ve_url_input.setPlaceholderText("wss://voice-editor.minipc.na/ws/transcribe")
        ve_form.addRow("WebSocket URL:", self.ve_url_input)
        self.ve_cleanup_chk = QCheckBox("Enable LLM copy-editing (punctuation, proper nouns)")
        ve_form.addRow("", self.ve_cleanup_chk)
        self.cf_id_input = QLineEdit()
        self.cf_id_input.setPlaceholderText("Optional Cloudflare CF-Access-Client-Id")
        ve_form.addRow("CF Access ID:", self.cf_id_input)
        self.cf_secret_input = QLineEdit()
        self.cf_secret_input.setPlaceholderText("Optional Cloudflare CF-Access-Client-Secret")
        self.cf_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        ve_form.addRow("CF Access Secret:", self.cf_secret_input)

        # OpenAI Settings
        self.grp_oa = QGroupBox("OpenAI Whisper")
        oa_form = QFormLayout(self.grp_oa)
        self.oa_key_input = QLineEdit()
        self.oa_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        oa_form.addRow("API Key:", self.oa_key_input)
        self.oa_model_input = QLineEdit("whisper-1")
        oa_form.addRow("Model:", self.oa_model_input)

        # Groq Settings
        self.grp_groq = QGroupBox("Groq Whisper")
        groq_form = QFormLayout(self.grp_groq)
        self.groq_key_input = QLineEdit()
        self.groq_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        groq_form.addRow("API Key:", self.groq_key_input)
        self.groq_model_input = QLineEdit("whisper-large-v3")
        groq_form.addRow("Model:", self.groq_model_input)

        # Local Whisper Settings
        self.grp_local = QGroupBox("Local Whisper")
        local_form = QFormLayout(self.grp_local)
        self.local_model_combo = QComboBox()
        self.local_model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        local_form.addRow("Model Size:", self.local_model_combo)

        trans_layout.addLayout(provider_form)
        trans_layout.addWidget(self.grp_ve)
        trans_layout.addWidget(self.grp_oa)
        trans_layout.addWidget(self.grp_groq)
        trans_layout.addWidget(self.grp_local)
        trans_layout.addStretch()

        self.tabs.addTab(trans_tab, "Transcription")

        # Tab 3: OpenClaw & TTS
        oc_tab = QWidget()
        oc_layout = QFormLayout(oc_tab)
        
        self.oc_url_input = QLineEdit()
        self.oc_url_input.setPlaceholderText("http://openclaw.minipc.na/v1/chat/completions")
        oc_layout.addRow("OpenClaw URL:", self.oc_url_input)
        
        self.oc_token_input = QLineEdit()
        self.oc_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.oc_token_input.setPlaceholderText("OpenClaw Bearer Token")
        oc_layout.addRow("OpenClaw Token:", self.oc_token_input)
        
        self.oc_model_input = QLineEdit()
        self.oc_model_input.setPlaceholderText("openclaw/voice-kit")
        oc_layout.addRow("OpenClaw Model:", self.oc_model_input)
        
        self.tts_url_input = QLineEdit()
        self.tts_url_input.setPlaceholderText("http://kokoro.minipc.na/v1/audio/speech")
        oc_layout.addRow("TTS (Kokoro) URL:", self.tts_url_input)
        
        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.addItems(["af_bella", "af_sarah", "am_adam", "am_michael"])
        oc_layout.addRow("TTS Voice:", self.tts_voice_combo)
        
        self.tabs.addTab(oc_tab, "OpenClaw / TTS")

        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_provider_changed(self, provider: str):
        self.grp_ve.setVisible(provider == "voice_editor")
        self.grp_oa.setVisible(provider == "openai")
        self.grp_groq.setVisible(provider == "groq")
        self.grp_local.setVisible(provider == "local")

    def _load_from_config(self):
        cfg = self.config_manager
        self.hotkey_input.setText(cfg.get("hotkey.combination", "right_fn"))
        self.mode_combo.setCurrentText(cfg.get("hotkey.mode", "toggle"))
        
        mic_id = cfg.get("audio.device_id", None)
        if mic_id is not None:
            idx = self.mic_combo.findData(mic_id)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)

        self.max_rec_spin.setValue(int(cfg.get("history.max_recordings", 100)))

        provider = cfg.get("transcription.provider", "voice_editor")
        self.provider_combo.setCurrentText(provider)
        self._on_provider_changed(provider)

        self.ve_url_input.setText(cfg.get("transcription.voice_editor.url", "wss://voice-editor.minipc.na/ws/transcribe"))
        self.ve_cleanup_chk.setChecked(cfg.get("transcription.voice_editor.do_cleanup", True))
        headers = cfg.get("transcription.voice_editor.headers", {})
        self.cf_id_input.setText(headers.get("CF-Access-Client-Id", ""))
        self.cf_secret_input.setText(headers.get("CF-Access-Client-Secret", ""))

        self.oa_key_input.setText(cfg.get("transcription.openai.api_key", ""))
        self.oa_model_input.setText(cfg.get("transcription.openai.model", "whisper-1"))

        self.groq_key_input.setText(cfg.get("transcription.groq.api_key", ""))
        self.groq_model_input.setText(cfg.get("transcription.groq.model", "whisper-large-v3"))

        self.local_model_combo.setCurrentText(cfg.get("transcription.local.model_size", "base"))

        self.oc_url_input.setText(cfg.get("openclaw.url", "http://openclaw.minipc.na/v1/chat/completions"))
        self.oc_token_input.setText(cfg.get("openclaw.token", ""))
        self.oc_model_input.setText(cfg.get("openclaw.model", "openclaw/voice-kit"))
        self.tts_url_input.setText(cfg.get("tts.kokoro_url", "http://kokoro.minipc.na/v1/audio/speech"))
        self.tts_voice_combo.setCurrentText(cfg.get("tts.voice", "af_bella"))

    def _save_and_close(self):
        cfg = self.config_manager
        cfg.set("hotkey.combination", self.hotkey_input.text().strip() or "right_fn")
        cfg.set("hotkey.mode", self.mode_combo.currentText())
        
        mic_id = self.mic_combo.currentData()
        if mic_id is not None:
            cfg.set("audio.device_id", int(mic_id))
        else:
            cfg.set("audio.device_id", None)
            
        cfg.set("history.max_recordings", int(self.max_rec_spin.value()))
        cfg.set("clipboard.auto_paste", True)
        cfg.set("clipboard.restore_clipboard", False)
        cfg.set("clipboard.direct_typing", False)
        cfg.set("ui.show_edit_window", False)

        cfg.set("transcription.provider", self.provider_combo.currentText())
        cfg.set("transcription.voice_editor.url", self.ve_url_input.text().strip())
        cfg.set("transcription.voice_editor.do_cleanup", self.ve_cleanup_chk.isChecked())

        headers = cfg.get("transcription.voice_editor.headers", {})
        cf_id = self.cf_id_input.text().strip()
        cf_secret = self.cf_secret_input.text().strip()
        if cf_id and cf_secret:
            headers["CF-Access-Client-Id"] = cf_id
            headers["CF-Access-Client-Secret"] = cf_secret
        else:
            headers.pop("CF-Access-Client-Id", None)
            headers.pop("CF-Access-Client-Secret", None)
        cfg.set("transcription.voice_editor.headers", headers)

        cfg.set("transcription.openai.api_key", self.oa_key_input.text().strip())
        cfg.set("transcription.openai.model", self.oa_model_input.text().strip())

        cfg.set("transcription.groq.api_key", self.groq_key_input.text().strip())
        cfg.set("transcription.groq.model", self.groq_model_input.text().strip())

        cfg.set("transcription.local.model_size", self.local_model_combo.currentText())

        cfg.set("openclaw.url", self.oc_url_input.text().strip())
        cfg.set("openclaw.token", self.oc_token_input.text().strip())
        cfg.set("openclaw.model", self.oc_model_input.text().strip() or "openclaw/voice-kit")
        cfg.set("tts.kokoro_url", self.tts_url_input.text().strip())
        cfg.set("tts.voice", self.tts_voice_combo.currentText())

        self.signal_config_changed.emit()
        self.accept()

    def _on_record_hotkey_clicked(self):
        self.btn_record_hotkey.setText("⏳ Press any key...")
        self.btn_record_hotkey.setEnabled(False)

        def _on_recorded(res: str):
            self.signal_key_recorded.emit(res)

        if self.hotkey_listener:
            self.hotkey_listener.on_record_key_callback = _on_recorded
        else:
            def _capture_key():
                from pynput import keyboard
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
                    return False

                with keyboard.Listener(on_press=_on_press) as listener:
                    listener.join()

            import threading
            threading.Thread(target=_capture_key, daemon=True).start()

    def _apply_recorded_key(self, key_str: str):
        self.hotkey_input.setText(key_str)
        self.btn_record_hotkey.setText("🎯 Record Shortcut")
        self.btn_record_hotkey.setEnabled(True)

    def _check_mac_perms(self):
        from src.ui.permissions_dialog import check_accessibility, PermissionsDialog
        if check_accessibility():
            QMessageBox.information(self, "Permission Active", "macOS Accessibility permission is active! Your global hotkeys will work cleanly.")
        else:
            dlg = PermissionsDialog(self)
            dlg.exec()

