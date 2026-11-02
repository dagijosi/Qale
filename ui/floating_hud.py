"""
Modern Sound-Wave Floating HUD for Qale.
Positioned comfortably at the bottom-center of the screen.

Features:
- Real-time animated audio soundwave (Google / Siri style) that reacts dynamically to voice volume.
- Instant visual confirmation that your microphone is actively hearing your voice.
- Zero-focus stealing: Uses WS_EX_NOACTIVATE so your cursor never leaves your editor.
"""
import ctypes
import math
import tkinter as tk
import threading
from typing import List, Optional

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32

# Premium Color Palette
HUD_BG = "#0B0C10"          # Obsidian black
HUD_CARD = "#131622"        # Dark slate card background
HUD_WAVE_BG = "#0D0F18"     # Waveform canvas well
HUD_BORDER = "#252B3E"      # Outer frame border
TEXT_MAIN = "#F8FAFC"       # Bright slate text
TEXT_MUTED = "#64748B"      # Subdued helper text
TEXT_TARGET = "#38BDF8"     # Electric sky blue target indicator
ACCENT_GREEN = "#10B981"    # Emerald success
ACCENT_AMBER = "#F59E0B"    # Amber formatting
ACCENT_RED = "#EF4444"      # Crimson recording

NUM_BARS = 28


def generate_gradient_colors(count: int) -> List[str]:
    """Generates a vibrant gradient: Sky Blue -> Electric Purple -> Rose Pink."""
    colors = []
    for i in range(count):
        ratio = i / max(1, count - 1)
        if ratio < 0.5:
            r = int(56 + (168 - 56) * (ratio * 2))
            g = int(189 + (85 - 189) * (ratio * 2))
            b = int(248 + (247 - 248) * (ratio * 2))
        else:
            r = int(168 + (236 - 168) * ((ratio - 0.5) * 2))
            g = int(85 + (72 - 85) * ((ratio - 0.5) * 2))
            b = int(247 + (153 - 247) * ((ratio - 0.5) * 2))
        colors.append(f"#{r:02x}{g:02x}{b:02x}")
    return colors


