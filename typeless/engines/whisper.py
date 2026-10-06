"""Local dictation with faster-whisper on CPU (slower than Parakeet, kept as an option)."""

from __future__ import annotations

import numpy as np

from ..agreement import Word
from ..languages import DEFAULT_LANGUAGE, LANGUAGE_MODES, build_prompt
from .streaming import SAMPLE_RATE, StreamingEngine

FINAL_BEAM = 5  # wider beam for the last pass of a phrase, only when it is short
FINAL_BEAM_MAX_S = 3.0
CPU_THREADS = 4  # measured on i5-13420H: ~as fast as 8 threads at half the CPU load
MAX_NEW_TOKENS = 200  # per pass; a 10 s buffer of fast speech is ~60-80 tokens


def _looks_hallucinated(seg) -> bool:
    """A segment that repeats itself ("что я не знаю, что я не знаю, …") or is
    low-confidence text over what the model itself calls silence."""
    if seg.compression_ratio > 2.4:
        return True
    return seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0


class WhisperEngine(StreamingEngine):
    @property
    def model_name(self) -> str:
        return f"whisper-{self.config.whisper_model}"

    def _load(self):
        from faster_whisper import WhisperModel

        return WhisperModel(self.config.whisper_model, device="cpu", compute_type="int8",
                            cpu_threads=CPU_THREADS)

    def _recognize(self, model, audio: np.ndarray, offset: float, context: str, final: bool) -> list[Word]:
        mode = LANGUAGE_MODES.get(self.config.language_mode, LANGUAGE_MODES[DEFAULT_LANGUAGE])
        prompt = build_prompt(self.config.language_mode, self.config.profile, self.config.dictionary, context)
        beam = FINAL_BEAM if final and len(audio) / SAMPLE_RATE <= FINAL_BEAM_MAX_S else 1
        segments, _ = model.transcribe(
            audio,
            language=mode.whisper,
            beam_size=beam,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            # No temperature fallback: on noisy audio the default re-decodes the same chunk
            # up to 6 times, which turned a stop into a 1.5-minute wait.
            temperature=0.0,
            # A looping model can't run away: ~3x more tokens than fast speech needs.
            max_new_tokens=MAX_NEW_TOKENS,
        )
        return [
            Word(offset + w.start, offset + w.end, w.word)
            for seg in segments
            if not _looks_hallucinated(seg)
            for w in (seg.words or [])
        ]
