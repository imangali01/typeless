"""Rule-based cleanup of recognised fragments (no LLM)."""

from __future__ import annotations

import re

# Hesitation sounds: "э", "ээ", "эм", "ммм", "а-а" (whole words only).
_FILLERS = re.compile(r"(?<!\w)(?:э+м*|м{2,}|а-а+)(?!\w)[,.]?\s*", re.IGNORECASE)
# Classic Whisper hallucinations on silence / noise in Russian.
_HALLUCINATIONS = (
    "продолжение следует",
    "субтитры сделал",
    "субтитры создавал",
    "редактор субтитров",
    "спасибо за просмотр",
    "подписывайтесь на канал",
)


def is_hallucination(text: str) -> bool:
    low = text.lower()
    return any(h in low for h in _HALLUCINATIONS)


def clean(text: str) -> str:
    text = _FILLERS.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()
