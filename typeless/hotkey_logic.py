"""Pure keyboard-event state machine behind the global hook.

The Windows hook feeds every physical key event here and gets back a decision:
swallow the event or not, whether the hotkey fired, and whether a "mask" key must be
injected so that releasing Win/Alt alone does not open Start or the menu bar.
"""

from __future__ import annotations

from dataclasses import dataclass

from .keys import Hotkey, VK_TO_MODIFIER, is_modifier


@dataclass(frozen=True)
class Decision:
    suppress: bool = False
    triggered: bool = False
    captured: Hotkey | None = None
    inject_mask: bool = False
    enter: bool = False  # plain Enter pressed while dictating


PASS = Decision()
VK_RETURN = 0x0D


class HotkeyMatcher:
    def __init__(self, hotkey: Hotkey) -> None:
        self.hotkey = hotkey
        self.capturing = False
        self.intercept_enter = False  # on while dictating: Enter finishes and sends
        self._down: set[int] = set()  # physically held modifier VKs
        self._swallowed: set[int] = set()  # non-modifier VKs whose key-up we must eat too

    def modifiers(self) -> frozenset[str]:
        return frozenset(VK_TO_MODIFIER[vk] for vk in self._down)

    def on_event(self, vk: int, is_down: bool) -> Decision:
        if is_modifier(vk):
            if is_down:
                self._down.add(vk)
            else:
                self._down.discard(vk)
            return PASS

        if not is_down:
            if vk in self._swallowed:
                self._swallowed.discard(vk)
                return Decision(suppress=True)
            return PASS

        if vk in self._swallowed:  # auto-repeat of a key we already handled
            return Decision(suppress=True)

        mods = self.modifiers()
        mask = bool(mods & {"win", "alt"})

        if self.capturing:
            self.capturing = False
            self._swallowed.add(vk)
            return Decision(suppress=True, captured=Hotkey(mods, vk), inject_mask=mask)

        if vk == self.hotkey.vk and mods == self.hotkey.modifiers:
            self._swallowed.add(vk)
            return Decision(suppress=True, triggered=True, inject_mask=mask)

        if vk == VK_RETURN and self.intercept_enter and not mods:
            self._swallowed.add(vk)
            return Decision(suppress=True, enter=True)

        return PASS
