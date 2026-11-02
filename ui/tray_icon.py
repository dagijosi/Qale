"""
System Tray Manager for Qale.
Keeps Qale running quietly next to the Windows clock.
Supports pystray with quick menu, pause toggle, and double-click to open settings.
"""
import os
import sys
import threading
from collections.abc import Callable
from typing import Any, Optional


class SystemTray:
    def __init__(self,
                 on_open_ui: Callable[..., Any],
                 on_toggle_pause: Callable[..., Any],
                 on_quit: Callable[..., Any]):
        self.on_open_ui = on_open_ui
        self.on_toggle_pause = on_toggle_pause
        self.on_quit = on_quit
        self.is_paused: bool = False
        self._tray: Optional[Any] = None

    def start(self):
        """Runs the tray icon in a background thread."""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            print("[Tray] Note: 'pystray' and 'Pillow' not available. Running in background mode.")
            return

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                icon_image = Image.open(icon_path)
            except Exception:
                icon_image = self._create_icon_image()
        else:
            icon_image = self._create_icon_image()

        menu = pystray.Menu(
            pystray.MenuItem("⚡ Open Qale Settings", self._handle_open, default=True),
            pystray.MenuItem(
                lambda text: "▶️ Resume Dictation" if self.is_paused else "⏸️ Pause Dictation",
                self._handle_toggle_pause
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit Qale", self._handle_quit)
        )

        tray = pystray.Icon("Qale", icon_image, "Qale - Developer Voice-to-Code", menu)
        self._tray = tray
        
        def _safe_run():
            try:
                tray.run()
            except Exception as e:
                print(f"[Tray] System tray running in background mode ({e}).")

        threading.Thread(target=_safe_run, daemon=True).start()

    def _handle_open(self, icon, item):
        self.on_open_ui()

    def _handle_toggle_pause(self, icon, item):
        self.is_paused = not self.is_paused
        if self._tray:
            self._tray.title = f"Qale ({'PAUSED' if self.is_paused else 'Active'})"
        self.on_toggle_pause(self.is_paused)

    def _handle_quit(self, icon, item):
        if self._tray:
            self._tray.stop()
        self.on_quit()

    def _create_icon_image(self):
        """Generates a crisp blue microphone icon dynamically in memory with anti-aliasing."""
        from PIL import Image, ImageDraw
        scale = 4
        size = 64 * scale
        img = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Outer glowing circle
        d.ellipse((8 * scale, 8 * scale, 56 * scale, 56 * scale), fill="#2563EB")
        d.ellipse((10 * scale, 10 * scale, 54 * scale, 54 * scale), fill="#3B82F6")

        # Inner mic pill
        d.rounded_rectangle((26 * scale, 16 * scale, 38 * scale, 34 * scale), radius=6 * scale, fill="#FFFFFF")

        # Mic stand arc
        d.arc((20 * scale, 24 * scale, 44 * scale, 42 * scale), start=0, end=180, fill="#FFFFFF", width=3 * scale)
        d.line((32 * scale, 42 * scale, 32 * scale, 48 * scale), fill="#FFFFFF", width=3 * scale)
        d.line((24 * scale, 48 * scale, 40 * scale, 48 * scale), fill="#FFFFFF", width=3 * scale)

        return img.resize((64, 64), Image.Resampling.LANCZOS)
