"""A tiny on-screen message ("Скопировано в буфер обмена") instead of a Windows notification.

Shows for a moment at the bottom centre and never takes focus. A plain toast lets clicks
pass through; a clickable one (new dictionary terms) opens something when clicked.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

LED = QColor("#2fd6ff")
SHOW_MS = 1500
BOTTOM_MARGIN = 72


class Toast(QWidget):
    clicked = Signal()

    def __init__(self, clickable: bool = False) -> None:
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                 | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        if not clickable:
            flags |= Qt.WindowType.WindowTransparentForInput
        super().__init__(None, flags)
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._font = QFont("Segoe UI Variable Text")
        self._font.setPointSizeF(10)
        self._font.setWeight(QFont.Weight.Medium)
        self._progress = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_progress)
        self._anim.finished.connect(self._on_anim_done)
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(lambda: self._animate(0.0, 220))

    def show_message(self, text: str, ms: int = SHOW_MS) -> None:
        self._text = text
        metrics = QFontMetricsF(self._font)
        w, h = int(metrics.horizontalAdvance(text) + 64), 44
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen.center().x() - w // 2, screen.bottom() - h - BOTTOM_MARGIN, w, h + 8)
        self.show()
        self._animate(1.0, 160)
        self._hide.start(ms)

    def mousePressEvent(self, event) -> None:
        self._hide.stop()
        self._animate(0.0, 160)
        self.clicked.emit()

    def _animate(self, end: float, ms: int) -> None:
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic if end > self._progress else QEasingCurve.Type.InCubic)
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(end)
        self._anim.start()

    def _on_progress(self, value) -> None:
        self._progress = float(value)
        self.setWindowOpacity(self._progress)
        self.update()

    def _on_anim_done(self) -> None:
        if self._progress <= 0.001:
            self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lift = (1 - self._progress) * 8  # rises into place
        pill = QRectF(0.5, 0.5 + lift, self.width() - 1, self.height() - 9)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(QColor(27, 28, 32, 240))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        center = QPointF(pill.left() + 24, pill.center().y())
        glow = QRadialGradient(center, 10)
        glow.setColorAt(0, QColor(47, 214, 255, 150))
        glow.setColorAt(1, QColor(47, 214, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, 10, 10)
        p.setBrush(LED)
        p.drawEllipse(center, 3.5, 3.5)
        p.setFont(self._font)
        p.setPen(QColor("#eceef2"))
        p.drawText(pill.adjusted(40, 0, -16, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
