"""Render every overlay style to PNGs for visual checks.

Usage: python scripts/render_overlay.py out_dir
"""

import random
import sys
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless.overlay import STYLES, Overlay  # noqa: E402

app = QApplication([])
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
random.seed(3)
area = QRect(0, 0, 1280, 400)  # stand-in screen strip
caret = QRect(300, 180, 2, 20)

for key, style in STYLES.items():
    o = Overlay(key)
    o.active = True
    o.presence = o.reveal = 1.0
    o.phase = 2.0
    o.levels.extend(random.uniform(0.3, 0.9) for _ in range(24))
    o.confirmed = "Сегодня я хочу сделать деплой нового сервиса на Kubernetes, потом проверить"
    o.tentative = "pull request"
    o.known_words = 10**6
    geo = style.geometry(area, caret if style.follows != "none" else None)
    o.setGeometry(geo)
    canvas = QPixmap(area.size())
    p = QPainter(canvas)
    bg = QLinearGradient(0, 0, 1280, 400)
    bg.setColorAt(0, QColor("#e9edf3"))
    bg.setColorAt(1, QColor("#b9c3d1"))
    p.fillRect(canvas.rect(), bg)
    p.end()
    o.render(canvas, geo.topLeft())
    canvas.save(str(out / f"overlay_{key}.png"))
    print("saved", key)
