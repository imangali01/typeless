"""Per-application rules: in some apps the hotkey sends that app's own shortcut instead.

Example: in VS Code the hotkey presses Ctrl+D to start VS Code's built-in dictation,
and Typeless itself stays idle.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from . import winapi as w
from .keys import MODIFIER_VKS, Hotkey

DEFAULT_RULES = {"Code.exe": "Ctrl+D"}

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
w.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
w.kernel32.OpenProcess.restype = wintypes.HANDLE
w.kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
w.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
w.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
w.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
w.user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def foreground_process() -> str:
    """Executable name of the foreground window, e.g. 'Code.exe' ('' if unknown)."""
    hwnd = w.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    w.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = w.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not w.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value)
    finally:
        w.kernel32.CloseHandle(handle)


def match(rules: dict[str, str], process: str) -> Hotkey | None:
    """Shortcut to send instead of dictating, if a rule covers this process."""
    for name, keys in rules.items():
        if name.strip().lower() == process.lower() and keys.strip():
            try:
                return Hotkey.parse(keys)
            except ValueError:
                return None
    return None


def combo_vks(hotkey: Hotkey) -> list[int]:
    """Hotkey -> keys to press in order: modifiers (left-hand variants) then the key."""
    order = ("ctrl", "alt", "shift", "win")
    left = {name: vks[1] if len(vks) > 2 else vks[0] for name, vks in MODIFIER_VKS.items()}
    return [left[m] for m in order if m in hotkey.modifiers] + [hotkey.vk]
