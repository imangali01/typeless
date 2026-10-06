"""Feed a WAV file into WhisperEngine in real time; print what would be typed and timings.

Usage: python scripts/simulate_stream.py speech.wav [model] [repeat]

`repeat` concatenates the file N times to simulate a long dictation. At the end it
prints how long the final pass took after "stop" and the average typing lag
(time a fragment was emitted minus the audio time it ends at).
"""

from __future__ import annotations

import sys
import threading
import time

import numpy as np
from PySide6.QtCore import QCoreApplication, QTimer

sys.path.insert(0, ".")
from scripts.bench import load_wav  # noqa: E402
from typeless.agreement import Word  # noqa: E402
from typeless.config import Config  # noqa: E402
from typeless.engines.whisper import SAMPLE_RATE, WhisperEngine  # noqa: E402


def main() -> None:
    app = QCoreApplication([])
    audio = load_wav(sys.argv[1])
    repeat = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    audio = np.concatenate([audio] * repeat)
    config = Config(whisper_model=sys.argv[2] if len(sys.argv) > 2 else "base",
                    dictionary=["Kubernetes", "pull request", "README", "API"])
    engine = WhisperEngine(config)
    engine._ensure_model()
    t0 = time.monotonic()
    stop_at: list[float] = []
    lags: list[float] = []
    texts: list[str] = []

    # measure lag from word timestamps: wrap _emit to see the confirmed words
    original_emit = engine._emit

    def emit(words: list[Word]) -> None:
        if words:
            now = time.monotonic() - t0
            if not stop_at:
                lags.append(now - words[-1].end)
        original_emit(words)

    engine._emit = emit

    def feed() -> None:
        block = 1600
        for i in range(0, len(audio), block):
            engine._chunks.put(audio[i:i + block])
            time.sleep(block / SAMPLE_RATE)
        stop_at.append(time.monotonic())
        engine._stop.set()  # same as pressing the hotkey again

    def done() -> None:
        finish = time.monotonic() - stop_at[0] if stop_at else float("nan")
        print(f"\nTEXT: {' '.join(texts)}")
        print(f"audio {len(audio) / SAMPLE_RATE:.1f}s | avg lag {np.mean(lags):.2f}s "
              f"(max {np.max(lags):.2f}s) | stop -> done {finish:.2f}s")
        app.quit()

    engine.final.connect(texts.append)
    engine.stopped.connect(done)
    engine._stop.clear()
    threading.Thread(target=engine._run, daemon=True).start()
    threading.Thread(target=feed, daemon=True).start()
    QTimer.singleShot(180_000, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
