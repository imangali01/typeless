"""Record a speech sample from the microphone for benchmarks.

Usage: python scripts/record_sample.py out.wav [seconds]

Read a prepared text aloud (with the English terms you really use); save that text
next to the WAV as out.txt — scripts/compare.py uses it as the reference.
"""

from __future__ import annotations

import sys
import wave

import numpy as np
import sounddevice as sd

RATE = 16_000


def main() -> None:
    out = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(f"Запись {seconds:.0f} с… говорите.")
    audio = sd.rec(int(seconds * RATE), samplerate=RATE, channels=1, dtype="float32")
    sd.wait()
    pcm = (np.clip(audio[:, 0], -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())
    print(f"Сохранено: {out}")


if __name__ == "__main__":
    main()
