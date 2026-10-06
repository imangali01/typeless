"""Compare recognition settings on a real recording: word error rate and speed.

Usage: python scripts/compare.py sample.wav sample.txt

Runs whole-file transcription for each configuration and prints WER (lower is
better) and seconds per pass. Close other heavy programs while it runs.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from faster_whisper import WhisperModel  # noqa: E402

from scripts.bench import load_wav  # noqa: E402
from typeless.languages import build_prompt  # noqa: E402

CONFIGS = [  # model, language mode, profile
    ("base", "ru_en", "general"),
    ("base", "ru_en", "coder"),
    ("small", "ru_en", "general"),
    ("small", "ru_en", "coder"),
]


def words(text: str) -> list[str]:
    return re.findall(r"[\w'+#.-]+", text.lower().replace("ё", "е"))


def wer(ref: list[str], hyp: list[str]) -> float:
    """Word error rate via edit distance."""
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[len(hyp)] / max(1, len(ref))


def main() -> None:
    audio = load_wav(sys.argv[1])
    ref = words(Path(sys.argv[2]).read_text(encoding="utf-8"))
    models: dict[str, WhisperModel] = {}
    print(f"audio {len(audio) / 16000:.1f}s, reference {len(ref)} words\n")
    for model_name, mode, profile in CONFIGS:
        model = models.setdefault(model_name, WhisperModel(model_name, device="cpu", compute_type="int8",
                                                           cpu_threads=4))
        prompt = build_prompt(mode, profile, [], "")
        t = time.monotonic()
        segments, _ = model.transcribe(audio, language="ru", beam_size=1, vad_filter=True,
                                       condition_on_previous_text=False, initial_prompt=prompt,
                                       temperature=0.0)
        text = " ".join(s.text.strip() for s in segments)
        took = time.monotonic() - t
        print(f"{model_name:5} {mode:5} {profile:7}  WER {wer(ref, words(text)) * 100:5.1f}%  "
              f"{took:5.1f}s ({took / (len(audio) / 16000):.2f}x realtime)")
        print(f"      {text[:160]}\n")


if __name__ == "__main__":
    main()
