"""Dictation session state machine: idle -> recording -> finishing -> idle."""

from __future__ import annotations

import logging
import threading
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import app_rules, typer
from . import winapi as w
from .cleanup import apply_corrections, clean, is_hallucination
from .config import CLIPBOARD_ALWAYS, CLIPBOARD_NEVER, Config
from .engines import Engine, create_engine
from .focus import focus_is_editable
from .live_text import Edit, LiveText
from .overlay import Overlay
from .overlay.textopts import TextOptions
from .terms import suggest_terms

log = logging.getLogger(__name__)

VK_RETURN = 0x0D


def _import_audio() -> None:
    import sounddevice  # noqa: F401  (~0.4 s import)


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    FINISHING = "finishing"


class Controller(QObject):
    state_changed = Signal(object)  # State
    notify = Signal(str, str)  # title, message (shown by the tray)
    terms_suggested = Signal(list)  # new words worth adding to the dictionary
    dictated = Signal(str)  # final text of the last dictation

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.state = State.IDLE
        self.overlay = Overlay(config.overlay_style, config.overlay_colors.get(config.overlay_style))
        self.overlay.text = TextOptions.from_dict(config.overlay_text)
        self.engine: Engine | None = None
        self.last_text = ""
        self._live = LiveText()
        self._target = None
        self._can_type = True  # focus was in a text field when dictation started
        self._missed = ""  # text we could not type because focus moved
        self._send_enter = False
        self._restart = False  # hotkey pressed while the previous dictation was finishing
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
        self.overlay.text = TextOptions.from_dict(config.overlay_text)
        if not self.overlay.demo_running:
            self.overlay.set_style(config.overlay_style, config.overlay_colors.get(config.overlay_style))
        if engine_changed:
            if self.state is not State.IDLE:
                self.engine.stop()
            self._set_engine(create_engine(config))
        elif hasattr(self.engine, "config"):
            self.engine.config = config  # language / dictionary apply on next pass

    def demo_style(self, key: str) -> None:
        """Show the chosen overlay style at the bottom of the screen with a fake dictation."""
        if self.state is not State.IDLE:
            return
        self.overlay.set_style(key, self.config.overlay_colors.get(key))
        self.overlay.demo()

    # --- session --------------------------------------------------------------
    @Slot()
    def toggle(self) -> None:
        log.info("toggle in state %s", self.state.value)
        if self.state is State.IDLE:
            process = app_rules.foreground_process()
            shortcut = app_rules.match(self.config.app_rules, process)
            if shortcut is not None:
                # e.g. VS Code: let the app's own dictation handle it
                log.info("%s: sending %s instead of dictating", process, shortcut)
                typer.press_combo(app_rules.combo_vks(shortcut))
                return
            self.start()
        elif self.state is State.RECORDING:
            self.stop()
        else:  # still typing the tail of the previous dictation: start again right after
            self._restart = True

    @Slot()
    def submit(self) -> None:
        """Enter while dictating: hide the overlay, finish typing, then press Enter."""
        if self.state is not State.RECORDING:
            return
        log.info("submit")
        self._send_enter = True
        self.stop()

    def start(self) -> None:
        self._target = w.user32.GetForegroundWindow()
        self._live = LiveText()
        self._missed = ""
        self._send_enter = False
        self._set_state(State.RECORDING)
        self.overlay.stop_demo()
        if self.config.show_overlay and not self.engine.types_natively:
            self.overlay.present()  # first, so the user sees a reaction immediately
        QTimer.singleShot(0, self._begin)

    def _begin(self) -> None:
        if self.state is not State.RECORDING:
            return
        self.engine.start()  # microphone first: every millisecond before it is lost speech
        editable = focus_is_editable()
        self._can_type = editable is not False
        log.info("focus editable: %s", editable)

    def warm_up(self) -> None:
        """Pay one-time costs at app start instead of on the first hotkey press."""
        focus_is_editable()  # UI Automation client: ~0.3 s the first time
        threading.Thread(target=_import_audio, name="warm-audio", daemon=True).start()

    def stop(self) -> None:
        self._set_state(State.FINISHING)
        # Hide right away: the last pass can take seconds, the tail is typed in the background.
        self.overlay.dismiss()
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
        text = apply_corrections(clean(text), self.config.corrections)
        if not text or is_hallucination(text):
            return
        edit = self._live.on_final(text)
        if self.config.live_typing and self._can_type:
            self._type(edit)
        self._refresh_overlay()

    @Slot(str)
    def _on_preview(self, text: str) -> None:
        self._live.hypothesis = text
        self._refresh_overlay()

    @Slot()
    def _on_stopped(self) -> None:
        text = self._live.committed.strip()
        if text and self._can_type and not self.config.live_typing:
            self._type(Edit(text=text))
        self._finish_clipboard(text)
        if self._send_enter and self._can_type and not self._missed:
            typer.press_combo([VK_RETURN])  # queued after the remaining text
        self._set_state(State.IDLE)
        log.info("dictation finished: %d chars", len(text))  # never log what was said
        if text:
            self.last_text = text
            self.dictated.emit(text)
            known = self.config.dictionary + self.config.ignored_terms + self.config.suggested_terms
            new_terms = suggest_terms(text, known)
            if new_terms:
                self.terms_suggested.emit(new_terms)
        if self._restart:
            self._restart = False
            self.start()

    def _finish_clipboard(self, text: str) -> None:
        if not text:
            return
        if self._missed:
            copy, reason = self._missed.strip(), "Окно сменилось во время диктовки — вставьте через Ctrl+V."
        elif not self._can_type and self.config.clipboard != CLIPBOARD_NEVER:
            copy, reason = text, "Курсор не стоял в поле ввода — вставьте через Ctrl+V."
        elif self.config.clipboard == CLIPBOARD_ALWAYS:
            copy, reason = text, ""
        else:
            return
        QGuiApplication.clipboard().setText(copy)
        if reason:
            self.notify.emit("Текст скопирован в буфер", reason)

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
