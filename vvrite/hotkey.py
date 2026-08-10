"""Global hotkey via CGEvent tap."""

import threading

import Quartz
from Quartz import (
    CGEventTapCreate,
    CGEventMaskBit,
    CGEventGetIntegerValueField,
    CGEventGetFlags,
    CGEventTapEnable,
    CGEventTapIsEnabled,
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventFlagsChanged,
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput,
    kCGKeyboardEventKeycode,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCFRunLoopDefaultMode,
)
from Foundation import NSLog, NSTimer

from vvrite.preferences import Preferences

MODIFIER_MASK = (
    kCGEventFlagMaskCommand | kCGEventFlagMaskShift
    | Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
)

# Virtual keycode of a lone modifier key -> the device-dependent flag bit that
# is set in the event flags while that specific (left/right) key is held. These
# IOKit NX_DEVICE*KEYMASK values are not exported by PyObjC, so they are
# hard-coded. Used to detect press vs release of a modifier-only push-to-talk
# key on flagsChanged events (where left/right cannot be told apart from the
# device-independent flags alone).
MODIFIER_DEVICE_BIT = {
    0x37: 0x00000008,  # Left Command
    0x36: 0x00000010,  # Right Command
    0x38: 0x00000002,  # Left Shift
    0x3C: 0x00000004,  # Right Shift
    0x3A: 0x00000020,  # Left Option
    0x3D: 0x00000040,  # Right Option
    0x3B: 0x00000001,  # Left Control
    0x3E: 0x00002000,  # Right Control
    0x3F: 0x00800000,  # Fn / Globe (no left/right variant)
}


class HotkeyManager:
    """Manages global hotkey via CGEvent tap. Not an NSObject."""

    def __init__(self, delegate):
        self._delegate = delegate
        self._prefs = Preferences()
        self._tap = None
        # Keycode that is currently holding a push-to-talk recording open
        # (None when not in a hold). Single source of truth for an active hold.
        self._ptt_active_keycode = None
        self._watchdog = None
        self._setup_tap()
        self._start_watchdog()

    def _setup_tap(self):
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            # Always subscribe key-up and flags-changed too, so push-to-talk
            # (including modifier-only keys) works without rebuilding the tap
            # when the recording mode is toggled in Settings.
            CGEventMaskBit(kCGEventKeyDown)
            | CGEventMaskBit(kCGEventKeyUp)
            | CGEventMaskBit(kCGEventFlagsChanged),
            self._callback,
            None,
        )

        if self._tap is None:
            NSLog("Failed to create CGEvent tap — accessibility not granted")
            return

        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopDefaultMode)
        CGEventTapEnable(self._tap, True)

    def _start_watchdog(self):
        """Re-enable the tap if macOS turned it off without telling us.

        _callback re-enables on the disable *event*, but that only helps when the
        tap still delivers events. A tap killed under load or by secure input can
        go silent, and then the hotkey is dead until the app restarts — which is
        exactly the "push-to-talk randomly stops working" symptom.
        """
        if self._watchdog is not None:
            return
        self._watchdog = (
            NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                2.0, True, lambda timer: self._check_tap()
            )
        )

    def _check_tap(self):
        if self._tap is None:
            self._setup_tap()
            return
        if not CGEventTapIsEnabled(self._tap):
            NSLog("vvrite: event tap was disabled — re-enabling")
            CGEventTapEnable(self._tap, True)

    def _callback(self, proxy, event_type, event, refcon):
        # macOS disables the tap on timeout AND on secure input (e.g. a password
        # field steals the event stream). Re-enable on both, otherwise the global
        # hotkey silently dies until the app is restarted.
        if event_type in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
            if self._tap:
                CGEventTapEnable(self._tap, True)
            # A key-up may have been dropped while the tap was disabled; drop
            # any half-open hold so the next press re-arms cleanly.
            self._ptt_active_keycode = None
            return event

        mode = "hold" if self._prefs.recording_mode == "hold" else "toggle"

        # --- Push-to-talk (hold) mode ---
        if mode == "hold":
            ptt_keycode = self._prefs.ptt_hotkey_keycode
            ptt_mods = self._prefs.ptt_hotkey_modifiers
            modifier_only = ptt_keycode in MODIFIER_DEVICE_BIT

            if modifier_only and event_type == kCGEventFlagsChanged:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                if keycode == ptt_keycode:
                    pressed = bool(CGEventGetFlags(event) & MODIFIER_DEVICE_BIT[ptt_keycode])
                    if pressed and self._ptt_active_keycode is None:
                        self._ptt_active_keycode = keycode
                        threading.Thread(
                            target=self._delegate.startRecordingPTT, daemon=True
                        ).start()
                    elif not pressed and self._ptt_active_keycode == keycode:
                        self._ptt_active_keycode = None
                        threading.Thread(
                            target=self._delegate.stopRecordingPTT, daemon=True
                        ).start()
                # Never swallow flagsChanged — that would break the modifier
                # for every other app system-wide.
                return event

            if not modifier_only and event_type == kCGEventKeyDown:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                flags = CGEventGetFlags(event)
                if keycode == ptt_keycode and (flags & MODIFIER_MASK) == ptt_mods:
                    # Only the first key-down starts; ignore the auto-repeat
                    # flood while the key stays held, but keep swallowing it.
                    if self._ptt_active_keycode is None:
                        self._ptt_active_keycode = keycode
                        threading.Thread(
                            target=self._delegate.startRecordingPTT, daemon=True
                        ).start()
                    return None

            if not modifier_only and event_type == kCGEventKeyUp:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                # Match on the tracked keycode only — on key-up the modifier
                # flags may already be cleared, so flag matching is unreliable.
                if self._ptt_active_keycode == keycode:
                    self._ptt_active_keycode = None
                    threading.Thread(
                        target=self._delegate.stopRecordingPTT, daemon=True
                    ).start()
                    return None

        # --- Key-down handling shared by both modes (toggle hotkey, retract, ESC) ---
        if event_type == kCGEventKeyDown:
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            flags = CGEventGetFlags(event)

            if mode == "toggle":
                target_keycode = self._prefs.hotkey_keycode
                target_mods = self._prefs.hotkey_modifiers
                if keycode == target_keycode and (flags & MODIFIER_MASK) == target_mods:
                    threading.Thread(
                        target=self._delegate.toggleRecording,
                        daemon=True,
                    ).start()
                    return None

            retract_enabled = self._prefs.retract_last_dictation_enabled
            retract_keycode = self._prefs.retract_hotkey_keycode
            retract_mods = self._prefs.retract_hotkey_modifiers

            if (
                retract_enabled
                and keycode == retract_keycode
                and (flags & MODIFIER_MASK) == retract_mods
            ):
                threading.Thread(
                    target=self._delegate.retractLastDictation,
                    daemon=True,
                ).start()
                return None

            # ESC (0x35) with no modifiers cancels recording
            if keycode == 0x35 and (flags & MODIFIER_MASK) == 0 and self._delegate._recording:
                threading.Thread(
                    target=self._delegate.cancelRecording,
                    daemon=True,
                ).start()
                return None

        return event
