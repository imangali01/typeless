"""Dictation session state machine: idle -> recording -> finishing -> idle."""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import typer
from . import winapi as w
from .cleanup import clean, is_hallucination
from .config import Config
from .engines import Engine, create_engine
from .live_text import Edit, LiveText
from .overlay import Overlay

log = logging.getLogger(__name__)

VK_RETURN = 0x0D


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    FINISHING = "finishing"


class Controller(QObject):
    state_changed = Signal(object)  # State
    notify = Signal(str, str)  # title, message (shown by the tray)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.state = State.IDLE
        self.overlay = Overlay()
        self.engine: Engine | None = None
        self._live = LiveText()
        self._target = None
        self._missed = ""  # text we could not type because focus moved
        self._send_enter = False
        self._set_engine(create_engine(config))

    # --- engine wiring --------------------------------------------------------
    def _set_engine(self, engine: Engine) -> None:
        if self.engine is not None:
            self.engine.shutdown()
            self.engine.deleteLater()
        self.engine = engine
        engine.started.connect(self._on_started)
        engine.stopped.connect(self._on_stopped)
        engine.final.connect(self._on_final)
        engine.preview.connect(self._on_preview)
        engine.level.connect(self.overlay.set_level)
        engine.status.connect(self.overlay.set_status)
        engine.error.connect(self._on_error)
        engine.preload()

    def apply_config(self, config: Config) -> None:
        engine_changed = (config.engine, config.whisper_model) != (
            self.config.engine, self.config.whisper_model)
        self.config = config
        if engine_changed:
            if self.state is not State.IDLE:
                self.engine.stop()
            self._set_engine(create_engine(config))
        elif hasattr(self.engine, "config"):
            self.engine.config = config  # language / dictionary apply on next pass

    # --- session --------------------------------------------------------------
    @Slot()
    def toggle(self) -> None:
        log.info("toggle in state %s", self.state.value)
        if self.state is State.IDLE:
            self.start()
        elif self.state is State.RECORDING:
            self.stop()

    @Slot()
    def submit(self) -> None:
        """Enter while dictating: hide the overlay, finish typing, then press Enter."""
        if self.state is not State.RECORDING:
            return
        log.info("submit")
        self._send_enter = True
        self.overlay.dismiss()
        self.stop()

    def start(self) -> None:
        self._target = w.user32.GetForegroundWindow()
        self._live = LiveText()
        self._missed = ""
        self._send_enter = False
        self._set_state(State.RECORDING)
        if self.config.show_overlay and not self.engine.types_natively:
            self.overlay.present()
        self.engine.start()

    def stop(self) -> None:
        self._set_state(State.FINISHING)
        self.overlay.active = False
        self.engine.stop()

    def _set_state(self, state: State) -> None:
        self.state = state
        self.state_changed.emit(state)

    # --- engine events ----------------------------------------------------------
    @Slot()
    def _on_started(self) -> None:
        log.info("dictation started")

    @Slot(str)
    def _on_final(self, text: str) -> None:
        text = clean(text)
        if not text or is_hallucination(text):
            return
        edit = self._live.on_final(text)
        if self.config.live_typing:
            self._type(edit)
        self._refresh_overlay()

    @Slot(str)
    def _on_preview(self, text: str) -> None:
        self._live.hypothesis = text
        self._refresh_overlay()

    @Slot()
    def _on_stopped(self) -> None:
        if not self.config.live_typing and self._live.committed:
            self._type(Edit(text=self._live.committed))
        if self._missed:
            QGuiApplication.clipboard().setText(self._missed.strip())
            self.notify.emit("Текст в буфере обмена",
                             "Окно сменилось во время диктовки — вставьте текст через Ctrl+V.")
        if self._send_enter:
            if not self._missed:
                typer.press_combo([VK_RETURN])  # queued after the remaining text
        else:
            self._refresh_overlay()
            self.overlay.finish()
        self._set_state(State.IDLE)
        log.info("dictation finished: %r", self._live.committed)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.overlay.set_status(message)
        self.notify.emit("Typeless", message)

    # --- helpers --------------------------------------------------------------
    def _type(self, edit: Edit) -> None:
        if not edit:
            return
        if w.user32.GetForegroundWindow() != self._target:
            self._missed += edit.text
            return
        typer.apply(edit)

    def _refresh_overlay(self) -> None:
        confirmed, tail = self._live.display()
        self.overlay.set_text(confirmed, tail)

    def shutdown(self) -> None:
        if self.engine is not None:
            self.engine.shutdown()
