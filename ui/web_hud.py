"""
Modern HTML5 / CSS3 Floating Sound Wave HUD for Qale.
Rendered via Microsoft Edge WebView2 (pywebview) with glassmorphism,
gradient sound wave visualizer, and non-activating window flags (WS_EX_NOACTIVATE).
Zero focus stealing: Your cursor never leaves VS Code or Notepad.
"""
import ctypes
import json
import os
import threading
import time
from typing import Any, List, Optional
import webview

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
HWND_TOPMOST = -1


class WebFloatingHUD:
    def __init__(self):
        self.window: Optional[Any] = None
        self._hwnd = 0
        self._is_visible = False
        self._is_ready = threading.Event()
        self._lock = threading.Lock()
        self._configured_style = False

    def create(self):
        """Creates the transparent frameless WebView2 HUD window."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "web_ui", "hud.html")

        if not os.path.exists(html_path):
            raise FileNotFoundError(f"web_ui/hud.html not found at {html_path}")

        import pathlib
        file_uri = pathlib.Path(html_path).as_uri()

        # Screen dimensions
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        w, h = 500, 76
        x = (screen_w - w) // 2
        y = screen_h - h - 50

        win = webview.create_window(
            title="Qale Voice HUD",
            url=file_uri,
            width=w,
            height=h,
            x=x,
            y=y,
            frameless=True,
            transparent=True,
            on_top=True,
            hidden=True,
            easy_drag=False,
            focus=False,
            text_select=False
        )
        self.window = win

        if win is not None:
            win.events.loaded += self._on_loaded
            win.events.closing += lambda: False  # Never destroy on close

    def _on_loaded(self):
        """Configures native Win32 styles once the window handle is ready."""
        try:
            if self.window is not None and getattr(self.window, "native", None):
                self._hwnd = int(self.window.native.Handle.ToString())
                self._apply_native_styles()
                self._is_ready.set()
        except Exception as e:
            print(f"[HUD] Error configuring native window: {e}")

    def _apply_native_styles(self, position: str = "bottom_center"):
        """Ensures the HUD never activates or steals focus from code editors."""
        if not self._hwnd:
            return
        try:
            old_style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                self._hwnd,
                GWL_EXSTYLE,
                old_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            )
            self.set_position(position)
            user32.ShowWindow(self._hwnd, SW_HIDE)
            self._configured_style = True
        except Exception as e:
            print(f"[HUD] Native style error: {e}")

    def set_position(self, position: str = "bottom_center"):
        """Updates screen placement (bottom_center, top_center, bottom_right)."""
        if not self._hwnd:
            return
        try:
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            w, h = 500, 76
            if position == "top_center":
                x = (screen_w - w) // 2
                y = 50
            elif position == "bottom_right":
                x = screen_w - w - 40
                y = screen_h - h - 50
            else:  # bottom_center
                x = (screen_w - w) // 2
                y = screen_h - h - 50
            user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    def _eval(self, js_code: str):
        if not self.window:
            return
        try:
            self.window.evaluate_js(js_code)
        except Exception:
            pass

    def show_listening(self, target_name: str = "Active Editor", hotkey: str = "F8", hw_chip: Optional[str] = None, gpu_badge: Optional[str] = None, profile: Optional[str] = None):
        """Displays the HUD in recording mode without stealing focus."""
        with self._lock:
            self._is_visible = True
            safe_target = json.dumps(target_name[:24])
            safe_hotkey = json.dumps(hotkey.upper())
            chip_text = hw_chip or gpu_badge or "2050 · small"
            # Strip emojis if legacy string passed
            chip_text = chip_text.replace("⚡", "").strip()
            safe_hw = json.dumps(chip_text)
            safe_profile = json.dumps(profile.upper() if profile else "")
            self._eval(f"window.showListening({safe_target}, {safe_hotkey}, {safe_hw}, {safe_profile})")

            if self._hwnd:
                user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)

    def update_waveform(self, levels: List[float]):
        """Updates the animated soundwave bars with live microphone energy."""
        if not self._is_visible:
            return
        try:
            # Round levels to 2 decimal places to minimize JS payload
            rounded = [round(float(v), 2) for v in levels]
            self._eval(f"window.setWaveLevels({rounded})")
        except Exception:
            pass

    def show_formatting(self):
        """Transitions HUD to formatting / transcribing state."""
        with self._lock:
            self._eval("window.showFormatting()")

    def show_done(self, target_name: str = "Active Editor", latency_str: Optional[str] = None, done_text: Optional[str] = None):
        """Shows success checkmark and auto-dismisses smoothly after 1.2s."""
        with self._lock:
            safe_target = json.dumps(target_name[:24])
            chip_text = latency_str or done_text or ""
            safe_latency = json.dumps(chip_text)
            self._eval(f"window.showDone({safe_target}, {safe_latency})")

        # Auto-hide after 1.2 seconds
        threading.Timer(1.2, self.hide).start()

    def hide(self):
        """Hides the HUD completely from the screen."""
        with self._lock:
            self._is_visible = False
            if self._hwnd:
                user32.ShowWindow(self._hwnd, SW_HIDE)

    def destroy(self):
        """Cleanly destroys the HUD window on application shutdown."""
        self.hide()
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

