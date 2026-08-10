"""User preferences backed by NSUserDefaults."""

import os
from pathlib import Path

from Foundation import NSBundle, NSProcessInfo, NSUserDefaults
from Quartz import (
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskShift,
)

from vvrite import APP_BUNDLE_IDENTIFIER

APP_DEFAULTS_DOMAIN = APP_BUNDLE_IDENTIFIER
_LEGACY_DEFAULTS_DOMAINS = ("com.vvrite.app", "python3", "python")

_DEFAULTS = {
    "hotkey_keycode": 0x31,  # Space
    "hotkey_modifiers": int(kCGEventFlagMaskAlternate),
    # Recording mode: "toggle" (press to start / press to stop, the default)
    # or "hold" (push-to-talk — hold the key to record, release to transcribe).
    "recording_mode": "toggle",
    # Push-to-talk hotkey, used only when recording_mode == "hold". Defaults to
    # Right Command (a modifier-only shortcut: keycode 0x36, no extra modifiers).
    "ptt_hotkey_keycode": 0x36,  # Right Command (kVK_RightCommand)
    "ptt_hotkey_modifiers": 0,
    "retract_last_dictation_enabled": False,
    "retract_hotkey_keycode": 0x06,  # Z
    "retract_hotkey_modifiers": int(kCGEventFlagMaskAlternate | kCGEventFlagMaskShift),
    # mic_device intentionally omitted — None/absent means system default
    "model_id": "mlx-community/Qwen3-ASR-1.7B-8bit",
    # Empty means on-device transcription. Set to a Qwen3-ASR server base URL
    # (e.g. "http://asr.local:8100") to transcribe there instead — audio then
    # leaves this Mac, so it is opt-in and off by default.
    "stt_endpoint": "",
    # Post-ASR correction (GER) on the remote server: an LLM fixes obvious
    # misrecognitions. Costs roughly +2s per dictation. Remote mode only.
    "stt_correction": False,
    # OpenAI-compatible chat endpoint used to clean up transcriptions. Works with
    # on-device ASR too, so the remote ASR server is not required for correction.
    "llm_endpoint": "",
    "llm_model": "",
    # Who is speaking, in one line. Without it the corrector has no domain to
    # anchor on and leaves jargon mangled — measured, not theoretical.
    "llm_context": "",
    "max_tokens": 128000,
    "launch_at_login": False,
    "sound_start": "Glass",
    "sound_stop": "Purr",
    "start_volume": 1.0,
    "stop_volume": 1.0,
    "onboarding_completed": False,
    "custom_words": "",
    "auto_update_check": True,
    "asr_language": "auto",
}


# Server addresses are personal, not project settings — hard-coding one means a
# fork carries someone's LAN hostname around forever. These read from .env (which
# is gitignored) or the environment, and only supply *defaults*: anything set in
# the Settings window still wins.
_ENV_KEYS = ("stt_endpoint", "llm_endpoint", "llm_model", "llm_context", "custom_words")


_DOTENV = Path(__file__).resolve().parent.parent / ".env"


def _apply_env_defaults(defaults: dict, dotenv: Path = _DOTENV):
    """Overlay VVRITE_* values from .env and the environment onto defaults."""
    env = {}
    try:
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass  # no .env in a packaged build, or unreadable — the environment still applies
    env.update(os.environ)

    for key in _ENV_KEYS:
        value = env.get(f"VVRITE_{key.upper()}")
        if value:
            defaults[key] = value


_apply_env_defaults(_DEFAULTS)

_PREFERENCE_KEYS = tuple(_DEFAULTS.keys()) + ("mic_device", "ui_language")

# Hard-coded constants (not user-configurable)
SAMPLE_RATE = 16000
CHANNELS = 1
CLIPBOARD_RESTORE_DELAY = 0.2


