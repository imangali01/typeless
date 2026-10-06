"""The overlay window: shared state and animations; the look comes from a Style.

The window never takes focus and lets mouse clicks through, so typing into the
target field keeps working while it is visible.
"""

from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import anchor
from .styles import DEFAULT_STYLE, FOLLOW_CARET, FOLLOW_MOUSE, STYLES, Style

HISTORY = 24  # waveform samples kept


class Overlay(QWidget):
    def __init__(self, style: str = DEFAULT_STYLE) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.style_: Style = STYLES.get(style, STYLES[DEFAULT_STYLE])

        # state read by styles
        self.confirmed = ""
        self.tentative = ""
        self.status = ""
        self.active = False  # listening: waveform follows the mic
        self.levels: deque[float] = deque([0.0] * HISTORY, maxlen=HISTORY)
        self.phase = 0.0
        self.known_words = 0  # words already revealed; newer ones animate in
        self.reveal = 1.0
        self.presence = 0.0  # 0 hidden .. 1 fully shown

        self._target_level = 0.0
        self._ticks = 0
        self._caret = None

        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._on_tick)

        self._reveal_anim = self._anim(260, QEasingCurve.Type.OutCubic)
        self._reveal_anim.valueChanged.connect(self._on_reveal)
        self._reveal_anim.finished.connect(self._on_reveal_done)

        self._presence_anim = self._anim(280, QEasingCurve.Type.OutCubic)
        self._presence_anim.valueChanged.connect(self._on_presence)
        self._presence_anim.finished.connect(self._on_presence_done)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

        self._demo_timer = QTimer(self)
        self._demo_timer.setInterval(70)
        self._demo_timer.timeout.connect(self._demo_step)
        self._demo_words: list[str] = []
        self._demo_frame = 0

    def _anim(self, ms: int, curve: QEasingCurve.Type) -> QVariantAnimation:
        anim = QVariantAnimation(self)
        anim.setDuration(ms)
        anim.setEasingCurve(curve)
        return anim

    # --- public API ----------------------------------------------------------
    def set_style(self, key: str) -> None:
        self.style_ = STYLES.get(key, STYLES[DEFAULT_STYLE])
        if self.isVisible():
            self._place()

    @property
    def demo_running(self) -> bool:
        return self._demo_timer.isActive()

    def demo(self, text: str = "Так будет выглядеть диктовка: слова появляются, пока вы говорите") -> None:
        """Play a short fake dictation so the user can see the chosen style for real."""
        self._demo_words = text.split()
        self._demo_frame = 0
        self.present()
        self._demo_timer.start()

    def stop_demo(self) -> None:
        self._demo_timer.stop()

    def _demo_step(self) -> None:
        self._demo_frame += 1
        frame = self._demo_frame
        # speech-like level: bursts with short pauses
        self.set_level(0.0 if frame % 9 == 0 else 0.35 + 0.55 * abs(math.sin(frame * 0.9)))
        shown = min(len(self._demo_words), frame // 4)
        confirmed = " ".join(self._demo_words[:max(0, shown - 2)])
        tentative = " ".join(self._demo_words[max(0, shown - 2):shown])
        self.set_text(confirmed, tentative)
        if shown >= len(self._demo_words) and frame > len(self._demo_words) * 4 + 6:
            self.set_text(" ".join(self._demo_words), "")
            self._demo_timer.stop()
            self.finish(1000)

    def present(self) -> None:
        self._hide_timer.stop()
        self.confirmed = self.tentative = self.status = ""
        self.known_words = 0
        self.active = True
        self._caret = anchor.caret_rect() if self.style_.follows == FOLLOW_CARET else None
        self._place()
        self.show()
        self._tick.start()
        self._animate_presence(1.0)

    def finish(self, delay_ms: int = 800) -> None:
        """Recording is over: settle the waveform and fade out after a pause."""
        self.active = False
        self._hide_timer.start(delay_ms)

    def dismiss(self) -> None:
        self._hide_timer.stop()
        if self.isVisible():
            self._animate_presence(0.0)

    def set_level(self, level: float) -> None:
        self._target_level = max(self._target_level, level)

    def set_text(self, confirmed: str, tentative: str) -> None:
        if (confirmed, tentative) == (self.confirmed, self.tentative):
            return
        self.confirmed, self.tentative = confirmed, tentative
        self._reveal_anim.stop()
        self._reveal_anim.setStartValue(0.0)
        self._reveal_anim.setEndValue(1.0)
        self._reveal_anim.start()

    def set_status(self, text: str) -> None:
        self.status = text
        self.update()

    # --- helpers for styles ----------------------------------------------------
    def tokens(self) -> list[tuple[int, str, bool]]:
        words = [(w, False) for w in self.confirmed.split()] + [(w, True) for w in self.tentative.split()]
        if not words and self.status:
            words = [(w, True) for w in self.status.split()]
        return [(i, w, t) for i, (w, t) in enumerate(words)]

    def tail_text(self, max_words: int) -> tuple[str, str]:
        """Last words as (confirmed part, tentative part)."""
        tokens = self.tokens()[-max_words:]
        firm = " ".join(w for _, w, t in tokens if not t)
        soft = " ".join(w for _, w, t in tokens if t)
        return firm, soft

    # --- internals ---------------------------------------------------------------
    def _place(self) -> None:
        follows = self.style_.follows
        if follows == FOLLOW_CARET:
            point_rect = self._caret or anchor.mouse_rect()
            target = self._caret
        elif follows == FOLLOW_MOUSE:
            point_rect = target = anchor.mouse_rect()
        else:
            point_rect, target = anchor.mouse_rect(), None
        area = anchor.screen_for(point_rect.center())
        self.setGeometry(self.style_.geometry(area, target))

    def _animate_presence(self, end: float) -> None:
        self._presence_anim.stop()
        # snappy in, a touch softer out
        self._presence_anim.setDuration(170 if end > self.presence else 220)
        self._presence_anim.setEasingCurve(
            QEasingCurve.Type.OutCubic if end > self.presence else QEasingCurve.Type.InOutCubic)
        self._presence_anim.setStartValue(self.presence)
        self._presence_anim.setEndValue(end)
        self._presence_anim.start()

    def _on_presence(self, value) -> None:
        self.presence = float(value)
        self.setWindowOpacity(min(1.0, self.presence * 1.4))
        self.update()

    def _on_presence_done(self) -> None:
        if self.presence <= 0.001:
            self._tick.stop()
            self.hide()

    def _on_reveal(self, value) -> None:
        self.reveal = float(value)
        self.update()

    def _on_reveal_done(self) -> None:
        self.known_words = len(self.tokens())
        self.reveal = 1.0

    def _on_tick(self) -> None:
        self._ticks += 1
        self.phase += 0.16
        if self.active:
            self.levels.append(max(self._target_level, 0.05))
            self._target_level *= 0.55
        else:
            self.levels.append(self.levels[-1] * 0.8)
        follows = self.style_.follows
        if follows == FOLLOW_MOUSE:
            self._place()
        elif follows == FOLLOW_CARET and self._ticks % 6 == 0:
            self._caret = anchor.caret_rect() or self._caret  # caret moves as we type
            self._place()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.style_.paint(p, self, QRectF(self.rect()))
