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


def apply_corrections(text: str, corrections: dict[str, str]) -> str:
    """User's fixes for words the model keeps getting wrong ("ттермен" -> "термин")."""
    for wrong, right in corrections.items():
        if not wrong.strip():
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(wrong.strip())}(?!\w)", re.IGNORECASE)

        def repl(m: re.Match, right: str = right) -> str:
            # keep a capital letter at the start of a sentence
            if m.group(0)[:1].isupper() and right[:1].islower():
                return right[:1].upper() + right[1:]
            return right

        text = pattern.sub(repl, text)
    return text
