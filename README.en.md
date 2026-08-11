<p align="center">
  <img src="assets/icon.png" width="128" height="128" alt="vvrite icon">
</p>

<h1 align="center">vvrite</h1>

<p align="center">
  macOS menu bar app that transcribes your voice and pastes the text — powered by on-device AI.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS_(Apple_Silicon)-blue" alt="macOS">
  <img src="https://img.shields.io/badge/model-Qwen3--ASR--1.7B--8bit-green" alt="Model">
  <img src="https://img.shields.io/badge/runtime-MLX-orange" alt="MLX">
</p>

<p align="center">
  <a href="README.md">한국어</a> · <a href="README.ja.md">日本語</a> · <a href="README.zh-Hans.md">简体中文</a> · <a href="README.zh-Hant.md">繁體中文</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a>
</p>

---

> **This is a fork of [shaircast/vvrite](https://github.com/shaircast/vvrite)** (MIT, © 2026 shpark).
> It adds an optional remote ASR server, LLM post-correction, an event-tap watchdog,
> and a local build script. See [What This Fork Adds](#what-this-fork-adds).

## How It Works

1. Press the hotkey (default: `Option + Space`)
2. Speak — a recording overlay appears on screen
3. Press the hotkey again to stop
4. Your speech is transcribed locally and pasted into the active text field

Prefer hold-to-talk? Switch to **push-to-talk** mode in Settings and just hold a key — even a single modifier like Right `⌘` — while you speak, then release to transcribe.

Everything runs on-device using [MLX](https://github.com/ml-explore/mlx). No audio leaves your Mac unless you explicitly configure a remote server.
The default model also brings strong multilingual ASR support, so supported languages such as Korean, English, Japanese, Chinese, Cantonese, French, German, and Spanish work out of the box.

## Features

- **On-device transcription** — Qwen3-ASR running via mlx-audio, no cloud API needed
- **Multilingual-ready** — the default Qwen3-ASR model supports language identification and transcription across 30 languages and 22 Chinese dialects, and vvrite does not lock transcription to a single language
- **Global hotkey** — trigger from any app, configurable in Settings
- **Two recording modes** — *toggle* (press to start/stop) or *push-to-talk* (hold to talk, even a single modifier like Right `⌘`), each with its own hotkey
- **Menu bar app** — lives quietly in your status bar
- **Recording overlay** — visual feedback with audio level bars and timer
- **ESC to cancel** — press Escape during recording to dismiss without transcribing
- **Auto-paste** — transcribed text is pasted directly into the active field
- **Guided onboarding** — first launch walks you through permissions and model download

## What This Fork Adds

### Remote ASR (optional)

Settings → **Model** → *Remote Server*. Point it at a Qwen3-ASR server that speaks
the OpenAI-shaped `/v1/audio/transcriptions` API and transcription happens there
instead of on this Mac — useful when the Mac is short on memory.

Audio leaves your machine in that mode, so it is off by default. If the server is
unreachable the recording falls back to the on-device model rather than being lost;
if no local model has been downloaded, the WAV is kept on disk and its path is reported.

### LLM post-correction (optional)

An LLM cleans up the raw transcription: fillers removed, broken sentences joined,
misheard jargon fixed against your custom-word list. It runs on the client, so the
same correction applies whether the audio was transcribed locally or remotely.

It **fails open** — a slow or dead LLM returns the raw text rather than costing you
the dictation. Connect and read timeouts are separate (2s / 12s) so an unreachable
endpoint costs about two seconds, not thirty.

Any OpenAI-compatible chat endpoint works (vLLM, llama.cpp, LM Studio, Ollama).

### Event-tap watchdog

macOS silently disables a `CGEventTap` under load or during secure input, which used
to kill the global hotkey until the app was restarted. A 2-second poll re-enables it.

### `.env` for personal defaults

Server addresses are personal, not project settings. Copy `.env.example` to `.env`
(gitignored) to preset them for a dev checkout:

```bash
cp .env.example .env
```

```ini
VVRITE_LLM_ENDPOINT=http://your-server:8000/v1/chat/completions
VVRITE_LLM_MODEL=your-model-name
VVRITE_LLM_CONTEXT=Software developer. Korean and English only.
```

Recognised keys: `VVRITE_STT_ENDPOINT`, `VVRITE_LLM_ENDPOINT`, `VVRITE_LLM_MODEL`,
`VVRITE_LLM_CONTEXT`, `VVRITE_CUSTOM_WORDS`. Environment variables override the file.

`.env` is also **baked into the .app** at build time, so a fresh install already knows
your endpoints instead of making you retype them. The values are written through to the
saved settings once per change, so edits in the Settings window stick until you change
`.env` and rebuild.

Because the file ships inside the bundle, anyone you hand that build to can read it —
the build prints a warning when it happens. Set `VVRITE_BAKE_ENV=0` to build without it.
Release builds run from a clean checkout, where `.env` is gitignored and absent.

### Local build script

`scripts/build-local.sh` builds and signs with a self-signed identity (`vvrite-dev`
by default) instead of an Apple Developer certificate, and skips notarization. Ad-hoc
signing has no stable identity, so macOS resets Accessibility and Microphone
permissions on every rebuild — a stable self-signed certificate avoids that.

```bash
# one-time: create the certificate, then trust it for code signing
./scripts/build-local.sh
```

Set `SIGN_IDENTITY` to use a different one. It falls back to ad-hoc signing if the
identity is not found.

## Language Support

vvrite uses [`mlx-community/Qwen3-ASR-1.7B-8bit`](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit), which is an MLX conversion of [`Qwen/Qwen3-ASR-1.7B`](https://huggingface.co/Qwen/Qwen3-ASR-1.7B). According to the official Qwen model card, Qwen3-ASR-1.7B supports language identification and speech recognition for 30 languages and 22 Chinese dialects.

That includes Korean, English, Japanese, Chinese, Cantonese, Arabic, German, French, Spanish, Portuguese, Indonesian, Italian, Russian, Thai, Vietnamese, Turkish, Hindi, Malay, Dutch, Swedish, Danish, Finnish, Polish, Czech, Filipino, Persian, Greek, Hungarian, Macedonian, and Romanian, plus regional Chinese dialect support. Because vvrite uses that checkpoint directly through mlx-audio and does not force a fixed recognition language, multilingual dictation works well for the model's supported languages.

## Requirements

- macOS 15+ on Apple Silicon for pre-built .app; macOS 13+ when building from source
- ~2 GB disk space for the ASR model
- Microphone permission
- Accessibility permission (for global hotkey)

No `ffmpeg` needed — mlx-audio decodes and resamples the WAV itself (miniaudio +
`scipy.signal.resample_poly`).

## Installation

### From Source

```bash
git clone https://github.com/changhyeon743/vvrite.git
cd vvrite

pip install -r requirements.txt

python -m vvrite
```

### Build as .app

For local use, `scripts/build-local.sh` is the short path — no Apple Developer
account required:

```bash
pip install -r requirements.txt
./scripts/build-local.sh
open dist/vvrite.dmg
```

For a signed, notarized, auto-updating release, `./scripts/build.sh` performs the
PyInstaller build, Sparkle framework embedding, code signing, notarization, stapling,
and DMG creation. It requires a configured Apple Developer signing identity, a
`notarytool` profile, and a Sparkle EdDSA public key:

```bash
./scripts/prepare_sparkle.sh
vendor/Sparkle/bin/generate_keys --account vvrite
export SPARKLE_PUBLIC_ED_KEY="..."  # SUPublicEDKey from generate_keys
./scripts/build.sh
```

For release publishing, set `SPARKLE_GENERATE_APPCAST=1` to copy the final DMG into `dist/sparkle-updates/` and generate `appcast.xml`. The build script signs appcasts with the Keychain item from `SPARKLE_KEY_ACCOUNT` (`vvrite` by default). Upload both `appcast.xml` and the versioned DMG to the GitHub release.

## Usage

| Action | Shortcut |
|---|---|
| Start / stop recording (toggle mode) | `Option + Space` (configurable) |
| Hold to talk (push-to-talk mode) | hold `Right ⌘` (configurable) |
| Cancel recording | `Escape` |
| Switch recording mode | Settings → General → Recording Mode |
| Remote server / correction | Settings → Model |
| Open settings | Click menu bar icon → Settings |

On first launch, the onboarding wizard will guide you through:
1. Granting microphone and accessibility permissions
2. Setting your preferred hotkey
3. Downloading the ASR model (~1.7 GB)

Configure a remote ASR server and the download step is satisfied without it.

## Tech Stack

| Component | Technology |
|---|---|
| UI | PyObjC (AppKit, Quartz) |
| ASR Model | [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit) |
| Inference | [mlx-audio](https://github.com/ml-explore/mlx-audio) on Apple Silicon GPU |
| Audio | sounddevice |
| Packaging | PyInstaller |

## License

MIT — see [LICENSE](LICENSE) for details. Original work © 2026 shpark
([shaircast/vvrite](https://github.com/shaircast/vvrite)).

The ASR model [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit) is licensed under Apache 2.0.
