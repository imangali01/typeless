from __future__ import annotations

from ..config import ENGINE_WINDOWS, Config
from .base import Engine


def create_engine(config: Config) -> Engine:
    if config.engine == ENGINE_WINDOWS:
        from .windows_voice import WindowsVoiceEngine

        return WindowsVoiceEngine()
    from .whisper import WhisperEngine

    return WhisperEngine(config)
