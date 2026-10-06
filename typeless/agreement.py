"""LocalAgreement-2: a word is confirmed once two consecutive hypotheses agree on it.

Hypotheses come from re-transcribing a growing audio buffer; word times are absolute
seconds since the start of the dictation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PUNCT = re.compile(r"[^\w]+", re.UNICODE)


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str  # as produced by the model, may carry punctuation

    @property
    def norm(self) -> str:
        return _PUNCT.sub("", self.text).lower()


def _drop_overlap(committed: list[Word], words: list[Word], max_n: int = 5) -> list[Word]:
    """Drop leading words that repeat the tail of what is already committed."""
    for n in range(min(max_n, len(committed), len(words)), 0, -1):
        if [w.norm for w in committed[-n:]] == [w.norm for w in words[:n]]:
            return words[n:]
    return words


class LocalAgreement:
    def __init__(self, tolerance: float = 0.1) -> None:
        self.tolerance = tolerance
        self.committed: list[Word] = []
        self._prev: list[Word] = []

    @property
    def committed_end(self) -> float:
        return self.committed[-1].end if self.committed else 0.0

    def _fresh(self, words: list[Word]) -> list[Word]:
        fresh = [w for w in words if w.start >= self.committed_end - self.tolerance and w.norm]
        return _drop_overlap(self.committed, fresh)

    def update(self, words: list[Word]) -> tuple[list[Word], list[Word]]:
        """Feed a new hypothesis; returns (newly confirmed words, tentative tail)."""
        cur = self._fresh(words)
        n = 0
        while n < len(cur) and n < len(self._prev) and cur[n].norm == self._prev[n].norm:
            n += 1
        confirmed, tail = cur[:n], cur[n:]
        self.committed += confirmed
        self._prev = tail
        return confirmed, tail

    def flush(self, words: list[Word]) -> list[Word]:
        """Final hypothesis at the end of dictation: everything new is confirmed."""
        rest = self._fresh(words)
        self.committed += rest
        self._prev = []
        return rest


_SENTENCE_END = (".", "!", "?", "…", ",", ";", ":")  # clause ends are safe cut points too


def trim_point(committed: list[Word], offset: float, buffer_s: float, soft: float, hard: float) -> float | None:
    """Absolute time to cut the audio buffer at, or None to keep it.

    Past `soft` seconds we cut after the last confirmed sentence, so the model never
    restarts mid-sentence (which makes it invent full stops); past `hard` we cut at
    the last confirmed word anyway to keep passes fast.
    """
    if buffer_s <= soft:
        return None
    inside = [w for w in committed if w.end > offset]
    for w in reversed(inside):
        if w.text.strip().endswith(_SENTENCE_END):
            return w.end
    if buffer_s > hard and inside:
        return inside[-1].end
    return None


def join_words(words: list[Word]) -> str:
    # Whisper words carry their own leading space (" слово"); normalise to single spaces.
    return " ".join(w.text.strip() for w in words if w.text.strip())
