"""Measure faster-whisper speed on this CPU.

Usage: python scripts/bench.py path/to/speech.wav [model ...]
"""

from __future__ import annotations

import sys
import time
import wave

import numpy as np
from faster_whisper import WhisperModel


def load_wav(path: str) -> np.ndarray:
    with wave.open(path) as f:
        assert f.getframerate() == 16000 and f.getnchannels() == 1 and f.getsampwidth() == 2
        return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def main() -> None:
    audio = load_wav(sys.argv[1])
    models = sys.argv[2:] or ["base", "small"]
    print(f"audio: {len(audio) / 16000:.1f}s")
    for name in models:
        t = time.monotonic()
        model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=8)
        print(f"\n[{name}] load {time.monotonic() - t:.1f}s")
        for seconds in (3, 6, 10):
            chunk = audio[: seconds * 16000]
            t = time.monotonic()
            segments, _ = model.transcribe(chunk, language="ru", beam_size=1, word_timestamps=True,
                                           vad_filter=True, condition_on_previous_text=False)
            text = " ".join(s.text.strip() for s in segments)
            print(f"  {seconds:>2}s audio -> {time.monotonic() - t:.2f}s  {text}")


if __name__ == "__main__":
    main()
