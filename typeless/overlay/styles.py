"""Overlay looks. A style only decides where the window goes and paints it.

Every style reads the shared state of the Overlay widget (levels, text tokens,
reveal/presence animations) and draws it its own way.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
)

from .text import TextLook, block_size, draw_block, draw_bubble, layout

if TYPE_CHECKING:
    from .base import Overlay

FOLLOW_NONE, FOLLOW_CARET, FOLLOW_MOUSE = "none", "caret", "mouse"


def _font(size: float, weight: QFont.Weight = QFont.Weight.Normal, italic: bool = False) -> QFont:
    f = QFont("Segoe UI Variable Text", 1)
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
    f.setPointSizeF(size)
    f.setWeight(weight)
    f.setItalic(italic)
    return f


def _avg_level(o: Overlay, last: int = 4) -> float:
    vals = list(o.levels)[-last:]
    return sum(vals) / len(vals)


class Style:
    key = ""
    title = ""
    description = ""
    follows = FOLLOW_NONE

    def geometry(self, area: QRect, anchor: QRect | None) -> QRect:
        raise NotImplementedError

    def paint(self, p: QPainter, o: Overlay, rect: QRectF) -> None:
        raise NotImplementedError


# --- 1. Voice line -------------------------------------------------------------
class LineStyle(Style):
    key = "line"
    title = "Линия голоса"
    description = "Светящаяся линия внизу экрана дрожит от голоса, слова проявляются из размытия"
    HEIGHT = 290

    look = TextLook(font=_font(15, QFont.Weight.Medium), outline=QColor(0, 0, 0, 170),
                    blur_reveal=True, max_lines=2, line_opacity=(1.0, 0.55))

    def geometry(self, area, anchor):
        return QRect(area.left(), area.bottom() - self.HEIGHT, area.width(), self.HEIGHT)

    def paint(self, p, o, rect):
        presence = o.presence
        y = rect.bottom() - 30
        half = rect.width() * 0.42 * presence
        cx = rect.center().x()
        level = _avg_level(o)

        # faint shade keeps light text readable on any background
        shade = QLinearGradient(0, rect.top() + 40, 0, rect.bottom())
        shade.setColorAt(0.0, QColor(10, 10, 20, 0))
        shade.setColorAt(1.0, QColor(10, 10, 20, int(120 * presence)))
        p.fillRect(rect, shade)

        # Loudness history spread from the centre outwards: the newest sound is in the
        # middle, earlier syllables travel to the edges, like a live oscilloscope.
        history = list(o.levels)
        newest = len(history) - 1

        def envelope(t: float) -> float:
            pos = abs(t - 0.5) * 2 * newest  # 0 at the centre .. newest at the edges
            i = int(pos)
            frac = pos - i
            a = history[newest - min(i, newest)]
            b = history[newest - min(i + 1, newest)]
            return a + (b - a) * frac

        # three strands with different phases make a living ribbon
        for strand, (alpha, width, phase_k) in enumerate(((60, 7.0, 1.0), (140, 2.4, 1.6), (255, 1.4, 2.3))):
            path = QPainterPath()
            steps = 140
            for i in range(steps + 1):
                t = i / steps
                x = cx - half + 2 * half * t
                taper = math.sin(math.pi * t) ** 1.2
                amp = (1.5 + envelope(t) ** 1.1 * 52) * taper
                dy = amp * math.sin(t * 18 + o.phase * phase_k + strand) * math.sin(t * 5 - o.phase * 0.7)
                if i == 0:
                    path.moveTo(x, y + dy)
                else:
                    path.lineTo(x, y + dy)
            grad = QLinearGradient(cx - half, y, cx + half, y)
            for stop, color in zip((0.0, 0.5, 1.0), o.palette.colors()):
                c = QColor(color)
                c.setAlpha(int(alpha * presence))
                grad.setColorAt(stop, c)
            p.setPen(QPen(grad, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        look = o.text.look(self.look)
        tokens = o.tokens()
        if tokens:
            m = QFontMetricsF(look.font, p.device())
            lines = layout(tokens, m, min(900, rect.width() - 80), look.max_lines)
            area = QRectF(rect.left(), rect.top(), rect.width(), y - 62 - rect.top())  # clear of the wave
            draw_block(p, lines, look, area, known_words=o.known_words, reveal=o.reveal)


# --- 2. Drop at the caret ----------------------------------------------------
class DropStyle(Style):
    key = "drop"
    title = "Капля у курсора"
    description = "Живая капля рядом с местом ввода, черновик тянется за ней хвостиком"
    follows = FOLLOW_CARET
    W, H = 560, 80
    font = _font(11)

    def geometry(self, area, anchor):
        if anchor is None:
            return QRect(area.center().x() - self.W // 2, area.bottom() - self.H - 40, self.W, self.H)
        x = anchor.right() + 6
        y = anchor.center().y() - self.H // 2
        x = min(max(x, area.left()), area.right() - self.W)
        y = min(max(y, area.top()), area.bottom() - self.H)
        return QRect(x, y, self.W, self.H)

    def paint(self, p, o, rect):
        center = QPointF(rect.left() + 22, rect.center().y())
        level = _avg_level(o)
        base_r = (10 + level * 4) * o.presence
        path = QPainterPath()
        n = 48
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            wobble = 1 + (0.06 + level * 0.22) * math.sin(3 * a + o.phase * 1.3) * math.cos(2 * a - o.phase)
            pt = QPointF(center.x() + math.cos(a) * base_r * wobble, center.y() + math.sin(a) * base_r * wobble)
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        light, main, deep = o.palette.colors()
        grad = QRadialGradient(center - QPointF(base_r * 0.35, base_r * 0.45), base_r * 1.6)
        grad.setColorAt(0.0, light)
        grad.setColorAt(0.45, main)
        grad.setColorAt(1.0, deep)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(center, base_r * 2.4)
        halo = QColor(main)
        halo.setAlpha(int(90 * o.presence))
        glow.setColorAt(0.0, halo)
        halo.setAlpha(0)
        glow.setColorAt(1.0, halo)
        p.setBrush(glow)
        p.drawEllipse(center, base_r * 2.4, base_r * 2.4)
        p.setBrush(grad)
        p.drawPath(path)

        firm, soft = o.tail_text(10)
        if firm or soft:
            left = center.x() + 24
            draw_bubble(p, firm, soft, o.text.font(self.font), QPointF(left, center.y()), rect.right() - left - 4, o.presence)


# --- 3. Cinema subtitles -------------------------------------------------------
class CinemaStyle(Style):
    key = "cinema"
    title = "Киносубтитры"
    description = "Крупные субтитры по центру, слова загораются как в караоке, точка REC"
    HEIGHT = 300

    look = TextLook(font=_font(21, QFont.Weight.DemiBold), tentative_color=QColor(150, 150, 158),
                    outline=QColor(0, 0, 0, 200), max_lines=2, line_opacity=(1.0, 0.7), line_gap=6)

    def geometry(self, area, anchor):
        return QRect(area.left(), area.bottom() - self.HEIGHT, area.width(), self.HEIGHT)

    def paint(self, p, o, rect):
        shade = QLinearGradient(0, rect.top(), 0, rect.bottom())
        shade.setColorAt(0.0, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, int(185 * o.presence)))
        p.fillRect(rect, shade)

        # REC indicator
        pulse = 0.55 + 0.45 * abs(math.sin(o.phase * 0.5)) if o.active else 0.35
        dot = QPointF(rect.left() + 36, rect.bottom() - 34)
        p.setPen(Qt.PenStyle.NoPen)
        rec = QColor(o.palette.main)
        rec.setAlpha(int(255 * pulse * o.presence))
        p.setBrush(rec)
        p.drawEllipse(dot, 6, 6)
        p.setFont(_font(9.5, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255, int(200 * o.presence)))
        p.drawText(dot + QPointF(13, 5), "REC")
        for i, lv in enumerate(list(o.levels)[-8:]):
            h = 3 + lv * 16
            p.setBrush(QColor(255, 255, 255, int(150 * o.presence)))
            p.drawRoundedRect(QRectF(dot.x() + 50 + i * 5, dot.y() - h / 2, 2.5, h), 1, 1)

        look = o.text.look(self.look)
        tokens = o.tokens()
        if tokens:
            m = QFontMetricsF(look.font, p.device())
            lines = layout(tokens, m, min(1100, rect.width() - 200), look.max_lines)
            area = QRectF(rect.left(), rect.top(), rect.width(), rect.height() - 62)
            draw_block(p, lines, look, area, known_words=o.known_words, reveal=o.reveal, lift=6)


# --- 4. Ring around the mouse ----------------------------------------------------
class RingStyle(Style):
    key = "ring"
    title = "Кольцо"
    description = "Кольцо вокруг курсора мыши пульсирует от голоса, текст рядом подсказкой"
    follows = FOLLOW_MOUSE
    W, H = 600, 170
    CX, CY = 70, 70  # cursor position inside the window
    font = _font(10.5)

    def geometry(self, area, anchor):
        pos = anchor.topLeft() if anchor is not None else area.center()
        return QRect(pos.x() - self.CX, pos.y() - self.CY, self.W, self.H)

    def paint(self, p, o, rect):
        c = QPointF(rect.left() + self.CX, rect.top() + self.CY)
        level = _avg_level(o)
        r = (20 + level * 10) * o.presence
        p.setBrush(Qt.BrushStyle.NoBrush)
        # echo rings travel outwards
        light, main, deep = o.palette.colors()
        for k in range(2):
            t = (o.phase * 0.12 + k * 0.5) % 1.0
            echo = QColor(main)
            echo.setAlpha(int(min(255, 120 * (1 - t) * (0.3 + level)) * o.presence))
            p.setPen(QPen(echo, 2))
            p.drawEllipse(c, r + t * 26, r + t * 26)
        grad = QLinearGradient(c.x() - r, c.y() - r, c.x() + r, c.y() + r)
        for stop, color in ((0.0, light), (1.0, deep)):
            color.setAlpha(int(255 * o.presence))
            grad.setColorAt(stop, color)
        p.setPen(QPen(grad, 3.2))
        p.drawEllipse(c, r, r)
        # small sweeping arc shows it is alive even in silence
        p.setPen(QPen(QColor(255, 255, 255, int(200 * o.presence)), 3.2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), int(-o.phase * 180) * 16, 40 * 16)

        firm, soft = o.tail_text(9)
        if firm or soft:
            left = c.x() + 44
            draw_bubble(p, firm, soft, o.text.font(self.font), QPointF(left, c.y() + 22), rect.right() - left - 4, o.presence)


# --- 5. Classic pill -------------------------------------------------------------
class PillStyle(Style):
    key = "pill"
    title = "Классика"
    description = "Тёмная капсула с волной, текст над ней"
    W, H = 640, 300
    PILL_W, PILL_H = 176, 44
    look = TextLook(font=_font(12, italic=True))

    def geometry(self, area, anchor):
        return QRect(area.center().x() - self.W // 2, area.bottom() - self.H - 56, self.W, self.H)

    def paint(self, p, o, rect):
        pill = QRectF(rect.center().x() - self.PILL_W / 2, rect.bottom() - self.PILL_H - 4, self.PILL_W, self.PILL_H)
        look = o.text.look(self.look)
        tokens = o.tokens()
        if tokens:
            m = QFontMetricsF(look.font, p.device())
            lines = layout(tokens, m, rect.width() - 48, look.max_lines)
            w, h = block_size(lines, m, look)
            panel = QRectF(0, 0, w + 28, h + 16)
            panel.moveCenter(QPointF(rect.center().x(), 0))
            panel.moveBottom(pill.top() - 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(28, 28, 30, 215))
            p.drawRoundedRect(panel, 12, 12)
            draw_block(p, lines, look, panel.adjusted(14, 8, -14, -8),
                       known_words=o.known_words, reveal=o.reveal)

        p.setPen(QColor(255, 255, 255, 22))
        p.setBrush(QColor(14, 14, 16, 238))
        p.drawRoundedRect(pill, self.PILL_H / 2, self.PILL_H / 2)
        center = QPointF(pill.left() + 24, pill.center().y())
        radius = 11 + (1.2 if o.active else 0) * abs(math.sin(o.phase / 2))
        grad = QRadialGradient(center - QPointF(3, 3), radius * 1.4)
        light, main, _ = o.palette.colors()
        grad.setColorAt(0.0, light)
        grad.setColorAt(1.0, main)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(center, radius, radius)
        left, right = pill.left() + 48, pill.right() - 18
        bars = list(o.levels)[-15:]
        step = (right - left) / len(bars)
        for i, level in enumerate(bars):
            envelope = 0.45 + 0.55 * (1 - abs(i - (len(bars) - 1) / 2) / ((len(bars) - 1) / 2))
            h = 4 + min(1.0, level * envelope) * (self.PILL_H - 16)
            x = left + i * step + step / 2 - 1.5
            p.setBrush(QColor(220, 220, 225, 225))
            p.drawRoundedRect(QRectF(x, pill.center().y() - h / 2, 3, h), 1.5, 1.5)


STYLES: dict[str, Style] = {s.key: s for s in (LineStyle(), DropStyle(), CinemaStyle(), RingStyle(), PillStyle())}
DEFAULT_STYLE = LineStyle.key
