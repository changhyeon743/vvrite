"""Keep mlx-audio's frozen model registry limited to Qwen3-ASR."""

# vvrite.mlx_runtime replaces this package's eager __init__ with a namespace at
# runtime.  These exclusions mirror that boundary for PyInstaller's static
# module graph so unused STT backends do not pull in their dependencies.
excludedimports = [
    "mlx_audio.stt.models.glmasr",
    "mlx_audio.stt.models.lasr_ctc",
    "mlx_audio.stt.models.parakeet",
    "mlx_audio.stt.models.vibevoice_asr",
    "mlx_audio.stt.models.voxtral",
    "mlx_audio.stt.models.voxtral_realtime",
    "mlx_audio.stt.models.wav2vec",
    "mlx_audio.stt.models.whisper",
]
