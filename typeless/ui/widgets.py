"""macOS-style widgets: grouped lists, switches, pop-up buttons, sidebar items, traffic lights."""

from __future__ import annotations

import random

from PySide6.QtCore import (
    Property, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
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


# --- grouped list ----------------------------------------------------------------
class Plate(QWidget):
    """macOS grouped list: header above, rounded group of rows, footnote below."""

    def __init__(self, title: str = "", note: str = "") -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        if title:
            outer.addWidget(label(title, "groupHeader"))
        self._group = QFrame()
        self._group.setObjectName("group")
        self._col = QVBoxLayout(self._group)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(0)
        outer.addWidget(self._group)
        if note:
            outer.addWidget(label(note, "footnote", wrap=True))
        self._items = 0

    def _separator(self) -> None:
        if self._items:
            holder = QWidget()
            holder.setStyleSheet("background: transparent;")
            h = QHBoxLayout(holder)
            h.setContentsMargins(14, 0, 0, 0)
            line = QFrame()
            line.setFixedHeight(1)
            # own stylesheet: the holder's "transparent" rule would otherwise hide it
            line.setStyleSheet(f"background: {theme.T.separator}; border: none;")
            h.addWidget(line)
            self._col.addWidget(holder)
        self._items += 1

    def row(self, title: str, description: str = "", *controls: QWidget) -> QHBoxLayout:
        self._separator()
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        row = QHBoxLayout(holder)
        row.setContentsMargins(14, 9, 12, 9)
        row.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(label(title, "rowTitle"))
        if description:
            text.addWidget(label(description, "secondary", wrap=True))
        row.addLayout(text, 1)
        for c in controls:
            row.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
        holder.setMinimumHeight(44)
        self._col.addWidget(holder)
        return row

    def add(self, widget: QWidget | None = None, layout=None) -> None:
        """Free-form content inside the group (galleries, chip lists)."""
        self._separator()
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        box = QVBoxLayout(holder)
        box.setContentsMargins(14, 10, 12, 10)
        if widget is not None:
            box.addWidget(widget)
        if layout is not None:
            box.addLayout(layout)
        self._col.addWidget(holder)


# --- controls --------------------------------------------------------------------
class KeyButton(QPushButton):
    """macOS push button; `default=True` gives the blue default button."""

    def __init__(self, text: str, min_width: int = 0, default: bool = False) -> None:
        super().__init__(text)
        self._default = default
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.setMinimumWidth(max(min_width, self.fontMetrics().horizontalAdvance(text) + 28))

    def paintEvent(self, event) -> None:
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -1.5)
        if not self.isEnabled():
            p.setOpacity(0.45)
        # soft drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60 if t.dark else 25))
        p.drawRoundedRect(r.translated(0, 1), 6, 6)
        if self._default:
            top, bottom, text = QColor(t.accent).lighter(112), QColor(t.accent), QColor("#ffffff")
        else:
            base = QColor(t.control if not t.dark else "#5a5a5e")
            top, bottom, text = base.lighter(104), base, QColor(t.text)
            if t.dark:
                top, bottom = QColor("#636366"), QColor("#58585c")
        if self.isDown():
            top, bottom = top.darker(112), bottom.darker(112)
        grad = QLinearGradient(0, r.top(), 0, r.bottom())
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        p.setBrush(grad)
        if t.dark:
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setPen(QPen(QColor(0, 0, 0, 30), 0.8))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(text)
        p.setFont(theme.font(9.5, QFont.Weight.Medium))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())


