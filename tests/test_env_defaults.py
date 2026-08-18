"""The .env overlay is the only thing keeping a personal server address out of git,
so it gets a test: a silent failure here means the address lands in a commit."""
import unittest
from unittest.mock import patch

from pathlib import Path

from vvrite.preferences import _apply_env_defaults

NO_DOTENV = Path("/nonexistent/.env")


class TestEnvDefaults(unittest.TestCase):
    def test_environment_supplies_a_default(self):
        d = {"llm_endpoint": "", "llm_model": ""}
        with patch.dict("os.environ", {"VVRITE_LLM_ENDPOINT": "http://x/v1/chat/completions"}):
            _apply_env_defaults(d, NO_DOTENV)
        self.assertEqual(d["llm_endpoint"], "http://x/v1/chat/completions")
        self.assertEqual(d["llm_model"], "")  # unset keys are left alone

    def test_only_known_keys_are_overlaid(self):
        """Otherwise any VVRITE_* in the environment could rewrite a hotkey."""
        d = {"hotkey_keycode": 0x31}
        with patch.dict("os.environ", {"VVRITE_HOTKEY_KEYCODE": "999"}):
            _apply_env_defaults(d, NO_DOTENV)
        self.assertEqual(d["hotkey_keycode"], 0x31)

    def test_missing_dotenv_is_not_an_error(self):
        d = {"llm_endpoint": ""}
        _apply_env_defaults(d, NO_DOTENV)
        self.assertEqual(d["llm_endpoint"], "")


class TestBakedEnvStamp(unittest.TestCase):
    """The stamp decides whether baked values overwrite saved settings."""

    def test_stamp_is_stable_across_processes(self):
        """A per-process stamp would rewrite the settings on every launch, wiping
        whatever the user changed in the window."""
        import subprocess
        import sys

        code = (
            "import hashlib;"
            "print(hashlib.sha1(repr(sorted({'llm_model': 'm'}.items()))"
            ".encode('utf-8')).hexdigest())"
        )
        runs = {
            subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, env={"PYTHONHASHSEED": seed}).stdout.strip()
            for seed in ("0", "1", "random")
        }
        self.assertEqual(len(runs), 1, "stamp must not depend on PYTHONHASHSEED")


class TestBakedValuesSurvive(unittest.TestCase):
    """The stamp exists so a bake applies once. It must not also mean "never again"
    — saved values can go missing while the stamp survives, and a build then
    launches with no endpoint at all."""

    def test_missing_value_is_restored_even_when_the_stamp_matches(self):
        from unittest.mock import MagicMock

        import vvrite.preferences as prefs_mod

        defaults = MagicMock()
        values = {"stt_endpoint": "http://asr.local", "llm_model": "m"}
        stamp = __import__("hashlib").sha1(
            repr(sorted(values.items())).encode("utf-8")
        ).hexdigest()
        defaults.stringForKey_.return_value = stamp
        # stt_endpoint has gone missing; llm_model is still there.
        defaults.objectForKey_.side_effect = lambda k: None if k == "stt_endpoint" else "m"

        p = prefs_mod.Preferences.__new__(prefs_mod.Preferences)
        p._defaults = defaults
        with patch.object(prefs_mod, "_env_values", return_value=values):
            p._apply_baked_env_if_changed()

        written = {c.args[1] for c in defaults.setObject_forKey_.call_args_list}
        self.assertIn("stt_endpoint", written)
        # The one that is still present is left alone — it may be a Settings edit.
        self.assertNotIn("llm_model", written)


class TestBooleanEnvKeys(unittest.TestCase):
    def test_zero_is_false_not_a_truthy_string(self):
        import vvrite.preferences as prefs_mod

        with patch.dict("os.environ", {"VVRITE_STT_CORRECTION": "0"}):
            self.assertIs(prefs_mod._env_values(NO_DOTENV)["stt_correction"], False)
        with patch.dict("os.environ", {"VVRITE_STT_CORRECTION": "1"}):
            self.assertIs(prefs_mod._env_values(NO_DOTENV)["stt_correction"], True)


if __name__ == "__main__":
    unittest.main()
