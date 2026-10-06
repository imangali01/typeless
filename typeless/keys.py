"""Virtual-key codes, hotkey model and text (de)serialization like "Win+C"."""

from __future__ import annotations

from dataclasses import dataclass

# Modifier name -> all VK codes that count as that modifier (generic, left, right).
MODIFIER_VKS: dict[str, tuple[int, ...]] = {
    "ctrl": (0x11, 0xA2, 0xA3),
    "shift": (0x10, 0xA0, 0xA1),
    "alt": (0x12, 0xA4, 0xA5),
    "win": (0x5B, 0x5C),
}
VK_TO_MODIFIER: dict[int, str] = {vk: name for name, vks in MODIFIER_VKS.items() for vk in vks}
MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MODIFIER_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}

_NAMED_KEYS: dict[int, str] = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End",
    0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2C: "PrintScreen", 0x2D: "Insert", 0x2E: "Delete", 0x5D: "Menu",
    0x90: "NumLock", 0x91: "ScrollLock",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
    0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
    0xAD: "VolumeMute", 0xAE: "VolumeDown", 0xAF: "VolumeUp",
    0xB0: "MediaNext", 0xB1: "MediaPrev", 0xB2: "MediaStop", 0xB3: "MediaPlayPause",
}
for _i in range(24):
    _NAMED_KEYS[0x70 + _i] = f"F{_i + 1}"
for _i in range(10):
    _NAMED_KEYS[0x60 + _i] = f"Num{_i}"
for _c in range(ord("0"), ord("9") + 1):
    _NAMED_KEYS[_c] = chr(_c)
for _c in range(ord("A"), ord("Z") + 1):
    _NAMED_KEYS[_c] = chr(_c)

_NAME_TO_VK = {name.lower(): vk for vk, name in _NAMED_KEYS.items()}


def is_modifier(vk: int) -> bool:
    return vk in VK_TO_MODIFIER


def key_name(vk: int) -> str:
    return _NAMED_KEYS.get(vk, f"VK{vk:02X}")


@dataclass(frozen=True)
class Hotkey:
    modifiers: frozenset[str]
    vk: int

    def __str__(self) -> str:
        mods = [MODIFIER_LABELS[m] for m in MODIFIER_ORDER if m in self.modifiers]
        return "+".join([*mods, key_name(self.vk)])

    @classmethod
    def parse(cls, text: str) -> Hotkey:
        parts = [p.strip() for p in text.split("+") if p.strip()]
        if not parts:
            raise ValueError(f"empty hotkey: {text!r}")
        *mod_parts, key_part = parts
        mods = set()
        for part in mod_parts:
            name = part.lower()
            if name not in MODIFIER_VKS:
                raise ValueError(f"unknown modifier {part!r} in {text!r}")
            mods.add(name)
        key = key_part.lower()
        if key in _NAME_TO_VK:
            vk = _NAME_TO_VK[key]
        elif key.startswith("vk") and len(key) > 2:
            vk = int(key[2:], 16)
        else:
            raise ValueError(f"unknown key {key_part!r} in {text!r}")
        return cls(frozenset(mods), vk)


DEFAULT_HOTKEY = Hotkey(frozenset({"win"}), ord("C"))
