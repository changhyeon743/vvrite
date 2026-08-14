"""Minimal Transformers hook for Qwen3-ASR inference.

The upstream PyInstaller hook copies source files and metadata for every
optional Transformers integration found in the build environment.  vvrite uses
only Qwen2 tokenization and Whisper feature extraction, neither of which needs
TorchScript source files.  Keep only metadata that Transformers validates at
import time and let normal PyInstaller analysis collect the used modules.
"""

from PyInstaller.utils.hooks import copy_metadata


datas = []

for distribution in (
    "transformers",
    "tqdm",
    "regex",
    "requests",
    "packaging",
    "filelock",
    "numpy",
    "tokenizers",
    "huggingface-hub",
    "safetensors",
    "PyYAML",
):
    datas += copy_metadata(distribution)