class Preferences:
    """Read/write app preferences via NSUserDefaults."""

    def __init__(self):
        self._defaults = NSUserDefaults.standardUserDefaults()
        self._defaults.registerDefaults_(_DEFAULTS)
        self._migrate_legacy_defaults_if_needed()

    def _migrate_legacy_defaults_if_needed(self):
        """Move values saved by older source runs into the current defaults domain."""
        standard_defaults = NSUserDefaults.standardUserDefaults()
        migrated = False

        for domain_name in _LEGACY_DEFAULTS_DOMAINS:
            domain = standard_defaults.persistentDomainForName_(domain_name)
            if not domain:
                continue

            for key in _PREFERENCE_KEYS:
                if self._has_persisted_value(key):
                    continue

                value = domain.objectForKey_(key)
                if value is None:
                    continue

                self._defaults.setObject_forKey_(value, key)
                migrated = True

        if migrated:
            self._defaults.synchronize()

    def _has_persisted_value(self, key: str) -> bool:
        """Return True when the current defaults domain already stores key."""
        bundle_identifier = NSBundle.mainBundle().bundleIdentifier()
        process_name = NSProcessInfo.processInfo().processName()
        candidate_domains = []

        for name in (
            bundle_identifier,
            process_name,
            process_name.lower() if process_name else None,
        ):
            if name and name not in candidate_domains:
                candidate_domains.append(name)

        for domain_name in candidate_domains:
            domain = self._defaults.persistentDomainForName_(domain_name)
            if domain and domain.objectForKey_(key) is not None:
                return True

        return False

    def _get(self, key):
        val = self._defaults.objectForKey_(key)
        if val is None:
            return _DEFAULTS.get(key)
        return val

    def _set(self, key, value):
        if value is None:
            self._defaults.removeObjectForKey_(key)
        else:
            self._defaults.setObject_forKey_(value, key)
        # Flush to disk immediately. Without this, a value written just before
        # the process exits (e.g. the last hotkey captured in onboarding before
        # the window closes) can be lost — NSUserDefaults buffers writes and the
        # process may terminate before cfprefsd flushes them.
        self._defaults.synchronize()

    @property
    def hotkey_keycode(self) -> int:
        return int(self._get("hotkey_keycode"))

    @hotkey_keycode.setter
    def hotkey_keycode(self, value: int):
        self._set("hotkey_keycode", value)

    @property
    def hotkey_modifiers(self) -> int:
        return int(self._get("hotkey_modifiers"))

    @hotkey_modifiers.setter
    def hotkey_modifiers(self, value: int):
        self._set("hotkey_modifiers", value)

    @property
    def recording_mode(self) -> str:
        return str(self._get("recording_mode"))

    @recording_mode.setter
    def recording_mode(self, value: str):
        self._set("recording_mode", value)

    @property
    def ptt_hotkey_keycode(self) -> int:
        return int(self._get("ptt_hotkey_keycode"))

    @ptt_hotkey_keycode.setter
    def ptt_hotkey_keycode(self, value: int):
        self._set("ptt_hotkey_keycode", value)

    @property
    def ptt_hotkey_modifiers(self) -> int:
        return int(self._get("ptt_hotkey_modifiers"))

    @ptt_hotkey_modifiers.setter
    def ptt_hotkey_modifiers(self, value: int):
        self._set("ptt_hotkey_modifiers", value)

    @property
    def retract_last_dictation_enabled(self) -> bool:
        return bool(self._get("retract_last_dictation_enabled"))

    @retract_last_dictation_enabled.setter
    def retract_last_dictation_enabled(self, value: bool):
        self._set("retract_last_dictation_enabled", value)

    @property
    def retract_hotkey_keycode(self) -> int:
        return int(self._get("retract_hotkey_keycode"))

    @retract_hotkey_keycode.setter
    def retract_hotkey_keycode(self, value: int):
        self._set("retract_hotkey_keycode", value)

    @property
    def retract_hotkey_modifiers(self) -> int:
        return int(self._get("retract_hotkey_modifiers"))

    @retract_hotkey_modifiers.setter
    def retract_hotkey_modifiers(self, value: int):
        self._set("retract_hotkey_modifiers", value)

    @property
    def mic_device(self) -> str | None:
        val = self._defaults.objectForKey_("mic_device")
        if val is None:
            return None
        return str(val)

    @mic_device.setter
    def mic_device(self, value: str | None):
        self._set("mic_device", value)

    @property
    def model_id(self) -> str:
        return str(self._get("model_id"))

    @model_id.setter
    def model_id(self, value: str):
        self._set("model_id", value)

    @property
    def stt_endpoint(self) -> str:
        return str(self._get("stt_endpoint") or "")

    @stt_endpoint.setter
    def stt_endpoint(self, value: str):
        self._set("stt_endpoint", value)

    @property
    def llm_endpoint(self) -> str:
        return str(self._get("llm_endpoint") or "")

    @llm_endpoint.setter
    def llm_endpoint(self, value: str):
        self._set("llm_endpoint", value)

    @property
    def llm_context(self) -> str:
        return str(self._get("llm_context") or "")

    @llm_context.setter
    def llm_context(self, value: str):
        self._set("llm_context", value)

    @property
    def llm_model(self) -> str:
        return str(self._get("llm_model"))

    @llm_model.setter
    def llm_model(self, value: str):
        self._set("llm_model", value)

    @property
    def stt_correction(self) -> bool:
        return bool(self._get("stt_correction"))

    @stt_correction.setter
    def stt_correction(self, value: bool):
        self._set("stt_correction", bool(value))

    @property
    def max_tokens(self) -> int:
        return int(self._get("max_tokens"))

    @max_tokens.setter
    def max_tokens(self, value: int):
        self._set("max_tokens", value)

    @property
    def launch_at_login(self) -> bool:
        return bool(self._get("launch_at_login"))

    @launch_at_login.setter
    def launch_at_login(self, value: bool):
        self._set("launch_at_login", value)

    @property
    def sound_start(self) -> str:
        return str(self._get("sound_start"))

    @sound_start.setter
    def sound_start(self, value: str):
        self._set("sound_start", value)

    @property
    def sound_stop(self) -> str:
        return str(self._get("sound_stop"))

    @sound_stop.setter
    def sound_stop(self, value: str):
        self._set("sound_stop", value)

    @property
    def start_volume(self) -> float:
        return float(self._get("start_volume"))

    @start_volume.setter
    def start_volume(self, value: float):
        self._set("start_volume", value)

    @property
    def stop_volume(self) -> float:
        return float(self._get("stop_volume"))

    @stop_volume.setter
    def stop_volume(self, value: float):
        self._set("stop_volume", value)

    @property
    def custom_words(self) -> str:
        return str(self._get("custom_words"))

    @custom_words.setter
    def custom_words(self, value: str):
        self._set("custom_words", value)

    @property
    def onboarding_completed(self) -> bool:
        return bool(self._get("onboarding_completed"))

    @onboarding_completed.setter
    def onboarding_completed(self, value: bool):
        self._set("onboarding_completed", value)

    @property
    def auto_update_check(self) -> bool:
        return bool(self._get("auto_update_check"))

    @auto_update_check.setter
    def auto_update_check(self, value: bool):
        self._set("auto_update_check", value)

    @property
    def ui_language(self) -> str | None:
        val = self._defaults.objectForKey_("ui_language")
        if val is None:
            return None
        return str(val)

    @ui_language.setter
    def ui_language(self, value: str | None):
        self._set("ui_language", value)

    @property
    def asr_language(self) -> str:
        return str(self._get("asr_language"))

    @asr_language.setter
    def asr_language(self, value: str):
        self._set("asr_language", value)
