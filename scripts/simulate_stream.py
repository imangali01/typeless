"""Feed a WAV file into an engine in real time; print what would be typed and timings.

Usage: python scripts/simulate_stream.py speech.wav [engine] [repeat] [reference.txt]

engine: parakeet (default), gigaam, whisper, whisper-small. `repeat` concatenates the
file N times to simulate a long dictation. Prints the typing lag (time a word was
emitted minus the time it was spoken), how long "stop" takes to finish, CPU seconds
used per second of audio (the load on the computer) and, with a reference, WER.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QTimer

sys.path.insert(0, ".")
from scripts.bench import load_wav  # noqa: E402
from scripts.compare import wer, words  # noqa: E402
from typeless.agreement import Word  # noqa: E402
from typeless.config import Config  # noqa: E402
from typeless.engines import create_engine  # noqa: E402
from typeless.engines.streaming import SAMPLE_RATE  # noqa: E402
from typeless.vocab import fix_terms, vocabulary  # noqa: E402


def main() -> None:
    app = QCoreApplication([])
    audio = load_wav(sys.argv[1])
    kind = sys.argv[2] if len(sys.argv) > 2 else "parakeet"
    repeat = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    ref = Path(sys.argv[4]).read_text(encoding="utf-8") if len(sys.argv) > 4 else None
    audio = np.concatenate([audio] * repeat + [np.zeros(SAMPLE_RATE, dtype=np.float32)])
    engine_name, _, size = kind.partition("-")
    config = Config(engine=engine_name, whisper_model=size or "base", profile="coder",
                    dictionary=["ClickHouse", "Slack", "README"])
    engine = create_engine(config)
    engine._ensure_model()
    t0 = time.monotonic()
    stop_at: list[float] = []
    lags: list[float] = []
    texts: list[str] = []

    original_emit = engine._emit

    def emit(ws: list[Word]) -> None:
        if ws and not stop_at:
            now = time.monotonic() - t0
            lags.extend(now - w.end for w in ws)
        original_emit(ws)

    engine._emit = emit

    def feed() -> None:
        block = 512
        for i in range(0, len(audio), block):
            engine._chunks.put(audio[i:i + block])
            time.sleep(block / SAMPLE_RATE)
        stop_at.append(time.monotonic())
        engine._stop.set()  # same as pressing the hotkey again

    cpu0 = time.process_time()

    def done() -> None:
        finish = time.monotonic() - stop_at[0] if stop_at else float("nan")
        cpu = (time.process_time() - cpu0) / (len(audio) / SAMPLE_RATE)
        text = fix_terms(" ".join(texts), vocabulary(config.dictionary, config.profile))
        print(f"\nTEXT: {text}")
        print(f"{kind}: audio {len(audio) / SAMPLE_RATE:.1f}s | lag avg {np.mean(lags):.2f}s "
              f"(p90 {np.percentile(lags, 90):.2f}s) | stop -> done {finish:.2f}s | CPU {cpu:.2f} s/s"
              + (f" | WER {wer(words(ref * repeat), words(text)):.3f}" if ref else ""))
        app.quit()

    engine.final.connect(texts.append)
    engine.stopped.connect(done)
    engine._stop.clear()
    threading.Thread(target=engine._run, daemon=True).start()
    threading.Thread(target=feed, daemon=True).start()
    QTimer.singleShot(300_000, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
