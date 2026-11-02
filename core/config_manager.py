"""
Configuration Manager for Qale.
Loads, validates, and updates app settings and custom dictionaries.
"""
import json
import os
import sys
from typing import Any, Dict, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, 'frozen', False) else __file__
)))
CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "general": {
        "trigger_mode": "toggle",
        "hotkey": "f8",
        "run_on_startup": False,
        "play_sounds": True,
        "show_floating_hud": True,
        "paste_method": "clipboard",
        "preserve_clipboard": True,
        "hud_position": "bottom_center",
        "typing_speed_ms": 10
    },
    "audio": {
        "device_index": None,
        "sample_rate": 16000,
        "channels": 1
    },
    "ai": {
        "engine": "whisper",
        "model_size": "base.en",
        "device": "cuda",
        "compute_type": "float16",
        "developer_prompt": "React, Next.js, TypeScript, JavaScript, Python, Node.js, Express, Tailwind, MongoDB, function, const, let, var, return, import, export, default, async, await, backslash, JSON, API, npm, GitHub, useState, useEffect, useContext, boolean, interface, type, class, enum, void, null, undefined, try, catch, finally, git, commit, push, pull, branch, checkout, merge",
        "language": "en"
    },
    "sound_alikes": {
        "snick js": "Next.js",
        "snick.js": "Next.js",
        "neck js": "Next.js",
        "neck.js": "Next.js",
        "next js": "Next.js",
        "next.js": "Next.js",
        "react js": "React",
        "react.js": "React",
        "view js": "Vue.js",
        "vue js": "Vue.js",
        "type script": "TypeScript",
        "java script": "JavaScript",
        "node js": "Node.js",
        "mongo db": "MongoDB",
        "tailwind css": "Tailwind CSS",
        "use state": "useState",
        "use effect": "useEffect",
        "use ref": "useRef",
        "use memo": "useMemo",
        "use callback": "useCallback",
        "use context": "useContext",
        "c plus plus": "C++",
        "c sharp": "C#",
        "dot net": ".NET",
        "post gres": "PostgreSQL",
        "post grass": "PostgreSQL",
        "docker file": "Dockerfile",
        "birr": "ETB",
        "ethiopian birr": "ETB",
        "eth b": "ETB"
    },
    "symbols": {
        "backslash": "\\",
        "back slash": "\\",
        "forward slash": "/",
        "slash": "/",
        "curly brackets": "{}",
        "curly braces": "{}",
        "open curly brace": "{",
        "close curly brace": "}",
        "open brace": "{",
        "close brace": "}",
        "square brackets": "[]",
        "open bracket": "[",
        "close bracket": "]",
        "parentheses": "()",
        "open parenthesis": "(",
        "close parenthesis": ")",
        "open paren": "(",
        "close paren": ")",
        "fat arrow": "=>",
        "arrow": "=>",
        "thin arrow": "->",
        "strictly equals": "===",
        "triple equals": "===",
        "double equals": "==",
        "equals": "=",
        "equal to": "=",
        "not equals": "!=",
        "exclamation mark": "!",
        "exclamation": "!",
        "semicolon": ";",
        "semi colon": ";",
        "colon": ":",
        "comma": ",",
        "dot": ".",
        "double quotes": "\"\"",
        "double quote": "\"",
        "quote": "\"",
        "single quotes": "''",
        "single quote": "'",
        "backtick": "`",
        "backticks": "``",
        "greater than": ">",
        "less than": "<",
        "greater than or equal": ">=",
        "less than or equal": "<=",
        "ampersand": "&",
        "double ampersand": "&&",
        "logical and": "&&",
        "pipe": "|",
        "double pipe": "||",
        "logical or": "||",
        "question mark": "?",
        "nullish coalescing": "??"
    },
    "actions": {
        "go back": "ACTION_BACKSPACE",
        "erase that": "ACTION_BACKSPACE",
        "scratch that": "ACTION_BACKSPACE",
        "delete that": "ACTION_BACKSPACE",
        "undo that": "ACTION_UNDO",
        "new line": "ACTION_ENTER",
        "enter": "ACTION_ENTER",
        "tab": "ACTION_TAB",
        "indent": "ACTION_TAB"
    }
}


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._last_mtime = 0.0
            cls._instance._load()
        return cls._instance

    def _load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                self._last_mtime = os.path.getmtime(CONFIG_PATH)
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[Config] Error loading config: {e}. Falling back to defaults.")
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save()

    def reload_if_modified(self):
        """Auto-reloads config.json if edited externally in VS Code or Notepad."""
        try:
            if os.path.exists(CONFIG_PATH):
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime > getattr(self, "_last_mtime", 0.0):
                    self._last_mtime = mtime
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        self.config = json.load(f)
                    print("[Config] Reloaded modified config.json from disk.")
        except Exception as e:
            pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            if os.path.exists(CONFIG_PATH):
                self._last_mtime = os.path.getmtime(CONFIG_PATH)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get_all(self) -> Dict[str, Any]:
        self.reload_if_modified()
        return self.config

    def update_all(self, new_config: Dict[str, Any]):
        self.config.update(new_config)
        self.save()

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        self.reload_if_modified()
        if key is None:
            return self.config.get(section, default)
        return self.config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save()

    def get_sound_alikes(self) -> Dict[str, str]:
        self.reload_if_modified()
        return self.config.get("sound_alikes", {})

    def add_sound_alike(self, spoken: str, replacement: str):
        spoken = spoken.strip().lower()
        if "sound_alikes" not in self.config:
            self.config["sound_alikes"] = {}
        self.config["sound_alikes"][spoken] = replacement
        self.save()

    def remove_sound_alike(self, spoken: str):
        spoken = spoken.strip().lower()
        if "sound_alikes" in self.config and spoken in self.config["sound_alikes"]:
            del self.config["sound_alikes"][spoken]
            self.save()

    def get_symbols(self) -> Dict[str, str]:
        self.reload_if_modified()
        return self.config.get("symbols", {})

    def add_symbol(self, phrase: str, symbol: str):
        phrase = phrase.strip().lower()
        if "symbols" not in self.config:
            self.config["symbols"] = {}
        self.config["symbols"][phrase] = symbol
        self.save()

    def remove_symbol(self, phrase: str):
        phrase = phrase.strip().lower()
        if "symbols" in self.config and phrase in self.config["symbols"]:
            del self.config["symbols"][phrase]
            self.save()

