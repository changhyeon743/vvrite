"""On-screen text as correction context.

Speech recognition cannot get `powerbanksharing-kakao` or `CGWindowListCreateImage`
right from audio alone — there is nothing in the sound to disambiguate. But those
words are usually sitting on screen while you dictate about them, and macOS ships an
on-device OCR engine (Vision) that reads them in about a second for free.

So: capture the frontmost window when recording starts, OCR it while the user is
still speaking, and hand the identifiers to the corrector as a spelling list. By the
time the audio is transcribed the terms are ready, which is why this runs at *start*
rather than at stop — it makes the OCR cost nothing in wall-clock, and it captures
the screen the user was actually looking at when they spoke.
"""

import os
import re
import threading

_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{2,}")
# A plain short word ("use", "next", "main") is ordinary English the recognizer
# already gets right, and it would eat the term budget. Keep a token only when it
# looks engineered — punctuation, a digit, or camelCase — or is long enough that
# mishearing it is plausible.
_ENGINEERED_RE = re.compile(r"[0-9_.\-]|[a-z][A-Z]")
_MIN_PLAIN_LEN = 6
# The prompt has to stay small enough not to drown the transcription itself.
MAX_TERMS = 40
# A window narrower than this is a palette or an HUD, not something being read.
MIN_WINDOW_WIDTH = 400

_lock = threading.Lock()
_terms: list[str] = []
_thread: threading.Thread | None = None


def _frontmost_window_image():
    """CGImage of the frontmost ordinary window, or None.

    Skips vvrite's own windows: the recording overlay appears at almost the same
    moment as this capture, and OCRing our own UI would feed the corrector nothing
    but its own labels.
    """
    import Quartz

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    own_pid = os.getpid()
    for window in windows or []:
        if window.get("kCGWindowLayer") != 0:  # 0 == normal app window
            continue
        if window.get("kCGWindowOwnerPID") == own_pid:
            continue
        bounds = window["kCGWindowBounds"]
        if bounds["Width"] < MIN_WINDOW_WIDTH:
            continue
        return Quartz.CGWindowListCreateImage(
            Quartz.CGRectMake(bounds["X"], bounds["Y"], bounds["Width"], bounds["Height"]),
            Quartz.kCGWindowListOptionIncludingWindow,
            window["kCGWindowNumber"],
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
    return None


def _read_terms() -> list[str]:
    """OCR the frontmost window and return the identifiers found in it."""
    import Quartz  # noqa: F401  (imported for its side effect of loading the framework)
    import Vision

    image = _frontmost_window_image()
    if image is None:
        return []

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    # Accurate, not Fast: Fast mangles Hangul into latin lookalikes ("AgeTht",
    # "JUEtr") which then survive the identifier filter and invite the corrector to
    # invent words. Accurate reads Hangul as Hangul, so it never reaches the regex.
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["ko-KR", "en-US"])
    # Language correction would "fix" code tokens into English words.
    request.setUsesLanguageCorrection_(False)
    handler.performRequests_error_([request], None)

    text = " ".join(
        observation.topCandidates_(1)[0].string() for observation in (request.results() or [])
    )
    return extract_terms(text)


def extract_terms(text: str, max_terms: int = MAX_TERMS) -> list[str]:
    """Identifier-shaped words from OCR text, deduped case-insensitively."""
    seen, terms = set(), []
    for token in _TERM_RE.findall(text):
        if len(token) < _MIN_PLAIN_LEN and not _ENGINEERED_RE.search(token):
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(token)
        if len(terms) >= max_terms:
            break
    return terms


def capture_async():
    """Start reading the screen in the background. Safe to call when unsupported."""
    global _thread

    def run():
        try:
            found = _read_terms()
        except Exception as e:  # missing permission, no window, Vision unavailable
            print(f"Screen context skipped: {e}")
            found = []
        with _lock:
            global _terms
            _terms = found

    with _lock:
        _terms.clear()
    _thread = threading.Thread(target=run, daemon=True)
    _thread.start()


def terms(timeout: float = 2.0) -> list[str]:
    """Terms from the last capture. Waits briefly, then gives up.

    Giving up matters more than completeness: this is a hint, and a slow OCR must
    never hold a finished transcription hostage.
    """
    thread = _thread
    if thread is not None:
        thread.join(timeout)
        if thread.is_alive():
            print("Screen context skipped: OCR still running")
            return []
    with _lock:
        return list(_terms)


def demo():
    """Self-check: run `python -m vvrite.screen` with something readable on screen."""
    assert extract_terms("use useEffect in App.tsx ok") == ["useEffect", "App.tsx"]
    assert extract_terms("Foobar foobar FOOBAR") == ["Foobar"], "dedupe is case-insensitive"
    assert extract_terms("한글은 걸리지 않는다") == [], "Hangul is not an identifier"
    assert extract_terms("the and but for") == [], "plain short words are not identifiers"
    assert extract_terms("nextbase-v3 PostgREST vvrite") == [
        "nextbase-v3", "PostgREST", "vvrite"
    ], "hyphens, camelCase and long plain words all survive"
    assert len(extract_terms(" ".join(f"term{i}" for i in range(100)))) == MAX_TERMS

    import time

    start = time.time()
    capture_async()
    found = terms(30)  # the first Vision call in a process loads the framework
    print(f"{time.time() - start:.2f}s · {len(found)} terms")
    print(", ".join(found) or "(none — grant Screen Recording permission?)")


if __name__ == "__main__":
    demo()
