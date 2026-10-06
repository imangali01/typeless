"""The Typeless logo: a keyboard key whose legend is a waveform.

Drawn in code so the tray, windows, exe icon and installer all share one source.
Small sizes get a simplified drawing (fewer, thicker bars) to stay legible at 16 px.
"""

from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap

IDLE_BARS = ("#00e5ff", "#7c5cff", "#ff4fd8")
RECORDING_BARS = ("#ffb199", "#f2384f", "#b3122f")
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _draw(p: QPainter, recording: bool, small: bool) -> None:
    """Paint on a 64x64 canvas."""
    p.setPen(Qt.PenStyle.NoPen)
    # key body (the side you see under the cap)
    p.setBrush(QColor("#2a2c38"))
    p.drawRoundedRect(QRectF(3, 9, 58, 52), 13, 13)
    # key cap
    cap = QLinearGradient(0, 3, 0, 50)
    cap.setColorAt(0, QColor("#f7f7fa"))
    cap.setColorAt(1, QColor("#d6d8e1"))
    p.setBrush(cap)
    p.drawRoundedRect(QRectF(3, 3, 58, 47), 13, 13)
    # legend: waveform bars
    colors = RECORDING_BARS if recording else IDLE_BARS
    grad = QLinearGradient(14, 0, 50, 0)
    for stop, c in zip((0.0, 0.5, 1.0), colors):
        grad.setColorAt(stop, QColor(c))
    p.setBrush(grad)
    if small:
        heights, width, step, left = (12, 24, 30, 20, 10), 5.5, 8.2, 13.4
    else:
        heights, width, step, left = (6, 12, 20, 26, 18, 10, 16, 8), 2.9, 4.8, 14.1
    for i, h in enumerate(heights):
        p.drawRoundedRect(QRectF(left + i * step, 26.5 - h / 2, width, h), width / 2, width / 2)


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
