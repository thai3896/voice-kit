import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.imagekit/config.yaml")

DEFAULT_CONFIG = {
    "hotkey": "cmd+shift+2",
    "api_url": "https://ollama.minipc.na/v1/chat/completions",
    "model": "llava:latest",
    "copy_to_clipboard": True,
    "show_editor": True,
    "ai_api_url": "https://ollama.minipc.na/v1/chat/completions",
    "vision_model": "llava:latest",
    "chat_model": "qwen2.5:14b",
    "general_vision_model": "qwen2.5vl:3b",
    "vision_prompts": {
        "General Description": "Analyze this image in detail. Describe the main subjects, the setting, objects present, their relationships, colors, and any text visible. Provide a comprehensive summary of what is happening in the scene.",
        "UI / Web Design": "Analyze this user interface. Describe the layout, color palette, typography, visual hierarchy, and interactive elements.",
        "Diagram / Chart": "Explain the flow, architecture, or data represented in this diagram or chart. Break down the components and their relationships.",
        "Code / Text Structure": "Analyze the structure and semantics of the code or structured text shown in this image."
    }
}

class ConfigManager:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.config = self.load_config()

    def load_config(self):
        if not self.config_path.exists():
            self.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                if not config:
                    return DEFAULT_CONFIG.copy()
                
                # Merge with defaults to ensure all keys exist
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self, config_data=None):
        if config_data is not None:
            self.config = config_data
            
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
