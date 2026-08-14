"""PyInstaller spec for vvrite macOS app."""
import os
import sys

ROOT_DIR = os.path.abspath(os.getcwd())
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PyInstaller.utils.hooks import collect_submodules
from vvrite import APP_BUNDLE_IDENTIFIER, __version__

block_cipher = None

# This fork's own feed, not upstream's. Pointed at shaircast, Sparkle offered
# upstream's 1.0.9 as an update to a build that shares only its version number —
# accepting it would have replaced every change in this fork.
SPARKLE_APPCAST_URL = os.environ.get(
    "SPARKLE_APPCAST_URL",
    "https://github.com/changhyeon743/vvrite/releases/latest/download/appcast.xml",
)
SPARKLE_PUBLIC_ED_KEY = os.environ.get("SPARKLE_PUBLIC_ED_KEY", "").strip()

# Bake .env into the bundle so a fresh install already knows your endpoints.
# It ships INSIDE the .app, so anyone you hand the build to can read it — hence the
# loud notice and the opt-out. Release builds run from a clean checkout, where the
# file is gitignored and therefore absent.
BAKE_ENV = os.environ.get("VVRITE_BAKE_ENV", "1") != "0"
env_datas = []
if BAKE_ENV and os.path.exists(os.path.join(ROOT_DIR, ".env")):
    env_datas.append((os.path.join(ROOT_DIR, ".env"), "."))
    print("\n▸ Baking .env into the bundle — do not distribute this build.")
    print("  Set VVRITE_BAKE_ENV=0 to build without it.\n")

info_plist = {
    "CFBundleName": "vvrite",
    "CFBundleShortVersionString": __version__,  # sourced from vvrite/__init__.__version__
    "CFBundleVersion": "9",  # monotonic build number; bump each release
    "LSUIElement": True,
    "NSMicrophoneUsageDescription": (
        "vvrite needs microphone access to record and transcribe your speech."
    ),
    # Only requested when the screen-context option is turned on: vvrite reads the
    # frontmost window so the corrector can spell on-screen names correctly.
    "NSScreenCaptureUsageDescription": (
        "vvrite reads text from the window in front while you dictate, so names "
        "already on screen are spelled correctly."
    ),
    "NSHighResolutionCapable": True,
    "NSSupportsAutomaticTermination": False,
    "NSSupportsSuddenTermination": False,
    "SUFeedURL": SPARKLE_APPCAST_URL,
    # Off by default: this fork is built locally, so there is nothing for Sparkle
    # to find, and a background check that silently resolves to someone else's
    # release is worse than no check at all.
    "SUEnableAutomaticChecks": False,
    "SUScheduledCheckInterval": 86400,
}

if SPARKLE_PUBLIC_ED_KEY:
    info_plist["SUPublicEDKey"] = SPARKLE_PUBLIC_ED_KEY

# site.getsitepackages(), not os.__file__: inside a venv the latter points at the
# base interpreter's stdlib, so the data files below would be looked up in the
# wrong prefix and the build would fail on a clean build environment.
import site

site_packages = next(
    (p for p in site.getsitepackages() if p.endswith("site-packages")),
    os.path.join(os.path.dirname(os.__file__), "site-packages"),
)

# PyObjC bridge modules need all submodules collected
pyobjc_hiddenimports = (
    collect_submodules("objc")
    + collect_submodules("AppKit")
    + collect_submodules("Foundation")
    + collect_submodules("Quartz")
    + collect_submodules("ApplicationServices")
    + collect_submodules("AVFoundation")
    + collect_submodules("Vision")
    + collect_submodules("ServiceManagement")
)

a = Analysis(
    ["vvrite/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        # soundfile needs libsndfile
        (os.path.join(site_packages, "_soundfile_data"), "_soundfile_data"),
        # MLX Metal shaders and native libs
        (os.path.join(site_packages, "mlx", "lib"), os.path.join("mlx", "lib")),
    ] + env_datas,
    hiddenimports=pyobjc_hiddenimports + [
        # Locale modules (dynamically imported by vvrite.locales)
        *collect_submodules("vvrite.locales"),
        # MLX (namespace package — must be explicit)
        "mlx",
        "mlx._reprlib_fix",
        "mlx.core",
        "mlx.nn",
        "mlx.optimizers",
        "mlx.utils",
        # MLX ecosystem
        "mlx_lm",
        "mlx_audio",
        "mlx_audio.stt",
        "mlx_audio.stt.models",
        "mlx_audio.stt.models.qwen3_asr",
        # WAV decode + 16k mono resample backend, lazy-imported by mlx_audio
        # at transcribe time (replaces the bundled ffmpeg normalization step)
        "mlx_audio.audio_io",
        "miniaudio",
        # Transformers
        "transformers",
        "tokenizers",
        # Audio
        "sounddevice",
        "soundfile",
        # Other
        "huggingface_hub",
        "safetensors",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        # Heavy packages not needed (we use mlx, not torch)
        "torch",
        "torchaudio",
        "torchvision",
        "pyarrow",
        "cv2",
        "opencv-python",
        "onnxruntime",
        "PIL",
        "matplotlib",
        "pandas",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vvrite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="vvrite",
)

app = BUNDLE(
    coll,
    name="vvrite.app",
    icon="assets/vvrite.icns",
    bundle_identifier=APP_BUNDLE_IDENTIFIER,
    info_plist=info_plist,
)
