"""
Modern Web Settings Window for Qale using Microsoft Edge WebView2 (pywebview).
Renders web_ui/index.html with full two-way JS/Python API integration.
"""
import os
import sys
import threading
from collections.abc import Callable
from typing import Optional, Dict, Any, List
import webview

from core.audio_recorder import AudioRecorder
from core.config_manager import ConfigManager
from core.startup_manager import StartupManager


PRESET_PACKS: Dict[str, Dict[str, Any]] = {
    "react_nextjs": {
        "name": "React & Next.js",
        "terms": {
            "next js": "Next.js",
            "snick js": "Next.js",
            "neck js": "Next.js",
            "react js": "React",
            "use state": "useState",
            "use effect": "useEffect",
            "use ref": "useRef",
            "use memo": "useMemo",
            "use callback": "useCallback",
            "use context": "useContext",
            "tailwind css": "Tailwind CSS",
            "zustand": "Zustand",
            "tanstack query": "TanStack Query",
            "tanstack": "TanStack",
            "zod": "Zod",
            "shad cn": "shadcn/ui",
            "radix ui": "Radix UI",
            "type script": "TypeScript",
            "java script": "JavaScript",
            "node js": "Node.js",
            "nest js": "NestJS",
            "jsx": "JSX",
            "tsx": "TSX"
        }
    },
    "python_ml": {
        "name": "Python & AI/ML",
        "terms": {
            "fast api": "FastAPI",
            "py test": "pytest",
            "numpy": "NumPy",
            "pandas": "Pandas",
            "pytorch": "PyTorch",
            "torch": "PyTorch",
            "tensor flow": "TensorFlow",
            "scikit learn": "scikit-learn",
            "hugging face": "Hugging Face",
            "poetry": "Poetry",
            "pydantic": "Pydantic",
            "pip install": "pip install",
            "cuda": "CUDA"
        }
    },
    "devops_cloud": {
        "name": "DevOps & Cloud",
        "terms": {
            "docker file": "Dockerfile",
            "docker compose": "docker compose",
            "kube ctl": "kubectl",
            "kubernetes": "Kubernetes",
            "terraform": "Terraform",
            "post gres": "PostgreSQL",
            "mongo db": "MongoDB",
            "redis": "Redis",
            "prisma": "Prisma",
            "nginx": "NGINX",
            "github actions": "GitHub Actions",
            "ci cd": "CI/CD",
            "aws": "AWS",
            "azure": "Azure",
            "gcp": "GCP"
        }
    },
    "git_terminal": {
        "name": "Git & Terminal",
        "terms": {
            "git status": "git status",
            "git commit": "git commit",
            "git push": "git push",
            "git pull": "git pull",
            "git checkout": "git checkout",
            "git merge": "git merge",
            "git rebase": "git rebase",
            "git stash": "git stash",
            "npm run dev": "npm run dev",
            "pnpm dev": "pnpm dev",
            "yarn build": "yarn build",
            "cargo run": "cargo run"
        }
    },
    "rust_go": {
        "name": "Rust & Go",
        "terms": {
            "golang": "Go",
            "goroutine": "goroutine",
            "cargo build": "cargo build",
            "cargo run": "cargo run",
            "cargo check": "cargo check",
            "rust c": "rustc",
            "tokio": "Tokio",
            "actix": "Actix",
            "axum": "Axum",
            "mutex": "Mutex",
            "gorm": "GORM"
        }
    }
}


