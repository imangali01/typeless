"""Snapping near-miss spellings of known terms ("ClickHourse") to the dictionary ("ClickHouse").

Parakeet and GigaAM take no prompt, so the dictionary can't steer them the way it steers
Whisper; instead their output is fixed up afterwards. Only Latin words are touched and
only close matches of longer terms, so ordinary words are never "corrected".
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .languages import CODER_TERMS, PROFILE_CODER

_LATIN_WORD = re.compile(r"(?<![\w.])[A-Za-z][A-Za-z0-9.+#-]*[A-Za-z0-9+#]|(?<![\w.])[A-Za-z]")
MIN_FUZZY_LEN = 5  # "test" vs "text" is a real difference; "ClickHourse" vs "ClickHouse" is not
MIN_RATIO = 0.84


def vocabulary(dictionary: list[str], profile: str) -> list[str]:
    terms = list(dictionary)
    if profile == PROFILE_CODER:
        terms += CODER_TERMS
    return [t for t in terms if t.strip() and " " not in t.strip()]


def fix_terms(text: str, terms: list[str]) -> str:
    if not terms:
        return text
    by_lower = {}
    for t in terms:  # the user's dictionary comes first and wins
        by_lower.setdefault(t.lower(), t)

    def repl(m: re.Match) -> str:
        word = m.group(0)
        low = word.lower()
        if low in by_lower:  # "github" -> "GitHub"; "Readme" -> "README"
            return by_lower[low]
        if len(word) < MIN_FUZZY_LEN:
            return word
        best, score = word, MIN_RATIO
        for key, term in by_lower.items():
            if len(term) < MIN_FUZZY_LEN or abs(len(key) - len(low)) > 2:
                continue
            r = SequenceMatcher(None, low, key).ratio()
            if r >= score:
                best, score = term, r
        return best

    return _LATIN_WORD.sub(repl, text)
