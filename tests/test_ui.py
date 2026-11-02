"""
Unit tests for Qalē UI components and window lifecycle.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from ui.widgets import ModernSwitch, SegmentedControl, HotkeyBadge, VUMeter, ToastNotification
from ui.main_window import MainWindow
from ui.floating_hud import FloatingHUD
import tkinter as tk


class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_switch(self):
        called = []
        switch = ModernSwitch(self.root, initial_state=False, command=lambda s: called.append(s))
        self.assertFalse(switch.get_state())
        switch.set_state(True)
        self.assertTrue(switch.get_state())

    def test_segmented_control(self):
        opts = [("Toggle", "toggle"), ("Push", "push_to_talk")]
        seg = SegmentedControl(self.root, options=opts, initial_value="toggle")
        self.assertEqual(seg.get_value(), "toggle")
        seg.set_value("push_to_talk")
        self.assertEqual(seg.get_value(), "push_to_talk")

    def test_hotkey_badge(self):
        badge = HotkeyBadge(self.root, initial_hotkey="f8")
        self.assertEqual(badge.get_hotkey(), "f8")
        badge.set_hotkey("ctrl+space")
        self.assertEqual(badge.get_hotkey(), "ctrl+space")

    def test_vu_meter(self):
        vu = VUMeter(self.root, width=200, height=14)
        vu.set_level(0.75)
        self.assertEqual(vu.level, 0.75)

    def test_toast_notification(self):
        toast = ToastNotification(self.root)
        toast.show("Test notification", duration_ms=500)
        toast.hide()

    def test_main_window_instantiation(self):
        app = MainWindow()
        self.assertIsNotNone(app.config_manager)

    def test_main_window_pages_build(self):
        app = MainWindow()
        app.root = self.root
        app._apply_ttk_styles()
        app._build_layout()
        self.assertIn("general", app._pages)
        self.assertIn("audio", app._pages)
        self.assertIn("vocab", app._pages)
        self.assertIn("symbols", app._pages)
        self.assertIn("ai", app._pages)
        self.assertIn("playground", app._pages)
        self.assertIn("diagnostics", app._pages)

        # Test switching between pages
        for page_id in ["general", "audio", "vocab", "symbols", "ai", "playground", "diagnostics"]:
            app._navigate_to(page_id)
            self.assertEqual(app._current_page, page_id)


if __name__ == "__main__":
    unittest.main()
