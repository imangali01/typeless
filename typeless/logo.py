"""The Typeless logo: a keyboard key whose legend is a waveform.

Drawn in code so the tray, windows, exe icon and installer all share one source.
Small sizes get a simplified drawing (fewer, thicker bars) to stay legible at 16 px.
"""

from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
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
    skirt = QRectF(4, 7, 56, 52)  # footprint of the key at the bottom
    top = QRectF(11, 3, 42, 39) if not small else QRectF(9, 3, 46, 41)  # dished top, sits towards the back

    # contact shadow on the desk
    shadow = QRadialGradient(32, 59, 30)
    shadow.setColorAt(0, QColor(0, 0, 0, 90))
    shadow.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(shadow)
    p.drawEllipse(QRectF(2, 52, 60, 12))

    body = QPainterPath()
    body.addRoundedRect(skirt, 11, 11)
    body.addRoundedRect(top, 8, 8)
    body = body.simplified()
    p.save()
    p.setClipPath(body)

    # base colour of the walls
    p.setBrush(QColor("#bfc3cc"))
    p.drawPath(body)

    def wall(points, gradient):
        path = QPainterPath()
        path.moveTo(*points[0])
        for pt in points[1:]:
            path.lineTo(*pt)
        path.closeSubpath()
        p.setBrush(gradient)
        p.drawPath(path)

    # light comes from the upper left: left wall bright, right wall in shade
    left = QLinearGradient(skirt.left(), 0, top.left(), 0)
    left.setColorAt(0, QColor("#c9ccd4"))
    left.setColorAt(1, QColor("#dfe2e8"))
    wall([(top.left(), top.top()), (top.left(), top.bottom()), (skirt.left(), skirt.bottom()),
          (skirt.left(), skirt.top())], left)
    right = QLinearGradient(top.right(), 0, skirt.right(), 0)
    right.setColorAt(0, QColor("#b3b7c1"))
    right.setColorAt(1, QColor("#979ca8"))
    wall([(top.right(), top.top()), (skirt.right(), skirt.top()), (skirt.right(), skirt.bottom()),
          (top.right(), top.bottom())], right)
    # front wall: the biggest visible face, darker towards the desk
    front = QLinearGradient(0, top.bottom(), 0, skirt.bottom())
    front.setColorAt(0, QColor("#c4c8d0"))
    front.setColorAt(1, QColor("#9297a3"))
    wall([(top.left(), top.bottom()), (top.right(), top.bottom()), (skirt.right(), skirt.bottom()),
          (skirt.left(), skirt.bottom())], front)
    # bright edge where the wall meets the desk catches a little light
    p.setPen(QPen(QColor(255, 255, 255, 60), 1))
    p.drawLine(QPointF(skirt.left() + 8, skirt.bottom() - 1.2), QPointF(skirt.right() - 8, skirt.bottom() - 1.2))
    p.setPen(Qt.PenStyle.NoPen)
    p.restore()

    # top surface: cylindrical dish — darker at the left/right edges, bright band in the middle
    cap = QLinearGradient(0, top.top(), 0, top.bottom())
    cap.setColorAt(0.0, QColor("#ffffff"))
    cap.setColorAt(1.0, QColor("#e4e6ec"))
    p.setBrush(cap)
    p.drawRoundedRect(top, 8, 8)
    dish = QLinearGradient(top.left(), 0, top.right(), 0)
    dish.setColorAt(0.0, QColor(140, 146, 162, 80))
    dish.setColorAt(0.22, QColor(255, 255, 255, 0))
    dish.setColorAt(0.78, QColor(255, 255, 255, 0))
    dish.setColorAt(1.0, QColor(120, 126, 142, 95))
    p.setBrush(dish)
    p.drawRoundedRect(top, 8, 8)
    # crease where the top turns into the front wall
    p.setPen(QPen(QColor(70, 76, 92, 70), 1.2))
    p.drawLine(QPointF(top.left() + 7, top.bottom() + 0.4), QPointF(top.right() - 7, top.bottom() + 0.4))
    # rim highlight along the back and left edges
    p.setPen(QPen(QColor(255, 255, 255, 230), 1.1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(top.adjusted(0.6, 0.6, -0.6, -0.6), 7.5, 7.5)
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
