"""Widgets of the keyboard-deck look: keycap buttons, LED toggles, plates."""

from __future__ import annotations

import random

from PySide6.QtCore import (
    Property, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ..overlay import Overlay
from ..overlay.styles import FOLLOW_NONE, Style
from . import theme


def label(text: str, kind: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if kind:
        lbl.setObjectName(kind)
    lbl.setWordWrap(wrap)
    return lbl


# --- keycap drawing ------------------------------------------------------------------
def draw_keycap(p: QPainter, rect: QRectF, text: str, font: QFont, *, pressed: bool = False,
                hover: bool = False, led: bool | None = None, align=Qt.AlignmentFlag.AlignCenter,
                radius: float = 7) -> QRectF:
    """A light keycap: side wall below, top surface above; pressed caps sink.

    led: None = no indicator, False = dark LED, True = lit LED.
    Returns the top surface rect.
    """
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    sink = 2.0 if pressed else 0.0
    # shadow on the deck
    p.setBrush(QColor(0, 0, 0, 90 if not pressed else 50))
    p.drawRoundedRect(rect.adjusted(0, 2 + sink, 0, 1), radius, radius)
    # wall
    wall = QLinearGradient(0, rect.top(), 0, rect.bottom())
    wall.setColorAt(0, QColor("#c4c7cf"))
    wall.setColorAt(1, QColor(theme.CAP_WALL))
    p.setBrush(wall)
    p.drawRoundedRect(rect.adjusted(0, sink, 0, 0), radius, radius)
    # top
    top = rect.adjusted(2.5, 1 + sink, -2.5, -(5 - sink * 1.2))
    cap = QLinearGradient(0, top.top(), 0, top.bottom())
    base = QColor(theme.CAP_TOP_PRESSED if pressed else theme.CAP_TOP)
    if hover and not pressed:
        base = base.lighter(103)
    cap.setColorAt(0, base.lighter(103))
    cap.setColorAt(1, base.darker(104))
    p.setBrush(cap)
    p.drawRoundedRect(top, radius - 1.5, radius - 1.5)
    text_rect = top.adjusted(10, 0, -10, 0)
    if led is not None:
        center = QPointF(top.left() + 13, top.center().y())
        if led:
            glow = QRadialGradient(center, 9)
            glow.setColorAt(0, QColor(47, 214, 255, 150))
            glow.setColorAt(1, QColor(47, 214, 255, 0))
            p.setBrush(glow)
            p.drawEllipse(center, 9, 9)
        p.setBrush(QColor(theme.LED if led else "#9a9ea8"))
        p.drawEllipse(center, 3.2, 3.2)
        text_rect.setLeft(top.left() + 26)
    p.setFont(font)
    p.setPen(QColor(theme.CAP_TEXT))
    p.drawText(text_rect, align | Qt.AlignmentFlag.AlignVCenter, text)
    return top


class KeyButton(QPushButton):
    """Push button drawn as a light keycap; sinks while pressed."""

    def __init__(self, text: str, min_width: int = 0) -> None:
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self._font = theme.title_font(9.5, QFont.Weight.Medium)
        self.setMinimumWidth(max(min_width, self.fontMetrics().horizontalAdvance(text) + 36))
        self.setFixedHeight(34)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -3)
        if not self.isEnabled():
            p.setOpacity(0.5)
        draw_keycap(p, r, self.text(), self._font, pressed=self.isDown(), hover=self._hover)


class NavKey(QPushButton):
    """Sidebar key: a wide keycap with an indicator LED; the current page stays pressed."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self._hover = False
        self._font = theme.title_font(10.5, QFont.Weight.Medium)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -4)
        on = self.isChecked()
        draw_keycap(p, r, self.text(), self._font, pressed=on or self.isDown(), hover=self._hover,
                    led=on, align=Qt.AlignmentFlag.AlignLeft)


# --- plates --------------------------------------------------------------------------
class Plate(QFrame):
    """A section: title on the plate, rows separated by thin dividers."""

    def __init__(self, title: str = "", note: str = "") -> None:
        super().__init__()
        self.setObjectName("plate")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._col = QVBoxLayout(self)
        self._col.setContentsMargins(20, 16, 20, 8)
        self._col.setSpacing(0)
        if title:
            self._col.addWidget(label(title, "plateTitle"))
        if note:
            self._col.addSpacing(2)
            self._col.addWidget(label(note, "muted", wrap=True))
        if title or note:
            self._col.addSpacing(8)
        self._rows = 0

    def row(self, title: str, description: str = "", *controls: QWidget) -> QHBoxLayout:
        if self._rows:
            line = QFrame()
            line.setObjectName("divider")
            self._col.addWidget(line)
        self._rows += 1
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(10)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(title, "rowTitle"))
        if description:
            text.addWidget(label(description, "muted", wrap=True))
        row.addLayout(text, 1)
        for c in controls:
            row.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
        self._col.addWidget(holder)
        return row

    def add(self, widget: QWidget | None = None, layout=None) -> None:
        """Free-form content (galleries, chip lists)."""
        if widget is not None:
            self._col.addWidget(widget)
        if layout is not None:
            self._col.addLayout(layout)
        self._col.addSpacing(8)


class Combo(QComboBox):
    """Recessed combo box with a drawn chevron."""

    def __init__(self, items: list[tuple[str, str]], value: str) -> None:
        super().__init__()
        for key, title in items:
            self.addItem(title, key)
        self.setCurrentIndex(max(0, self.findData(value)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.MUTED), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = self.width() - 18, self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))


class Toggle(QAbstractButton):
    """Switch with an indicator LED on the knob: lit when on."""

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 28)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#0e0f11"), 1))
        p.setBrush(QColor(theme.WELL))
        p.drawRoundedRect(QRectF(0.5, 0.5, 51, 27), 13.5, 13.5)
        knob = QRectF(3 + self._pos * 24, 3, 22, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawEllipse(knob.translated(0, 1.5))
        cap = QLinearGradient(0, knob.top(), 0, knob.bottom())
        cap.setColorAt(0, QColor(theme.CAP_TOP))
        cap.setColorAt(1, QColor(theme.CAP_WALL))
        p.setBrush(cap)
        p.drawEllipse(knob)
        center = knob.center()
        lit = self._pos > 0.5
        if lit:
            glow = QRadialGradient(center, 9)
            glow.setColorAt(0, QColor(47, 214, 255, 170))
            glow.setColorAt(1, QColor(47, 214, 255, 0))
            p.setBrush(glow)
            p.drawEllipse(center, 9, 9)
        p.setBrush(QColor(theme.LED if lit else "#8a8e98"))
        p.drawEllipse(center, 3.2, 3.2)


class KeyCaps(QWidget):
    """The hotkey drawn as real keycaps: [Win] + [C]. The one loud element of the window."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._text = text
        self._waiting = False
        self.setFixedHeight(64)
        self.setMinimumWidth(260)
        self._blink_on = True
        self._blink = QTimer(self)
        self._blink.setInterval(450)
        self._blink.timeout.connect(self._on_blink)

    def _on_blink(self) -> None:
        self._blink_on = not self._blink_on
        self.update()

    def set_text(self, text: str) -> None:
        self._text, self._waiting = text, False
        self._blink.stop()
        self.update()

    def set_waiting(self) -> None:
        self._waiting = True
        self._blink.start()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.title_font(14, QFont.Weight.DemiBold)
        if self._waiting:
            p.setFont(theme.title_font(12, QFont.Weight.Medium))
            p.setPen(QColor(theme.LED if self._blink_on else theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "Нажмите новое сочетание…   Esc — отмена")
            return
        p.setFont(font)
        fm = p.fontMetrics()
        x = 0.0
        for i, key in enumerate(self._text.split("+")):
            if i:
                p.setPen(QColor(theme.MUTED))
                p.setFont(theme.title_font(14))
                p.drawText(QRectF(x, 0, 26, self.height() - 6), Qt.AlignmentFlag.AlignCenter, "+")
                x += 26
            w = max(58.0, fm.horizontalAdvance(key) + 34)
            draw_keycap(p, QRectF(x, 2, w, self.height() - 6), key, font, radius=9)
            x += w


class StylePreview(QFrame):
    """A live, animated miniature of an overlay style."""

    clicked = Signal()
    AREA = QRect(0, 0, 1280, 400)
    CARET = QRect(300, 180, 2, 20)

    def __init__(self, style: Style) -> None:
        super().__init__()
        self.style_obj = style
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 150)
        self.setStyleSheet("background: transparent;")
        self._state = Overlay(style.key)  # never shown: only its state is used for painting
        s = self._state
        s.active, s.presence, s.reveal = True, 1.0, 1.0
        s.confirmed = "Сегодня сделаю деплой сервиса на Kubernetes и"
        s.tentative = "проверю pull request"
        s.known_words = 10**6
        self._selected = False
        self._hover = False
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, event) -> None:
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self.update()

    def set_color(self, color: str | None) -> None:
        self._state.set_style(self.style_obj.key, color)
        self.update()

    def set_text_options(self, opts) -> None:
        self._state.text = opts
        self.update()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()

    def _tick(self) -> None:
        s = self._state
        s.phase += 0.16
        s.levels.append(max(0.08, min(1.0, s.levels[-1] * 0.5 + random.uniform(0.0, 0.9) * 0.6)))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        screen = outer.adjusted(0, 0, 0, -30)
        bg = QLinearGradient(screen.topLeft(), screen.bottomRight())
        bg.setColorAt(0, QColor("#3a4256"))
        bg.setColorAt(1, QColor("#1c1f29"))
        p.setPen(QPen(QColor(theme.LED), 2) if self._selected else
                 QPen(QColor(theme.MUTED if self._hover else theme.PLATE_EDGE), 1))
        p.setBrush(bg)
        p.drawRoundedRect(screen, 9, 9)

        p.save()
        p.setClipRect(screen.adjusted(2, 2, -2, -2))
        scale = screen.width() / self.AREA.width()
        p.translate(screen.left(), screen.bottom() - self.AREA.height() * scale)
        p.scale(scale, scale)
        anchor = self.CARET if self.style_obj.follows != FOLLOW_NONE else None
        geo = self.style_obj.geometry(self.AREA, anchor)
        p.translate(geo.topLeft())
        self.style_obj.paint(p, self._state, QRectF(0, 0, geo.width(), geo.height()))
        p.restore()

        text_rect = QRectF(outer.left() + 2, outer.bottom() - 26, outer.width(), 24)
        if self._selected:
            p.setPen(Qt.PenStyle.NoPen)
            glow = QRadialGradient(QPointF(text_rect.left() + 5, text_rect.center().y()), 8)
            glow.setColorAt(0, QColor(47, 214, 255, 150))
            glow.setColorAt(1, QColor(47, 214, 255, 0))
            p.setBrush(glow)
            p.drawEllipse(QPointF(text_rect.left() + 5, text_rect.center().y()), 8, 8)
            p.setBrush(QColor(theme.LED))
            p.drawEllipse(QPointF(text_rect.left() + 5, text_rect.center().y()), 3, 3)
            text_rect.setLeft(text_rect.left() + 16)
        p.setPen(QColor(theme.TEXT if self._selected else theme.MUTED))
        p.setFont(theme.title_font(10, QFont.Weight.Medium))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.style_obj.title)


