"""Tests for the Qwen-only mlx-audio import boundary."""

import importlib
import sys
import unittest

from vvrite.mlx_runtime import (
    _MODELS_PACKAGE,
    install_qwen_only_model_namespace,
)


class TestQwenOnlyModelNamespace(unittest.TestCase):
    def setUp(self):
        self._saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == _MODELS_PACKAGE or name.startswith(f"{_MODELS_PACKAGE}.")
        }
        for name in self._saved_modules:
            sys.modules.pop(name, None)

    def tearDown(self):
        for name in list(sys.modules):
            if name == _MODELS_PACKAGE or name.startswith(f"{_MODELS_PACKAGE}."):
                sys.modules.pop(name, None)
        sys.modules.update(self._saved_modules)

    def test_installs_idempotent_namespace(self):
        self.assertTrue(install_qwen_only_model_namespace())
        self.assertFalse(install_qwen_only_model_namespace())

        namespace = sys.modules[_MODELS_PACKAGE]
        self.assertTrue(namespace.__path__[0].endswith("mlx_audio/stt/models"))
        self.assertEqual(
            list(namespace.__spec__.submodule_search_locations),
            list(namespace.__path__),
        )

    def test_imports_qwen_without_eager_sibling_models(self):
        install_qwen_only_model_namespace()

        module = importlib.import_module(f"{_MODELS_PACKAGE}.qwen3_asr")

        self.assertTrue(hasattr(module, "Model"))
        self.assertNotIn(f"{_MODELS_PACKAGE}.whisper", sys.modules)
        self.assertNotIn(f"{_MODELS_PACKAGE}.voxtral", sys.modules)


if __name__ == "__main__":
    unittest.main()
