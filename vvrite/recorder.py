"""Microphone recording using sounddevice."""

import os
import tempfile
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

from vvrite.audio_devices import invalidate_device_cache, get_preferred_input_device, refresh_portaudio_device_list
from vvrite.preferences import CHANNELS


def _compute_rms(data: np.ndarray) -> float:
    """Compute RMS level normalized to 0.0-1.0 range for int16 audio."""
    float_data = data.astype(np.float64)
    rms = np.sqrt(np.mean(float_data ** 2))
    return min(rms / 32768.0, 1.0)


class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._stream_samplerate = None
        self._level_callback: Callable[[float], None] | None = None

    def start(self, device=None, level_callback=None):
        """Start recording from the specified microphone.

        Args:
            device: Saved device identifier or None for the system default.
            level_callback: Called with RMS level (0.0-1.0) per audio chunk.
        """
        self._frames = []
        self._stream_samplerate = None
        self._level_callback = level_callback

        last_error = None
        for refresh in (False, True):
            if refresh:
                refresh_portaudio_device_list()

            preferred_device = get_preferred_input_device(device)
            if preferred_device is None:
                continue

            try:
                self._stream_samplerate = preferred_device.default_samplerate
                self._stream = sd.InputStream(
                    samplerate=self._stream_samplerate,
                    channels=CHANNELS,
                    dtype="int16",
                    device=preferred_device.index,
                    callback=self._callback,
                )
                self._stream.start()
                return
            except Exception as exc:
                last_error = exc
                self._stream = None
                self._stream_samplerate = None

        raise RuntimeError("No usable microphone input device found") from last_error

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())
        if self._level_callback is not None:
            level = _compute_rms(indata)
            self._level_callback(level)

    def stop(self) -> str | None:
        """Stop recording and return path to the raw WAV file."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._level_callback = None

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(path, audio, self._stream_samplerate, subtype="PCM_16")
        return path
