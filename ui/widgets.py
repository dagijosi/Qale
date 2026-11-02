"""
Modern Custom Widgets for Qale Settings Window.
Clean, dark-themed Windows 11 Fluent style components including
Toggle Switches, Hotkey Pickers, VU Meters, and Toast Notifications.
Built with pure native vector Canvas primitives for 100% stability and zero image errors.
"""
import math
import tkinter as tk
from typing import Callable, Optional, List, Tuple

# Modern Dark Palette
COLOR_BG_DARK = "#121217"
COLOR_SIDEBAR = "#181820"
COLOR_CARD = "#1E1E26"
COLOR_CARD_BORDER = "#2D2D3A"
COLOR_CARD_HOVER = "#262632"
COLOR_INPUT_BG = "#262633"
COLOR_INPUT_BORDER = "#3D3D4E"
COLOR_ACCENT = "#3B82F6"
COLOR_ACCENT_HOVER = "#2563EB"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"
COLOR_TEXT_MAIN = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"
COLOR_TEXT_DIM = "#64748B"


class ModernSwitch(tk.Canvas):
    """
    Modern iOS/Windows 11-style toggle switch.
    Built with pure vector canvas shapes: 100% stable, zero PIL image conflicts.
    """
    def __init__(self, parent, initial_state: bool = False, command: Optional[Callable[[bool], None]] = None,
                 width: int = 46, height: int = 24, bg_color: str = COLOR_CARD, bg: Optional[str] = None, **kwargs):
        chosen_bg = bg or bg_color
        super().__init__(parent, width=width, height=height, bg=chosen_bg,
                         highlightthickness=0, cursor="hand2")
        self.w = width
        self.h = height
        self.bg_color = chosen_bg
        self.is_on = initial_state
        self.command = command

        self.bind("<Button-1>", self._on_click)
        self._render()

    def _render(self):
        self.delete("all")
        # Track colors
        if self.is_on:
            track_fill = COLOR_ACCENT
            track_outline = "#60A5FA"
        else:
            track_fill = "#33333F"
            track_outline = "#444455"

        r = self.h // 2
        # Pill background: Left cap, right cap, middle rectangle
        self.create_oval(1, 1, self.h - 1, self.h - 1, fill=track_fill, outline=track_outline)
        self.create_oval(self.w - self.h + 1, 1, self.w - 1, self.h - 1, fill=track_fill, outline=track_outline)
        self.create_rectangle(r, 1, self.w - r, self.h - 1, fill=track_fill, outline=track_fill)
        self.create_line(r, 1, self.w - r, 1, fill=track_outline)
        self.create_line(r, self.h - 1, self.w - r, self.h - 1, fill=track_outline)

        # White Knob
        knob_margin = 3
        knob_size = self.h - (knob_margin * 2)
        if self.is_on:
            knob_x1 = self.w - knob_size - knob_margin
        else:
            knob_x1 = knob_margin

        knob_y1 = knob_margin
        knob_x2 = knob_x1 + knob_size
        knob_y2 = knob_y1 + knob_size

        self.create_oval(knob_x1, knob_y1, knob_x2, knob_y2, fill="#FFFFFF", outline="#E2E8F0")

    def _on_click(self, event=None):
        self.set_state(not self.is_on)
        if self.command:
            self.command(self.is_on)

    def set_state(self, state: bool):
        self.is_on = bool(state)
        self._render()

    def get_state(self) -> bool:
        return self.is_on


