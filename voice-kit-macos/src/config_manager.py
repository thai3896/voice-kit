import os
import yaml
from typing import Any, Dict

DEFAULT_CONFIG = {
    "hotkey": {
        "combination": "right_fn",
        "mode": "toggle"
    },
    "transcription": {
        "provider": "voice_editor",
        "voice_editor": {
            "url": "wss://voice-editor.minipc.na/ws/transcribe",
            "do_cleanup": True,
            "language": "auto",
            "headers": {}
        },
        "openai": {
            "api_key": "",
            "model": "whisper-1",
            "prompt": ""
        },
        "groq": {
            "api_key": "",
            "model": "whisper-large-v3"
        },
        "local": {
            "model_size": "base",
            "device": "auto"
        }
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "device": None
    },
    "clipboard": {
        "auto_paste": True,
        "restore_clipboard": False,
        "direct_typing": False
    },
    "ui": {
        "show_edit_window": False
    },
    "history": {
        "max_recordings": 100
    }
}


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        if config_path == "config.yaml" and not os.path.exists("config.yaml"):
            home_dir = os.path.expanduser("~/.voicekit")
            os.makedirs(home_dir, exist_ok=True)
            self.config_path = os.path.join(home_dir, "config.yaml")
            old_path = os.path.expanduser("~/.gemini/antigravity/voicekit_config.yaml")
            if os.path.exists(old_path) and not os.path.exists(self.config_path):
                try:
                    import shutil
                    shutil.copy2(old_path, self.config_path)
                except Exception:
                    pass
        else:
            self.config_path = os.path.expanduser(config_path)
        self._config = self.load()

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            self.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if not isinstance(loaded, dict):
                    return DEFAULT_CONFIG.copy()
                return self._merge_dict(DEFAULT_CONFIG, loaded)
        except Exception as e:
            print(f"Error loading config {self.config_path}: {e}")
            return DEFAULT_CONFIG.copy()

    def _merge_dict(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        result = default.copy()
        for k, v in user.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge_dict(result[k], v)
            else:
                result[k] = v
        return result

    def save(self, data: Dict[str, Any] = None) -> bool:
        if data is not None:
            self._config = data
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key_path: str, value: Any) -> None:
        keys = key_path.split(".")
        val = self._config
        for k in keys[:-1]:
            if k not in val or not isinstance(val[k], dict):
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self.save()

    @property
    def data(self) -> Dict[str, Any]:
        return self._config
