"""Parakeet (NVIDIA) and GigaAM (Sber) through onnx-asr.

Unlike Whisper they don't pad audio to 30 s or generate text token by token: a pass over
a 3 s phrase takes ~0.3 s on two cores, and they can't loop or invent text on silence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..agreement import Word
from ..config import ENGINE_GIGAAM, ENGINE_PARAKEET, Config
from .streaming import SAMPLE_RATE, StreamingEngine

THREADS = 2  # measured on i5-13420H: as fast as 4 threads at half the CPU
LAST_WORD_S = 0.3  # timestamps mark where tokens start; assume the last word lasts this long


@dataclass(frozen=True)
class OnnxModel:
    repo: str
    quantization: str | None


MODELS = {
    ENGINE_PARAKEET: OnnxModel("nemo-parakeet-tdt-0.6b-v3", "int8"),
    ENGINE_GIGAAM: OnnxModel("gigaam-v3-e2e-ctc", "int8"),
}


def tokens_to_words(tokens: list[str], stamps: list[float], offset: float, audio_s: float) -> list[Word]:
    """A token starting with a space starts a word; others (sub-words, punctuation) extend it."""
    spans: list[list] = []  # [start, text]
    for tok, ts in zip(tokens, stamps):
        if tok.startswith(" ") or not spans:
            spans.append([ts if tok.strip() else None, tok.strip()])
        else:
            if spans[-1][0] is None:
                spans[-1][0] = ts
            spans[-1][1] += tok
    spans = [s for s in spans if s[1] and s[0] is not None]
    words = []
    for i, (start, text) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else min(audio_s, stamps[-1] + LAST_WORD_S)
        words.append(Word(offset + start, offset + max(end, start), " " + text))
    return words


class OnnxEngine(StreamingEngine):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._spec = MODELS[config.engine]

    @property
    def model_name(self) -> str:
        return self._spec.repo

    def _load(self):
        import onnx_asr
        import onnxruntime

        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = THREADS
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        # Idle worker threads would otherwise busy-wait between passes and burn whole cores.
        opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        return onnx_asr.load_model(self._spec.repo, quantization=self._spec.quantization,
                                   sess_options=opts).with_timestamps()

    def _recognize(self, model, audio: np.ndarray, offset: float, context: str, final: bool) -> list[Word]:
        result = model.recognize(audio)
        if not result.tokens:
            return []
        return tokens_to_words(result.tokens, result.timestamps, offset, len(audio) / SAMPLE_RATE)
