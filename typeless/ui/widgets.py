"""Small custom widgets for the settings window."""

from __future__ import annotations

import random

from PySide6.QtCore import (
    Property, QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ..overlay import Overlay
from ..overlay.styles import FOLLOW_NONE, Style
from . import theme


def card(parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(parent)
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


def label(text: str, kind: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if kind:
        lbl.setObjectName(kind)
    lbl.setWordWrap(wrap)
    return lbl


class Toggle(QAbstractButton):
    """iOS-like switch with an animated knob."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def _on_toggled(self, on: bool) -> None:
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
        track = QRectF(0, 0, 44, 24)
        off, on = QColor(theme.BORDER), QColor(theme.ACCENT)
        color = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, 12, 12)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(3 + self._pos * 20, 3, 18, 18))


class SettingRow(QWidget):
    """Title + description on the left, a control on the right."""

    def __init__(self, title: str, description: str, control: QWidget) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(title, "h2"))
        if description:
            text.addWidget(label(description, "muted", wrap=True))
        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)


class KeyCaps(QWidget):
    """Hotkey shown as keyboard keys: [Win] + [C]."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._text = text
        self._waiting = False
        self.setMinimumHeight(46)
        self._blink_on = True
        self._blink = QTimer(self)
        self._blink.setInterval(500)
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
        font = QFont(self.font())
        font.setPointSizeF(11)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        if self._waiting:
            p.setPen(QColor(theme.ACCENT if self._blink_on else theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "Нажмите сочетание…  (Esc — отмена)")
            return
        x = 0
        fm = p.fontMetrics()
        for i, key in enumerate(self._text.split("+")):
            if i:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRect(x, 0, 18, self.height()), Qt.AlignmentFlag.AlignCenter, "+")
                x += 18
            w = max(40, fm.horizontalAdvance(key) + 26)
            box = QRectF(x, 4, w, self.height() - 10)
            p.setPen(QPen(QColor(theme.BORDER), 1))
            grad = QLinearGradient(box.topLeft(), box.bottomLeft())
            grad.setColorAt(0, QColor("#2a2c38"))
            grad.setColorAt(1, QColor("#1c1d25"))
            p.setBrush(grad)
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor(0, 0, 0, 120))
            p.drawLine(box.bottomLeft() + QPoint(6, 1), box.bottomRight() + QPoint(-6, 1))
            p.setPen(QColor(theme.TEXT))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, key)
            x += int(w) + 4


class OptionCard(QFrame):
    """Selectable card (radio-like) with a title and a hint."""

    clicked = Signal()

    def __init__(self, title: str, hint: str = "") -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        layout.addWidget(label(title, "h2"))
        if hint:
            layout.addWidget(label(hint, "muted", wrap=True))
        self.set_selected(False)

    def set_selected(self, on: bool) -> None:
        border = theme.ACCENT if on else theme.BORDER
        bg = theme.ACCENT_SOFT if on else theme.CARD_HOVER
        self.setStyleSheet(f"OptionCard {{ background: {bg}; border: 1.5px solid {border}; border-radius: 12px; }}")

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()


class OptionGroup(QWidget):
    """A row/grid of OptionCards with one selected value."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str, str]], value: str, columns: int = 2) -> None:
        super().__init__()
        from PySide6.QtWidgets import QGridLayout

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self._cards: dict[str, OptionCard] = {}
        for i, (key, title, hint) in enumerate(options):
            c = OptionCard(title, hint)
            c.clicked.connect(lambda k=key: self.set_value(k, emit=True))
            grid.addWidget(c, i // columns, i % columns)
            self._cards[key] = c
        self.value = ""
        self.set_value(value)

    def set_value(self, key: str, emit: bool = False) -> None:
        if key not in self._cards:
            key = next(iter(self._cards))
        self.value = key
        for k, c in self._cards.items():
            c.set_selected(k == key)
        if emit:
            self.changed.emit(key)


class StylePreview(QFrame):
    """Card with a live, animated miniature of an overlay style."""

    clicked = Signal()
    AREA = QRect(0, 0, 1280, 400)
    CARET = QRect(300, 180, 2, 20)

    def __init__(self, style: Style) -> None:
        super().__init__()
        self.style_obj = style
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(250, 170)
        self._state = Overlay(style.key)  # never shown: only its state is used for painting
        s = self._state
        s.active, s.presence, s.reveal = True, 1.0, 1.0
        s.confirmed = "Сегодня сделаю деплой сервиса на Kubernetes и"
        s.tentative = "проверю pull request"
        s.known_words = 10**6
        self._selected = False
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, event) -> None:
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()

    def set_selected(self, on: bool) -> None:
        self._selected = on
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
        p.setPen(QPen(QColor(theme.ACCENT if self._selected else theme.BORDER), 2 if self._selected else 1))
        p.setBrush(QColor(theme.CARD))
        p.drawRoundedRect(outer, 14, 14)

        screen = outer.adjusted(10, 10, -10, -52)
        bg = QLinearGradient(screen.topLeft(), screen.bottomRight())
        bg.setColorAt(0, QColor("#3b4160"))
        bg.setColorAt(1, QColor("#1b1e2c"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(screen, 9, 9)

        p.save()
        p.setClipRect(screen)
        scale = screen.width() / self.AREA.width()
        p.translate(screen.left(), screen.bottom() - self.AREA.height() * scale)
        p.scale(scale, scale)
        anchor = self.CARET if self.style_obj.follows != FOLLOW_NONE else None
        geo = self.style_obj.geometry(self.AREA, anchor)
        p.translate(geo.topLeft())
        self.style_obj.paint(p, self._state, QRectF(0, 0, geo.width(), geo.height()))
        p.restore()

        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(outer.left() + 14, outer.bottom() - 46, outer.width() - 28, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.style_obj.title)
        p.setPen(QColor(theme.MUTED))
        f.setWeight(QFont.Weight.Normal)
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.drawText(QRectF(outer.left() + 14, outer.bottom() - 26, outer.width() - 28, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(self.style_obj.description, Qt.TextElideMode.ElideRight,
                                              int(outer.width() - 28)))


class Chip(QFrame):
    """Rounded tag with optional action buttons."""

    def __init__(self, text: str, actions: list[tuple[str, str, object]]) -> None:
        super().__init__()
        self.setStyleSheet(f"Chip {{ background: {theme.CARD_HOVER}; border: 1px solid {theme.BORDER}; border-radius: 13px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 3, 4, 3)
        row.setSpacing(2)
        row.addWidget(label(text))
        for symbol, tip, callback in actions:
            b = QPushButton(symbol)
            b.setObjectName("ghost")
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(callback)
            row.addWidget(b)


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
