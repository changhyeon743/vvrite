<p align="center">
  <img src="assets/icon.png" width="128" height="128" alt="vvrite icon">
</p>

<h1 align="center">vvrite</h1>

<p align="center">
  말하면 받아써서 커서 자리에 붙여넣는 macOS 메뉴바 앱. 전부 이 맥 안에서 돕니다.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS_(Apple_Silicon)-blue" alt="macOS">
  <img src="https://img.shields.io/badge/model-Qwen3--ASR--1.7B--8bit-green" alt="Model">
  <img src="https://img.shields.io/badge/runtime-MLX-orange" alt="MLX">
</p>

<p align="center">
  한국어 · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <a href="README.zh-Hans.md">简体中文</a> · <a href="README.zh-Hant.md">繁體中文</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a>
</p>

---

> **[shaircast/vvrite](https://github.com/shaircast/vvrite)의 포크입니다** (MIT, © 2026 shpark).
> 원격 ASR 서버, LLM 후교정, 화면 OCR 문맥, 이벤트 탭 워치독, 로컬 빌드 스크립트를 더했습니다.

## 어떻게 쓰나

1. 단축키를 누릅니다 (기본값 `Option + Space`)
2. 말합니다 — 화면에 녹음 오버레이가 뜹니다
3. 다시 누르면 멈춥니다
4. 받아쓴 텍스트가 커서 자리에 붙습니다

누르고 있는 동안만 녹음하고 싶으면 설정에서 **푸시투토크**로 바꾸세요. 오른쪽 `⌘` 같은 수식키 하나만으로도 됩니다.

음성 인식은 [MLX](https://github.com/ml-explore/mlx)로 이 맥에서 돕니다. 원격 서버를 직접 설정하지 않는 한 **음성이 기기 밖으로 나가지 않습니다.**

## 속도

M4 맥북, 실측입니다.

| 단계 | 시간 |
|---|---|
| 마이크 스트림 열기 | 53ms |
| 로컬 ASR (3.7초 발화) | 0.65초 |
| 로컬 ASR (12초 발화) | 1.30초 |
| 화면 OCR | 1.1~1.5초 (말하는 동안 병렬이라 **0초**) |
| LLM 교정 | 0.6~1.3초 |

교정을 켜면 **1.5~2초**, 끄면 **1초 미만**입니다.

## 이 포크가 더한 것

### 화면에 보이는 단어를 교정에 씁니다

`powerbanksharing-kakao` 같은 걸 소리만으로 맞힐 방법은 없습니다. 소리에 그 정보가 없으니까요. 그런데 그걸 말할 땐 대개 화면에 떠 있고, macOS에는 온디바이스 OCR(Vision)이 있습니다.

**녹음이 시작될 때** 포커스된 창을 캡처해서 OCR을 돌립니다. 말하는 동안 끝나기 때문에 지연이 붙지 않습니다. 거기서 뽑은 식별자를 교정기에 표기 후보로 넘깁니다.

```
"파워뱅크쉐어링 카카오 배포 상태 어떻게 됐지"
  → powerbanksharing-kakao 배포 상태 어떻게 됐지?

"콴트랩에서 백테스트 돌렸어"  →  quant-lab에서 백테스트 돌렸어.
"넥스트베이스 브이쓰리 레포에 커밋했어"  →  nextbase-v3 레포에 커밋했어.
```

화면과 무관한 말은 건드리지 않습니다. 후보 40개가 떠 있어도 "오늘 점심 뭐 먹지"는 그대로 나옵니다.

인식 정확도는 `Accurate`로 고정했습니다. `Fast`는 한글을 라틴 문자 비슷한 것으로 뭉개서(`AgeTht`, `JUEtr`) 그 쓰레기가 식별자 필터를 통과하고, 교정기에게 없는 단어를 지어내라고 부추깁니다.

**화면 기록 권한**이 필요하므로 기본은 꺼져 있습니다.

### LLM 후교정 (선택)

받아쓴 문장을 LLM이 다듬습니다. 필러 제거, 끊긴 말 잇기, 잘못 들은 전문 용어 교정.

**실패해도 손해가 없습니다.** LLM이 죽었거나 느리면 원문을 그대로 돌려줍니다. 연결과 응답 타임아웃을 분리해서(2초 / 12초), 닿지 않는 주소는 30초가 아니라 2초만 씁니다.

OpenAI 호환 엔드포인트면 뭐든 됩니다 (vLLM, llama.cpp, LM Studio, Ollama).

프롬프트의 각 줄은 실제로 겪은 실패를 하나씩 막은 것이라 손댈 때 주의가 필요합니다. 자세한 내력은 `_correction_prompt`의 독스트링에 있습니다.

- `"지울 수 있는 것은 감탄사와 반복뿐"` — 느슨하게 "필러만 지운다"로 뒀더니 `그`를 필러로 보고 `그게`, `우리` 같은 뜻 있는 단어까지 지웠습니다
- 입력 언어 판별은 **코드에서** 합니다. 한국어 프롬프트만으로는 영어 입력이 한국어로 번역돼 나왔고, 문구를 아무리 고쳐도 절반쯤만 먹혔습니다

### 원격 ASR 서버 (선택)

설정 → **모델** → *원격 서버*. OpenAI 형식의 `/v1/audio/transcriptions`를 말하는 Qwen3-ASR 서버를 가리키면 거기서 인식합니다. 맥 메모리가 빠듯할 때 쓸 수 있습니다.

이 모드에서는 음성이 기기 밖으로 나가므로 기본은 꺼져 있습니다. 서버가 닿지 않으면 받아쓰기를 잃는 대신 로컬 모델로 넘어갑니다. 로컬 모델이 없으면 WAV를 디스크에 남기고 경로를 알려줍니다.

> 참고로 GPU 박스(DGX Spark GB10)에 올려서 비교해봤는데 **맥이 더 빨랐습니다** — 12초 오디오 기준 맥 MLX 8bit 1.30초 vs GPU bf16 2.36초. 메모리를 비우는 게 목적이 아니라면 로컬이 낫습니다.

### 이벤트 탭 워치독

macOS는 이벤트 탭을 조용히 꺼버립니다 — 응답이 늦거나, 보안 입력 필드가 이벤트 흐름을 가져갈 때.

탭과 워치독 타이머 모두 `kCFRunLoopCommonModes`에서 돕니다. 기본 모드는 모달 루프(경고창, 파일 선택, 메뉴 클릭, 창 드래그) 동안 서비스되지 않아서, **탭이 죽는 바로 그 순간에 워치독도 같이 자고 있었습니다.**

재활성화가 먹히지 않으면 탭을 새로 만들고, 무슨 일이 있었는지 로그에 남깁니다.

### 로그

```bash
tail -f ~/Library/Logs/vvrite.log
```

Finder에서 실행한 `.app`은 stdout이 `/dev/null`로 갑니다. 그래서 파일에 남깁니다.

```
screen  1.13s  40 terms: nextbase-v3, powerbanksharing-kakao, useEffect, ...
correct 0.91s  40 terms
  raw   그럼 그 그럼 그것들을 좀 마크다운으로 해가지고 해줘.
  out   그럼 그것들을 좀 마크다운으로 해가지고 해줘.
```

교정 전후를 **항상 같이** 남깁니다. 교정기에 뭘 줬는지와 그걸로 뭘 했는지를 둘 다 봐야, "화면 캡처가 쓸모없었던 것"과 "프롬프트가 멀쩡한 단어를 무시한 것"을 구분할 수 있습니다.

### `.env` 개인 설정

서버 주소는 프로젝트 설정이 아니라 개인 설정입니다. 하드코딩하면 포크마다 남의 LAN 호스트명을 달고 다니게 됩니다.

```bash
cp .env.example .env
```

```ini
VVRITE_LLM_ENDPOINT=http://your-server:8000/v1/chat/completions
VVRITE_LLM_MODEL=your-model-name
VVRITE_LLM_CONTEXT=소프트웨어 개발자. 한국어와 영어만 사용한다.
```

키는 `VVRITE_STT_ENDPOINT`, `VVRITE_LLM_ENDPOINT`, `VVRITE_LLM_MODEL`, `VVRITE_LLM_CONTEXT`, `VVRITE_CUSTOM_WORDS`입니다. 환경변수가 파일보다 우선합니다.

`.env`는 빌드할 때 **`.app` 안에 구워집니다.** 새로 설치해도 주소를 다시 입력할 필요가 없습니다. 값은 내용이 바뀔 때 한 번만 설정에 기록되므로, 그 사이 설정 창에서 바꾼 값은 유지됩니다.

번들 안에 들어가니 **그 빌드를 받은 사람은 주소를 읽을 수 있습니다.** 빌드할 때 경고가 뜨고, `VVRITE_BAKE_ENV=0`으로 끌 수 있습니다. 릴리스 빌드는 깨끗한 체크아웃에서 도니 `.env`가 없습니다.

### 로컬 빌드 스크립트

```bash
./scripts/build-local.sh
open dist/vvrite.dmg
```

애플 개발자 계정 없이 자체 서명 인증서(`vvrite-dev`)로 빌드합니다. **ad-hoc 서명(`--sign -`)은 고정된 신원이 없어서 다시 빌드할 때마다 macOS가 손쉬운 사용·마이크 권한을 초기화합니다.** 자체 서명 인증서를 쓰면 권한이 유지됩니다.

`SIGN_IDENTITY`로 다른 인증서를 지정할 수 있고, 없으면 ad-hoc으로 넘어갑니다.

## 지원 언어

[`mlx-community/Qwen3-ASR-1.7B-8bit`](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)을 씁니다. Qwen 공식 모델 카드 기준 **30개 언어와 22개 중국어 방언**을 지원합니다.

한국어, 영어, 일본어, 중국어, 광둥어, 아랍어, 독일어, 프랑스어, 스페인어, 포르투갈어, 인도네시아어, 이탈리아어, 러시아어, 태국어, 베트남어, 튀르키예어, 힌디어, 말레이어, 네덜란드어, 스웨덴어, 덴마크어, 핀란드어, 폴란드어, 체코어, 필리핀어, 페르시아어, 그리스어, 헝가리어, 마케도니아어, 루마니아어가 포함됩니다.

인식 언어를 하나로 고정하지 않으므로 다국어 받아쓰기가 그대로 됩니다.

## 요구 사항

- Apple Silicon · 빌드된 앱은 macOS 15+, 소스 실행은 macOS 13+
- ASR 모델용 디스크 약 2GB
- 마이크 권한
- 손쉬운 사용 권한 (전역 단축키용)
- 화면 기록 권한 (화면 문맥 기능을 켤 때만)

`ffmpeg`는 필요 없습니다. mlx-audio가 WAV 디코딩과 리샘플링을 직접 합니다.

## 설치

### 소스에서 실행

```bash
git clone https://github.com/changhyeon743/vvrite.git
cd vvrite
pip install -r requirements.txt
python -m vvrite
```

### 앱으로 빌드

로컬용은 위의 `scripts/build-local.sh`가 가장 짧은 길입니다.

서명·공증·자동 업데이트까지 붙은 릴리스는 `./scripts/build.sh`가 PyInstaller 빌드, Sparkle 임베딩, 코드 서명, 공증, 스테이플링, DMG 생성을 합니다. 애플 개발자 서명 신원, `notarytool` 프로필, Sparkle EdDSA 공개키가 필요합니다.

```bash
./scripts/prepare_sparkle.sh
vendor/Sparkle/bin/generate_keys --account vvrite
export SPARKLE_PUBLIC_ED_KEY="..."
./scripts/build.sh
```

## 단축키

| 동작 | 키 |
|---|---|
| 녹음 시작/중지 (토글 모드) | `Option + Space` (변경 가능) |
| 누르고 있는 동안 녹음 (푸시투토크) | 오른쪽 `⌘` (변경 가능) |
| 녹음 취소 | `Escape` |
| 모드 전환 | 설정 → 일반 → 녹음 모드 |
| 원격 서버 · 교정 · 화면 문맥 | 설정 → 모델 |

처음 실행하면 온보딩이 권한 허용, 단축키 설정, 모델 다운로드를 안내합니다. 원격 ASR 서버를 설정하면 다운로드 없이 넘어갈 수 있습니다.

## 기술 스택

| 구성 요소 | 기술 |
|---|---|
| UI | PyObjC (AppKit, Quartz) |
| ASR 모델 | [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit) |
| 추론 | Apple Silicon GPU에서 [mlx-audio](https://github.com/ml-explore/mlx-audio) |
| 화면 OCR | Vision.framework (`VNRecognizeTextRequest`) |
| 오디오 | sounddevice |
| 패키징 | PyInstaller |

## 라이선스

MIT — [LICENSE](LICENSE) 참조. 원저작물 © 2026 shpark ([shaircast/vvrite](https://github.com/shaircast/vvrite)).

ASR 모델 [Qwen3-ASR-1.7B-8bit](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)은 Apache 2.0 라이선스입니다.
