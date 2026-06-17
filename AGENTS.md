# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

vvrite is a macOS menu bar application (Python) that performs on-device voice transcription using the Qwen3-ASR model via mlx-audio. It captures audio through a global hotkey, transcribes speech, and pastes text into the active application.

- Platform: macOS 13+ (Apple Silicon only)
- UI Framework: PyObjC (AppKit, Quartz, Foundation)
- ML Backend: mlx-audio with Qwen3-ASR model
- App Type: Menu bar accessory (LSUIElement — no dock icon)

## Commands

# Run from source
pip install -r requirements.txt
python -m vvrite

# Run tests
python -m unittest discover tests/
python -m unittest tests.test_preferences
python -m unittest tests.test_transcriber

# Build, sign, notarize, and staple (ALWAYS use this for builds)
./scripts/build.sh

IMPORTANT: Never run pyinstaller vvrite.spec directly. Always use ./scripts/build.sh.

## Architecture

Application flow: Entry (__main__.py → main.py) → Onboarding wizard → Menu bar loop → Hotkey press → Record → Transcribe → Paste into active app.

Key modules:
- main.py: AppDelegate — app lifecycle, recording state machine, threading
- transcriber.py: Model download, loading, and mlx-audio inference
- hotkey.py: HotkeyManager — CGEvent tap for global keyboard interception
- recorder.py: Recorder — sounddevice input stream with RMS level callback
- overlay.py: OverlayController — floating panel (timer, level bars, spinner)
- status_bar.py: Menu bar status item and dropdown menu
- onboarding.py: Multi-step first-run wizard
- settings.py: Settings window controller
- preferences.py: Preferences — thin wrapper around NSUserDefaults
- clipboard.py: Clipboard write + Cmd-V paste + clipboard restore
- audio_utils.py: FFmpeg-based audio normalization
- widgets.py: Reusable UI components (ShortcutField for hotkey capture)

Threading: Main thread = NSApplication run loop (UI). Model loading + transcription = background threads via threading.Thread. Results posted back via performSelectorOnMainThread.

State machine: Idle → Recording (hotkey down) → Transcribing (hotkey up) → Pasting → Idle. ESC cancels.

## Build & Distribution

- vvrite.spec: PyInstaller build config (arm64, MLX Metal shaders, ffmpeg, PyObjC)
- scripts/build.sh: Full pipeline (PyInstaller → codesign → notarize → staple)
- entitlements.plist: macOS entitlements for hardened runtime
- Version string: vvrite/__init__.__version__

## Sparkle Updates

vvrite uses Sparkle 2 for direct-distribution macOS updates. Do not reintroduce
the old GitHub Releases polling updater; manual "Check for Updates" should go
through `vvrite.updater.SparkleUpdater` and Sparkle's standard UI.

- Sparkle runtime bridge: `vvrite/updater.py`
- Menu action wiring: `vvrite/main.py` → `checkForUpdates`
- Settings checkbox wiring: `vvrite/settings.py` → Sparkle's `automaticallyChecksForUpdates`
- App bundle config: `vvrite.spec` injects `SUFeedURL`, `SUPublicEDKey`,
  `SUEnableAutomaticChecks`, and `SUScheduledCheckInterval`
- Sparkle framework cache: `./scripts/prepare_sparkle.sh` downloads
  `vendor/Sparkle/` (ignored by git)

Release builds require a Sparkle EdDSA public key:

```bash
./scripts/prepare_sparkle.sh
vendor/Sparkle/bin/generate_keys --account vvrite
export SPARKLE_PUBLIC_ED_KEY="..."  # printed SUPublicEDKey
./scripts/build.sh
```

`./scripts/build.sh` intentionally fails when `SPARKLE_PUBLIC_ED_KEY` is missing.
Use `SPARKLE_ENABLED=0` only for local builds that must omit Sparkle.
Sparkle Keychain signing uses `SPARKLE_KEY_ACCOUNT`, defaulting to `vvrite`;
use the same account when running `generate_keys`.

To generate update feed artifacts for a release:

```bash
SPARKLE_GENERATE_APPCAST=1 ./scripts/build.sh
```

Upload both `dist/sparkle-updates/appcast.xml` and the versioned DMG from the
same directory to the GitHub release. The default appcast URL is:
`https://github.com/shaircast/vvrite/releases/latest/download/appcast.xml`
