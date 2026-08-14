"""Tests for transcriber download/load split."""
from array import array
import unittest
from unittest.mock import patch, MagicMock

import numpy as np


class TestGetModelSize(unittest.TestCase):
    @patch("vvrite.transcriber.model_info")
    def test_returns_size_in_bytes(self, mock_info):
        sibling = MagicMock()
        sibling.size = 600_000_000
        mock_info.return_value = MagicMock(siblings=[sibling, sibling])

        from vvrite.transcriber import get_model_size
        size = get_model_size("mlx-community/Qwen3-ASR-1.7B-8bit")
        self.assertEqual(size, 1_200_000_000)
        mock_info.assert_called_once_with("mlx-community/Qwen3-ASR-1.7B-8bit", files_metadata=True)

    @patch("vvrite.transcriber.model_info")
    def test_returns_zero_on_error(self, mock_info):
        mock_info.side_effect = Exception("network error")

        from vvrite.transcriber import get_model_size
        size = get_model_size("mlx-community/Qwen3-ASR-1.7B-8bit")
        self.assertEqual(size, 0)


class TestDownloadModel(unittest.TestCase):
    @patch("vvrite.transcriber.snapshot_download")
    def test_calls_snapshot_download(self, mock_dl):
        mock_dl.return_value = "/fake/path"

        from vvrite.transcriber import download_model
        path = download_model("test-model")
        self.assertEqual(path, "/fake/path")
        mock_dl.assert_called_once_with(repo_id="test-model")


