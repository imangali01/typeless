"""Common interface of speech engines. Signals may be emitted from any thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Engine(QObject):
    started = Signal()
    stopped = Signal()  # all results delivered, engine idle again
    final = Signal(str)  # confirmed text fragment, safe to type
    preview = Signal(str)  # tentative tail, shown in the overlay only
    level = Signal(float)  # microphone level 0..1 for the waveform
    status = Signal(str)  # short human-readable state ("Загрузка модели…")
    error = Signal(str)

    #: True when the engine inserts text itself (we must not type or show text).
    types_natively = False

    def preload(self) -> None:
        """Heavy initialisation done once at app start (may run in background)."""

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        """Release resources on app exit."""
