<p align="center">
  <img src="assets/icon.png" width="128" height="128" alt="vvrite 아이콘">
</p>

<h1 align="center">vvrite</h1>

<p align="center">
  음성을 받아쓰기하여 텍스트로 붙여넣는 macOS 메뉴 막대 앱 — 온디바이스 AI로 구동됩니다.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS_(Apple_Silicon)-blue" alt="macOS">
  <img src="https://img.shields.io/badge/model-Qwen3--ASR--1.7B--8bit-green" alt="Model">
  <img src="https://img.shields.io/badge/runtime-MLX-orange" alt="MLX">
</p>

<p align="center">
  <a href="README.md">English</a> · 한국어 · <a href="README.ja.md">日本語</a> · <a href="README.zh-Hans.md">简体中文</a> · <a href="README.zh-Hant.md">繁體中文</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a>
</p>

---

## 작동 방식

1. 단축키를 누릅니다 (기본값: `Option + Space`)
2. 말합니다 — 화면에 녹음 오버레이가 나타납니다
3. 단축키를 다시 눌러 녹음을 중지합니다
4. 음성이 로컬에서 변환되어 활성 텍스트 필드에 붙여넣기됩니다

눌러서 말하는 방식을 선호하시나요? 설정에서 **푸시투토크** 모드로 전환하면, 키 — 오른쪽 `⌘` 같은 단일 보조 키도 가능 — 를 누른 채로 말하고 손을 떼면 변환됩니다.

