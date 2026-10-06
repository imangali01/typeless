"""Temporarily switch a window to the English keyboard layout.

Some apps (VS Code webview panels, browsers) check the *typed character* of a shortcut:
Ctrl+D arrives as Ctrl+"в" in the Russian layout and as another letter in the Kazakh
one, so the shortcut silently does nothing. Sending it while the target window is in
the English layout makes it work whatever layout the user has.
"""

from __future__ import annotations

import ctypes
import logging
import time
from contextlib import contextmanager
from ctypes import wintypes

from . import winapi as w

log = logging.getLogger(__name__)

WM_INPUTLANGCHANGEREQUEST = 0x0050
LANG_ENGLISH = 0x09
US_LAYOUT = "00000409"

w.user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
w.user32.GetKeyboardLayout.restype = wintypes.HKL
w.user32.LoadKeyboardLayoutW.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
w.user32.LoadKeyboardLayoutW.restype = wintypes.HKL
w.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
w.user32.PostMessageW.restype = wintypes.BOOL
w.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
w.user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def is_english(hkl: int) -> bool:
    """HKL low word is the language id; its low 10 bits are the primary language."""
    return (int(hkl or 0) & 0x3FF) == LANG_ENGLISH


def _layout_of(thread_id: int) -> int:
    return int(w.user32.GetKeyboardLayout(thread_id) or 0)


def _request(hwnd, hkl: int) -> None:
    w.user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)


@contextmanager
def english_layout(hwnd, settle_s: float = 0.15):
    """Within the block the window's thread uses the US layout; restored afterwards."""
    thread_id = w.user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
    previous = _layout_of(thread_id) if thread_id else 0
    if not thread_id or is_english(previous):
        yield
        return
    english = int(w.user32.LoadKeyboardLayoutW(US_LAYOUT, 0) or 0)
    if not english:
        yield
        return
    _request(hwnd, english)
    deadline = time.monotonic() + 0.4
    while _layout_of(thread_id) != english and time.monotonic() < deadline:
        time.sleep(0.01)
    log.info("layout %#x -> English for the shortcut", previous & 0xFFFF)
    try:
        yield
        time.sleep(settle_s)  # let the app handle the keys before the layout flips back
    finally:
        _request(hwnd, previous)
