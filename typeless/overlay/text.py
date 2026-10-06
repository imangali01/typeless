"""Word layout and drawing shared by overlay styles."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

# (index in the token stream, word, is_tentative)
Token = tuple[int, str, bool]


@dataclass
class TextLook:
    font: QFont
    color: QColor = field(default_factory=lambda: QColor(236, 236, 240))
    tentative_color: QColor | None = None  # None: same color, faded by tentative_alpha
    tentative_alpha: float = 0.5
    line_opacity: tuple[float, ...] = (1.0, 0.6, 0.35)  # newest line first
    max_lines: int = 3
    outline: QColor | None = None  # dark halo for text drawn without a panel
    blur_reveal: bool = False  # new words come into focus instead of just fading in
    line_gap: float = 4.0


def layout(tokens: list[Token], metrics: QFontMetricsF, max_width: float, max_lines: int) -> list[list[Token]]:
    lines: list[list[Token]] = []
    line: list[Token] = []
    width = 0.0
    space = metrics.horizontalAdvance(" ")
    for token in tokens:
        w = metrics.horizontalAdvance(token[1])
        if line and width + space + w > max_width:
            lines.append(line)
            line, width = [], 0.0
        width += (space if line else 0) + w
        line.append(token)
    if line:
        lines.append(line)
    return lines[-max_lines:]


def line_width(line: list[Token], metrics: QFontMetricsF) -> float:
    space = metrics.horizontalAdvance(" ")
    return sum(metrics.horizontalAdvance(w) for _, w, _ in line) + space * (len(line) - 1)


def block_size(lines: list[list[Token]], metrics: QFontMetricsF, look: TextLook) -> tuple[float, float]:
    if not lines:
        return 0.0, 0.0
    width = max(line_width(line, metrics) for line in lines)
    return width, len(lines) * (metrics.height() + look.line_gap) - look.line_gap


def draw_block(
    p: QPainter,
    lines: list[list[Token]],
    look: TextLook,
    rect: QRectF,
    *,
    known_words: int,
    reveal: float,
    align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignHCenter,
    lift: float = 8.0,
) -> None:
    """Draw lines bottom-up inside rect; words with index >= known_words animate in."""
    metrics = QFontMetricsF(look.font, p.device())
    p.setFont(look.font)
    line_h = metrics.height() + look.line_gap
    space = metrics.horizontalAdvance(" ")
    rise = (1 - reveal) * lift
    for row, line in enumerate(reversed(lines)):
        baseline = rect.bottom() - row * line_h - metrics.descent() + rise
        if align == Qt.AlignmentFlag.AlignHCenter:
            x = rect.center().x() - line_width(line, metrics) / 2
        else:
            x = rect.left()
        base_alpha = look.line_opacity[min(row, len(look.line_opacity) - 1)]
        for index, word, tentative in line:
            alpha = base_alpha
            color = QColor(look.color)
            if tentative:
                if look.tentative_color is not None:
                    color = QColor(look.tentative_color)
                else:
                    alpha *= look.tentative_alpha
            fresh = index >= known_words
            if fresh:
                alpha *= reveal
            _draw_word(p, QPointF(x, baseline), word, color, alpha, look,
                       blur=(1 - reveal) if fresh and look.blur_reveal else 0.0)
            x += metrics.horizontalAdvance(word) + space


def _draw_word(p: QPainter, at: QPointF, word: str, color: QColor, alpha: float, look: TextLook, blur: float) -> None:
    if alpha <= 0.01:
        return
    if look.outline is not None:
        # Soft shadow (wide faint stroke + narrow one) instead of a hard outline.
        path = QPainterPath()
        path.addText(at + QPointF(0, 1), look.font, word)
        for width, k in ((7.0, 0.18), (3.0, 0.35)):
            halo = QColor(look.outline)
            halo.setAlphaF(halo.alphaF() * alpha * k)
            p.strokePath(path, QPen(halo, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                    Qt.PenJoinStyle.RoundJoin))
    if blur > 0.02:
        # Fake defocus: a few offset ghosts that converge as the word sharpens.
        ghost = QColor(color)
        ghost.setAlphaF(alpha * 0.3)
        p.setPen(ghost)
        r = blur * 4
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
            p.drawText(at + QPointF(dx, dy), word)
        alpha *= 1 - blur * 0.6
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    p.setPen(c)
    p.drawText(at, word)


def draw_bubble(p: QPainter, firm: str, soft: str, font: QFont, anchor: QPointF, max_width: float,
                alpha: float = 1.0) -> QRectF:
    """One-line dark bubble with its left-middle at anchor.

    `firm` (confirmed) is elided on the left when space runs out; `soft` (tentative)
    is always shown, dimmer.
    """
    metrics = QFontMetricsF(font, p.device())
    pad = 11
    space = metrics.horizontalAdvance(" ")
    inner = max_width - 2 * pad
    soft_w = metrics.horizontalAdvance(soft) if soft else 0.0
    gap = space if firm and soft else 0.0
    if firm and metrics.horizontalAdvance(firm) + gap + soft_w > inner:
        firm = metrics.elidedText(firm, Qt.TextElideMode.ElideLeft, max(0.0, inner - gap - soft_w))
    firm_w = metrics.horizontalAdvance(firm) if firm else 0.0
    rect = QRectF(anchor.x(), anchor.y() - metrics.height() / 2 - 7,
                  min(max_width, firm_w + gap + soft_w + 2 * pad), metrics.height() + 14)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(20, 20, 24, int(225 * alpha)))
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    p.setFont(font)
    base = QPointF(rect.left() + pad, rect.center().y() + (metrics.ascent() - metrics.descent()) / 2)
    p.setPen(QColor(236, 236, 240, int(255 * alpha)))
    p.drawText(base, firm)
    if soft:
        p.setPen(QColor(236, 236, 240, int(120 * alpha)))
        p.drawText(base + QPointF(firm_w + gap, 0), soft)
    return rect