class SegmentedControl(tk.Frame):
    """Segmented Radio Selector (e.g. Mode: Live | Batch | Push-to-Talk)."""
    def __init__(self, parent, options: List[Tuple[str, str]], initial_value: str,
                 on_change: Optional[Callable[[str], None]] = None, bg: str = COLOR_CARD):
        super().__init__(parent, bg=COLOR_INPUT_BG, padx=3, pady=3,
                         highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        self.options = options
        self.current_val = initial_value
        self.on_change = on_change
        self.buttons: Dict[str, tk.Label] = {}

        for text, val in options:
            btn = tk.Label(
                self,
                text=text,
                font=("Segoe UI", 9, "bold" if val == initial_value else "normal"),
                fg=COLOR_TEXT_MAIN if val == initial_value else COLOR_TEXT_MUTED,
                bg=COLOR_ACCENT if val == initial_value else COLOR_INPUT_BG,
                padx=12,
                pady=6,
                cursor="hand2"
            )
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, v=val: self._select(v))
            self.buttons[val] = btn

    def _select(self, val: str):
        if val == self.current_val:
            return
        self.current_val = val
        for v, btn in self.buttons.items():
            if v == val:
                btn.config(bg=COLOR_ACCENT, fg="#FFFFFF", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(bg=COLOR_INPUT_BG, fg=COLOR_TEXT_MUTED, font=("Segoe UI", 9, "normal"))

        if self.on_change:
            self.on_change(val)

    def get_value(self) -> str:
        return self.current_val


class HotkeyBadge(tk.Frame):
    """Interactive badge for setting/recording the global hotkey."""
    def __init__(self, parent, initial_hotkey: str = "f8", on_hotkey_changed: Optional[Callable[[str], None]] = None,
                 bg: str = COLOR_CARD):
        super().__init__(parent, bg=bg)
        self.hotkey = initial_hotkey.lower()
        self.on_hotkey_changed = on_hotkey_changed
        self.is_recording = False

        self.lbl_badge = tk.Label(
            self,
            text=f"  {self.hotkey.upper()}  ",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=COLOR_ACCENT,
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2"
        )
        self.lbl_badge.pack(side="left", padx=(0, 10))
        self.lbl_badge.bind("<Button-1>", self._start_recording)

        self.lbl_hint = tk.Label(
            self,
            text="Click badge to re-bind (e.g. F8, Ctrl+Space, Alt+V)",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_MUTED,
            bg=bg
        )
        self.lbl_hint.pack(side="left")

    def _start_recording(self, event=None):
        if self.is_recording:
            return
        self.is_recording = True
        self.lbl_badge.config(text="  Press Any Key...  ", bg=COLOR_WARNING, fg="#000000")
        top = self.winfo_toplevel()
        top.bind("<Key>", self._on_key_pressed)

    def _on_key_pressed(self, event):
        top = self.winfo_toplevel()
        top.unbind("<Key>")
        self.is_recording = False

        key_name = event.keysym.lower()
        # Handle special key mappings
        key_map = {
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "shift_l": "shift", "shift_r": "shift",
            "return": "enter", "space": "space"
        }
        self.hotkey = key_map.get(key_name, key_name)
        self.lbl_badge.config(text=f"  {self.hotkey.upper()}  ", bg=COLOR_ACCENT, fg="#FFFFFF")

        if self.on_hotkey_changed:
            self.on_hotkey_changed(self.hotkey)

    def get_hotkey(self) -> str:
        return self.hotkey


class VUMeter(tk.Canvas):
    """Live microphone level VU meter with 16 responsive animated LEDs."""
    def __init__(self, parent, width: int = 240, height: int = 16, bg_color: str = COLOR_CARD, bg: Optional[str] = None, **kwargs):
        chosen_bg = bg or bg_color
        super().__init__(parent, width=width, height=height, bg=chosen_bg, highlightthickness=0)
        self.w = width
        self.h = height
        self.num_bars = 16
        self.level = 0.0  # 0.0 to 1.0
        self._render()

    def set_level(self, level: float):
        self.level = max(0.0, min(1.0, level))
        self._render()

    def _render(self):
        self.delete("all")
        bar_w = (self.w - (self.num_bars * 3)) / self.num_bars
        active_bars = int(self.level * self.num_bars)

        for i in range(self.num_bars):
            x1 = i * (bar_w + 3)
            x2 = x1 + bar_w
            y1 = 2
            y2 = self.h - 2

            if i < active_bars:
                if i < self.num_bars * 0.6:
                    color = COLOR_SUCCESS  # Green
                elif i < self.num_bars * 0.85:
                    color = COLOR_WARNING  # Yellow
                else:
                    color = COLOR_DANGER   # Red
            else:
                color = "#2E2E3C"  # Inactive dim

            self.create_rectangle(x1, y1, x2, y2, fill=color, outline="")


class ToastNotification(tk.Frame):
    """Sleek animated toast notification banner that slides down and auto-dismisses."""
    def __init__(self, parent):
        super().__init__(parent, bg=COLOR_SUCCESS, padx=16, pady=8,
                         highlightthickness=1, highlightbackground="#34D399")
        self.lbl = tk.Label(self, text="", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg=COLOR_SUCCESS)
        self.lbl.pack()
        self.place_forget()

    def show(self, message: str, is_error: bool = False, duration_ms: int = 3000):
        color = COLOR_DANGER if is_error else COLOR_SUCCESS
        border = "#F87171" if is_error else "#34D399"
        self.config(bg=color, highlightbackground=border)
        self.lbl.config(text=message, bg=color)

        self.place(relx=0.5, y=20, anchor="n")
        self.lift()
        self.after(duration_ms, self.hide)

    def hide(self):
        self.place_forget()
