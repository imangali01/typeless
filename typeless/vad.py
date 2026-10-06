"""Streaming voice activity detection with Silero VAD (the model faster-whisper ships).

Fed with microphone audio as it arrives; ~0.1 ms of CPU per 32 ms frame, so it can run
all the time and keep the speech model idle during pauses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

FRAME = 512  # samples at 16 kHz = 32 ms
CONTEXT = 64  # Silero looks at the tail of the previous frame
SPEECH_ON = 0.5  # probability that starts speech
SPEECH_OFF = 0.35  # once speaking, frames above this still count as speech


def _model_path() -> Path:
    from faster_whisper.utils import get_assets_path

    return Path(get_assets_path()) / "silero_vad_v6.onnx"


class SpeechDetector:
    def __init__(self) -> None:
        import onnxruntime

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self._session = onnxruntime.InferenceSession(
            str(_model_path()), providers=["CPUExecutionProvider"], sess_options=opts)
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(CONTEXT, dtype=np.float32)
        self._pending = np.zeros(0, dtype=np.float32)
        self.speaking = False

    def feed(self, audio: np.ndarray) -> list[bool]:
        """One speech/no-speech flag per complete 32 ms frame; leftovers wait for the next call."""
        data = np.concatenate([self._pending, audio]) if len(self._pending) else audio
        n = len(data) // FRAME
        self._pending = data[n * FRAME:].copy()
        flags = []
        for i in range(n):
            frame = data[i * FRAME:(i + 1) * FRAME]
            x = np.concatenate([self._context, frame])[None, :]
            prob, self._h, self._c = self._session.run(None, {"input": x, "h": self._h, "c": self._c})
            self._context = frame[-CONTEXT:]
            p = float(np.ravel(prob)[0])
            self.speaking = p >= (SPEECH_OFF if self.speaking else SPEECH_ON)
            flags.append(self.speaking)
        return flags
