"""
Single-Instance Application Enforcer for Qale.
Uses Windows Win32 Named Mutex and Named Event for zero-network,
firewall-free, lightning-fast single-instance enforcement and window restoration.
"""
import ctypes
from ctypes import wintypes
import sys
import threading
from typing import Callable, Optional

k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32

ERROR_ALREADY_EXISTS = 183
SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002
MUTEX_NAME = "Local\\QaleSingleInstanceMutex_v1"
EVENT_NAME = "Local\\QaleShowDashboardEvent_v1"


def is_already_running() -> bool:
    """Checks if another instance of Qale is already running."""
    mutex = k32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
    if mutex:
        k32.CloseHandle(mutex)
        return True
    return False


def notify_existing_instance(show_ui: bool = True) -> bool:
    """
    Checks if an existing instance is running.
    If running and show_ui is True, triggers the show dashboard event and brings window to front.
    Returns True if an existing instance was running, False otherwise.
    """
    if not is_already_running():
        return False

    if show_ui:
        # 1. Trigger the named event to wake up running instance
        ev = k32.OpenEventW(EVENT_MODIFY_STATE, False, EVENT_NAME)
        if ev:
            k32.SetEvent(ev)
            k32.CloseHandle(ev)

        # 2. Also try direct window activation via FindWindow as immediate helper
        try:
            hwnd = u32.FindWindowW(None, "Qale - Developer Voice Assistant")
            if not hwnd:
                hwnd = u32.FindWindowW(None, "Qale - Developer Voice Assistant")
            if hwnd:
                u32.ShowWindow(hwnd, 9)  # SW_RESTORE
                from core.text_injector import force_foreground_window
                force_foreground_window(hwnd)
        except Exception:
            pass

    return True


class SingleInstanceServer:
    def __init__(self, on_show_ui: Callable[[], None]):
        self.on_show_ui = on_show_ui
        self._mutex = None
        self._event = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Acquires the primary mutex and starts listening for wake-up events."""
        self._mutex = k32.CreateMutexW(None, False, MUTEX_NAME)
        if not self._mutex or k32.GetLastError() == ERROR_ALREADY_EXISTS:
            return False

        self._event = k32.CreateEventW(None, False, False, EVENT_NAME)
        self._running = True
        self._thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._thread.start()
        return True

    def _wait_loop(self):
        while self._running and self._event:
            # Wait with a 500ms timeout so the thread can cleanly terminate on exit
            res = k32.WaitForSingleObject(self._event, 500)
            if res == 0:  # WAIT_OBJECT_0
                if self._running and self.on_show_ui:
                    try:
                        self.on_show_ui()
                    except Exception as e:
                        print(f"[SingleInstance] Error triggering on_show_ui: {e}")

    def stop(self):
        self._running = False
        if self._event:
            try:
                k32.CloseHandle(self._event)
            except Exception:
                pass
            self._event = None
        if self._mutex:
            try:
                k32.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
