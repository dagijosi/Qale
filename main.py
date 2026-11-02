"""
Qale - Developer Voice-to-Code Assistant
Main Application Entry Point.
Features: Live Sound Waveform HUD + Instant Full-Sentence Code Formatting & Injection.
"""
import argparse
import ctypes
import os
import sys
import threading
import time

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import webview

from core.audio_recorder import AudioRecorder
from core.code_parser import CodeParser
from core.config_manager import ConfigManager
from core.context import ContextProfileManager, active_window, pick_profile
from core.single_instance import SingleInstanceServer, notify_existing_instance
from core.text_injector import TextInjector
from core.whisper_engine import WhisperEngine
from ui.web_hud import WebFloatingHUD
from ui.web_window import WebSettingsWindow
from ui.tray_icon import SystemTray

user32 = ctypes.windll.user32


class QaleApp:
    def __init__(self):
        self.config = ConfigManager()
        self.context_mgr = ContextProfileManager(self.config)
        self.parser = CodeParser(self.config)
        self.hud = WebFloatingHUD()
        self.injector = TextInjector(
            paste_method=self.config.get("general", "paste_method", "clipboard"),
            typing_speed_ms=self.config.get("general", "typing_speed_ms", 10),
            hud=self.hud,
            preserve_clipboard=self.config.get("general", "preserve_clipboard", True)
        )
        self.recorder = AudioRecorder(
            sample_rate=self.config.get("audio", "sample_rate", 16000),
            highpass=self.config.get("audio", "audio_highpass", True),
            spectral_gate=self.config.get("audio", "audio_spectral_gate", False),
            pre_emphasis=float(self.config.get("audio", "audio_pre_emphasis", 0.0))
        )

        self.engine = WhisperEngine(
            model_size=self.config.get("ai", "model_size", "base.en"),
            device=self.config.get("ai", "device", "cpu"),
            compute_type=self.config.get("ai", "compute_type", "float16"),
            developer_prompt=self.config.get("ai", "developer_prompt", ""),
            quantize_int8=self.config.get("ai", "quantize_int8", True),
            torch_threads=self.config.get("ai", "torch_threads", None),
            beam_size=self.config.get("ai", "beam_size", 2),
            language=self.config.get("ai", "language", "en")
        )

        self.web_window = WebSettingsWindow(
            config_manager=self.config,
            on_config_changed=self.on_config_updated,
            on_quit=self.quit_app,
            parser=self.parser,
            injector=self.injector,
            context_mgr=self.context_mgr
        )
        self.tray = SystemTray(
            on_open_ui=self.open_ui,
            on_toggle_pause=self.toggle_pause,
            on_quit=self.quit_app
        )
        self.instance_server = SingleInstanceServer(on_show_ui=self.open_ui)

        self.is_recording = False
        self.is_paused = False
        self.target_hwnd = 0
        self.captured_exe = ""
        self.captured_title = ""
        self.captured_profile = "prose"
        self._lock = threading.Lock()
        self._wave_thread = None

    def start(self, minimized: bool = False):
        print("[Qale] Starting developer voice assistant...")
        print("[Qale] Mode: Sound-Wave HUD + Full Sentence Code Formatting & Paste.")

        # 0. Start Single Instance Server
        self.instance_server.start()

        # 1. Create Webview Settings Window (Main Application Window)
        self.web_window.create(hidden=minimized)

        # 2. Create HTML Floating Sound-Wave HUD (Overlay Window)
        if self.config.get("general", "show_floating_hud", True):
            self.hud.create()

        # 3. Start System Tray Icon
        self.tray.start()

        # 4. Setup Global Hotkey Listener
        self._setup_hotkey()

        # 5. Preload Whisper in background
        threading.Thread(target=self.engine.load_model, daemon=True).start()

        if not minimized:
            print("[Qale] Web Dashboard initialized (Edge WebView2).")
        else:
            print("[Qale] Started minimized to system tray.")

        # 6. Start pywebview main event loop without internal HTTP server (pure offline file://)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        try:
            webview.start(http_server=False, icon=icon_path if os.path.exists(icon_path) else None)
        except KeyboardInterrupt:
            self.quit_app()

    def _setup_hotkey(self):
        hotkey_str = self.config.get("general", "hotkey", "f8")
        mode = self.config.get("general", "trigger_mode", "toggle")

        try:
            import keyboard
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
            print(f"[Qale] Registering hotkey '{hotkey_str}' (Mode: {mode})...")

            if mode in ("toggle", "live"):
                keyboard.add_hotkey(hotkey_str, self._handle_toggle)
            else:
                keyboard.on_press_key(hotkey_str, lambda _: self._handle_push_start())
                keyboard.on_release_key(hotkey_str, lambda _: self._handle_push_stop())
            return
        except ImportError:
            pass

        try:
            from pynput import keyboard as pk
            print(f"[Qale] Using pynput hotkey listener for '{hotkey_str}'...")

            def for_canonical(f):
                return lambda k: f(l.canonical(k))

            hotkey = pk.HotKey(pk.HotKey.parse(f"<{hotkey_str}>"), self._handle_toggle)
            l = pk.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release)
            )
            l.start()
            return
        except ImportError:
            print("[Qale] Warning: 'keyboard' or 'pynput' not installed.")

    def _handle_toggle(self):
        with self._lock:
            if self.is_paused:
                return

            if not self.is_recording:
                self._start_dictation()
            else:
                self._finish_and_inject()

    def _handle_push_start(self):
        with self._lock:
            if self.is_paused or self.is_recording:
                return
            self._start_dictation()

    def _handle_push_stop(self):
        with self._lock:
            if self.is_paused or not self.is_recording:
                return
            self._finish_and_inject()

    def _get_target_window_name(self, hwnd: int) -> str:
        """Retrieves a friendly clean name for the focused foreground editor."""
        if not hwnd or not user32.IsWindow(hwnd):
            return "Active Editor"
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            full_title = buff.value.strip()
            if not full_title:
                return "Active Editor"
            if " - " in full_title:
                parts = [p.strip() for p in full_title.split(" - ") if p.strip()]
                app_name = parts[-1]
                file_name = parts[0]
                if len(parts) >= 2:
                    return f"{app_name} ({file_name[:18]})"
                return app_name[:24]
            return full_title[:24]
        return "Active Editor"

    # =========================================================================
    # DICTATION: RECORD WITH LIVE SOUND WAVE VISUALIZER
    # =========================================================================
    def _start_dictation(self):
        # 1. Capture foreground window BEFORE HUD appears to prevent focus theft
        exe, title, hwnd = active_window()
        self.target_hwnd = hwnd or user32.GetForegroundWindow()
        self.captured_exe = exe
        self.captured_title = title
        if self.config.get("context_profiles", "enabled", True):
            self.captured_profile = pick_profile(exe, title)
        else:
            self.captured_profile = "prose"

        self.is_recording = True
        target_name = self._get_target_window_name(self.target_hwnd)

        is_cuda = (self.engine.actual_device == "cuda")
        try:
            import torch
            device_label = f"{torch.cuda.get_device_name(0)} (CUDA)" if is_cuda else "CPU"
        except Exception:
            device_label = "GPU (CUDA)" if is_cuda else "CPU"
        print(f"[Qale] Listening (Target: {target_name} | Profile: {self.captured_profile} | Device: {device_label})...")
        print("          Microphone active. Tap F8 again to finish speaking and paste.")

        if self.config.get("general", "play_sounds", True):
            threading.Thread(target=self.recorder.play_start_sound, daemon=True).start()

        if self.config.get("general", "show_floating_hud", True):
            hotkey_str = self.config.get("general", "hotkey", "f8")
            model_short = (self.engine.model_size or "base").replace(".en", "")
            try:
                import torch
                gpu_short = torch.cuda.get_device_name(0).replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")[:12] if is_cuda else "cpu"
            except Exception:
                gpu_short = "GPU" if is_cuda else "cpu"
            hw_label = f"{gpu_short} · {model_short}"
            self.hud.show_listening(target_name=target_name, hotkey=hotkey_str, hw_chip=hw_label, profile=self.captured_profile)

        device_idx = self.config.get("audio", "device_index", None)
        try:
            self.recorder.start(device_index=device_idx)
        except Exception as e:
            print(f"[Qale] Error starting microphone: {e}")

        # Start live sound wave visualizer thread (0% CPU, 30 FPS)
        self._wave_thread = threading.Thread(target=self._waveform_update_loop, daemon=True)
        self._wave_thread.start()

    def _waveform_update_loop(self):
        """Feeds microphone audio energy levels to the HUD sound wave."""
        while self.is_recording:
            try:
                levels = self.recorder.get_audio_levels(num_bars=28)
                self.hud.update_waveform(levels)
            except Exception:
                pass
            time.sleep(0.03)

    # =========================================================================
    # FINISH & INJECT: ONE-SHOT HIGH ACCURACY TRANSLATION & PASTE
    # =========================================================================
    def _finish_and_inject(self):
        self.is_recording = False
        target_name = self._get_target_window_name(self.target_hwnd)
        print(f"[Qale] ⚡ Formatting code & pasting into {target_name}...")

        if self.config.get("general", "play_sounds", True):
            threading.Thread(target=self.recorder.play_stop_sound, daemon=True).start()

        # Immediately transition HUD to formatting state
        self.hud.show_formatting()

        # Stop recording and get conditioned float32 NumPy array
        audio_data = self.recorder.stop()

        if audio_data is None or len(audio_data) < 4000:
            print("[Qale] Audio too short or empty. Nothing to paste.")
            self.hud.hide()
            return

        # Run final full-sentence transcription in background thread
        threading.Thread(
            target=self._process_final_injection,
            args=(audio_data, self.target_hwnd, target_name, self.captured_profile, self.captured_exe, self.captured_title),
            daemon=True
        ).start()

    def _process_final_injection(self, audio_data, target_hwnd: int, target_name: str, profile_name: str, exe: str, title: str):
        try:
            # 1. Profile-specific prompt priming
            prompt = self.context_mgr.get_prompt(profile_name, self.config.get("ai", "developer_prompt", ""))

            # 2. Transcribe directly from float32 NumPy array with timing
            t0 = time.perf_counter()
            raw_text = self.engine.transcribe(audio_data, custom_prompt=prompt)
            infer_ms = (time.perf_counter() - t0) * 1000.0

            is_cuda = (self.engine.actual_device == "cuda")
            try:
                import torch
                gpu_name = torch.cuda.get_device_name(0) if is_cuda else "CPU"
            except Exception:
                gpu_name = "GPU" if is_cuda else "CPU"

            device_desc = f"{gpu_name} (CUDA FP16)" if is_cuda else "CPU"
            print(f"[Whisper Output ({infer_ms:.0f}ms on {device_desc})]: '{raw_text}'")

            if not raw_text or not raw_text.strip():
                print("[Qale] No speech detected.")
                self.hud.hide()
                return

            # 3. Apply TechCorrector for profile + CodeParser
            corrector = self.context_mgr.get_corrector(profile_name) if profile_name != "prose" else None
            parsed = self.parser.parse(raw_text, corrector=corrector)
            print(f"[Qale Formatted Code]: {parsed}")

            # 4. Inject keystrokes directly into the active editor
            t_inj = time.perf_counter()
            self.injector.execute(parsed, target_hwnd=target_hwnd)
            inj_ms = (time.perf_counter() - t_inj) * 1000.0
            print(f"[Qale] Injected into {target_name} in {inj_ms:.1f}ms (Total round-trip: {infer_ms + inj_ms:.0f}ms)")

            # Record in history for settings dashboard
            injected_str = parsed.get("content") or f"[{parsed.get('action', 'ACTION')}]"
            self.injector.record_history(injected_str, target_name=target_name, profile=profile_name, latency=f"{int(infer_ms)}ms")

            # 5. Show clean status in HUD with real inference latency then auto-hide
            latency_str = f"{int(infer_ms)}ms"
            self.hud.show_done(target_name=target_name, latency_str=latency_str)

            # 6. Save eval clip if enabled in config
            if self.config.get("general", "save_eval_clips", False):
                self._save_eval_clip(audio_data, raw_text, parsed.get("content", ""), profile_name, exe, title)

        except Exception as e:
            print(f"[Qale Pipeline Error]: {e}")
            self.hud.hide()

    def _save_eval_clip(self, audio_data, raw_text: str, final_text: str, profile: str, exe: str, title: str):
        try:
            import json
            clips_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_clips")
            os.makedirs(clips_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            wav_path = os.path.join(clips_dir, f"{ts}.wav")
            json_path = os.path.join(clips_dir, f"{ts}.json")
            wav_bytes = self.recorder.to_wav(audio_data)
            with open(wav_path, "wb") as f:
                f.write(wav_bytes)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": ts,
                    "raw_text": raw_text,
                    "final_text": final_text,
                    "profile": profile,
                    "exe": exe,
                    "title": title,
                    "expected": ""
                }, f, indent=2)
            print(f"[Qale] Saved evaluation clip: {wav_path}")
        except Exception as e:
            print(f"[Qale] Notice: Could not save eval clip: {e}")

    def open_ui(self):
        self.web_window.show()

    def toggle_pause(self, paused: bool):
        self.is_paused = paused
        print(f"[Qale] Dictation {'PAUSED' if paused else 'RESUMED'}")

    def on_config_updated(self):
        print("[Qale] Reloading updated configuration...")
        new_model = self.config.get("ai", "model_size", "base.en")
        if self.engine.model_size != new_model:
            print(f"[Qale] Switching Whisper model: {self.engine.model_size} -> {new_model}...")
            self.engine.model_size = new_model
            self.engine.model = None
            threading.Thread(target=self.engine.load_model, daemon=True).start()

        self.engine.developer_prompt = self.config.get("ai", "developer_prompt", "")
        self.engine.language = self.config.get("ai", "language", "en")
        self.injector.paste_method = self.config.get("general", "paste_method", "clipboard")
        self.injector.typing_speed_ms = self.config.get("general", "typing_speed_ms", 10)
        self.injector.preserve_clipboard = self.config.get("general", "preserve_clipboard", True)
        self.hud.set_position(self.config.get("general", "hud_position", "bottom_center"))
        self.context_mgr._reload_cache()
        self._setup_hotkey()

    def quit_app(self):
        print("[Qale] Shutting down...")
        self.instance_server.stop()
        self.hud.destroy()
        self.web_window.destroy()
        time.sleep(0.2)
        os._exit(0)


def main():
    parser = argparse.ArgumentParser(description="Qale Voice-to-Code Assistant")
    parser.add_argument("--minimized", action="store_true", help="Start directly in system tray")
    args = parser.parse_args()

    # Check if Qale is already running
    if notify_existing_instance(show_ui=not args.minimized):
        print("[Qale] Already running. Brought Dashboard to foreground.")
        sys.exit(0)

    app = QaleApp()
    app.start(minimized=args.minimized)


if __name__ == "__main__":
    main()
