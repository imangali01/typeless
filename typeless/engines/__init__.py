from __future__ import annotations

from ..config import ENGINE_WHISPER, Config
from .base import Engine


def create_engine(config: Config) -> Engine:
    if config.engine == ENGINE_WHISPER:
        from .whisper import WhisperEngine

        return WhisperEngine(config)
    from .onnx import OnnxEngine

    return OnnxEngine(config)
