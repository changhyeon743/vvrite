"""Tests for the global hotkey callback, especially push-to-talk dispatch."""

import unittest
from unittest.mock import patch

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventSetFlags,
    CGEventSetIntegerValueField,
    kCGKeyboardEventKeycode,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventFlagsChanged,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
)

from vvrite.hotkey import HotkeyManager, MODIFIER_DEVICE_BIT


class _FakePrefs:
    def __init__(self, **kw):
        self.recording_mode = "toggle"
        self.hotkey_keycode = 0x31  # Space
        self.hotkey_modifiers = int(kCGEventFlagMaskAlternate)
        self.ptt_hotkey_keycode = 0x36  # Right Command
        self.ptt_hotkey_modifiers = 0
        self.retract_last_dictation_enabled = False
        self.retract_hotkey_keycode = 0x06
        self.retract_hotkey_modifiers = 0
        self.__dict__.update(kw)


class _FakeDelegate:
    def __init__(self):
        self.calls = []
        self._recording = False

    def startRecordingPTT(self):
        self.calls.append("start")
        self._recording = True

    def stopRecordingPTT(self):
        self.calls.append("stop")
        self._recording = False

    def toggleRecording(self):
        self.calls.append("toggle")

    def retractLastDictation(self):
        self.calls.append("retract")

    def cancelRecording(self):
        self.calls.append("cancel")


class _SyncThread:
    """Stand-in for threading.Thread that runs the target synchronously."""

    def __init__(self, target=None, daemon=None, **kw):
        self._target = target

    def start(self):
        if self._target is not None:
            self._target()


def _make_event(keycode, flags):
    ev = CGEventCreateKeyboardEvent(None, keycode, True)
    if ev is None:
        return None
    CGEventSetIntegerValueField(ev, kCGKeyboardEventKeycode, keycode)
    CGEventSetFlags(ev, flags)
    return ev


class HotkeyCallbackTest(unittest.TestCase):
    def setUp(self):
        with patch.object(HotkeyManager, "_setup_tap", lambda self: None):
            self.mgr = HotkeyManager(_FakeDelegate())
        self.mgr._prefs = _FakePrefs()
        self.delegate = self.mgr._delegate

    def _fire(self, event_type, keycode, flags):
        ev = _make_event(keycode, flags)
        if ev is None:
            self.skipTest("CGEventCreateKeyboardEvent unavailable in this environment")
        with patch("vvrite.hotkey.threading.Thread", _SyncThread):
            return self.mgr._callback(None, event_type, ev, None)

    def test_modifier_device_bits(self):
        self.assertEqual(MODIFIER_DEVICE_BIT[0x36], 0x10)  # Right Command
        self.assertEqual(MODIFIER_DEVICE_BIT[0x37], 0x08)  # Left Command
        self.assertEqual(MODIFIER_DEVICE_BIT[0x3D], 0x40)  # Right Option

    def test_modifier_only_ptt_press_then_release(self):
        self.mgr._prefs.recording_mode = "hold"
        # Right Command pressed (device bit 0x10 set)
        self._fire(kCGEventFlagsChanged, 0x36, 0x10 | int(kCGEventFlagMaskCommand))
        self.assertEqual(self.delegate.calls, ["start"])
        self.assertEqual(self.mgr._ptt_active_keycode, 0x36)
        # Right Command released (device bit cleared)
        self._fire(kCGEventFlagsChanged, 0x36, 0)
        self.assertEqual(self.delegate.calls, ["start", "stop"])
        self.assertIsNone(self.mgr._ptt_active_keycode)

    def test_modifier_only_flagschanged_never_swallowed(self):
        self.mgr._prefs.recording_mode = "hold"
        ev = _make_event(0x36, 0x10 | int(kCGEventFlagMaskCommand))
        if ev is None:
            self.skipTest("CGEventCreateKeyboardEvent unavailable")
        with patch("vvrite.hotkey.threading.Thread", _SyncThread):
            result = self.mgr._callback(None, kCGEventFlagsChanged, ev, None)
        # flagsChanged must pass through (return the event), never be swallowed.
        self.assertIsNotNone(result)

    def test_regular_key_ptt_autorepeat_starts_once(self):
        self.mgr._prefs.recording_mode = "hold"
        self.mgr._prefs.ptt_hotkey_keycode = 0x0F  # R
        self.mgr._prefs.ptt_hotkey_modifiers = int(kCGEventFlagMaskAlternate)
        mods = int(kCGEventFlagMaskAlternate)
        # First key-down starts; auto-repeat key-downs must not re-start.
        r1 = self._fire(kCGEventKeyDown, 0x0F, mods)
        r2 = self._fire(kCGEventKeyDown, 0x0F, mods)
        r3 = self._fire(kCGEventKeyDown, 0x0F, mods)
        self.assertEqual(self.delegate.calls, ["start"])
        self.assertIsNone(r1)  # owned key swallowed
        self.assertIsNone(r2)
        self.assertIsNone(r3)
        # Release stops once.
        ru = self._fire(kCGEventKeyUp, 0x0F, 0)
        self.assertEqual(self.delegate.calls, ["start", "stop"])
        self.assertIsNone(ru)
        self.assertIsNone(self.mgr._ptt_active_keycode)

    def test_toggle_mode_dispatches_toggle(self):
        self.mgr._prefs.recording_mode = "toggle"
        self._fire(kCGEventKeyDown, 0x31, int(kCGEventFlagMaskAlternate))
        self.assertEqual(self.delegate.calls, ["toggle"])

    def test_toggle_hotkey_inert_in_hold_mode(self):
        self.mgr._prefs.recording_mode = "hold"
        # Pressing the toggle hotkey (Option+Space) must do nothing in hold mode.
        self._fire(kCGEventKeyDown, 0x31, int(kCGEventFlagMaskAlternate))
        self.assertEqual(self.delegate.calls, [])

    def test_esc_cancels_while_recording_in_hold_mode(self):
        self.mgr._prefs.recording_mode = "hold"
        self.delegate._recording = True
        self._fire(kCGEventKeyDown, 0x35, 0)  # ESC, no modifiers
        self.assertEqual(self.delegate.calls, ["cancel"])

    def test_tap_disabled_resets_active_keycode(self):
        from Quartz import kCGEventTapDisabledByTimeout
        self.mgr._ptt_active_keycode = 0x36
        ev = _make_event(0, 0)
        if ev is None:
            self.skipTest("CGEventCreateKeyboardEvent unavailable")
        self.mgr._callback(None, kCGEventTapDisabledByTimeout, ev, None)
        self.assertIsNone(self.mgr._ptt_active_keycode)


if __name__ == "__main__":
    unittest.main()
