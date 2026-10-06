"""Spotting words worth adding to the user's dictionary."""

from __future__ import annotations

import re

from .languages import CODER_TERMS

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9.+#/-]*[A-Za-z0-9+#]|[A-Za-z]{2}")
_COMMON_EN = {
    "the", "and", "for", "you", "are", "with", "this", "that", "not", "but", "was", "have",
    "ok", "okay", "yes", "no", "hi", "hello", "is", "it", "to", "of", "in", "on", "a", "an",
}


def suggest_terms(text: str, known: list[str], limit: int = 8) -> list[str]:
    """Latin-script words from a Russian dictation that the dictionary doesn't know yet."""
    known_low = {k.lower() for k in known} | {t.lower() for t in CODER_TERMS} | _COMMON_EN
    found: list[str] = []
    seen: set[str] = set()
    for match in _WORD.finditer(text):
        word = match.group(0).strip(".-/")
        low = word.lower()
        if len(word) < 2 or low in known_low or low in seen:
            continue
        seen.add(low)
        found.append(word)
        if len(found) >= limit:
            break
    return found
