"""Qwen3 ASR transcription using mlx-audio, or a remote Qwen3-ASR server."""

import os
import time

import miniaudio
import numpy as np
from huggingface_hub import model_info, snapshot_download

from vvrite.logs import log
from vvrite.mlx_runtime import install_qwen_only_model_namespace


install_qwen_only_model_namespace()

from mlx_audio.stt.utils import load_model  # noqa: E402

from vvrite.preferences import Preferences, SAMPLE_RATE  # noqa: E402

# ponytail: one shared timeout, no retry. Retry when a flaky link actually shows up.
REMOTE_TIMEOUT = 120
# (connect, read). A dead LLM must not hold a dictation hostage — connecting is
# either near-instant on a LAN or never, so 2s is generous. Reading can take a
# few seconds because the model is generating.
CORRECTION_TIMEOUT = (2, 12)

_model = None
_warmed_up = False


def _endpoint(prefs: Preferences = None) -> str:
    """Base URL of a remote ASR server, or "" to transcribe on-device.

    A bare "host:port" is what people actually type, and requests rejects it for
    having no scheme — so assume http rather than silently falling back to local.
    """
    if prefs is None:
        prefs = Preferences()
    url = prefs.stt_endpoint.strip().rstrip("/")
    if url and "://" not in url:
        url = f"http://{url}"
    return url


def is_model_loaded() -> bool:
    """Return True if the ASR model is ready. A remote endpoint is always ready."""
    return bool(_endpoint()) or _model is not None


def _is_downloaded(model_id: str) -> bool:
    """True if the model files are on disk. Ignores the remote endpoint on purpose —
    the fallback path needs to know whether a local model is actually available."""
    try:
        snapshot_download(repo_id=model_id, local_files_only=True)
        return True
    except Exception:
        return False


def is_model_cached(model_id: str) -> bool:
    """Return True if transcription can start without downloading anything."""
    return bool(_endpoint()) or _is_downloaded(model_id)


def get_model_size(model_id: str) -> int:
    """Return total model size in bytes. Returns 0 on error."""
    try:
        info = model_info(model_id, files_metadata=True)
        return sum(s.size for s in info.siblings if s.size)
    except Exception:
        return 0


def download_model(model_id: str) -> str:
    """Download model files and return local path."""
    return snapshot_download(repo_id=model_id)


def load_from_local(local_path: str):
    """Load model from a local directory into memory."""
    global _model, _warmed_up
    _model = load_model(local_path)
    _warmed_up = False
    _safe_warm_up()


def load(prefs: Preferences = None):
    """Download + load in one step. Used by existing non-onboarding flow."""
    global _model, _warmed_up
    if prefs is None:
        prefs = Preferences()
    if _endpoint(prefs):
        log.info(f"Using remote ASR endpoint: {_endpoint(prefs)}")
        return
    model_id = prefs.model_id
    log.info(f"Loading model: {model_id} ...")
    _model = load_model(model_id)
    _warmed_up = False
    _safe_warm_up()
    log.info("Model loaded.")


def _decode_audio(path: str) -> np.ndarray:
    """Decode and resample a recorded WAV to mono 16 kHz float32 audio."""
    decoded = miniaudio.decode_file(
        path,
        output_format=miniaudio.SampleFormat.FLOAT32,
        nchannels=1,
        sample_rate=SAMPLE_RATE,
    )
    return np.asarray(decoded.samples, dtype=np.float32)


def warm_up():
    """Run a tiny silent transcription to trigger first-use compilation work."""
    global _warmed_up
    if _model is None or _warmed_up:
        return

    silence = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
    _model.generate(silence, max_tokens=1)
    _warmed_up = True


def _safe_warm_up():
    try:
        warm_up()
    except Exception as e:
        log.info(f"Model warm-up skipped: {e}")


