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


if __name__ == "__main__":
    unittest.main()
