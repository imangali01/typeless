"""The Typeless logo: a keyboard key whose legend is a waveform.

Drawn in code so the tray, windows, exe icon and installer all share one source.
Small sizes get a simplified drawing (fewer, thicker bars) to stay legible at 16 px.
"""

from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

IDLE_BARS = ("#00e5ff", "#7c5cff", "#ff4fd8")
RECORDING_BARS = ("#ffb199", "#f2384f", "#b3122f")
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _draw(p: QPainter, recording: bool, small: bool) -> None:
    """Paint a mechanical keycap seen from above and slightly in front, on a 64x64 canvas.

    A wide skirt at the bottom, walls that slope in, and a narrower top with a
    concave dish carrying the waveform legend.
    """
    p.setPen(Qt.PenStyle.NoPen)
    skirt = QRectF(3, 7, 58, 55)
    top = QRectF(10, 3, 44, 42) if not small else QRectF(8, 3, 48, 44)

    # soft contact shadow
    shadow = QRadialGradient(32, 60, 30)
    shadow.setColorAt(0, QColor(0, 0, 0, 70))
    shadow.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(shadow)
    p.drawEllipse(QRectF(4, 54, 56, 10))

    # skirt (the walls): lighter at the top edge, darker towards the bottom
    walls = QLinearGradient(0, skirt.top(), 0, skirt.bottom())
    walls.setColorAt(0.0, QColor("#d9dce4"))
    walls.setColorAt(1.0, QColor("#9ea3b2"))
    p.setBrush(walls)
    p.drawRoundedRect(skirt, 12, 12)

    # front wall is the most visible face: shade it a bit darker
    front = QPainterPath()
    front.moveTo(top.left() + 4, top.bottom() - 2)
    front.lineTo(top.right() - 4, top.bottom() - 2)
    front.lineTo(skirt.right() - 6, skirt.bottom() - 1)
    front.lineTo(skirt.left() + 6, skirt.bottom() - 1)
    front.closeSubpath()
    face = QLinearGradient(0, top.bottom(), 0, skirt.bottom())
    face.setColorAt(0.0, QColor(120, 125, 140, 70))
    face.setColorAt(1.0, QColor(90, 95, 110, 120))
    p.setBrush(face)
    p.drawPath(front)

    # top surface with a concave dish
    cap = QLinearGradient(0, top.top(), 0, top.bottom())
    cap.setColorAt(0.0, QColor("#ffffff"))
    cap.setColorAt(1.0, QColor("#e3e5ec"))
    p.setBrush(cap)
    p.drawRoundedRect(top, 9, 9)
    dish = QRadialGradient(top.center().x(), top.center().y() - 3, top.width() * 0.62)
    dish.setColorAt(0.0, QColor(255, 255, 255, 0))
    dish.setColorAt(0.75, QColor(180, 185, 200, 40))
    dish.setColorAt(1.0, QColor(150, 155, 172, 110))
    p.setBrush(dish)
    p.drawRoundedRect(top, 9, 9)
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(top.adjusted(0.6, 0.6, -0.6, -0.6), 8.5, 8.5)
    p.setPen(Qt.PenStyle.NoPen)

    # legend: waveform bars
    colors = RECORDING_BARS if recording else IDLE_BARS
    grad = QLinearGradient(top.left() + 4, 0, top.right() - 4, 0)
    for stop, c in zip((0.0, 0.5, 1.0), colors):
        grad.setColorAt(stop, QColor(c))
    p.setBrush(grad)
    if small:
        heights, width, gap = (12, 24, 30, 20, 10), 5.4, 2.8
    else:
        heights, width, gap = (6, 12, 19, 25, 17, 10, 15, 7), 2.7, 2.0
    total = len(heights) * width + (len(heights) - 1) * gap
    x = top.center().x() - total / 2
    cy = top.center().y()
    for h in heights:
        p.drawRoundedRect(QRectF(x, cy - h / 2, width, h), width / 2, width / 2)
        x += width + gap


def pixmap(size: int, recording: bool = False) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 64, size / 64)
    _draw(p, recording, small=size <= 32)
    p.end()
    return pix


def icon(recording: bool = False) -> QIcon:
    result = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        result.addPixmap(pixmap(size, recording))
    return result


def write_ico(path: str) -> None:
    """Multi-size .ico with PNG frames (supported since Windows Vista)."""
    frames = []
    for size in ICO_SIZES:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap(size).save(buf, "PNG")
        frames.append((size, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, blobs = b"", b""
    for size, png in frames:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    with open(path, "wb") as f:
        f.write(header + entries + blobs)
