"""Global low-level keyboard hook that intercepts the configured hotkey (Win+C by default).

The hook must live on a thread with a message loop; we install it on the Qt main thread.
The callback stays tiny: Windows silently drops hooks that exceed LowLevelHooksTimeout.
"""

from __future__ import annotations

import ctypes
import logging

from PySide6.QtCore import QObject, QTimer, Signal

from . import winapi as w
from .hotkey_logic import HotkeyMatcher
from .keys import Hotkey

log = logging.getLogger(__name__)

VK_MASK = 0xE8  # unassigned VK: releasing Win/Alt after it won't open Start / menu bar


def _send_mask() -> None:
    arr = (w.INPUT * 2)()
    for i, flags in enumerate((0, w.KEYEVENTF_KEYUP)):
        arr[i].type = w.INPUT_KEYBOARD
        arr[i].ki = w.KEYBDINPUT(VK_MASK, 0, flags, 0, w.TYPELESS_EXTRA_INFO)
    w.user32.SendInput(2, arr, ctypes.sizeof(w.INPUT))


class GlobalHotkey(QObject):
    # Connect receivers with Qt.QueuedConnection: anything slow running inside the hook
    # callback makes Windows drop the hook.
    triggered = Signal()
    enter_pressed = Signal()  # only while matcher.intercept_enter is on
    captured = Signal(object)  # Hotkey

    def __init__(self, hotkey: Hotkey, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.matcher = HotkeyMatcher(hotkey)
        self._proc = w.HOOKPROC(self._callback)  # keep a reference: ctypes won't
        self._hook = None
        # Re-install periodically in case Windows dropped the hook after a timeout.
        self._refresh = QTimer(self)
        self._refresh.setInterval(60_000)
        self._refresh.timeout.connect(self._reinstall)

    def install(self) -> None:
        self._hook = w.user32.SetWindowsHookExW(
            w.WH_KEYBOARD_LL, self._proc, w.kernel32.GetModuleHandleW(None), 0
        )
        if not self._hook:
            raise ctypes.WinError(ctypes.get_last_error())
        self._refresh.start()
        log.info("keyboard hook installed, hotkey=%s", self.matcher.hotkey)

    def uninstall(self) -> None:
        self._refresh.stop()
        if self._hook:
            w.user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def _reinstall(self) -> None:
        old = self._hook
        self._hook = w.user32.SetWindowsHookExW(
            w.WH_KEYBOARD_LL, self._proc, w.kernel32.GetModuleHandleW(None), 0
        )
        if old:
            w.user32.UnhookWindowsHookEx(old)

    def set_hotkey(self, hotkey: Hotkey) -> None:
        self.matcher.hotkey = hotkey
        log.info("hotkey changed to %s", hotkey)

    def start_capture(self) -> None:
        self.matcher.capturing = True

    def cancel_capture(self) -> None:
        self.matcher.capturing = False

    def _callback(self, n_code: int, w_param: int, l_param: int) -> int:
        try:
            if n_code == 0:
                kb = ctypes.cast(l_param, ctypes.POINTER(w.KBDLLHOOKSTRUCT)).contents
                if kb.dwExtraInfo != w.TYPELESS_EXTRA_INFO:
                    is_down = w_param in (w.WM_KEYDOWN, w.WM_SYSKEYDOWN)
                    decision = self.matcher.on_event(kb.vkCode, is_down)
                    if decision.inject_mask:
                        _send_mask()
                    if decision.triggered:
                        log.debug("hotkey vk=%#x flags=%#x t=%d", kb.vkCode, kb.flags, kb.time)
                        self.triggered.emit()  # queued to receivers by Qt
                    if decision.enter:
                        self.enter_pressed.emit()
                    if decision.captured is not None:
                        self.captured.emit(decision.captured)
                    if decision.suppress:
                        return 1
        except Exception:  # never let an exception escape into the hook chain
            log.exception("hook callback failed")
        return w.user32.CallNextHookEx(None, n_code, w_param, l_param)
