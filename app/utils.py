import json
import os
import sys
import threading
from datetime import datetime

# Path setup based on file location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CACHE_FILE = os.path.join(BASE_DIR, "ps5_game_cache.json")
LOG_FILE = os.path.join(BASE_DIR, "app.log")

DEFAULT_CONFIG = {
    "general": {
        "ps5_ip": "",
        "klog_port": 9081,
        "stats_port": 1214,
        "language": "en"
    },
    "discord": {
        "enabled": False,
        "client_id": ""
    },
    "haos": {
        "enabled": False,
        "mqtt_broker": "homeassistant.local",
        "mqtt_port": 1883,
        "mqtt_user": "",
        "mqtt_pass": "",
        "mqtt_topic": "homeassistant/sensor/ps5_custom/state"
    },
    "plugins": {}
}

class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton to ensure a single configuration instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
                    cls._instance.data = {}
                    cls._instance.load_config()
        return cls._instance

    def load_config(self):
        loaded_data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
            except Exception as e:
                print(f"Error reading config: {e}")

        self.data = self._deep_merge(DEFAULT_CONFIG.copy(), loaded_data)
        self.save_config()
        return self.data

    def _deep_merge(self, default, current):
        for key, value in default.items():
            if key in current:
                if isinstance(value, dict) and isinstance(current[key], dict):
                    self._deep_merge(value, current[key])
                else:
                    pass 
            else:
                current[key] = value
        return current

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, section, key):
        val = self.data.get(section, {}).get(key)
        if val is None:
            return DEFAULT_CONFIG.get(section, {}).get(key)
        return val

    def set(self, section, key, value):
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value
        self.save_config()

class Logger:
    _callback = None

    @staticmethod
    def set_callback(func):
        """Sets the function to call when a log is generated (e.g., GUI update)."""
        Logger._callback = func

    @staticmethod
    def log(message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        
        # If GUI callback is registered, send the message there too
        if Logger._callback:
            try: Logger._callback(formatted)
            except: pass
            
        return formatted

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except: pass