"""
Windows Startup Manager for Qale.
Configures auto-start on Windows boot via HKCU registry.
Does not require Administrator elevation.
"""
import importlib
import os
import sys
from typing import Any

# Use dynamic import to prevent static linters/type checkers from raising false-positive
# "No attribute ... in module winreg" errors when analyzing in cross-platform/generic mode.
reg: Any = importlib.import_module("winreg") if sys.platform == "win32" else None

APP_NAME = "Qale_VoiceCode"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


class StartupManager:
    @staticmethod
    def get_run_command() -> str:
        """Returns the full command line to run Qale silently on boot."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vbs_path = os.path.join(base_dir, "run_silent.vbs")
        if os.path.exists(vbs_path):
            return f'wscript.exe "{vbs_path}" --minimized'

        python_exe = sys.executable
        main_py = os.path.join(base_dir, "main.py")
        pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        exe_to_use = pythonw if os.path.exists(pythonw) else python_exe
        
        return f'"{exe_to_use}" "{main_py}" --minimized'

    @classmethod
    def is_startup_enabled(cls) -> bool:
        """Checks if Qale is currently set to start with Windows."""
        if not reg:
            return False
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_READ) as key:
                value, _ = reg.QueryValueEx(key, APP_NAME)
                return bool(value)
        except (FileNotFoundError, OSError):
            return False

    @classmethod
    def enable_startup(cls) -> bool:
        """Enables auto-start on Windows boot."""
        if not reg:
            return False
        try:
            command = cls.get_run_command()
            with reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_SET_VALUE) as key:
                reg.SetValueEx(key, APP_NAME, 0, reg.REG_SZ, command)
            print(f"[Startup] Enabled auto-start: {command}")
            return True
        except Exception as e:
            print(f"[Startup] Failed to enable auto-start: {e}")
            return False

    @classmethod
    def disable_startup(cls) -> bool:
        """Disables auto-start on Windows boot."""
        if not reg:
            return False
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_SET_VALUE) as key:
                try:
                    reg.DeleteValue(key, APP_NAME)
                    print("[Startup] Disabled auto-start.")
                except FileNotFoundError:
                    pass
            return True
        except Exception as e:
            print(f"[Startup] Failed to disable auto-start: {e}")
            return False
