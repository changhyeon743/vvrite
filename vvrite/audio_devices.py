"""Helpers for enumerating and resolving audio input devices."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import sounddevice as sd

from vvrite.preferences import CHANNELS


@dataclass(frozen=True)
class AudioInputDevice:
    device_id: str
    name: str
    display_name: str
    index: int
    hostapi_name: str
    default_samplerate: int


def make_device_id(name: str, hostapi_name: str) -> str:
    if not hostapi_name:
        return name
    return f"{hostapi_name}::{name}"


def _query_devices():
    return list(sd.query_devices())


def _query_hostapis():
    return list(sd.query_hostapis())


def refresh_portaudio_device_list():
    """Force PortAudio to rebuild its device list after hot-plug changes."""
    invalidate_device_cache()
    terminate = getattr(sd, "_terminate", None)
    initialize = getattr(sd, "_initialize", None)
    if not callable(terminate) or not callable(initialize):
        return

    try:
        terminate()
    except Exception:
        # Best effort only; a fresh initialize still helps recover.
        pass

    initialize()


def _get_default_input_index() -> int | None:
    default_device = getattr(sd.default, "device", None)
    if isinstance(default_device, (list, tuple)) and default_device:
        try:
            index = int(default_device[0])
        except (TypeError, ValueError):
            index = -1
        if index >= 0:
            return index

    if isinstance(default_device, int) and default_device >= 0:
        return int(default_device)

    for hostapi in _query_hostapis():
        index = int(hostapi.get("default_input_device", -1))
        if index >= 0:
            return index
    return None


def _hostapi_name(device: dict, hostapis: list[dict]) -> str:
    index = int(device.get("hostapi", -1))
    if 0 <= index < len(hostapis):
        return str(hostapis[index].get("name", ""))
    return ""


def _supports_input(index: int, device: dict) -> bool:
    max_input_channels = int(device.get("max_input_channels", 0) or 0)
    if max_input_channels < CHANNELS:
        return False

    samplerate = float(device.get("default_samplerate", 0) or 0)
    if samplerate <= 0:
        return False

    try:
        sd.check_input_settings(
            device=index,
            samplerate=samplerate,
            channels=CHANNELS,
            dtype="int16",
        )
        return True
    except Exception:
        return False


def list_input_devices(refresh: bool = False) -> list[AudioInputDevice]:
    if refresh:
        refresh_portaudio_device_list()

    devices = _query_devices()
    hostapis = _query_hostapis()
    default_input_index = _get_default_input_index()

    usable_devices: list[tuple[int, dict, str]] = []
    for index, device in enumerate(devices):
        if not _supports_input(index, device):
            continue
        usable_devices.append((index, device, _hostapi_name(device, hostapis)))

    name_counts = Counter(str(device.get("name", "")) for _, device, _ in usable_devices)

    result = []
    for index, device, hostapi_name in usable_devices:
        name = str(device.get("name", f"Input {index}"))
        display_name = name
        if name_counts[name] > 1:
            suffix = hostapi_name or f"#{index}"
            display_name = f"{name} ({suffix})"
        if index == default_input_index:
            display_name = f"{display_name} [Default]"

        samplerate = int(round(float(device.get("default_samplerate", 0) or 0)))
        result.append(
            AudioInputDevice(
                device_id=make_device_id(name, hostapi_name),
                name=name,
                display_name=display_name,
                index=index,
                hostapi_name=hostapi_name,
                default_samplerate=samplerate,
            )
        )

    return result


def get_default_input_device(
    devices: list[AudioInputDevice] | None = None,
) -> AudioInputDevice | None:
    if devices is None:
        devices = list_input_devices()

    default_input_index = _get_default_input_index()
    if default_input_index is None:
        return None

    for device in devices:
        if device.index == default_input_index:
            return device
    return None


def resolve_input_device(
    selection: str | None,
    devices: list[AudioInputDevice] | None = None,
) -> AudioInputDevice | None:
    if not selection:
        return None

    if devices is None:
        devices = list_input_devices()

    for device in devices:
        if selection == device.device_id:
            return device

    # Legacy preference values stored the plain device name.
    for device in devices:
        if selection == device.name:
            return device

    return None


# Resolving a device means asking PortAudio to enumerate every input on the
# machine, which measured 204ms — paid on every single dictation, before the mic
# stream even opens, so it came straight off the front of the recording. Devices
# do not change between two presses of a hotkey, so remember the answer.
_preferred_cache: dict = {}


def invalidate_device_cache():
    """Forget the resolved device. Called when opening the stream fails, which is
    how an unplugged mic announces itself, and when the user picks a new one."""
    _preferred_cache.clear()


def get_preferred_input_device(
    selection: str | None,
    devices: list[AudioInputDevice] | None = None,
) -> AudioInputDevice | None:
    if devices is None:
        if selection in _preferred_cache:
            return _preferred_cache[selection]
        devices = list_input_devices()
        resolved = _resolve_preferred(selection, devices)
        _preferred_cache[selection] = resolved
        return resolved
    return _resolve_preferred(selection, devices)


def _resolve_preferred(
    selection: str | None,
    devices: list[AudioInputDevice],
) -> AudioInputDevice | None:

    selected = resolve_input_device(selection, devices)
    if selected is not None:
        return selected

    default_device = get_default_input_device(devices)
    if default_device is not None:
        return default_device

    if devices:
        return devices[0]

    return None
