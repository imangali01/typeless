"""Types text into whatever window has keyboard focus, via SendInput unicode events."""

from __future__ import annotations

import ctypes
import queue
import threading
import time

from . import winapi as w
from .keys import MODIFIER_VKS
from .live_text import Edit

VK_BACK = 0x08
VK_RETURN = 0x0D

# (vk, scan, flags) per key event; pure so it can be tested without Windows input.
KeyEvent = tuple[int, int, int]


def _press(vk: int = 0, scan: int = 0, flags: int = 0) -> list[KeyEvent]:
    return [(vk, scan, flags), (vk, scan, flags | w.KEYEVENTF_KEYUP)]


def build_events(edit: Edit) -> list[KeyEvent]:
    events: list[KeyEvent] = []
    for _ in range(edit.backspaces):
        events += _press(vk=VK_BACK)
    for ch in edit.text:
        if ch == "\n":
            events += _press(vk=VK_RETURN)
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):  # surrogate pairs become two code units
            unit = int.from_bytes(data[i:i + 2], "little")
            events += _press(scan=unit, flags=w.KEYEVENTF_UNICODE)
    return events


def _modifiers_held() -> bool:
    return any(w.user32.GetAsyncKeyState(vk) & 0x8000 for vks in MODIFIER_VKS.values() for vk in vks)


def _wait_modifiers_released(timeout: float = 1.5) -> None:
    # Typing while Win/Ctrl/Alt is still physically held would turn letters into shortcuts.
    deadline = time.monotonic() + timeout
    while _modifiers_held() and time.monotonic() < deadline:
        time.sleep(0.02)


def send_events(events: list[KeyEvent]) -> None:
    if not events:
        return
    _wait_modifiers_released()
    arr = (w.INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = w.INPUT_KEYBOARD
        arr[i].ki = w.KEYBDINPUT(vk, scan, flags, 0, w.TYPELESS_EXTRA_INFO)
    w.user32.SendInput(len(events), arr, ctypes.sizeof(w.INPUT))


def combo_events(vks: list[int]) -> list[KeyEvent]:
    """Press keys in order and release in reverse, e.g. [VK_LWIN, ord('H')]."""
    return [(vk, 0, 0) for vk in vks] + [(vk, 0, w.KEYEVENTF_KEYUP) for vk in reversed(vks)]


class _Worker:
    """Sends input from its own thread.

    The keyboard hook lives on the Qt main thread; blocking that thread while waiting
    for modifiers to be released would stall the hook and the key state itself.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[list[KeyEvent]] = queue.Queue()
        threading.Thread(target=self._run, name="typer", daemon=True).start()

    def _run(self) -> None:
        while True:
            send_events(self._queue.get())

    def put(self, events: list[KeyEvent]) -> None:
        if events:
            self._queue.put(events)


_worker: _Worker | None = None


def _get_worker() -> _Worker:
    global _worker
    if _worker is None:
        _worker = _Worker()
    return _worker


def apply(edit: Edit) -> None:
    _get_worker().put(build_events(edit))


def press_combo(vks: list[int]) -> None:
    _get_worker().put(combo_events(vks))