모든 처리는 [MLX](https://github.com/ml-explore/mlx)를 사용하여 기기에서 이루어집니다. 음성 데이터가 Mac 밖으로 나가지 않습니다.
기본 모델은 강력한 다국어 음성 인식을 지원하므로, 한국어, 영어, 일본어, 중국어, 광둥어, 프랑스어, 독일어, 스페인어 등 지원 언어를 바로 사용할 수 있습니다.

## 주요 기능

- **온디바이스 변환** — mlx-audio를 통해 Qwen3-ASR이 실행되며, 클라우드 API가 필요 없습니다
- **다국어 지원** — 기본 Qwen3-ASR 모델이 30개 언어와 22개 중국어 방언의 언어 식별 및 변환을 지원하며, vvrite는 변환 언어를 하나로 고정하지 않습니다
- **전역 단축키** — 어떤 앱에서든 실행 가능하며, 설정에서 변경할 수 있습니다
- **두 가지 녹음 모드** — *토글* (눌러서 시작/중지) 또는 *푸시투토크* (오른쪽 `⌘` 같은 단일 보조 키도 가능, 누른 채로 말하기) 중 선택할 수 있으며, 각 모드마다 별도의 단축키를 가집니다
- **메뉴 막대 앱** — 상태 막대에 조용히 자리 잡습니다
- **녹음 오버레이** — 오디오 레벨 바와 타이머로 시각적 피드백을 제공합니다
- **ESC로 취소** — 녹음 중 Escape를 누르면 변환 없이 취소됩니다
- **자동 붙여넣기** — 변환된 텍스트가 활성 필드에 바로 붙여넣기됩니다
- **안내형 온보딩** — 첫 실행 시 권한 설정과 모델 다운로드를 안내합니다

## 언어 지원

vvrite는 [`mlx-community/Qwen3-ASR-1.7B-8bit`](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)을 사용합니다. 이 모델은 [`Qwen/Qwen3-ASR-1.7B`](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)의 MLX 변환 버전입니다. 공식 Qwen 모델 카드에 따르면, Qwen3-ASR-1.7B은 30개 언어와 22개 중국어 방언의 언어 식별 및 음성 인식을 지원합니다.

지원 언어에는 한국어, 영어, 일본어, 중국어, 광둥어, 아랍어, 독일어, 프랑스어, 스페인어, 포르투갈어, 인도네시아어, 이탈리아어, 러시아어, 태국어, 베트남어, 터키어, 힌디어, 말레이어, 네덜란드어, 스웨덴어, 덴마크어, 핀란드어, 폴란드어, 체코어, 필리핀어, 페르시아어, 그리스어, 헝가리어, 마케도니아어, 루마니아어가 포함되며, 중국어 지역 방언도 지원됩니다. vvrite는 이 체크포인트를 mlx-audio를 통해 직접 사용하며 특정 인식 언어를 강제하지 않으므로, 모델이 지원하는 언어라면 다국어 받아쓰기가 잘 작동합니다.

## 요구 사항

- 빌드된 .app은 Apple Silicon (M1/M2/M3/M4) 탑재 macOS 15 이상; 소스에서 빌드 시 macOS 13 이상
- ASR 모델용 디스크 공간 약 2 GB
- 소스에서 실행 시 `ffmpeg` 필요
- 마이크 권한
- 손쉬운 사용 권한 (전역 단축키용)

## 설치

### 소스에서 실행

```bash
# 복제
git clone https://github.com/shaircast/vvrite.git
cd vvrite

# 의존성 설치
pip install -r requirements.txt
brew install ffmpeg

# 실행
python -m vvrite
```

### .app으로 빌드

```bash
pip install -r requirements.txt
./scripts/prepare_sparkle.sh
vendor/Sparkle/bin/generate_keys --account vvrite
export SPARKLE_PUBLIC_ED_KEY="..."  # generate_keys가 출력한 SUPublicEDKey
./scripts/build.sh
open dist/vvrite.dmg
```

`./scripts/build.sh`가 지원되는 빌드 방법입니다. PyInstaller 빌드, Sparkle framework 포함, 코드 서명, 공증, 스테이플링, DMG 생성을 수행합니다. 설정된 Apple Developer 서명 인증서, `notarytool` 프로파일, Sparkle EdDSA 공개키가 필요합니다.

릴리스 배포 시 `SPARKLE_GENERATE_APPCAST=1`을 설정하면 최종 DMG를 `dist/sparkle-updates/`로 복사하고 `appcast.xml`을 생성합니다. build script는 `SPARKLE_KEY_ACCOUNT`의 Keychain 항목으로 appcast에 서명하며 기본값은 `vvrite`입니다. GitHub Release에는 `appcast.xml`과 버전이 붙은 DMG를 함께 업로드하세요. 기본 appcast URL은 `https://github.com/shaircast/vvrite/releases/latest/download/appcast.xml`입니다.

## 사용법

| 동작 | 단축키 |
|---|---|
| 녹음 시작 / 중지 (토글 모드) | `Option + Space` (변경 가능) |
| 누른 채로 말하기 (푸시투토크 모드) | `Right ⌘` 누르고 있기 (변경 가능) |
| 녹음 취소 | `Escape` |
| 녹음 모드 전환 | 설정 → 일반 → 녹음 모드 |
| 설정 열기 | 메뉴 막대 아이콘 클릭 → 설정 |

첫 실행 시 온보딩 마법사가 다음을 안내합니다:
1. 마이크 및 손쉬운 사용 권한 부여
2. 선호하는 단축키 설정
3. ASR 모델 다운로드 (약 1.7 GB)

## 기술 스택

| 구성 요소 | 기술 |
|---|---|
| UI | PyObjC (AppKit, Quartz) |
| ASR 모델 | [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit) |
| 추론 | Apple Silicon GPU에서 [mlx-audio](https://github.com/ml-explore/mlx-audio) |
| 오디오 | sounddevice + ffmpeg |
| 패키징 | PyInstaller |

## 라이선스

MIT — 자세한 내용은 [LICENSE](LICENSE)를 참조하세요.

이 앱은 [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html) 라이선스의 [ffmpeg](https://ffmpeg.org/)을 번들로 포함합니다. ffmpeg 소스 코드는 https://ffmpeg.org/download.html 에서 받을 수 있습니다. ASR 모델 [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)은 Apache 2.0 라이선스입니다.
