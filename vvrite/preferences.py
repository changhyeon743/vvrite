"""User preferences backed by NSUserDefaults."""

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
    "retract_last_dictation_enabled": False,
    "retract_hotkey_keycode": 0x06,  # Z
    "retract_hotkey_modifiers": int(kCGEventFlagMaskAlternate | kCGEventFlagMaskShift),
    # mic_device intentionally omitted — None/absent means system default
    "model_id": "mlx-community/Qwen3-ASR-1.7B-8bit",
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

_PREFERENCE_KEYS = tuple(_DEFAULTS.keys()) + ("mic_device", "ui_language")

# Hard-coded constants (not user-configurable)
SAMPLE_RATE = 16000
CHANNELS = 1
CLIPBOARD_RESTORE_DELAY = 0.2
FFMPEG_ARGS = ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]


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
