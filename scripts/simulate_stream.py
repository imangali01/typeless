"""Feed a WAV file into WhisperEngine in real time and print what would be typed, with lag.

Usage: python scripts/simulate_stream.py speech.wav [model]
"""

from __future__ import annotations

import sys
import threading
import time

from PySide6.QtCore import QCoreApplication, QTimer

sys.path.insert(0, ".")
from scripts.bench import load_wav  # noqa: E402
from typeless.config import Config  # noqa: E402
from typeless.engines.whisper import SAMPLE_RATE, WhisperEngine  # noqa: E402


def main() -> None:
    app = QCoreApplication([])
    audio = load_wav(sys.argv[1])
    config = Config(whisper_model=sys.argv[2] if len(sys.argv) > 2 else "base",
                    dictionary=["Kubernetes", "pull request", "README", "API"])
    engine = WhisperEngine(config)
    engine._ensure_model()
    t0 = time.monotonic()
    fed = [0.0]

    def feed() -> None:
        block = 1600
        for i in range(0, len(audio), block):
            engine._chunks.put(audio[i:i + block])
            fed[0] = (i + block) / SAMPLE_RATE
            time.sleep(block / SAMPLE_RATE)
        engine._stop.set()  # same as pressing the hotkey again

    engine.final.connect(lambda t: print(f"[{time.monotonic() - t0:5.1f}s, audio {fed[0]:4.1f}s] TYPE: {t}"))
    engine.stopped.connect(app.quit)
    engine._stop.clear()
    threading.Thread(target=engine._run, daemon=True).start()
    threading.Thread(target=feed, daemon=True).start()
    QTimer.singleShot(60_000, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
