"""Where the user is typing: the text caret of the focused window, or the mouse."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QCursor, QGuiApplication

from .. import winapi as w


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


w.user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
w.user32.GetGUIThreadInfo.restype = wintypes.BOOL
w.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
w.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
w.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
w.user32.ClientToScreen.restype = wintypes.BOOL


def _to_logical(x: int, y: int) -> QPoint:
    """Physical screen pixels (Win32) -> Qt device-independent pixels."""
    for screen in QGuiApplication.screens():
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        native = QRect(geo.topLeft(), geo.size() * dpr)
        if native.contains(x, y):
            return QPoint(geo.left() + round((x - geo.left()) / dpr), geo.top() + round((y - geo.top()) / dpr))
    return QPoint(x, y)


def caret_rect() -> QRect | None:
    """Caret of the foreground window in logical coordinates, if the app exposes one.

    Classic Win32 controls do; browsers and Electron apps usually don't.
    """
    hwnd = w.user32.GetForegroundWindow()
    if not hwnd:
        return None
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    tid = w.user32.GetWindowThreadProcessId(hwnd, None)
    if not w.user32.GetGUIThreadInfo(tid, ctypes.byref(info)) or not info.hwndCaret:
        return None
    rc = info.rcCaret
    if rc.bottom - rc.top <= 0:
        return None
    top_left = wintypes.POINT(rc.left, rc.top)
    bottom = wintypes.POINT(rc.right, rc.bottom)
    w.user32.ClientToScreen(info.hwndCaret, ctypes.byref(top_left))
    w.user32.ClientToScreen(info.hwndCaret, ctypes.byref(bottom))
    tl = _to_logical(top_left.x, top_left.y)
    br = _to_logical(bottom.x, bottom.y)
    return QRect(tl, br)


def mouse_rect() -> QRect:
    pos = QCursor.pos()
    return QRect(pos.x(), pos.y(), 1, 1)


def screen_for(point: QPoint) -> QRect:
    screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
    return screen.availableGeometry()
