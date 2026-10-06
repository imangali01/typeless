"""Render README screenshots into docs/screenshots/ (demo data, no microphone needed).

Usage: python scripts/screenshots.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless.app import make_icon  # noqa: E402
from typeless.config import Config  # noqa: E402
from typeless.hotkey import GlobalHotkey  # noqa: E402
from typeless.keys import DEFAULT_HOTKEY  # noqa: E402
from typeless.overlay import STYLES, Overlay  # noqa: E402
from typeless.ui.settings_window import SettingsWindow  # noqa: E402

OUT = Path("docs/screenshots")
CONFIRMED = "Привет! Сегодня выкатываем новый сервис на Kubernetes, после ревью"
TENTATIVE = "pull request"


def wallpaper(p: QPainter, rect: QRect) -> None:
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.0, QColor("#1d2b4f"))
    bg.setColorAt(0.55, QColor("#3a2f5c"))
    bg.setColorAt(1.0, QColor("#141826"))
    p.fillRect(rect, bg)
    glow = QRadialGradient(QPointF(rect.width() * 0.75, rect.height() * 0.2), rect.width() * 0.5)
    glow.setColorAt(0.0, QColor(124, 92, 255, 90))
    glow.setColorAt(1.0, QColor(124, 92, 255, 0))
    p.fillRect(rect, glow)


def editor_window(p: QPainter, rect: QRectF, typed: str) -> None:
    """A plain text editor window the dictated text goes into."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawRoundedRect(rect.translated(0, 10), 10, 10)
    p.setBrush(QColor("#fbfbfb"))
    p.drawRoundedRect(rect, 10, 10)
    p.setBrush(QColor("#ececf0"))
    p.drawRoundedRect(QRectF(rect.left(), rect.top(), rect.width(), 40), 10, 10)
    p.drawRect(QRectF(rect.left(), rect.top() + 30, rect.width(), 10))
    title = QFont("Segoe UI", 10)
    p.setFont(title)
    p.setPen(QColor("#333"))
    p.drawText(QRectF(rect.left() + 16, rect.top(), 300, 40), Qt.AlignmentFlag.AlignVCenter,
               "Сообщение команде — Блокнот")
    body = QFont("Segoe UI", 13)
    p.setFont(body)
    p.setPen(QColor("#1a1a1a"))
    text_rect = QRectF(rect.left() + 24, rect.top() + 60, rect.width() - 48, rect.height() - 80)
    p.drawText(text_rect, Qt.TextFlag.TextWordWrap, typed)
    # caret after the text
    fm = p.fontMetrics()
    last_line = typed.split("\n")[-1]
    lines = typed.count("\n")
    x = text_rect.left() + fm.horizontalAdvance(last_line) + 2
    y = text_rect.top() + lines * fm.lineSpacing()
    p.setPen(QColor("#1a1a1a"))
    p.drawLine(QPointF(x, y + 3), QPointF(x, y + fm.height() - 2))


def taskbar(p: QPainter, rect: QRectF) -> None:
    p.fillRect(rect, QColor(24, 24, 30, 235))
    p.setPen(QColor(255, 255, 255, 18))
    p.drawLine(rect.topLeft(), rect.topRight())
    p.setPen(Qt.PenStyle.NoPen)
    icons = ["#3d8bfd", "#f2c94c", "#7c5cff", "#2fbf71", "#e8eaed"]
    start = rect.center().x() - len(icons) * 22
    for i, color in enumerate(icons):
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(start + i * 44 + 10, rect.top() + 9, 22, 22), 5, 5)
    # Typeless tray icon on the right, red while recording
    p.drawPixmap(int(rect.right() - 120), int(rect.top() + 8), make_icon(True).pixmap(24, 24))
    p.setPen(QColor("#e8e8ee"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(rect.right() - 86, rect.top(), 76, rect.height()), Qt.AlignmentFlag.AlignCenter, "14:20")


def fresh_overlay(style: str) -> Overlay:
    random.seed(7)
    o = Overlay(style)
    o.active = True
    o.presence = o.reveal = 1.0
    o.phase = 2.2
    o.levels.extend(random.uniform(0.3, 0.95) for _ in range(24))
    o.confirmed, o.tentative = CONFIRMED, TENTATIVE
    o.known_words = 10**6
    return o


def desktop_with_overlay() -> None:
    screen = QRect(0, 0, 1600, 900)
    pix = QPixmap(screen.size())
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    wallpaper(p, screen)
    editor_window(p, QRectF(330, 110, 940, 420),
                  "Привет! Сегодня выкатываем новый сервис на Kubernetes, после ревью")
    taskbar(p, QRectF(0, screen.height() - 40, screen.width(), 40))
    p.end()
    o = fresh_overlay("line")
    geo = STYLES["line"].geometry(screen.adjusted(0, 0, 0, -40), None)
    o.setGeometry(geo)
    o.render(pix, geo.topLeft())
    pix.save(str(OUT / "desktop-with-overlay.png"))


def styles_gallery() -> None:
    tile_w, tile_h, gap = 620, 230, 20
    keys = list(STYLES)
    cols = 2
    rows = (len(keys) + cols - 1) // cols
    pix = QPixmap(cols * tile_w + (cols + 1) * gap, rows * (tile_h + 40) + (rows + 1) * gap)
    pix.fill(QColor("#0f1014"))
    for i, key in enumerate(keys):
        x = gap + (i % cols) * (tile_w + gap)
        y = gap + (i // cols) * (tile_h + 40 + gap)
        tile = QPixmap(tile_w, tile_h)
        tp = QPainter(tile)
        tp.setRenderHint(QPainter.RenderHint.Antialiasing)
        wallpaper(tp, tile.rect())
        tp.end()
        area = QRect(0, 0, tile_w, tile_h)
        style = STYLES[key]
        caret = QRect(70, 110, 2, 20)
        geo = style.geometry(area, caret if style.follows != "none" else None)
        o = fresh_overlay(key)
        o.setGeometry(geo)
        o.render(tile, geo.topLeft())
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(x, y, tile)
        p.setPen(QColor("#ececf1"))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, y + tile_h + 6, tile_w, 30), Qt.AlignmentFlag.AlignLeft, style.title)
        p.end()
    pix.save(str(OUT / "overlay-styles.png"))


def settings_pages(app: QApplication) -> None:
    config = Config(dictionary=["Kubernetes", "Terraform", "ClickHouse"],
                    corrections={"ттермен": "термин", "кубернитис": "Kubernetes"},
                    suggested_terms=["Helm", "Grafana"], overlay_colors={"line": "neon"})
    win = SettingsWindow(config, GlobalHotkey(DEFAULT_HOTKEY), make_icon(False),
                         "Сегодня обсудим ттермен и деплой на кубернитис.")
    win.resize(1000, 700)
    win.show()
    for key in ("general", "recognition", "look", "dictionary"):
        win.open_page(key)
        for _ in range(6):
            app.processEvents()
        win.grab().save(str(OUT / f"settings-{key}.png"))
    win.close()


def main() -> None:
    app = QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    desktop_with_overlay()
    styles_gallery()
    settings_pages(app)
    for f in sorted(OUT.glob("*.png")):
        print(f)


if __name__ == "__main__":
    main()