class FloatingHUD:
    def __init__(self):
        self.root = None
        self.is_running = False
        self.is_listening = False
        self._thread = None
        self._ready_event = threading.Event()

        # Waveform animation state
        self.phase = 0.0
        self.target_levels = [0.0] * NUM_BARS
        self.current_levels = [0.0] * NUM_BARS
        self.colors = generate_gradient_colors(NUM_BARS)

        # UI elements
        self.card_frame = None
        self.lbl_badge = None
        self.lbl_target = None
        self.lbl_hotkey = None
        self.lbl_subtitle = None
        self.canvas = None
        self.bar_items = []

    def start(self):
        """Starts the HUD in a background UI thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_hud_loop, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=2.0)

    def _run_hud_loop(self):
        self.root = tk.Tk()
        self.root.title("Qale Sound Wave HUD")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.configure(bg=HUD_BG)

        try:
            self.root.wm_attributes("-alpha", 0.96)
        except Exception:
            pass

        # Apply WS_EX_NOACTIVATE: Window NEVER steals focus from VS Code / Notepad
        try:
            self.root.update_idletasks()
            hwnd = user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, old_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except Exception as e:
            print(f"[HUD] Note on window style: {e}")

        # Position at the BOTTOM-CENTER of the screen (above the taskbar)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w, h = 540, 112
        x = (screen_w - w) // 2
        y = screen_h - h - 60

        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Outer Shadow & Border Frame
        outer_frame = tk.Frame(self.root, bg=HUD_BORDER, padx=1, pady=1)
        outer_frame.pack(fill="both", expand=True)

        # Main Card Frame
        self.card_frame = tk.Frame(
            outer_frame,
            bg=HUD_CARD,
            padx=14,
            pady=8
        )
        self.card_frame.pack(fill="both", expand=True)

        # =====================================================================
        # TOP ROW: Status Badge, Target App & Hotkey
        # =====================================================================
        top_row = tk.Frame(self.card_frame, bg=HUD_CARD)
        top_row.pack(fill="x", pady=(0, 6))

        # Left: Live Status Pill
        self.lbl_badge = tk.Label(
            top_row,
            text="🔴 RECORDING",
            font=("Segoe UI", 8, "bold"),
            fg=ACCENT_RED,
            bg="#281517",
            padx=7,
            pady=2
        )
        self.lbl_badge.pack(side="left")

        # Center: Active Target Editor
        self.lbl_target = tk.Label(
            top_row,
            text="🎯 Active Editor",
            font=("Segoe UI", 8, "bold"),
            fg=TEXT_TARGET,
            bg=HUD_CARD,
            padx=8
        )
        self.lbl_target.pack(side="left")

        # Right: Hotkey Badge
        self.lbl_hotkey = tk.Label(
            top_row,
            text="[ Tap F8 to Finish & Paste ]",
            font=("Segoe UI", 8, "bold"),
            fg="#94A3B8",
            bg="#1B1F2D",
            padx=8,
            pady=2
        )
        self.lbl_hotkey.pack(side="right")

        # =====================================================================
        # MIDDLE: Live Audio Sound Wave Canvas (Google / Siri Style)
        # =====================================================================
        canvas_container = tk.Frame(
            self.card_frame,
            bg=HUD_WAVE_BG,
            highlightbackground="#1E2333",
            highlightthickness=1,
            padx=4,
            pady=2
        )
        canvas_container.pack(fill="x", pady=(0, 5))

        self.canvas = tk.Canvas(
            canvas_container,
            width=500,
            height=38,
            bg=HUD_WAVE_BG,
            highlightthickness=0
        )
        self.canvas.pack(fill="x", expand=True)

        # Create the 28 waveform bars
        start_x = (500 - (NUM_BARS * 14)) // 2
        self.bar_items = []
        for i in range(NUM_BARS):
            bx = start_x + (i * 14) + 6
            line = self.canvas.create_line(
                bx, 19, bx, 19,
                width=4,
                capstyle="round",
                fill=self.colors[i]
            )
            self.bar_items.append((line, bx))

        # =====================================================================
        # BOTTOM ROW: Helper Subtitle
        # =====================================================================
        self.lbl_subtitle = tk.Label(
            self.card_frame,
            text="Microphone listening • Speak code or text, tap F8 when done",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=HUD_CARD,
            anchor="w"
        )
        self.lbl_subtitle.pack(fill="x")

        self.lbl_timer = tk.Label(
            self.card_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#64748B",
            bg=HUD_CARD,
            anchor="e"
        )
        self.lbl_timer.pack(fill="x")
        self._record_start_time = 0.0

        self.root.withdraw()
        self._ready_event.set()
        self.root.mainloop()

    def show_listening(self, target_name: str = "Active Editor", hotkey: str = "F8", hw_chip: str = ""):
        """Displays the floating HUD at the bottom and starts the live sound wave."""
        if not self.root:
            return
        self.root.after(0, self._render_listening, target_name, hotkey, hw_chip)

    def update_waveform(self, levels: List[float]):
        """Updates the audio frequency/volume levels for the sound wave."""
        if not levels:
            return
        # Store target levels safely
        count = min(len(levels), NUM_BARS)
        for i in range(count):
            self.target_levels[i] = levels[i]

    def copy_to_clipboard(self, text: str):
        """Sets clipboard safely via Tkinter main loop."""
        if not self.root:
            return
        def _do():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.root.update()
            except Exception:
                pass
        self.root.after(0, _do)

    def show_formatting(self):
        """Displays code formatting state while Whisper & parser execute."""
        if not self.root:
            return
        self.root.after(0, self._render_formatting)

    def show_done(self, target_name: str = "Active Editor", latency_str: str = ""):
        """Displays injection success and auto-hides."""
        if not self.root:
            return
        self.root.after(0, self._render_done, target_name, latency_str)

    def hide(self):
        """Hides the HUD."""
        if not self.root:
            return
        self.root.after(0, self._hide)

    # =========================================================================
    # INTERNAL UI RENDERING & SOUND WAVE ANIMATION LOOP
    # =========================================================================
    def _render_listening(self, target_name: str, hotkey: str = "F8", hw_chip: str = ""):
        if not self.root:
            return
        self.is_listening = True
        self.lbl_badge.config(text="🔴 RECORDING", fg=ACCENT_RED, bg="#281517")
        self.lbl_target.config(text=f"🎯 {target_name}", fg=TEXT_TARGET)
        hotkey_disp = hotkey.upper()
        self.lbl_hotkey.config(text=f"[ Tap {hotkey_disp} to Finish & Paste ]", fg="#94A3B8", bg="#1B1F2D")
        self.lbl_subtitle.config(text="Microphone listening • Speak code or text, tap F8 when done", fg=TEXT_MUTED)
        self.root.deiconify()
        # Start sound wave animation loop
        import time as _time
        self._record_start_time = _time.time()
        self._update_timer()
        self._animate_wave_frame()

    def _animate_wave_frame(self):
        if not self.is_listening or not self.root or not self.canvas:
            return

        self.phase += 0.16
        center_y = 19
        max_half_h = 16

        for i in range(NUM_BARS):
            line_id, bx = self.bar_items[i]

            # Smoothly interpolate towards target level
            target = self.target_levels[i]
            self.current_levels[i] = 0.45 * self.current_levels[i] + 0.55 * target

            cur_level = self.current_levels[i]

            # Ambient breathing oscillation when quiet
            ambient = 2.5 + 2.0 * math.sin(self.phase + i * 0.28)

            # Active voice pulse when sound is present
            voice_height = cur_level * max_half_h

            half_h = max(2.0, ambient + voice_height)
            half_h = min(max_half_h, half_h)

            y0 = center_y - half_h
            y1 = center_y + half_h

            self.canvas.coords(line_id, bx, y0, bx, y1)

        # Schedule next animation frame (~33 FPS)
        self.root.after(30, self._animate_wave_frame)

    def _render_formatting(self):
        if not self.root:
            return
        self.is_listening = False
        self.lbl_badge.config(text="⚡ FORMATTING", fg=ACCENT_AMBER, bg="#2E2310")
        self.lbl_subtitle.config(text="Formatting code syntax, keywords & casing...", fg=ACCENT_AMBER)
        # Gently level out bars into amber processing pulse
        center_y = 19
        for i in range(NUM_BARS):
            line_id, bx = self.bar_items[i]
            self.canvas.coords(line_id, bx, center_y - 3, bx, center_y + 3)
            self.canvas.itemconfig(line_id, fill=ACCENT_AMBER)
        self.root.deiconify()

    def _render_done(self, target_name: str, latency_str: str = ""):
        if not self.root:
            return
        self.is_listening = False
        self.lbl_badge.config(text="✅ INJECTED", fg=ACCENT_GREEN, bg="#11291F")
        latency_info = f"  ({latency_str})" if latency_str else ""
        self.lbl_subtitle.config(text=f"Pasted into {target_name} at cursor!{latency_info}", fg=ACCENT_GREEN)
        center_y = 19
        for i in range(NUM_BARS):
            line_id, bx = self.bar_items[i]
            self.canvas.coords(line_id, bx, center_y - 4, bx, center_y + 4)
            self.canvas.itemconfig(line_id, fill=ACCENT_GREEN)
        self.root.after(650, self._hide)

    def _update_timer(self):
        if not self.is_listening or not self.root:
            return
        import time as _time
        elapsed = int(_time.time() - self._record_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        self.lbl_timer.config(text=f"{mins}:{secs:02d}")
        self.root.after(1000, self._update_timer)

    def _hide(self):
        self.is_listening = False
        if self.root:
            self.root.withdraw()
            # Reset bar colors back to gradient
            if self.canvas and self.bar_items:
                for i in range(NUM_BARS):
                    line_id, _ = self.bar_items[i]
                    self.canvas.itemconfig(line_id, fill=self.colors[i])
            if hasattr(self, 'lbl_timer') and self.lbl_timer.winfo_exists():
                self.lbl_timer.config(text="")