class Swatch(QAbstractButton):
    """Round colour sample showing a palette's gradient; LED-coloured ring when selected."""

    def __init__(self, light: str, main: str, deep: str, tip: str) -> None:
        super().__init__()
        self.colors = (light, main, deep)
        self.setToolTip(tip)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(34, 34)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            p.setPen(QPen(QColor(theme.LED), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(1.5, 1.5, 31, 31))
        grad = QLinearGradient(6, 6, 28, 28)
        for stop, c in zip((0.0, 0.5, 1.0), self.colors):
            grad.setColorAt(stop, QColor(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QRectF(6, 6, 22, 22))


class Chip(QWidget):
    """A small keycap-shaped tag with + / × actions."""

    def __init__(self, text: str, actions: list[tuple[str, str, object]]) -> None:
        super().__init__()
        self._text = text
        self._actions = actions
        self._font = theme.title_font(9.5, QFont.Weight.Medium)
        self._hits: list[tuple[QRectF, object]] = []
        fm = self.fontMetrics()
        self.setFixedSize(int(fm.horizontalAdvance(text) * 1.05) + 26 + 22 * len(actions), 32)
        self.setToolTip("  ".join(tip for _, tip, _ in actions))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -3)
        top = draw_keycap(p, r, "", self._font, radius=6)
        p.setFont(self._font)
        p.setPen(QColor(theme.CAP_TEXT))
        text_w = top.width() - 22 * len(self._actions)
        p.drawText(QRectF(top.left() + 10, top.top(), text_w - 10, top.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        self._hits = []
        x = top.left() + text_w
        for symbol, _, callback in self._actions:
            box = QRectF(x, top.top(), 22, top.height())
            p.setPen(QColor("#5b5f69"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, symbol)
            self._hits.append((box, callback))
            x += 22

    def mousePressEvent(self, event) -> None:
        for box, callback in self._hits:
            if box.contains(event.position()):
                callback()
                return


class FlowLayout(QLayout):
    """Wraps child widgets onto new lines (for chips)."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _layout(self, rect: QRect, apply: bool) -> int:
        x, y, line_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line_h > 0:
                x, y = rect.x(), y + line_h + self._spacing
                line_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()

    def clear(self) -> None:
        while self._items:
            item = self._items.pop()
            if item.widget():
                item.widget().deleteLater()


def transparent_holder() -> tuple[QWidget, FlowLayout]:
    holder = QWidget()
    holder.setStyleSheet("background: transparent;")
    holder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return holder, FlowLayout(holder)
