"""
Main Settings and Configuration Window for Qale.
A modern, dark-themed developer desktop interface built with high-DPI scaling,
native Windows dark titlebars, modern sidebar navigation, interactive hotkey recorder,
live microphone VU meter, tech vocabulary manager with presets, and an in-app test playground.
"""
import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable
from typing import Optional, Dict, List

from core.audio_recorder import AudioRecorder
from core.code_parser import CodeParser
from core.config_manager import ConfigManager
from core.startup_manager import StartupManager
from ui.widgets import (
    COLOR_BG_DARK, COLOR_SIDEBAR, COLOR_CARD, COLOR_CARD_BORDER,
    COLOR_CARD_HOVER, COLOR_INPUT_BG, COLOR_INPUT_BORDER, COLOR_ACCENT,
    COLOR_ACCENT_HOVER, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    COLOR_TEXT_MAIN, COLOR_TEXT_MUTED, COLOR_TEXT_DIM,
    ModernSwitch, SegmentedControl, HotkeyBadge, VUMeter, ToastNotification
)

# Enable Windows Per-Monitor High DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def apply_dark_titlebar(window: tk.Tk):
    """Applies Windows 10/11 DWM immersive dark mode to the native window frame."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 on Win11 / Win10 20H1+; 19 on older Win10
        value = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


class MainWindow:
    def __init__(self, on_config_changed: Optional[Callable] = None):
        self.config_manager = ConfigManager()
        self.on_config_changed = on_config_changed
        self.root: Optional[tk.Tk] = None
        self.toast: Optional[ToastNotification] = None

        # Navigation state
        self._current_page = "general"
        self._nav_buttons: Dict[str, tk.Frame] = {}
        self._pages: Dict[str, tk.Frame] = {}

        # Audio tester state
        self._mic_test_stream = None
        self._is_testing_mic = False
        self._test_dictation_active = False

    def show(self):
        """Displays the main window or brings it into focus."""
        if self.root is not None:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            return

        self.root = tk.Tk()
        self.root.title("Qale — Developer Voice-to-Code Assistant")
        self.root.geometry("980x680")
        self.root.minsize(860, 580)
        self.root.configure(bg=COLOR_BG_DARK)

        # Center on screen
        self._center_window(980, 680)

        # Apply Windows 11 Dark Frame
        apply_dark_titlebar(self.root)

        # Intercept close button to hide to tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Apply TTK Styles
        self._apply_ttk_styles()

        # Build Main Layout: Left Sidebar + Right Content Area
        self._build_layout()

        # Toast notification banner
        self.toast = ToastNotification(self.root)

        self.root.mainloop()

    def hide(self):
        """Hides window to background tray."""
        self._stop_mic_test()
        if self.root:
            self.root.withdraw()

    def destroy(self):
        """Destroys window entirely."""
        self._stop_mic_test()
        if self.root:
            self.root.destroy()
            self.root = None

    def _center_window(self, width: int, height: int):
        if not self.root:
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2 - 30)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_ttk_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Treeview styling
        style.configure(
            "Treeview",
            background=COLOR_CARD,
            foreground=COLOR_TEXT_MAIN,
            fieldbackground=COLOR_CARD,
            borderwidth=0,
            rowheight=32,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#252530",
            foreground=COLOR_TEXT_MAIN,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#FFFFFF")]
        )

        # Combobox styling
        style.configure(
            "TCombobox",
            fieldbackground=COLOR_INPUT_BG,
            background=COLOR_CARD_BORDER,
            foreground=COLOR_TEXT_MAIN,
            arrowcolor=COLOR_TEXT_MAIN,
            borderwidth=0,
            font=("Segoe UI", 10)
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLOR_INPUT_BG)],
            foreground=[("readonly", COLOR_TEXT_MAIN)]
        )

        # Scrollbar styling
        style.configure(
            "Vertical.TScrollbar",
            background=COLOR_CARD,
            troughcolor=COLOR_BG_DARK,
            bordercolor=COLOR_BG_DARK,
            arrowcolor=COLOR_TEXT_MUTED
        )

    def _build_layout(self):
        # Master container
        master = tk.Frame(self.root, bg=COLOR_BG_DARK)
        master.pack(fill="both", expand=True)

        # 1. Left Sidebar
        self.sidebar = tk.Frame(master, bg=COLOR_SIDEBAR, width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # 2. Right Content Area
        self.content_container = tk.Frame(master, bg=COLOR_BG_DARK)
        self.content_container.pack(side="left", fill="both", expand=True)

        # Build Pages
        self._pages["general"] = self._build_page_general()
        self._pages["audio"] = self._build_page_audio()
        self._pages["vocab"] = self._build_page_vocab()
        self._pages["symbols"] = self._build_page_symbols()
        self._pages["ai"] = self._build_page_ai()
        self._pages["playground"] = self._build_page_playground()
        self._pages["diagnostics"] = self._build_page_diagnostics()

        # Show initial page
        self._navigate_to("general")

    # =========================================================================
    # SIDEBAR
    # =========================================================================
    def _build_sidebar(self):
        # App Header Brand
        header = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR, padx=16, pady=20)
        header.pack(fill="x")

        # Title row
        title_row = tk.Frame(header, bg=COLOR_SIDEBAR)
        title_row.pack(fill="x")

        tk.Label(title_row, text="🦁 Qale", font=("Segoe UI", 14, "bold"),
                 fg="#FFFFFF", bg=COLOR_SIDEBAR).pack(side="left")

        # Version chip
        badge = tk.Label(title_row, text="v1.2", font=("Segoe UI", 8, "bold"),
                         bg="#1E293B", fg="#60A5FA", padx=6, pady=2)
        badge.pack(side="right")

        tk.Label(header, text="Offline Developer Voice-to-Code", font=("Segoe UI", 8),
                 fg=COLOR_TEXT_MUTED, bg=COLOR_SIDEBAR).pack(anchor="w", pady=(2, 0))

        # Thin separator
        tk.Frame(self.sidebar, bg=COLOR_CARD_BORDER, height=1).pack(fill="x", padx=14, pady=6)

        # Navigation items
        nav_items = [
            ("general", "⚡", "General & Hotkeys"),
            ("audio", "🎙️", "Audio & Mic Test"),
            ("vocab", "📖", "Tech Vocabulary"),
            ("symbols", "⌨️", "Symbols & Actions"),
            ("ai", "🧠", "AI Whisper Model"),
            ("playground", "🧪", "Voice Playground"),
            ("diagnostics", "ℹ️", "Status & Shortcuts"),
        ]

        nav_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR, padx=10, pady=8)
        nav_frame.pack(fill="both", expand=True)

        for page_id, icon, label in nav_items:
            btn_frame = tk.Frame(nav_frame, bg=COLOR_SIDEBAR, cursor="hand2")
            btn_frame.pack(fill="x", pady=2)

            indicator = tk.Frame(btn_frame, bg=COLOR_SIDEBAR, width=3, height=36)
            indicator.pack(side="left")

            btn_label = tk.Label(
                btn_frame,
                text=f"  {icon}  {label}",
                font=("Segoe UI", 9),
                fg=COLOR_TEXT_MUTED,
                bg=COLOR_SIDEBAR,
                anchor="w",
                padx=8,
                pady=8
            )
            btn_label.pack(side="left", fill="x", expand=True)

            # Store references
            btn_frame.indicator = indicator
            btn_frame.btn_label = btn_label
            btn_frame.page_id = page_id

            # Bind clicks and hover
            for widget in (btn_frame, btn_label):
                widget.bind("<Button-1>", lambda e, p=page_id: self._navigate_to(p))
                widget.bind("<Enter>", lambda e, f=btn_frame, p=page_id: self._on_nav_hover(f, p, True))
                widget.bind("<Leave>", lambda e, f=btn_frame, p=page_id: self._on_nav_hover(f, p, False))

            self._nav_buttons[page_id] = btn_frame

        # Sidebar Footer: Live Hardware & Engine Chip
        footer = tk.Frame(self.sidebar, bg="#131317", padx=14, pady=14)
        footer.pack(fill="x", side="bottom")

        # Hardware verification
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            hw_text = "⚡ GPU RTX 2050 (CUDA)" if has_cuda else "⚙️ CPU Mode (Fast)"
            hw_color = "#34D399" if has_cuda else "#94A3B8"
            hw_bg = "#064E3B" if has_cuda else "#262630"
        except Exception:
            hw_text = "⚙️ CPU Engine"
            hw_color = "#94A3B8"
            hw_bg = "#262630"

        hw_badge = tk.Label(footer, text=hw_text, font=("Segoe UI", 8, "bold"),
                            bg=hw_bg, fg=hw_color, padx=8, pady=4)
        hw_badge.pack(fill="x")

        # Save all button in sidebar
        btn_save = tk.Button(
            footer,
            text="💾 Save All Settings",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_SUCCESS,
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._save_all_settings
        )
        btn_save.pack(fill="x", pady=(10, 0))

    def _on_nav_hover(self, frame, page_id: str, is_hover: bool):
        if self._current_page == page_id:
            return
        bg = COLOR_CARD_HOVER if is_hover else COLOR_SIDEBAR
        fg = COLOR_TEXT_MAIN if is_hover else COLOR_TEXT_MUTED
        frame.configure(bg=bg)
        frame.btn_label.configure(bg=bg, fg=fg)

    def _navigate_to(self, page_id: str):
        self._current_page = page_id

        # Update sidebar active highlights
        for pid, frame in self._nav_buttons.items():
            if pid == page_id:
                frame.configure(bg="#22222E")
                frame.btn_label.configure(bg="#22222E", fg="#FFFFFF", font=("Segoe UI", 9, "bold"))
                frame.indicator.configure(bg=COLOR_ACCENT)
            else:
                frame.configure(bg=COLOR_SIDEBAR)
                frame.btn_label.configure(bg=COLOR_SIDEBAR, fg=COLOR_TEXT_MUTED, font=("Segoe UI", 9))
                frame.indicator.configure(bg=COLOR_SIDEBAR)

        # Show active page, hide others
        for pid, page in self._pages.items():
            if pid == page_id:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

    # =========================================================================
    # PAGE: GENERAL & HOTKEYS
    # =========================================================================
    def _build_page_general(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        # Page Header
        tk.Label(page, text="General & Shortcuts", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(page, text="Configure global activation hotkeys, trigger behavior, and startup preferences.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 16))

        gen = self.config_manager.get("general", default={})

        # Card 1: Activation Hotkey
        card_hotkey = self._create_card(page, "Global Hotkey Activation")
        tk.Label(card_hotkey, text="Press this key anywhere on Windows to activate Qale speech dictation.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(0, 10))

        self.hotkey_badge = HotkeyBadge(
            card_hotkey,
            initial_hotkey=gen.get("hotkey", "f8"),
            bg=COLOR_CARD
        )
        self.hotkey_badge.pack(anchor="w", pady=4)

        # Card 2: Trigger Mode
        card_mode = self._create_card(page, "Dictation Trigger Mode")
        tk.Label(card_mode, text="Choose how your microphone listens when pressing the global hotkey.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(0, 10))

        self.seg_mode = SegmentedControl(
            card_mode,
            options=[
                ("🔴 Live Auto-Streaming (Types as you speak on natural pauses)", "live"),
                ("🔁 Batch Toggle (Tap to Start, Tap to Finish)", "toggle"),
                ("🎙️ Push-to-Talk (Hold Key While Speaking)", "push_to_talk")
            ],
            initial_value=gen.get("trigger_mode", "live"),
            bg=COLOR_CARD
        )
        self.seg_mode.pack(anchor="w", pady=4)

        # Card 3: Windows Integration & Behavior
        card_switches = self._create_card(page, "System Integration & Preferences")

        # Switch 1: Startup
        row1 = tk.Frame(card_switches, bg=COLOR_CARD)
        row1.pack(fill="x", pady=6)
        self.sw_startup = ModernSwitch(row1, initial_state=StartupManager.is_startup_enabled(),
                                       command=self._on_toggle_startup)
        self.sw_startup.pack(side="right", padx=(10, 0))
        t1 = tk.Frame(row1, bg=COLOR_CARD)
        t1.pack(side="left", fill="x", expand=True)
        tk.Label(t1, text="Launch automatically on Windows Startup", font=("Segoe UI", 10, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(t1, text="Starts Qale minimized to your system tray on PC boot.", font=("Segoe UI", 8),
                 fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")

        # Switch 2: HUD
        row2 = tk.Frame(card_switches, bg=COLOR_CARD)
        row2.pack(fill="x", pady=6)
        self.sw_hud = ModernSwitch(row2, initial_state=gen.get("show_floating_hud", True))
        self.sw_hud.pack(side="right", padx=(10, 0))
        t2 = tk.Frame(row2, bg=COLOR_CARD)
        t2.pack(side="left", fill="x", expand=True)
        tk.Label(t2, text="Show Floating HUD Status Pill", font=("Segoe UI", 10, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(t2, text="Displays the sleek rounded status pill (Listening / Transcribing) on screen.",
                 font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")

        # Switch 3: Sound effects
        row3 = tk.Frame(card_switches, bg=COLOR_CARD)
        row3.pack(fill="x", pady=6)
        self.sw_sound = ModernSwitch(row3, initial_state=gen.get("play_sounds", True))
        self.sw_sound.pack(side="right", padx=(10, 0))
        t3 = tk.Frame(row3, bg=COLOR_CARD)
        t3.pack(side="left", fill="x", expand=True)
        tk.Label(t3, text="Audio Chimes Feedback", font=("Segoe UI", 10, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(t3, text="Plays subtle acoustic chime cues when recording starts and finishes.",
                 font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")

        return page

    # =========================================================================
    # PAGE: AUDIO & MIC TEST
    # =========================================================================
    def _build_page_audio(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        tk.Label(page, text="Audio & Microphone", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(page, text="Select your input device and monitor live volume levels with the visual VU meter.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 16))

        audio_cfg = self.config_manager.get("audio", default={})

        # Card 1: Device Selection
        card_dev = self._create_card(page, "Input Microphone Device")
        tk.Label(card_dev, text="Qale captures clean 16kHz audio directly into local Whisper neural decoders.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(0, 10))

        # Query audio input devices
        self.audio_devices = AudioRecorder.get_input_devices()
        dev_names = [f"[{d['index']}] {d['name']}" for d in self.audio_devices]
        if not dev_names:
            dev_names = ["Default Windows Recording Device"]

        current_idx = audio_cfg.get("device_index")
        selected_text = dev_names[0]
        if current_idx is not None:
            for name in dev_names:
                if name.startswith(f"[{current_idx}]"):
                    selected_text = name
                    break

        self.cmb_mic = ttk.Combobox(card_dev, values=dev_names, state="readonly", width=55)
        self.cmb_mic.set(selected_text)
        self.cmb_mic.pack(anchor="w", pady=4)

        # Card 2: Live Mic VU Volume Meter
        card_vu = self._create_card(page, "Live Microphone VU Meter & Test")
        tk.Label(card_vu, text="Speak into your microphone to verify that audio is detected and not muted.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(0, 10))

        vu_row = tk.Frame(card_vu, bg=COLOR_CARD)
        vu_row.pack(fill="x", pady=6)

        self.vu_meter = VUMeter(vu_row, width=320, height=16, bg=COLOR_CARD)
        self.vu_meter.pack(side="left", padx=(0, 16))

        self.lbl_vu_status = tk.Label(vu_row, text="Idle (Click Test Mic to start)",
                                      font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_vu_status.pack(side="left")

        # Test Mic Button
        ctrl_row = tk.Frame(card_vu, bg=COLOR_CARD)
        ctrl_row.pack(anchor="w", pady=(8, 0))

        self.btn_test_mic = tk.Button(
            ctrl_row,
            text="🎙️ Start Live Mic Test",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_ACCENT,
            fg="#FFFFFF",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._toggle_mic_test
        )
        self.btn_test_mic.pack(side="left", padx=(0, 12))

        # Test sound chimes
        btn_beep_start = tk.Button(
            ctrl_row,
            text="🔊 Test Start Chime",
            font=("Segoe UI", 8),
            bg="#2A2A38",
            fg=COLOR_TEXT_MAIN,
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            command=lambda: AudioRecorder().play_start_sound()
        )
        btn_beep_start.pack(side="left", padx=4)

        btn_beep_stop = tk.Button(
            ctrl_row,
            text="🔊 Test Stop Chime",
            font=("Segoe UI", 8),
            bg="#2A2A38",
            fg=COLOR_TEXT_MAIN,
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            command=lambda: AudioRecorder().play_stop_sound()
        )
        btn_beep_stop.pack(side="left", padx=4)

        return page

    def _toggle_mic_test(self):
        if self._is_testing_mic:
            self._stop_mic_test()
        else:
            self._start_mic_test()

    def _start_mic_test(self):
        try:
            import sounddevice as sd
            import numpy as np
        except Exception as e:
            self.lbl_vu_status.configure(text=f"Audio error: {e}", fg=COLOR_DANGER)
            return

        self._is_testing_mic = True
        self.btn_test_mic.configure(text="⏹️ Stop Mic Test", bg=COLOR_DANGER)
        self.lbl_vu_status.configure(text="🎙️ Listening... Speak now!", fg=COLOR_SUCCESS)

        # Parse selected device index
        sel = self.cmb_mic.get()
        dev_idx = None
        if sel.startswith("["):
            try:
                dev_idx = int(sel.split("]")[0][1:])
            except Exception:
                pass

        def audio_callback(indata, frames, time_info, status):
            if not self._is_testing_mic:
                return
            # Calculate RMS / peak level
            peak = float(np.max(np.abs(indata))) / 32767.0 if indata.dtype == np.int16 else float(np.max(np.abs(indata)))
            level = min(1.0, peak * 2.5)  # slight boost for visual clarity
            if self.root:
                self.root.after(0, self._update_vu_meter, level)

        try:
            self._mic_test_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                device=dev_idx,
                callback=audio_callback
            )
            self._mic_test_stream.start()
        except Exception as e:
            self._stop_mic_test()
            self.lbl_vu_status.configure(text=f"Failed to open mic: {e}", fg=COLOR_DANGER)

    def _update_vu_meter(self, level: float):
        if self.vu_meter and self._is_testing_mic:
            self.vu_meter.set_level(level)
            pct = int(level * 100)
            if pct > 10:
                self.lbl_vu_status.configure(text=f"🎙️ Audio Detected ({pct}%)", fg=COLOR_SUCCESS)
            else:
                self.lbl_vu_status.configure(text="Listening... (Speak to test level)", fg=COLOR_TEXT_MUTED)

    def _stop_mic_test(self):
        self._is_testing_mic = False
        if self._mic_test_stream:
            try:
                self._mic_test_stream.stop()
                self._mic_test_stream.close()
            except Exception:
                pass
            self._mic_test_stream = None

        if hasattr(self, "btn_test_mic") and self.btn_test_mic.winfo_exists():
            self.btn_test_mic.configure(text="🎙️ Start Live Mic Test", bg=COLOR_ACCENT)
        if hasattr(self, "lbl_vu_status") and self.lbl_vu_status.winfo_exists():
            self.lbl_vu_status.configure(text="Idle", fg=COLOR_TEXT_MUTED)
        if hasattr(self, "vu_meter") and self.vu_meter.winfo_exists():
            self.vu_meter.set_level(0.0)

    # =========================================================================
    # PAGE: TECH VOCABULARY & SOUND-ALIKES
    # =========================================================================
    def _build_page_vocab(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        # Header with Search & Presets
        header_row = tk.Frame(page, bg=COLOR_BG_DARK)
        header_row.pack(fill="x")

        title_col = tk.Frame(header_row, bg=COLOR_BG_DARK)
        title_col.pack(side="left")
        tk.Label(title_col, text="Tech Vocabulary & Mishearings", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(title_col, text="Map spoken sound-alikes to exact programming terms (e.g. 'snick js' ➔ 'Next.js').",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 0))

        # Import Presets Button
        btn_presets = tk.Menubutton(
            header_row,
            text="📦 Import Presets ▼",
            font=("Segoe UI", 9, "bold"),
            bg="#2A2A38",
            fg=COLOR_TEXT_MAIN,
            activebackground=COLOR_CARD_HOVER,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2"
        )
        btn_presets.pack(side="right")

        preset_menu = tk.Menu(btn_presets, tearoff=0, bg=COLOR_CARD, fg=COLOR_TEXT_MAIN,
                              activebackground=COLOR_ACCENT, activeforeground="#FFFFFF")
        preset_menu.add_command(label="⚛️ Next.js & React Ecosystem", command=lambda: self._import_preset("react"))
        preset_menu.add_command(label="🐍 Python & PyTorch / ML", command=lambda: self._import_preset("python"))
        preset_menu.add_command(label="🐙 Git & DevOps Commands", command=lambda: self._import_preset("devops"))
        preset_menu.add_command(label="☕ TypeScript & JavaScript Essentials", command=lambda: self._import_preset("typescript"))
        btn_presets["menu"] = preset_menu

        # Filter search bar
        search_card = tk.Frame(page, bg=COLOR_CARD, padx=12, pady=10)
        search_card.pack(fill="x", pady=(14, 8))

        tk.Label(search_card, text="🔍 Search:", font=("Segoe UI", 9, "bold"),
                 fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(0, 8))

        self.entry_vocab_search = tk.Entry(search_card, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                           fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN,
                                           relief="flat", width=30)
        self.entry_vocab_search.pack(side="left", padx=4)
        self.entry_vocab_search.bind("<KeyRelease>", lambda e: self._refresh_vocab_tree())

        self.lbl_vocab_count = tk.Label(search_card, text="", font=("Segoe UI", 9),
                                        fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_vocab_count.pack(side="right")

        # Table container
        table_frame = tk.Frame(page, bg=COLOR_CARD, padx=1, pady=1)
        table_frame.pack(fill="both", expand=True)

        cols = ("spoken", "typed")
        self.tree_vocab = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        self.tree_vocab.heading("spoken", text="When You Say (Spoken / Phonetic Mishearing)")
        self.tree_vocab.heading("typed", text="Qale Types Exactly (Clean Tech Term)")
        self.tree_vocab.column("spoken", width=340)
        self.tree_vocab.column("typed", width=340)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_vocab.yview,
                                  style="Vertical.TScrollbar")
        self.tree_vocab.configure(yscrollcommand=scrollbar.set)

        self.tree_vocab.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add Term Form Card
        add_frame = tk.Frame(page, bg=COLOR_CARD, padx=14, pady=12)
        add_frame.pack(fill="x", pady=(10, 0))

        tk.Label(add_frame, text="Say:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(0, 4))
        self.entry_vocab_spoken = tk.Entry(add_frame, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                           fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, relief="flat", width=20)
        self.entry_vocab_spoken.pack(side="left", padx=4)

        tk.Label(add_frame, text="➔ Types as:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(8, 4))
        self.entry_vocab_typed = tk.Entry(add_frame, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                          fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, relief="flat", width=20)
        self.entry_vocab_typed.pack(side="left", padx=4)

        btn_add = tk.Button(add_frame, text="＋ Add Term", font=("Segoe UI", 9, "bold"), bg=COLOR_ACCENT, fg="#FFFFFF",
                            activebackground=COLOR_ACCENT_HOVER, activeforeground="#FFFFFF", relief="flat",
                            padx=14, pady=4, cursor="hand2", command=self._add_vocab_term)
        btn_add.pack(side="left", padx=(10, 0))

        btn_del = tk.Button(add_frame, text="🗑️ Delete Selected", font=("Segoe UI", 9), bg="#451A1A", fg="#FCA5A5",
                            activebackground=COLOR_DANGER, activeforeground="#FFFFFF", relief="flat",
                            padx=12, pady=4, cursor="hand2", command=self._delete_vocab_term)
        btn_del.pack(side="right")

        self._refresh_vocab_tree()
        return page

    def _refresh_vocab_tree(self):
        for item in self.tree_vocab.get_children():
            self.tree_vocab.delete(item)

        sound_alikes = self.config_manager.get_sound_alikes()
        query = self.entry_vocab_search.get().strip().lower()

        count = 0
        for spoken, typed in sorted(sound_alikes.items()):
            if query and (query not in spoken.lower() and query not in typed.lower()):
                continue
            self.tree_vocab.insert("", "end", values=(spoken, typed))
            count += 1

        self.lbl_vocab_count.configure(text=f"Showing {count} of {len(sound_alikes)} terms")

    def _add_vocab_term(self):
        spoken = self.entry_vocab_spoken.get().strip().lower()
        typed = self.entry_vocab_typed.get().strip()
        if spoken and typed:
            self.config_manager.add_sound_alike(spoken, typed)
            self._refresh_vocab_tree()
            self.entry_vocab_spoken.delete(0, "end")
            self.entry_vocab_typed.delete(0, "end")
            if self.toast:
                self.toast.show(f"Added vocabulary term: '{spoken}' ➔ '{typed}'")

    def _delete_vocab_term(self):
        selected = self.tree_vocab.selection()
        if not selected:
            return
        item = self.tree_vocab.item(selected[0])
        spoken = item["values"][0]
        self.config_manager.remove_sound_alike(str(spoken))
        self._refresh_vocab_tree()
        if self.toast:
            self.toast.show(f"Deleted term: '{spoken}'")

    def _import_preset(self, pack_id: str):
        presets = {
            "react": {
                "snick js": "Next.js", "neck js": "Next.js", "next js": "Next.js",
                "react js": "React", "type script": "TypeScript", "tailwind css": "Tailwind CSS",
                "use state": "useState", "use effect": "useEffect", "use callback": "useCallback",
                "use memo": "useMemo", "use ref": "useRef", "use context": "useContext",
                "zustand": "Zustand", "prisma": "Prisma", "dot tsx": ".tsx", "dot jsx": ".jsx"
            },
            "python": {
                "py torch": "PyTorch", "num py": "NumPy", "pandas": "Pandas",
                "init": "__init__", "async def": "async def", "fast api": "FastAPI",
                "dot py": ".py", "self dot": "self.", "dunder init": "__init__"
            },
            "devops": {
                "git commit": "git commit", "git checkout": "git checkout", "git push": "git push",
                "git pull": "git pull", "git branch": "git branch", "docker compose": "docker-compose",
                "kube ctl": "kubectl", "npm run": "npm run", "pnpm add": "pnpm add"
            },
            "typescript": {
                "interface": "interface", "type alias": "type", "async await": "async/await",
                "json parse": "JSON.parse", "json stringify": "JSON.stringify",
                "console log": "console.log"
            }
        }
        pack = presets.get(pack_id, {})
        for spoken, typed in pack.items():
            self.config_manager.add_sound_alike(spoken, typed)
        self._refresh_vocab_tree()
        if self.toast:
            self.toast.show(f"✓ Imported {len(pack)} terms from preset pack!")

    # =========================================================================
    # PAGE: SYMBOLS & ACTIONS
    # =========================================================================
    def _build_page_symbols(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        header_row = tk.Frame(page, bg=COLOR_BG_DARK)
        header_row.pack(fill="x")

        tk.Label(header_row, text="Symbols & Developer Actions", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(header_row, text="Convert spoken punctuation & symbol names into precise code syntax and keystrokes.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 0))

        # Search bar
        search_card = tk.Frame(page, bg=COLOR_CARD, padx=12, pady=10)
        search_card.pack(fill="x", pady=(14, 8))

        tk.Label(search_card, text="🔍 Search:", font=("Segoe UI", 9, "bold"),
                 fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(0, 8))

        self.entry_sym_search = tk.Entry(search_card, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                         fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN,
                                         relief="flat", width=30)
        self.entry_sym_search.pack(side="left", padx=4)
        self.entry_sym_search.bind("<KeyRelease>", lambda e: self._refresh_sym_tree())

        self.lbl_sym_count = tk.Label(search_card, text="", font=("Segoe UI", 9),
                                      fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_sym_count.pack(side="right")

        # Table container
        table_frame = tk.Frame(page, bg=COLOR_CARD, padx=1, pady=1)
        table_frame.pack(fill="both", expand=True)

        cols = ("phrase", "symbol")
        self.tree_sym = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        self.tree_sym.heading("phrase", text="Voice Phrase Spoken")
        self.tree_sym.heading("symbol", text="Symbol / Keystroke Produced")
        self.tree_sym.column("phrase", width=340)
        self.tree_sym.column("symbol", width=340)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_sym.yview,
                                  style="Vertical.TScrollbar")
        self.tree_sym.configure(yscrollcommand=scrollbar.set)

        self.tree_sym.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add Symbol Form Card
        add_frame = tk.Frame(page, bg=COLOR_CARD, padx=14, pady=12)
        add_frame.pack(fill="x", pady=(10, 0))

        tk.Label(add_frame, text="Phrase:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(0, 4))
        self.entry_sym_phrase = tk.Entry(add_frame, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                         fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, relief="flat", width=18)
        self.entry_sym_phrase.pack(side="left", padx=4)

        tk.Label(add_frame, text="➔ Symbol:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(8, 4))
        self.entry_sym_val = tk.Entry(add_frame, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                      fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, relief="flat", width=18)
        self.entry_sym_val.pack(side="left", padx=4)

        btn_add = tk.Button(add_frame, text="＋ Add Symbol", font=("Segoe UI", 9, "bold"), bg=COLOR_ACCENT, fg="#FFFFFF",
                            activebackground=COLOR_ACCENT_HOVER, activeforeground="#FFFFFF", relief="flat",
                            padx=14, pady=4, cursor="hand2", command=self._add_sym_term)
        btn_add.pack(side="left", padx=(10, 0))

        btn_del = tk.Button(add_frame, text="🗑️ Delete Selected", font=("Segoe UI", 9), bg="#451A1A", fg="#FCA5A5",
                            activebackground=COLOR_DANGER, activeforeground="#FFFFFF", relief="flat",
                            padx=12, pady=4, cursor="hand2", command=self._delete_sym_term)
        btn_del.pack(side="right")

        self._refresh_sym_tree()
        return page

    def _refresh_sym_tree(self):
        for item in self.tree_sym.get_children():
            self.tree_sym.delete(item)

        symbols = self.config_manager.get_symbols()
        query = self.entry_sym_search.get().strip().lower()

        count = 0
        for phrase, sym in sorted(symbols.items()):
            if query and (query not in phrase.lower() and query not in sym.lower()):
                continue
            self.tree_sym.insert("", "end", values=(phrase, sym))
            count += 1

        self.lbl_sym_count.configure(text=f"Showing {count} of {len(symbols)} symbols")

    def _add_sym_term(self):
        phrase = self.entry_sym_phrase.get().strip().lower()
        sym = self.entry_sym_val.get().strip()
        if phrase and sym:
            self.config_manager.add_symbol(phrase, sym)
            self._refresh_sym_tree()
            self.entry_sym_phrase.delete(0, "end")
            self.entry_sym_val.delete(0, "end")
            if self.toast:
                self.toast.show(f"Added symbol: '{phrase}' ➔ '{sym}'")

    def _delete_sym_term(self):
        selected = self.tree_sym.selection()
        if not selected:
            return
        item = self.tree_sym.item(selected[0])
        phrase = item["values"][0]
        self.config_manager.remove_symbol(str(phrase))
        self._refresh_sym_tree()
        if self.toast:
            self.toast.show(f"Deleted symbol: '{phrase}'")

    # =========================================================================
    # PAGE: AI WHISPER MODEL & BIASING
    # =========================================================================
    def _build_page_ai(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        tk.Label(page, text="AI Whisper Engine & Context Biasing", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(page, text="Select neural model weights and configure developer context conditioning for high accuracy.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 16))

        ai_cfg = self.config_manager.get("ai", default={})

        # Card 1: Whisper Model Size Selection
        card_model = self._create_card(page, "Whisper Model Selection")
        self.var_model = tk.StringVar(value=ai_cfg.get("model_size", "base.en"))

        models_info = [
            ("tiny.en", "⚡ tiny.en (Ultra-fast, ~100ms)", "Minimal latency, optimal for low-spec hardware or rapid dictation."),
            ("base.en", "⭐ base.en (Recommended, ~180ms)", "Ideal balance of speed and precision for code syntax and technical vocabulary."),
            ("small.en", "🎯 small.en (High Precision, ~300ms)", "Enhanced recognition accuracy for heavy multi-language developer terms."),
            ("turbo", "🚀 large-v3-turbo (State of the Art)", "Maximum Whisper intelligence, multi-speaker and acoustic nuances.")
        ]

        for val, title, desc in models_info:
            row = tk.Frame(card_model, bg=COLOR_CARD)
            row.pack(fill="x", pady=4)

            rb = tk.Radiobutton(
                row,
                text=title,
                variable=self.var_model,
                value=val,
                font=("Segoe UI", 10, "bold"),
                fg=COLOR_TEXT_MAIN,
                bg=COLOR_CARD,
                selectcolor="#2A2A38",
                activebackground=COLOR_CARD,
                activeforeground="#FFFFFF"
            )
            rb.pack(anchor="w")

            tk.Label(row, text=f"     {desc}", font=("Segoe UI", 8),
                     fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")

        # Card 2: Context Biasing Prompt
        card_prompt = self._create_card(page, "Developer Context Biasing (Prompt Conditioning)")
        tk.Label(card_prompt, text="Whisper reads these keywords prior to decoding, priming its AI to expect programming terms:",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(0, 6))

        self.txt_prompt = tk.Text(card_prompt, height=4, font=("Segoe UI", 10), bg=COLOR_INPUT_BG,
                                  fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, relief="flat",
                                  wrap="word", padx=8, pady=8)
        self.txt_prompt.insert("1.0", ai_cfg.get("developer_prompt", ""))
        self.txt_prompt.pack(fill="both", expand=True, pady=(0, 8))

        btn_reset_prompt = tk.Button(
            card_prompt,
            text="🔄 Reset to Default Developer Prompt",
            font=("Segoe UI", 8),
            bg="#2A2A38",
            fg=COLOR_TEXT_MUTED,
            activebackground=COLOR_CARD_HOVER,
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._reset_developer_prompt
        )
        btn_reset_prompt.pack(anchor="e")

        return page

    def _reset_developer_prompt(self):
        default_prompt = (
            "camel case, camelCase, snake case, snake_case, pascal case, kebab case, constant case, "
            "dot tsx, dot jsx, dot js, dot json, dot py, backslash, go back, erase that, undo, source, "
            "components, Next.js, React, TypeScript, JavaScript, Python, Node.js, Express, Tailwind, "
            "MongoDB, function, const, let, var, return, import, export, default, async, await, JSON, "
            "API, npm, GitHub, useState, useEffect, useContext, boolean, interface, type, class, enum, "
            "void, null, undefined, try, catch, finally, git, commit, push, pull, branch, checkout, merge"
        )
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", default_prompt)
        if self.toast:
            self.toast.show("Reset developer prompt to defaults.")

    # =========================================================================
    # PAGE: VOICE PLAYGROUND & SCRATCHPAD
    # =========================================================================
    def _build_page_playground(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        tk.Label(page, text="Voice Dictation Playground", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(page, text="Test your voice, hotkey, and syntax transformations instantly right inside this scratchpad.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 16))

        # Playground Action Card
        card_action = self._create_card(page, "Live Test Control")

        ctrl_row = tk.Frame(card_action, bg=COLOR_CARD)
        ctrl_row.pack(fill="x", pady=4)

        self.btn_play_record = tk.Button(
            ctrl_row,
            text="🎙️ Record Test Dictation (3s)",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_ACCENT,
            fg="#FFFFFF",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._start_playground_test
        )
        self.btn_play_record.pack(side="left", padx=(0, 14))

        self.lbl_play_status = tk.Label(ctrl_row, text="Ready. Click record or press your hotkey.",
                                        font=("Segoe UI", 10), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_play_status.pack(side="left")

        # Scratchpad Result Box Card
        card_scratchpad = self._create_card(page, "Transcribed & Parsed Syntax Output")

        self.txt_playground = tk.Text(
            card_scratchpad,
            height=8,
            font=("Cascadia Code", 11),
            bg=COLOR_INPUT_BG,
            fg="#67E8F9",
            insertbackground="#FFFFFF",
            relief="flat",
            wrap="word",
            padx=12,
            pady=12
        )
        self.txt_playground.pack(fill="both", expand=True, pady=(0, 8))
        self.txt_playground.insert("1.0", "// Speak code like:\n// 'const data strictly equals camel case user profile semicolon'\n// And see it parsed here instantly!\n")

        # Bottom actions
        bar = tk.Frame(card_scratchpad, bg=COLOR_CARD)
        bar.pack(fill="x")

        btn_copy = tk.Button(
            bar,
            text="📋 Copy Output",
            font=("Segoe UI", 9),
            bg="#2A2A38",
            fg=COLOR_TEXT_MAIN,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._copy_playground_output
        )
        btn_copy.pack(side="left")

        btn_clear = tk.Button(
            bar,
            text="🧹 Clear Scratchpad",
            font=("Segoe UI", 9),
            bg="#2A2A38",
            fg=COLOR_TEXT_MAIN,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=lambda: self.txt_playground.delete("1.0", "end")
        )
        btn_clear.pack(side="left", padx=8)

        return page

    def _start_playground_test(self):
        if self._test_dictation_active:
            return
        self._test_dictation_active = True
        self.btn_play_record.configure(text="🔴 Recording (3s)...", bg=COLOR_DANGER)
        self.lbl_play_status.configure(text="Listening... Speak your code or symbols now!", fg=COLOR_DANGER)

        threading.Thread(target=self._run_playground_recording, daemon=True).start()

    def _run_playground_recording(self):
        recorder = AudioRecorder(sample_rate=16000)
        recorder.play_start_sound()
        recorder.start()
        time.sleep(3.0)
        wav_bytes = recorder.stop()
        recorder.play_stop_sound()

        if self.root:
            self.root.after(0, self._process_playground_audio, wav_bytes)

    def _process_playground_audio(self, wav_bytes: bytes):
        self.lbl_play_status.configure(text="⚡ Transcribing with local Whisper...", fg=COLOR_WARNING)

        def worker():
            try:
                from core.whisper_engine import WhisperEngine
                engine = WhisperEngine(
                    model_size=self.var_model.get(),
                    developer_prompt=self.txt_prompt.get("1.0", "end-1c").strip()
                )
                raw_text = engine.transcribe(wav_bytes)
                parser = CodeParser(self.config_manager)
                parsed = parser.parse(raw_text)

                if self.root:
                    self.root.after(0, self._finish_playground_test, raw_text, parsed)
            except Exception as e:
                if self.root:
                    self.root.after(0, self._finish_playground_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_playground_test(self, raw_text: str, parsed: Dict):
        self._test_dictation_active = False
        self.btn_play_record.configure(text="🎙️ Record Test Dictation (3s)", bg=COLOR_ACCENT)
        self.lbl_play_status.configure(text="✓ Transcribed and parsed successfully!", fg=COLOR_SUCCESS)

        content = parsed.get("content", str(parsed))
        self.txt_playground.insert("end", f"\n[Spoken]: '{raw_text}'\n[Result]: {content}\n")
        self.txt_playground.see("end")

    def _finish_playground_error(self, err_msg: str):
        self._test_dictation_active = False
        self.btn_play_record.configure(text="🎙️ Record Test Dictation (3s)", bg=COLOR_ACCENT)
        self.lbl_play_status.configure(text=f"Error: {err_msg}", fg=COLOR_DANGER)

    def _copy_playground_output(self):
        text = self.txt_playground.get("1.0", "end-1c")
        if self.root:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            if self.toast:
                self.toast.show("Copied scratchpad text to clipboard!")

    # =========================================================================
    # PAGE: STATUS & DIAGNOSTICS & SHORTCUTS
    # =========================================================================
    def _build_page_diagnostics(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=COLOR_BG_DARK, padx=28, pady=24)

        tk.Label(page, text="Status & Voice Shortcuts Cheat Sheet", font=("Segoe UI", 16, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_BG_DARK).pack(anchor="w")
        tk.Label(page, text="Quick reference guide for developer voice commands and environment diagnostics.",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK).pack(anchor="w", pady=(2, 16))

        # Card 1: Commands reference
        card_ref = self._create_card(page, "Voice Commands Reference Sheet")

        ref_text = (
            "🔤 Code Case Converters:\n"
            "  • 'camel case user profile'       ➔ userProfile\n"
            "  • 'snake case fetch data'         ➔ fetch_data\n"
            "  • 'constant case api key'         ➔ API_KEY\n"
            "  • 'pascal case auth provider'     ➔ AuthProvider\n\n"
            "⌨️ Developer Actions:\n"
            "  • 'go back' / 'erase that'        ➔ Triggers Backspace\n"
            "  • 'go back 3 times'               ➔ Backspaces 3 characters\n"
            "  • 'new line' / 'enter'            ➔ Hits Enter\n"
            "  • 'indent' / 'tab'                ➔ Hits Tab\n\n"
            "⚡ Common Symbols:\n"
            "  • 'fat arrow' ➔ =>      • 'strictly equals' ➔ ===      • 'curly braces' ➔ {}\n"
            "  • 'backslash' ➔ \\      • 'forward slash'   ➔ /        • 'backticks'    ➔ ``"
        )

        tk.Label(card_ref, text=ref_text, font=("Cascadia Code", 9),
                 fg="#CBD5E1", bg=COLOR_CARD, justify="left").pack(anchor="w")

        # Card 2: Environment info
        card_diag = self._create_card(page, "System Environment & Diagnostics")

        try:
            import torch
            cuda_status = f"CUDA {torch.version.cuda} Available (GPU: {torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "CUDA not active (Running CPU)"
        except Exception:
            cuda_status = "PyTorch not found"

        diag_text = (
            f"• Python: {sys.version.split()[0]} ({sys.executable})\n"
            f"• Acceleration: {cuda_status}\n"
            f"• Startup Mode: {'Enabled (Windows Registry)' if StartupManager.is_startup_enabled() else 'Disabled'}"
        )
        tk.Label(card_diag, text=diag_text, font=("Segoe UI", 9),
                 fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, justify="left").pack(anchor="w")

        return page

    # =========================================================================
    # HELPERS & EVENT HANDLERS
    # =========================================================================
    def _create_card(self, parent: tk.Frame, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=COLOR_CARD, padx=18, pady=16,
                        highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        card.pack(fill="x", pady=6)

        tk.Label(card, text=title, font=("Segoe UI", 11, "bold"),
                 fg=COLOR_TEXT_MAIN, bg=COLOR_CARD).pack(anchor="w", pady=(0, 6))
        return card

    def _on_toggle_startup(self, enabled: bool):
        if enabled:
            StartupManager.enable_startup()
        else:
            StartupManager.disable_startup()
        self.config_manager.set("general", "run_on_startup", enabled)
        if self.toast:
            status = "enabled" if enabled else "disabled"
            self.toast.show(f"Windows startup {status}.")

    def _save_all_settings(self):
        # 1. Save general
        self.config_manager.set("general", "trigger_mode", self.seg_mode.get_value())
        self.config_manager.set("general", "hotkey", self.hotkey_badge.get_hotkey())
        self.config_manager.set("general", "show_floating_hud", self.sw_hud.get_state())
        self.config_manager.set("general", "play_sounds", self.sw_sound.get_state())
        self.config_manager.set("general", "run_on_startup", self.sw_startup.get_state())

        # 2. Save audio device
        sel = self.cmb_mic.get()
        dev_idx = None
        if sel.startswith("["):
            try:
                dev_idx = int(sel.split("]")[0][1:])
            except Exception:
                pass
        self.config_manager.set("audio", "device_index", dev_idx)

        # 3. Save AI
        self.config_manager.set("ai", "model_size", self.var_model.get())
        self.config_manager.set("ai", "developer_prompt", self.txt_prompt.get("1.0", "end-1c").strip())

        # Notify callbacks
        if self.on_config_changed:
            self.on_config_changed()

        if self.toast:
            self.toast.show("✓ All Qale settings saved successfully!")


if __name__ == "__main__":
    app = MainWindow()
    app.show()