class WebSettingsApi:
    """Exposed to window.pywebview.api in JavaScript."""
    def __init__(self, config_manager: ConfigManager, on_config_changed: Optional[Callable] = None, on_minimize: Optional[Callable] = None, parser=None, injector=None, context_mgr=None):
        # All internal objects MUST start with an underscore so pywebview's JS bridge doesn't reflect into them!
        self._config_manager = config_manager
        self._on_config_changed = on_config_changed
        self._on_minimize = on_minimize
        self._parser = parser
        self._injector = injector
        self._context_mgr = context_mgr
        self._test_stream = None
        self._latest_mic_level = 0.0

    def get_config(self) -> Dict[str, Any]:
        """Returns the full active configuration dictionary."""
        return self._config_manager.get_all()

    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """Saves updated settings and triggers live engine reload."""
        try:
            self._config_manager.update_all(new_config)
            if self._on_config_changed:
                self._on_config_changed()
            return True
        except Exception as e:
            print(f"[WebUI] Error saving config: {e}")
            return False

    def get_audio_devices(self) -> List[Dict]:
        """Returns available microphone devices."""
        return AudioRecorder.get_input_devices()

    def toggle_startup(self, enabled: bool) -> bool:
        """Enables or disables auto-start on Windows boot."""
        if enabled:
            return StartupManager.enable_startup()
        else:
            return StartupManager.disable_startup()

    def minimize_to_tray(self) -> bool:
        """Minimizes the window to the system tray."""
        if self._on_minimize:
            self._on_minimize()
        return True

    def get_mic_level(self, device_index: Optional[int] = None) -> float:
        """Captures a quick 80ms sample to test real microphone volume."""
        try:
            import sounddevice as sd
            import numpy as np
            rec = sd.rec(int(16000 * 0.08), samplerate=16000, channels=1, dtype='int16', device=device_index)
            sd.wait()
            raw = rec.astype(np.float32)
            rms = float(np.sqrt(np.mean(raw ** 2))) / 32768.0
            return min(1.0, rms * 9.5)
        except Exception as e:
            return 0.0

    def test_parse(self, raw_text: str, profile_name: str = "ts") -> Dict[str, Any]:
        """Runs speech through the live CodeParser and context corrector for the Playground."""
        parser = self._parser
        if not parser:
            from core.code_parser import CodeParser
            parser = CodeParser(self._config_manager)

        corrector = None
        if self._context_mgr and profile_name != "prose":
            corrector = self._context_mgr.get_corrector(profile_name)

        try:
            parsed = parser.parse(raw_text, corrector=corrector)
            return {"success": True, "parsed": parsed}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns recent dictations history."""
        if self._injector and hasattr(self._injector, "get_history"):
            return self._injector.get_history()
        return []

    def copy_to_clipboard(self, text: str) -> bool:
        """Copies text to the system clipboard."""
        if not text:
            return False
        if self._injector and hasattr(self._injector, "_set_clipboard"):
            return self._injector._set_clipboard(text)
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(text)
            r.update()
            r.destroy()
            return True
        except Exception:
            return False

    def load_preset_pack(self, pack_id: str) -> Dict[str, Any]:
        """Merges a curated developer vocabulary preset pack into sound_alikes."""
        pack = PRESET_PACKS.get(pack_id)
        if not pack or not isinstance(pack.get("terms"), dict):
            return {"success": False, "error": "Unknown preset pack"}

        cfg = self._config_manager.get_all()
        sound_alikes = cfg.get("sound_alikes", {})
        count_added = 0
        terms: Dict[str, str] = pack["terms"]
        for spoken, target in terms.items():
            if spoken not in sound_alikes:
                count_added += 1
            sound_alikes[spoken] = target

        cfg["sound_alikes"] = sound_alikes
        self._config_manager.update_all(cfg)
        if self._on_config_changed:
            self._on_config_changed()

        return {
            "success": True,
            "pack_name": pack["name"],
            "added_count": count_added,
            "sound_alikes": sound_alikes
        }


class WebSettingsWindow:
    def __init__(self, config_manager: ConfigManager, on_config_changed: Optional[Callable] = None, on_quit: Optional[Callable] = None, parser=None, injector=None, context_mgr=None):
        self._config_manager = config_manager
        self._on_config_changed = on_config_changed
        self._on_quit = on_quit
        self._parser = parser
        self._injector = injector
        self._context_mgr = context_mgr
        self.window: Optional[Any] = None
        self._is_quitting = False
        self._is_ready = threading.Event()

        self.api = WebSettingsApi(
            config_manager=self._config_manager,
            on_config_changed=self._on_config_changed,
            on_minimize=self.hide,
            parser=self._parser,
            injector=self._injector,
            context_mgr=self._context_mgr
        )

    def create(self, hidden: bool = False):
        """Creates the pywebview window pointed at web_ui/index.html."""
        import pathlib
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "web_ui", "index.html")

        if not os.path.exists(html_path):
            raise FileNotFoundError(f"web_ui/index.html not found at {html_path}")

        file_uri = pathlib.Path(html_path).as_uri()

        win = webview.create_window(
            title="Qale - Developer Voice Assistant",
            url=file_uri,
            js_api=self.api,
            width=960,
            height=680,
            min_size=(800, 520),
            hidden=hidden,
            background_color="#090A0F",
            text_select=True
        )
        self.window = win

        if win is not None:
            win.events.closing += self._on_closing
            win.events.loaded += self._on_loaded

    def _on_loaded(self):
        self._is_ready.set()

    def _on_closing(self):
        """Intercepts window close: hides to tray instead of quitting."""
        if self._is_quitting:
            return True
        self.hide()
        return False

    def show(self):
        """Shows the settings window and brings it to the foreground."""
        if self.window:
            try:
                self.window.show()
                self.window.restore()
                self.window.focus()
            except Exception as e:
                print(f"[WebUI] Error showing window: {e}")

            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = 0
                if hasattr(self.window, "native") and hasattr(self.window.native, "Handle"):
                    try:
                        hwnd = int(self.window.native.Handle.ToString())
                    except Exception:
                        hwnd = 0
                if not hwnd:
                    hwnd = user32.FindWindowW(None, "Qale - Developer Voice Assistant")
                if hwnd:
                    from core.text_injector import force_foreground_window
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    force_foreground_window(hwnd)
            except Exception:
                pass

    def hide(self):
        """Hides the settings window to the tray."""
        if self.window:
            try:
                self.window.hide()
            except Exception as e:
                print(f"[WebUI] Error hiding window: {e}")

    def destroy(self):
        """Cleanly destroys the window and exits pywebview loop."""
        self._is_quitting = True
        if self.window:
            try:
                self.window.destroy()
            except Exception as e:
                pass