class TestWarmUp(unittest.TestCase):
    def test_warm_up_runs_single_dummy_generate(self):
        import vvrite.transcriber as transcriber

        model = MagicMock()
        old_model = transcriber._model
        old_warmed_up = transcriber._warmed_up
        try:
            transcriber._model = model
            transcriber._warmed_up = False

            transcriber.warm_up()

            model.generate.assert_called_once()
            audio = model.generate.call_args.args[0]
            np.testing.assert_array_equal(
                audio,
                np.zeros(transcriber.SAMPLE_RATE // 2, dtype=np.float32),
            )
            self.assertEqual(model.generate.call_args.kwargs, {"max_tokens": 1})
            self.assertTrue(transcriber._warmed_up)
        finally:
            transcriber._model = old_model
            transcriber._warmed_up = old_warmed_up

    @patch("vvrite.transcriber._safe_warm_up")
    @patch("vvrite.transcriber.load_model", return_value=MagicMock())
    def test_load_from_local_triggers_warm_up(self, mock_load_model, mock_safe_warm_up):
        from vvrite.transcriber import load_from_local

        load_from_local("/tmp/model")

        mock_load_model.assert_called_once_with("/tmp/model")
        mock_safe_warm_up.assert_called_once_with()


class TestDecodeAudio(unittest.TestCase):
    @patch("vvrite.transcriber.miniaudio.decode_file")
    def test_decodes_as_mono_16khz_float32(self, mock_decode):
        from vvrite import transcriber

        mock_decode.return_value = MagicMock(samples=array("f", [0.25, -0.5]))

        audio = transcriber._decode_audio("/tmp/recording.wav")

        mock_decode.assert_called_once_with(
            "/tmp/recording.wav",
            output_format=transcriber.miniaudio.SampleFormat.FLOAT32,
            nchannels=1,
            sample_rate=transcriber.SAMPLE_RATE,
        )
        np.testing.assert_array_equal(
            audio,
            np.array([0.25, -0.5], dtype=np.float32),
        )


class TestRemoteEndpoint(unittest.TestCase):
    def _prefs(self, **kw):
        prefs = MagicMock()
        prefs.stt_endpoint = kw.get("stt_endpoint", "http://asr.local:8100/")
        prefs.custom_words = kw.get("custom_words", "")
        prefs.asr_language = kw.get("asr_language", "auto")
        prefs.stt_correction = kw.get("stt_correction", False)
        prefs.llm_endpoint = kw.get("llm_endpoint", "")
        prefs.llm_model = "test-model"
        prefs.llm_context = ""
        prefs.screen_context = kw.get("screen_context", False)
        return prefs

    @patch("vvrite.transcriber.os.unlink")
    def test_remote_posts_wav_and_returns_text(self, mock_unlink):
        from vvrite.transcriber import transcribe

        resp = MagicMock()
        resp.json.return_value = {"text": "  안녕하세요  "}
        requests = MagicMock()
        requests.post.return_value = resp

        with patch.dict("sys.modules", {"requests": requests}), \
                patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
            text = transcribe("/tmp/rec.wav", self._prefs(custom_words="vvrite", asr_language="ko"))

        self.assertEqual(text, "안녕하세요")
        url, = requests.post.call_args[0]
        self.assertEqual(url, "http://asr.local:8100/v1/audio/transcriptions")
        self.assertEqual(
            requests.post.call_args[1]["data"],
            {"prompt": "vvrite", "language": "Korean", "correction": "0"},
        )
        mock_unlink.assert_called_once_with("/tmp/rec.wav")

    @patch("vvrite.transcriber.os.unlink")
    def test_correction_runs_on_the_client_not_the_server(self, mock_unlink):
        """The server only transcribes; the LLM pass happens here, so the same
        correction applies whether the audio was handled locally or remotely."""
        from vvrite.transcriber import transcribe

        asr = MagicMock()
        asr.json.return_value = {"text": "교정 전"}
        llm = MagicMock()
        llm.json.return_value = {"choices": [{"message": {"content": " 교정 후 "}}]}
        requests = MagicMock()
        requests.post.side_effect = [asr, llm]

        with patch.dict("sys.modules", {"requests": requests}), \
                patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
            text = transcribe(
                "/tmp/rec.wav",
                self._prefs(stt_correction=True, llm_endpoint="http://llm.local:8000/v1/chat/completions"),
            )

        self.assertEqual(text, "교정 후")
        # The ASR request must not ask the server to correct as well.
        self.assertEqual(requests.post.call_args_list[0][1]["data"]["correction"], "0")
        self.assertEqual(requests.post.call_args_list[1][0][0],
                         "http://llm.local:8000/v1/chat/completions")

    @patch("vvrite.transcriber.os.unlink")
    def test_correction_failure_keeps_the_transcription(self, mock_unlink):
        """A dead LLM must cost the user nothing — the raw text still comes back."""
        from vvrite.transcriber import transcribe

        asr = MagicMock()
        asr.json.return_value = {"text": "원문 유지"}
        requests = MagicMock()
        requests.post.side_effect = [asr, OSError("connection refused")]

        with patch.dict("sys.modules", {"requests": requests}), \
                patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
            text = transcribe(
                "/tmp/rec.wav",
                self._prefs(stt_correction=True, llm_endpoint="http://llm.local:8000/v1/chat/completions"),
            )

        self.assertEqual(text, "원문 유지")

    @patch("vvrite.transcriber._decode_audio", return_value=np.zeros(16000, dtype=np.float32))
    @patch("vvrite.transcriber.os.unlink")
    @patch("vvrite.transcriber.snapshot_download", return_value="/fake/model")
    @patch("vvrite.transcriber.load_from_local")
    def test_remote_failure_falls_back_to_local_model(self, mock_load, mock_dl, mock_unlink,
                                                      mock_decode):
        import vvrite.transcriber as transcriber

        requests = MagicMock()
        requests.post.side_effect = OSError("connection refused")
        model = MagicMock()
        model.generate.return_value = MagicMock(text="  로컬 폴백  ")

        old_model = transcriber._model
        try:
            transcriber._model = model
            with patch.dict("sys.modules", {"requests": requests}), \
                    patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
                text = transcriber.transcribe("/tmp/rec.wav", self._prefs())
        finally:
            transcriber._model = old_model

        self.assertEqual(text, "로컬 폴백")
        model.generate.assert_called_once()
        mock_load.assert_not_called()  # already in memory, no reload
        mock_unlink.assert_called_once_with("/tmp/rec.wav")

    @patch("vvrite.transcriber.os.unlink")
    @patch("vvrite.transcriber._is_downloaded", return_value=False)
    def test_remote_failure_without_local_model_keeps_the_recording(self, mock_dl, mock_unlink):
        import vvrite.transcriber as transcriber

        requests = MagicMock()
        requests.post.side_effect = OSError("connection refused")

        old_model = transcriber._model
        try:
            transcriber._model = None
            with patch.dict("sys.modules", {"requests": requests}), \
                    patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
                with self.assertRaises(RuntimeError) as ctx:
                    transcriber.transcribe("/tmp/rec.wav", self._prefs())
        finally:
            transcriber._model = old_model

        self.assertIn("/tmp/rec.wav", str(ctx.exception))
        mock_unlink.assert_not_called()

    def test_empty_endpoint_means_on_device(self):
        import vvrite.transcriber as transcriber

        self.assertEqual(transcriber._endpoint(self._prefs(stt_endpoint="  ")), "")

    def test_bare_host_port_gets_an_http_scheme(self):
        import vvrite.transcriber as transcriber

        ep = transcriber._endpoint
        self.assertEqual(ep(self._prefs(stt_endpoint="asr.local:8100")), "http://asr.local:8100")
        self.assertEqual(ep(self._prefs(stt_endpoint="http://asr.local:8100/")), "http://asr.local:8100")
        self.assertEqual(ep(self._prefs(stt_endpoint="https://x/")), "https://x")

    @patch("vvrite.transcriber._is_downloaded", return_value=False)
    def test_endpoint_counts_as_ready_without_a_download(self, mock_downloaded):
        """Onboarding gates its Done button on these two, so a configured server has
        to satisfy both — otherwise a remote-only user is stuck at the download step."""
        import vvrite.transcriber as transcriber

        old_model = transcriber._model
        try:
            transcriber._model = None
            with patch("vvrite.transcriber.Preferences", return_value=self._prefs()):
                self.assertTrue(transcriber.is_model_loaded())
                self.assertTrue(transcriber.is_model_cached("any/model"))
            with patch("vvrite.transcriber.Preferences",
                       return_value=self._prefs(stt_endpoint="")):
                self.assertFalse(transcriber.is_model_loaded())
                self.assertFalse(transcriber.is_model_cached("any/model"))
        finally:
            transcriber._model = old_model


class TestScreenContext(unittest.TestCase):
    """On-screen words reach the corrector, but only as candidates."""

    def test_terms_appear_in_the_prompt(self):
        from vvrite.transcriber import _correction_prompt

        prompt = _correction_prompt("훅 얘기", "", "", ["useEffect", "nextbase-v3"])
        self.assertIn("useEffect, nextbase-v3", prompt)
        # Framed as "fix only if the pronunciation matches" — the window in front
        # is mostly unrelated to what was said, so these must not read as vocabulary.
        self.assertIn("들어맞지 않으면 무시한다", prompt)
        # The two worked examples are what make the rule fire at all.
        self.assertIn("콴트랩→quant-lab", prompt)

    def test_no_terms_means_no_extra_rule(self):
        from vvrite.transcriber import _correction_prompt

        self.assertNotIn("화면에 있던", _correction_prompt("아무 말", "", "", []))
        self.assertNotIn("화면에 있던", _correction_prompt("아무 말", "", "", None))

    @patch("vvrite.transcriber.os.unlink")
    def test_screen_terms_are_not_read_when_disabled(self, mock_unlink):
        import vvrite.screen as screen
        from vvrite.transcriber import transcribe

        asr = MagicMock()
        asr.json.return_value = {"text": "원문"}
        llm = MagicMock()
        llm.json.return_value = {"choices": [{"message": {"content": "교정"}}]}
        requests = MagicMock()
        requests.post.side_effect = [asr, llm]

        with patch.object(screen, "terms") as mock_terms, \
                patch.dict("sys.modules", {"requests": requests}), \
                patch("builtins.open", unittest.mock.mock_open(read_data=b"RIFF")):
            transcribe("/tmp/rec.wav", self._prefs())
        mock_terms.assert_not_called()

    def _prefs(self, **kw):
        return TestRemoteEndpoint._prefs(
            self, stt_correction=True,
            llm_endpoint="http://llm.local:8000/v1/chat/completions", **kw)


class TestLocalModelNotReady(unittest.TestCase):
    """A dictation fired before the background load finishes must still work."""

    @patch("vvrite.transcriber._decode_audio", return_value=np.zeros(16000, dtype=np.float32))
    @patch("vvrite.transcriber.os.unlink")
    @patch("vvrite.transcriber.snapshot_download", return_value="/fake/model")
    def test_loads_on_demand_when_model_is_none(self, mock_dl, mock_unlink, mock_decode):
        import vvrite.transcriber as transcriber

        prefs = MagicMock()
        prefs.stt_endpoint = ""
        prefs.stt_correction = False
        prefs.custom_words = ""
        prefs.asr_language = "auto"
        prefs.max_tokens = 128000
        prefs.model_id = "mlx-community/Qwen3-ASR-1.7B-8bit"

        loaded = MagicMock()
        loaded.generate.return_value = MagicMock(text=" 늦게 로드됨 ")

        def fake_load(path):
            transcriber._model = loaded

        old = transcriber._model
        try:
            transcriber._model = None
            with patch("vvrite.transcriber.load_from_local", side_effect=fake_load) as ld:
                text = transcriber.transcribe("/tmp/rec.wav", prefs)
            ld.assert_called_once_with("/fake/model")
        finally:
            transcriber._model = old

        self.assertEqual(text, "늦게 로드됨")


if __name__ == "__main__":
    unittest.main()


class TestOnboardingGate(unittest.TestCase):
    """Onboarding's Done button asks "can we transcribe?", not "is it in RAM?"."""

    @patch("vvrite.transcriber._is_downloaded", return_value=True)
    def test_downloaded_but_unloaded_model_can_proceed(self, mock_dl):
        """The weights are only loaded after onboarding, so gating on memory left
        anyone with the model already on disk unable to finish."""
        import vvrite.transcriber as transcriber

        old = transcriber._model
        try:
            transcriber._model = None
            prefs = MagicMock()
            prefs.stt_endpoint = ""
            with patch("vvrite.transcriber.Preferences", return_value=prefs):
                self.assertFalse(transcriber.is_model_loaded())
                self.assertTrue(transcriber.is_model_cached("any/model"))
        finally:
            transcriber._model = old
