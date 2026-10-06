"""Proxy to the built-in Windows voice typing (the Win+H panel).

Windows exposes no API to that recogniser, so we toggle it with a synthetic Win+H.
Windows then types into the focused field itself and shows its own panel.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from .. import typer
from .base import Engine

VK_LWIN = 0x5B


class WindowsVoiceEngine(Engine):
    types_natively = True

    def start(self) -> None:
        typer.press_combo([VK_LWIN, ord("H")])
        self.started.emit()

    def stop(self) -> None:
        typer.press_combo([VK_LWIN, ord("H")])
        QTimer.singleShot(0, self.stopped.emit)
