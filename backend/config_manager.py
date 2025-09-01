import json
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self._default_config()

    def _default_config(self):
        return {
            "gemini_api_key": "",
            "model": "gemini-2.5-flash",
            "tmdb_api_key": "",
            "language": "English",
            "language_code": "en",
            "extract_audio": False,
            "auto_fetch_tmdb": True,
            "is_tv_series": False,
            "add_translator_info": True
        }

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def update(self, new_config):
        self.config.update(new_config)
