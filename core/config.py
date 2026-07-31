"""Agent configuration - loaded from environment / config file."""
import json
import os

CONFIG_PATH = os.path.expanduser("~/.agent_config.json")

DEFAULTS = {
    "llm": {
        "model": "llama3.2",
        "ollama_host": "http://localhost:11434",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "groq": {
        "model": "llama-3.1-8b-instant",
        "alt_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "voice": {
        "stt_model": "whisper-tiny",  # tiny/base/small/medium/large
        "tts_enabled": True,
        "wake_word": "hey agent",
        "language": "en",
    },
    "android": {
        "adb_path": "adb",
        "default_device": None,
    },
    "automation": {
        "screenshot_dir": os.path.expanduser("~/agent_screenshots"),
        "click_duration": 0.1,
    },
    "memory": {
        "db_path": os.path.expanduser("~/.agent_memory.db"),
        "max_history": 1000,
    },
    "web": {
        "host": "127.0.0.1",
        "port": 8765,
        "enabled": True,
    },
    "tasks": {
        "max_concurrent": 5,
    },
    "profile": {
        "name": "Abhinav",
        "theme": "dark",
        "autosave": True,
        "auto_pr": True,
        "telemetry": False,
    },
    "telegram": {
        "bot_token": "",
        "allowed_chat_ids": [],
        "enabled": False,
    },
}


class Config:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        self.data = dict(DEFAULTS)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    user = json.load(f)
                self._deep_merge(self.data, user)
            except Exception:
                pass

    def _deep_merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def get(self, *keys, default=None):
        val = self.data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def set(self, *keys, value):
        val = self.data
        for k in keys[:-1]:
            if k not in val:
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self.save()


config = Config()
