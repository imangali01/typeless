"""Floating "pill" with a waveform and live text above it (see docs/references/*.png).

The window never takes focus and lets mouse clicks through, so typing into the
target field keeps working while it is visible.
"""

from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QVariantAnimation,
)
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

WIDTH, HEIGHT = 560, 190
PILL_W, PILL_H = 176, 44
BARS = 15
MAX_LINES = 3
LINE_OPACITY = (1.0, 0.6, 0.35)  # newest line first
TENTATIVE_ALPHA = 0.5
BOTTOM_MARGIN = 56


class Overlay(QWidget):
    def __init__(self) -> None:
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
        self.resize(WIDTH, HEIGHT)

        self.font = QFont("Segoe UI", 12)
        self.font.setItalic(True)
        self.metrics = QFontMetricsF(self.font)

        self.confirmed = ""
        self.tentative = ""
        self.status = ""
        self.active = False  # listening: bars follow the mic; otherwise they idle
        self._levels: deque[float] = deque([0.0] * BARS, maxlen=BARS)
        self._target_level = 0.0
        self._phase = 0.0
        self._known_words = 0  # words already revealed; newer ones fade in
        self._reveal = 1.0

        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._on_tick)

        self._reveal_anim = QVariantAnimation(self)
        self._reveal_anim.setDuration(240)
        self._reveal_anim.setStartValue(0.0)
        self._reveal_anim.setEndValue(1.0)
        self._reveal_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal_anim.valueChanged.connect(self._on_reveal)
        self._reveal_anim.finished.connect(self._on_reveal_done)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._slide = QPropertyAnimation(self, b"pos", self)
        for anim in (self._fade, self._slide):
            anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._on_fade_done)
        self._hiding = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

    # --- public API ----------------------------------------------------------
    def present(self) -> None:
        self._hide_timer.stop()
        self.confirmed = self.tentative = self.status = ""
        self._known_words = 0
        self.active = True
        screen = QGuiApplication.primaryScreen().availableGeometry()
        end = QPoint(screen.center().x() - WIDTH // 2, screen.bottom() - HEIGHT - BOTTOM_MARGIN)
        self._hiding = False
        self._slide.setStartValue(end + QPoint(0, 18))
        self._slide.setEndValue(end)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self.setWindowOpacity(0.0)
        self.move(end + QPoint(0, 18))
        self.show()
        self._tick.start()
        self._fade.start()
        self._slide.start()

    def finish(self, delay_ms: int = 1200) -> None:
        """Recording is over: settle the bars and fade out after a pause."""
        self.active = False
        self._hide_timer.start(delay_ms)

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self._hiding = True
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(self.pos() + QPoint(0, 18))
        self._fade.start()
        self._slide.start()

    def set_level(self, level: float) -> None:
        self._target_level = level

    def set_text(self, confirmed: str, tentative: str) -> None:
        if (confirmed, tentative) == (self.confirmed, self.tentative):
            return
        self.confirmed, self.tentative = confirmed, tentative
        self._reveal_anim.stop()
        self._reveal_anim.start()

    def set_status(self, text: str) -> None:
        self.status = text
        self.update()

    # --- animation plumbing ------------------------------------------------
    def _on_fade_done(self) -> None:
        if self._hiding:
            self._tick.stop()
            self.hide()

    def _on_reveal(self, value) -> None:
        self._reveal = float(value)
        self.update()

    def _on_reveal_done(self) -> None:
        self._known_words = len(self._tokens())
        self._reveal = 1.0

    def _on_tick(self) -> None:
        self._phase += 0.18
        if self.active:
            # New sample enters on the right; keep a little motion even in silence.
            self._levels.append(max(self._target_level, 0.06))
            self._target_level *= 0.6
        else:
            self._levels.append(self._levels[-1] * 0.7)
        self.update()

    # --- painting -----------------------------------------------------------
    def _tokens(self) -> list[tuple[str, bool]]:
        tokens = [(w, False) for w in self.confirmed.split()]
        tokens += [(w, True) for w in self.tentative.split()]
        if not tokens and self.status:
            tokens = [(w, True) for w in self.status.split()]
        return tokens

    def _layout(self, tokens, max_width: float):
        """Greedy word wrap -> list of lines, each a list of (index, word, tentative)."""
        lines, line, width = [], [], 0.0
        space = self.metrics.horizontalAdvance(" ")
        for i, (word, tentative) in enumerate(tokens):
            w = self.metrics.horizontalAdvance(word)
            if line and width + space + w > max_width:
                lines.append(line)
                line, width = [], 0.0
            width += (space if line else 0) + w
            line.append((i, word, tentative))
        if line:
            lines.append(line)
        return lines[-MAX_LINES:]

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pill = QRectF((WIDTH - PILL_W) / 2, HEIGHT - PILL_H - 4, PILL_W, PILL_H)
        self._paint_text(p, pill)
        self._paint_pill(p, pill)

    def _paint_pill(self, p: QPainter, pill: QRectF) -> None:
        p.setPen(QColor(255, 255, 255, 22))
        p.setBrush(QColor(14, 14, 16, 238))
        p.drawRoundedRect(pill, PILL_H / 2, PILL_H / 2)

        center = QPointF(pill.left() + 24, pill.center().y())
        radius = 11 + (1.2 if self.active else 0) * abs(math.sin(self._phase / 2))
        grad = QRadialGradient(center - QPointF(3, 3), radius * 1.4)
        grad.setColorAt(0.0, QColor("#8cc4ff"))
        grad.setColorAt(1.0, QColor("#2f6bff"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(center, radius, radius)

        left, right = pill.left() + 48, pill.right() - 18
        step = (right - left) / BARS
        for i, level in enumerate(self._levels):
            # Taller in the middle, like the reference waveform.
            envelope = 0.45 + 0.55 * (1 - abs(i - (BARS - 1) / 2) / ((BARS - 1) / 2))
            h = 4 + min(1.0, level * envelope) * (PILL_H - 16)
            x = left + i * step + step / 2 - 1.5
            p.setBrush(QColor(220, 220, 225, 225))
            p.drawRoundedRect(QRectF(x, pill.center().y() - h / 2, 3, h), 1.5, 1.5)

    def _paint_text(self, p: QPainter, pill: QRectF) -> None:
        tokens = self._tokens()
        if not tokens:
            return
        max_width = WIDTH - 48
        lines = self._layout(tokens, max_width)
        line_h = self.metrics.height() + 4
        widest = max(
            sum(self.metrics.horizontalAdvance(w) for _, w, _ in line)
            + self.metrics.horizontalAdvance(" ") * (len(line) - 1)
            for line in lines
        )
        panel = QRectF(0, 0, widest + 28, line_h * len(lines) + 14)
        panel.moveCenter(QPointF(WIDTH / 2, 0))
        panel.moveBottom(pill.top() - 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(28, 28, 30, 215))
        p.drawRoundedRect(panel, 12, 12)

        p.setFont(self.font)
        lift = (1 - self._reveal) * 8  # new text rises from below
        space = self.metrics.horizontalAdvance(" ")
        for row, line in enumerate(reversed(lines)):  # row 0 = newest, bottom line
            y = panel.bottom() - 9 - row * line_h + lift - self.metrics.descent()
            x = panel.left() + 14
            for index, word, tentative in line:
                alpha = LINE_OPACITY[min(row, len(LINE_OPACITY) - 1)]
                if tentative:
                    alpha *= TENTATIVE_ALPHA
                if index >= self._known_words:
                    alpha *= self._reveal
                color = QColor(232, 232, 236)
                color.setAlphaF(alpha)
                p.setPen(color)
                p.drawText(QPointF(x, y), word)
                x += self.metrics.horizontalAdvance(word) + space