class Combo(QComboBox):
    """macOS pop-up button: value on the left, blue square with up/down chevrons on the right."""

    def __init__(self, items: list[tuple[str, str]], value: str) -> None:
        super().__init__()
        for key, title in items:
            self.addItem(title, key)
        self.setCurrentIndex(max(0, self.findData(value)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(self.width() - 22, (self.height() - 16) / 2, 16, 16)
        p.setPen(QPen(QColor(t.secondary), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        cx, cy = box.center().x(), box.center().y()
        p.drawPolyline([QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2), QPointF(cx + 3.5, cy - 1.5)])


class Toggle(QAbstractButton):
    """macOS switch: accent track when on, white knob with a soft shadow."""

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 24)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
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
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off, on = QColor(t.switch_off), QColor(t.accent)
        k = self._pos
        track = QColor(int(off.red() + (on.red() - off.red()) * k), int(off.green() + (on.green() - off.green()) * k),
                       int(off.blue() + (on.blue() - off.blue()) * k))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 1, 40, 22), 11, 11)
        knob = QRectF(2 + k * 16, 3, 18, 18)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(knob.translated(0, 0.8))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(knob)


class NavKey(QPushButton):
    """Sidebar item: coloured rounded-square icon + title; selection fills with the accent."""

    def __init__(self, text: str, glyph: str = "", color: str = "#8e8e93") -> None:
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self._glyph, self._color = glyph, color

    def paintEvent(self, event) -> None:
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        selected = self.isChecked()
        if selected or self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            fill = QColor(t.text)
            fill.setAlpha((28 if t.dark else 20) if selected else 12)
            p.setBrush(fill)
            p.drawRoundedRect(r, 6, 6)
        p.setFont(theme.font(10, QFont.Weight.DemiBold if selected else QFont.Weight.Normal))
        p.setPen(QColor(t.text if selected else t.secondary))
        p.drawText(r.adjusted(12, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

    def enterEvent(self, event) -> None:
        self.update()

    def leaveEvent(self, event) -> None:
        self.update()


class TrafficLights(QWidget):
    """Close / minimise / zoom buttons; glyphs appear on hover, as on macOS."""

    def __init__(self, window: QWidget) -> None:
        super().__init__()
        self._window = window
        self.setFixedSize(68, 20)
        self.setMouseTracking(True)
        self._hover = False

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def _circles(self) -> list[tuple[QRectF, str, str]]:
        return [(QRectF(2 + i * 22, 2, 13, 13), color, sym) for i, (color, sym) in
                enumerate((("#ff5f57", "×"), ("#febc2e", "–"), ("#28c840", "+")))]

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self._window.isActiveWindow() or self._hover
        for rect, color, sym in self._circles():
            p.setPen(QPen(QColor(0, 0, 0, 40), 0.6))
            p.setBrush(QColor(color if active else ("#4d4d50" if theme.T.dark else "#d0d0d4")))
            p.drawEllipse(rect)
            if self._hover:
                p.setPen(QColor(0, 0, 0, 150))
                p.setFont(theme.font(8, QFont.Weight.Bold))
                p.drawText(rect.adjusted(0, -1, 0, 0), Qt.AlignmentFlag.AlignCenter, sym)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        actions = (self._window.close, self._window.showMinimized,
                   lambda: self._window.showNormal() if self._window.isMaximized() else self._window.showMaximized())
        for (rect, _, _), action in zip(self._circles(), actions):
            if rect.adjusted(-3, -3, 3, 3).contains(pos):
                action()
                return


class KeyCaps(QWidget):
    """The hotkey shown as macOS-style key symbols: [Win] [C]."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._text = text
        self._waiting = False
        self.setFixedHeight(28)
        self.setMinimumWidth(110)
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

    def sizeHint(self) -> QSize:
        return QSize(160, 28)

    def paintEvent(self, event) -> None:
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(9.5, QFont.Weight.Medium))
        if self._waiting:
            p.setPen(QColor(t.accent if self._blink_on else t.secondary))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       "Нажмите сочетание…")
            return
        fm = p.fontMetrics()
        keys = self._text.split("+")
        widths = [max(26, fm.horizontalAdvance(k) + 14) for k in keys]
        x = self.width() - (sum(widths) + 4 * (len(keys) - 1))
        for key, w in zip(keys, widths):
            box = QRectF(x, 2, w, self.height() - 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 70 if t.dark else 30))
            p.drawRoundedRect(box.translated(0, 1.2), 5, 5)
            p.setBrush(QColor("#4a4a4d" if t.dark else "#ffffff"))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QColor(t.text))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, key)
            x += w + 4


class StylePreview(QFrame):
    """Picker tile with a live, animated miniature of an overlay style (like the wallpaper picker)."""

    clicked = Signal()
    AREA = QRect(0, 0, 1280, 400)
    CARET = QRect(300, 180, 2, 20)

    def __init__(self, style: Style) -> None:
        super().__init__()
        self.style_obj = style
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 140)
        self.setStyleSheet("background: transparent;")
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
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        screen = outer.adjusted(0, 0, 0, -24)
        if self._selected:
            p.setPen(QPen(QColor(t.accent), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(screen.adjusted(-2, -2, 2, 2), 10, 10)
        bg = QLinearGradient(screen.topLeft(), screen.bottomRight())
        bg.setColorAt(0, QColor("#3e5a8a"))
        bg.setColorAt(1, QColor("#2a2440"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(screen, 8, 8)
        p.save()
        p.setClipRect(screen.adjusted(1, 1, -1, -1))
        scale = screen.width() / self.AREA.width()
        p.translate(screen.left(), screen.bottom() - self.AREA.height() * scale)
        p.scale(scale, scale)
        anchor = self.CARET if self.style_obj.follows != FOLLOW_NONE else None
        geo = self.style_obj.geometry(self.AREA, anchor)
        p.translate(geo.topLeft())
        self.style_obj.paint(p, self._state, QRectF(0, 0, geo.width(), geo.height()))
        p.restore()
        p.setFont(theme.font(9, QFont.Weight.DemiBold if self._selected else QFont.Weight.Normal))
        p.setPen(QColor(t.text if self._selected else t.secondary))
        p.drawText(QRectF(outer.left(), outer.bottom() - 20, outer.width(), 20),
                   Qt.AlignmentFlag.AlignCenter, self.style_obj.title)


class Swatch(QAbstractButton):
    """Colour well: gradient dot with an accent ring when selected."""

    def __init__(self, light: str, main: str, deep: str, tip: str) -> None:
        super().__init__()
        self.colors = (light, main, deep)
        self.setToolTip(tip)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(28, 28)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(5, 5, 23, 23)
        for stop, c in zip((0.0, 0.5, 1.0), self.colors):
            grad.setColorAt(stop, QColor(c))
        p.setPen(QPen(QColor(0, 0, 0, 40), 0.8))
        p.setBrush(grad)
        p.drawEllipse(QRectF(5, 5, 18, 18))
        if self.isChecked():
            p.setPen(QPen(QColor(theme.T.text), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(1.5, 1.5, 25, 25))


class Chip(QWidget):
    """Token like in macOS mail fields: rounded capsule with + / × actions."""

    def __init__(self, text: str, actions: list[tuple[str, str, object]]) -> None:
        super().__init__()
        self._text = text
        self._actions = actions
        self._font = theme.font(9.5)
        self._hits: list[tuple[QRectF, object]] = []
        from PySide6.QtGui import QFontMetricsF

        w = QFontMetricsF(self._font).horizontalAdvance(text)
        self.setFixedSize(int(w) + 22 + 20 * len(actions), 26)
        self.setToolTip("  ".join(tip for _, tip, _ in actions))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        t = theme.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        tint = QColor(t.accent)
        tint.setAlpha(55 if t.dark else 35)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tint)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(self._font)
        p.setPen(QColor(t.text))
        text_w = r.width() - 20 * len(self._actions)
        p.drawText(QRectF(r.left() + 11, r.top(), text_w - 11, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        self._hits = []
        x = r.left() + text_w
        for symbol, _, callback in self._actions:
            box = QRectF(x, r.top(), 20, r.height())
            p.setPen(QColor(t.secondary))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, symbol)
            self._hits.append((box, callback))
            x += 20

    def mousePressEvent(self, event) -> None:
        for box, callback in self._hits:
            if box.contains(event.position()):
                callback()
                return


class FlowLayout(QLayout):
    """Wraps child widgets onto new lines (for chips)."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
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
