"""Tests for preferences module."""
import unittest
from unittest.mock import patch

from Foundation import NSUserDefaults

from vvrite.preferences import APP_DEFAULTS_DOMAIN

_TEST_KEYS = [
    "hotkey_keycode",
    "hotkey_modifiers",
    "recording_mode",
    "ptt_hotkey_keycode",
    "ptt_hotkey_modifiers",
    "retract_last_dictation_enabled",
    "retract_hotkey_keycode",
    "retract_hotkey_modifiers",
    "mic_device",
    "model_id",
    "max_tokens",
    "launch_at_login",
    "sound_start",
    "sound_stop",
    "start_volume",
    "stop_volume",
    "onboarding_completed",
    "custom_words",
    "auto_update_check",
    "ui_language",
    "asr_language",
]
_LEGACY_DOMAINS = ["com.vvrite.app", "python3", "python", "Python"]


class TestPreferences(unittest.TestCase):
    """A developer checkout may carry a .env, whose values are written through to
    the saved settings on construction. These tests are about the defaults and the
    legacy migration, so the overlay is switched off rather than left to depend on
    whatever the machine happens to have configured."""

    def setUp(self):
        import vvrite.preferences as prefs_mod

        self._no_env = patch.object(prefs_mod, "_env_values", return_value={})
        self._no_env.start()
        self.addCleanup(self._no_env.stop)
        # _DEFAULTS is overlaid at import time too, so clearing the write-through
        # alone would still leave a .env value sitting in the registered defaults.
        blank = {k: "" for k in prefs_mod._ENV_KEYS if k != "model_id"}
        self._no_env_defaults = patch.dict(prefs_mod._DEFAULTS, blank)
        self._no_env_defaults.start()
        self.addCleanup(self._no_env_defaults.stop)
        defaults = NSUserDefaults.standardUserDefaults()
        for key in _TEST_KEYS:
            defaults.removeObjectForKey_(key)
        defaults.removePersistentDomainForName_(APP_DEFAULTS_DOMAIN)
        for domain in _LEGACY_DOMAINS:
            defaults.removePersistentDomainForName_(domain)

    def tearDown(self):
        defaults = NSUserDefaults.standardUserDefaults()
        for key in _TEST_KEYS:
            defaults.removeObjectForKey_(key)
        defaults.removePersistentDomainForName_(APP_DEFAULTS_DOMAIN)
        for domain in _LEGACY_DOMAINS:
            defaults.removePersistentDomainForName_(domain)

    def test_default_hotkey_keycode(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.hotkey_keycode, 0x31)

    def test_default_hotkey_modifiers(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        from Quartz import kCGEventFlagMaskAlternate
        expected = int(kCGEventFlagMaskAlternate)
        self.assertEqual(prefs.hotkey_modifiers, expected)

    def test_default_mic_device_is_none(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertIsNone(prefs.mic_device)

    def test_default_retract_last_dictation_enabled(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertFalse(prefs.retract_last_dictation_enabled)

    def test_default_retract_hotkey(self):
        from vvrite.preferences import Preferences
        from Quartz import kCGEventFlagMaskAlternate, kCGEventFlagMaskShift

        prefs = Preferences()
        self.assertEqual(prefs.retract_hotkey_keycode, 0x06)
        self.assertEqual(
            prefs.retract_hotkey_modifiers,
            int(kCGEventFlagMaskAlternate | kCGEventFlagMaskShift),
        )

    def test_default_recording_mode_is_toggle(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.recording_mode, "toggle")

    def test_set_recording_mode(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.recording_mode = "hold"
        self.assertEqual(prefs.recording_mode, "hold")
        prefs.recording_mode = "toggle"
        self.assertEqual(prefs.recording_mode, "toggle")

    def test_default_ptt_hotkey(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.ptt_hotkey_keycode, 0x36)  # Right Command
        self.assertEqual(prefs.ptt_hotkey_modifiers, 0)

    def test_set_ptt_hotkey(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.ptt_hotkey_keycode = 0x3D  # Right Option
        prefs.ptt_hotkey_modifiers = 0
        self.assertEqual(prefs.ptt_hotkey_keycode, 0x3D)
        self.assertEqual(prefs.ptt_hotkey_modifiers, 0)

    def test_recording_mode_persists_across_instances(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.recording_mode = "hold"
        self.assertEqual(Preferences().recording_mode, "hold")

    def test_default_max_tokens(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.max_tokens, 128000)

    def test_default_model_id(self):
        """0.6B, not 1.7B: twice as fast on Korean at the same character accuracy,
        and 1.4GB less resident. VVRITE_MODEL_ID overrides it."""
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.model_id, "mlx-community/Qwen3-ASR-0.6B-8bit")

    def test_default_sounds(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.sound_start, "Glass")
        self.assertEqual(prefs.sound_stop, "Purr")

    def test_default_launch_at_login(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertFalse(prefs.launch_at_login)

    def test_set_and_get_hotkey_keycode(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.hotkey_keycode = 0x00  # 'A'
        self.assertEqual(prefs.hotkey_keycode, 0x00)

    def test_set_and_get_mic_device(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.mic_device = "Blue Yeti"
        self.assertEqual(prefs.mic_device, "Blue Yeti")

    def test_set_retract_preferences(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.retract_last_dictation_enabled = True
        prefs.retract_hotkey_keycode = 0x06  # Z
        prefs.retract_hotkey_modifiers = 1 << 20

        self.assertTrue(prefs.retract_last_dictation_enabled)
        self.assertEqual(prefs.retract_hotkey_keycode, 0x06)
        self.assertEqual(prefs.retract_hotkey_modifiers, 1 << 20)

    def test_set_mic_device_to_none(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.mic_device = "Blue Yeti"
        prefs.mic_device = None
        self.assertIsNone(prefs.mic_device)

    def test_default_onboarding_completed(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertFalse(prefs.onboarding_completed)

    def test_set_onboarding_completed(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.onboarding_completed = True
        self.assertTrue(prefs.onboarding_completed)

    def test_default_custom_words(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.custom_words, "")

    def test_set_custom_words(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.custom_words = "MLX, Qwen, vvrite"
        self.assertEqual(prefs.custom_words, "MLX, Qwen, vvrite")

    def test_custom_words_persist_across_instances(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.custom_words = "MLX, Qwen, vvrite"

        reloaded = Preferences()
        self.assertEqual(reloaded.custom_words, "MLX, Qwen, vvrite")

    def test_migrates_custom_words_from_legacy_python_domain(self):
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setPersistentDomain_forName_(
            {"custom_words": "legacy term"}, "python3"
        )

        from vvrite.preferences import Preferences

        prefs = Preferences()
        self.assertEqual(prefs.custom_words, "legacy term")

    def test_migrates_custom_words_from_old_bundle_identifier(self):
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setPersistentDomain_forName_(
            {"custom_words": "old bundle term"}, "com.vvrite.app"
        )

        from vvrite.preferences import Preferences

        prefs = Preferences()
        self.assertEqual(prefs.custom_words, "old bundle term")

    def test_default_auto_update_check(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        # Off in this fork: it is built locally and has no release feed, and the
        # inherited upstream feed offered someone else's build as an update.
        self.assertFalse(prefs.auto_update_check)

    def test_set_auto_update_check(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.auto_update_check = False
        self.assertFalse(prefs.auto_update_check)

    def test_default_start_volume(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.start_volume, 1.0)

    def test_default_stop_volume(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.stop_volume, 1.0)

    def test_set_start_volume(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.start_volume = 0.5
        self.assertAlmostEqual(prefs.start_volume, 0.5)

    def test_set_stop_volume(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.stop_volume = 0.3
        self.assertAlmostEqual(prefs.stop_volume, 0.3)

    def test_default_ui_language_is_none(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertIsNone(prefs.ui_language)

    def test_set_ui_language(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.ui_language = "ko"
        self.assertEqual(prefs.ui_language, "ko")

    def test_set_ui_language_to_none(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.ui_language = "ko"
        prefs.ui_language = None
        self.assertIsNone(prefs.ui_language)

    def test_default_asr_language(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        self.assertEqual(prefs.asr_language, "auto")

    def test_set_asr_language(self):
        from vvrite.preferences import Preferences
        prefs = Preferences()
        prefs.asr_language = "ko"
        self.assertEqual(prefs.asr_language, "ko")


if __name__ == "__main__":
    unittest.main()