def _is_korean(text: str) -> bool:
    """True unless the text is clearly not Korean.

    A low bar on purpose: mixed Korean-English speech is the norm here, and only a
    sentence with almost no Hangul should switch the corrector into English.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    return sum("\uac00" <= c <= "\ud7a3" for c in letters) / len(letters) >= 0.15


def _correction_prompt(text: str, vocab: str, context: str = "",
                       screen_terms: list = None, pronunciations: str = "") -> str:
    """Rules for the post-ASR corrector.

    Every line replaced a failure seen in practice, so trim with care:
    "감탄사와 반복뿐이다" — the looser "필러만 지운다" let it drop meaning:
        "그게 지금 ... 작업한 건가 우리?" came back without "그게 지금" or "우리";
    "없는 단어를 만들지 마라" — "후프"(훅) became "useEffect";
    "요청은 마침표" — "알려줘." became "알려줘?".

    Screen terms go last on purpose. They are the only part that changes between
    dictations, so putting them at the end leaves every preceding token identical
    and lets the server's prefix cache cover the whole rule block — measured at
    1.04s with them in the middle versus 0.92s at the end.
    """
    rules = ["너는 음성인식(STT) 결과를 읽기 좋게 다듬는다."]
    if context:
        rules[0] += f" 화자 정보: {context}"
    # A Korean prompt alone made English input come back translated, and no
    # wording of "절대 번역하지 마라" fixed it reliably — the instruction landed
    # about half the time. Detecting the language here and switching the rule to
    # English when the input is English is deterministic and did fix it.
    rules.append(
        "- 입력한 언어를 그대로 유지한다. 절대 번역하지 마라. "
        "영어 문장은 영어로, 한국어 문장은 한국어로 출력한다."
        if _is_korean(text) else
        "- The input is English. Output English only. Do not translate it to Korean."
    )
    if vocab:
        rules.append(f"- 다음 표기는 그대로 둔다: {vocab}")
    if pronunciations:
        # The spellings above are enough when the recogniser keeps the syllables
        # apart — "씨에스" and "디비" already came back as CS and DB. They are not
        # enough when it runs them together: "피 알" arrives as "피아", a perfectly
        # ordinary Korean word, and the corrector has no reason to touch it.
        # Naming the pronunciation gives it the one thing it was missing.
        rules.append(
            f"- 자주 쓰는 약어의 한국어 발음이다. 이렇게 들렸으면 해당 표기로 바꾼다: {pronunciations}"
        )
    rules += [
        "- 지울 수 있는 것은 감탄사(음, 어, 아)와 같은 말의 반복뿐이다. "
        "그 외에는 입력의 모든 단어가 출력에 그대로 있어야 한다.",
        "- 끊긴 말은 자연스러운 한 문장으로 잇는다.",
        "- 발음이 비슷한 오인식을 고친다. 문맥으로 추측해 없는 단어를 만들지 마라.",
        "- 질문이면 물음표로 끝낸다(아니야→아니야?, 안 나나→안 나나?). "
        "요청(~줘/~해)은 마침표.",
        "- 반말은 반말로 유지한다. 내용 추가·요약 금지.",
        "- 결과 문장만 출력한다.",
    ]
    if screen_terms:
        # These come off whatever window was in front, so most have nothing to do
        # with what was said — hence "들어맞지 않으면 무시한다". The two worked
        # examples are load-bearing: without them "파워뱅크쉐어링 카카오" was left
        # alone, and "콴트랩" came back as "QuantLab" instead of the exact
        # "quant-lab". Naming the Korean-pronunciation case is what makes it fire.
        rules.append(
            "- 말할 때 화면에 있던 표기다. 한국어 발음으로 말한 것이 이 중 하나와 들어맞으면 "
            "그 표기를 글자 그대로 복사한다"
            "(파워뱅크쉐어링 카카오→powerbanksharing-kakao, 콴트랩→quant-lab). "
            f"들어맞지 않으면 무시한다: {', '.join(screen_terms)}"
        )
    return "\n".join(rules)


def _correct(text: str, prefs) -> str:
    """Run the LLM corrector over a transcription.

    Fails open: a dead or slow LLM returns the raw text rather than costing the
    user their dictation. Applied on the client so it works the same whether the
    audio was transcribed on-device or on a remote ASR server.
    """
    endpoint = prefs.llm_endpoint.strip().rstrip("/")
    if not text or not endpoint:
        return text
    if "://" not in endpoint:
        endpoint = f"http://{endpoint}"

    import requests

    from vvrite import screen

    screen_terms = screen.terms() if prefs.screen_context else []
    started = time.time()

    try:
        resp = requests.post(
            endpoint,
            json={
                "model": prefs.llm_model,
                "temperature": 0,
                "max_tokens": 1024,
                # DeepSeek reasons by default: 15s and sometimes an empty completion.
                "chat_template_kwargs": {"thinking": False},
                "messages": [
                    {"role": "system",
                     "content": _correction_prompt(text,
                                                   prefs.custom_words.strip(),
                                                   prefs.llm_context.strip(),
                                                   screen_terms,
                                                   prefs.pronunciations.strip())},
                    {"role": "user", "content": text},
                ],
            },
            timeout=CORRECTION_TIMEOUT,
        )
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"].get("content")
        corrected = out.strip() if out and out.strip() else text
        # Both sides, always: seeing what the corrector was given and what it did
        # with it is the only way to tell a useless screen capture from a prompt
        # that ignored a perfectly good one.
        log.info(f"correct {time.time() - started:.2f}s  {len(screen_terms)} terms")
        log.info(f"  raw   {text}")
        log.info(f"  out   {corrected}" if corrected != text else "  out   (unchanged)")
        return corrected
    except Exception as e:
        log.info(f"Correction skipped: {e}")
        return text


def _transcribe_remote(raw_wav_path, prefs, endpoint, language_map) -> str:
    """POST the WAV to a Qwen3-ASR server (OpenAI-shaped /v1/audio/transcriptions).

    Leaves the recording on disk when the request fails so the caller can retry it
    on-device; only deletes it once the text is safely in hand.
    """
    import requests

    # Correction happens on the client now, so the server only transcribes.
    data = {"prompt": prefs.custom_words.strip(), "correction": "0"}
    asr_lang = prefs.asr_language
    if asr_lang != "auto":
        language = language_map.get(asr_lang)
        if language is None:
            log.info(f"Unknown ASR language code: {asr_lang}, falling back to auto-detect")
        else:
            data["language"] = language

    started = time.time()
    with open(raw_wav_path, "rb") as f:
        resp = requests.post(
            f"{endpoint}/v1/audio/transcriptions",
            files={"file": ("audio.wav", f, "audio/wav")},
            data=data,
            timeout=REMOTE_TIMEOUT,
        )
    resp.raise_for_status()

    text = resp.json()["text"].strip()
    # ASR was the one stage with no timing of its own, so every discussion of where
    # a dictation spends its time had to guess at the largest single piece.
    log.info(f"asr    {time.time() - started:.2f}s  remote  {len(text)} chars")

    try:
        os.unlink(raw_wav_path)
    except OSError:
        pass
    return text


def transcribe(raw_wav_path: str, prefs: Preferences = None) -> str:
    """
    Transcribe a recorded WAV with Qwen3-ASR.

    miniaudio decodes and resamples the WAV to 16 kHz mono, so no external
    ffmpeg or SciPy runtime is needed. Cleans up the temp file after processing.
    """
    if prefs is None:
        prefs = Preferences()

    from vvrite.locales import ASR_LANGUAGE_MAP

    endpoint = _endpoint(prefs)
    if endpoint:
        try:
            text = _transcribe_remote(raw_wav_path, prefs, endpoint, ASR_LANGUAGE_MAP)
            return _correct(text, prefs) if prefs.stt_correction else text
        except Exception as e:
            # The server is down or unreachable. Fall through to the on-device model
            # rather than losing the dictation — but only if it is already downloaded,
            # since a multi-GB download is not an acceptable surprise mid-dictation.
            if not (_model is not None or _is_downloaded(prefs.model_id)):
                raise RuntimeError(
                    f"{e}\nNo local model to fall back to. Recording kept at: {raw_wav_path}"
                ) from e
            log.info(f"Remote ASR failed ({e}), falling back to on-device model.")
            if _model is None:
                load_from_local(snapshot_download(repo_id=prefs.model_id, local_files_only=True))

    # The model loads in a background thread at launch, so a dictation started
    # during those first seconds would otherwise hit _model = None. Load it here
    # rather than losing the recording — slow once, correct always.
    if _model is None:
        load_from_local(snapshot_download(repo_id=prefs.model_id, local_files_only=True))

    try:
        kwargs = {"max_tokens": prefs.max_tokens}
        custom_words = prefs.custom_words.strip()
        if custom_words:
            kwargs["system_prompt"] = f"Use the following spellings: {custom_words}"

        asr_lang = prefs.asr_language
        if asr_lang != "auto":
            language_param = ASR_LANGUAGE_MAP.get(asr_lang)
            if language_param is None:
                log.info(f"Unknown ASR language code: {asr_lang}, falling back to auto-detect")
            else:
                kwargs["language"] = language_param

        started = time.time()
        audio = _decode_audio(raw_wav_path)
        result = _model.generate(audio, **kwargs)
        text = result.text.strip()
        log.info(f"asr    {time.time() - started:.2f}s  local   {len(text)} chars")
        return _correct(text, prefs) if prefs.stt_correction else text
    finally:
        try:
            os.unlink(raw_wav_path)
        except OSError:
            pass
