"""Tests for shortcut formatting and active-shortcut selection."""

import types
import unittest

from Quartz import (
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskCommand,
)

from vvrite.widgets import format_shortcut, active_shortcut


class TestFormatShortcut(unittest.TestCase):
    def test_regular_chord(self):
        self.assertEqual(format_shortcut(0x31, int(kCGEventFlagMaskAlternate)), "⌥Space")

    def test_regular_chord_multiple_modifiers(self):
        mods = int(kCGEventFlagMaskAlternate | kCGEventFlagMaskShift)
        self.assertEqual(format_shortcut(0x06, mods), "⌥⇧Z")

    def test_modifier_only_right_command(self):
        self.assertEqual(format_shortcut(0x36, 0), "Right ⌘")

    def test_modifier_only_left_command(self):
        self.assertEqual(format_shortcut(0x37, 0), "Left ⌘")

    def test_modifier_only_right_option(self):
        self.assertEqual(format_shortcut(0x3D, 0), "Right ⌥")

    def test_modifier_only_fn(self):
        self.assertEqual(format_shortcut(0x3F, 0), "fn")

    def test_unknown_keycode_falls_back_to_hex(self):
        self.assertEqual(format_shortcut(0x7A, 0), "0x7A")


class TestActiveShortcut(unittest.TestCase):
    def _prefs(self, mode):
        return types.SimpleNamespace(
            recording_mode=mode,
            hotkey_keycode=0x31,
            hotkey_modifiers=int(kCGEventFlagMaskAlternate),
            ptt_hotkey_keycode=0x36,
            ptt_hotkey_modifiers=0,
        )

    def test_toggle_mode_uses_main_hotkey(self):
        self.assertEqual(
            active_shortcut(self._prefs("toggle")),
            (0x31, int(kCGEventFlagMaskAlternate)),
        )

    def test_hold_mode_uses_ptt_hotkey(self):
        self.assertEqual(active_shortcut(self._prefs("hold")), (0x36, 0))


if __name__ == "__main__":
    unittest.main()
