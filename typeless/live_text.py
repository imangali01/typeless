"""Turns a stream of recognizer hypotheses/final phrases into edits for the target field.

Edits are append-only except for the phrase currently being dictated: when the final
result of a phrase arrives (with punctuation and capitalization), the part of that
phrase we typed from hypotheses is corrected with backspaces.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Edit:
    backspaces: int = 0
    text: str = ""

    def __bool__(self) -> bool:
        return bool(self.backspaces or self.text)


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


class LiveText:
    def __init__(self, live: bool = True) -> None:
        self.live = live
        self.committed = ""  # final text of finished phrases (as typed)
        self.typed = ""  # what we typed for the current phrase, including its leading space
        self.hypothesis = ""  # latest raw hypothesis, for the overlay

    def _prefix(self) -> str:
        return " " if self.committed and not self.committed.endswith((" ", "\n")) else ""

    def on_hypothesis(self, text: str) -> Edit:
        self.hypothesis = text.strip()
        if not self.live:
            return Edit()
        words = self.hypothesis.split()
        stable = " ".join(words[:-1])  # the last word is still likely to change
        if not stable:
            return Edit()
        target = self._prefix() + stable
        if target.startswith(self.typed) and len(target) > len(self.typed):
            extra = target[len(self.typed):]
            self.typed = target
            return Edit(text=extra)
        return Edit()  # hypothesis revised earlier words: wait for the final result

    def on_final(self, text: str) -> Edit:
        text = text.strip()
        self.hypothesis = ""
        if not text:
            # rejected phrase: remove whatever we typed for it
            edit = Edit(backspaces=len(self.typed))
            self.typed = ""
            return edit
        target = self._prefix() + text
        keep = _common_prefix_len(self.typed, target)
        edit = Edit(backspaces=len(self.typed) - keep, text=target[keep:])
        self.committed += target
        self.typed = ""
        return edit

    def display(self) -> tuple[str, str]:
        """(confirmed text, tentative tail) for the overlay."""
        confirmed = (self.committed + self.typed).strip()
        tail = self.hypothesis
        if self.typed.strip() and tail.startswith(self.typed.strip()):
            tail = tail[len(self.typed.strip()):]
        return confirmed, tail.strip()
