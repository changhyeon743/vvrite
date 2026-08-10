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


if __name__ == "__main__":
    unittest.main()
