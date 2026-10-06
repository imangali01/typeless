"""Colour palettes for overlay styles: presets plus any custom colour."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class Palette:
    light: str  # highlights, gradient start
    main: str  # the colour people will remember
    deep: str  # shadows, gradient end
    title: str = ""

    def colors(self) -> tuple[QColor, QColor, QColor]:
        return QColor(self.light), QColor(self.main), QColor(self.deep)


PRESETS: dict[str, Palette] = {
    "neon": Palette("#00e5ff", "#7c5cff", "#ff4fd8", "Неон"),
    "coral": Palette("#ffb199", "#f2384f", "#b3122f", "Коралл"),
    "ocean": Palette("#8cc4ff", "#2f6bff", "#1a3fb3", "Океан"),
    "mint": Palette("#b6fff3", "#22d3b6", "#0e7c86", "Мята"),
    "amber": Palette("#ffe08a", "#ffb020", "#e0561f", "Янтарь"),
    "violet": Palette("#d6c8ff", "#8b6cff", "#4a2fc0", "Аметист"),
    "graphite": Palette("#f0f0f3", "#a3a3ad", "#5a5a64", "Графит"),
}

STYLE_DEFAULTS = {"line": "neon", "drop": "mint", "cinema": "coral", "ring": "amber", "pill": "coral"}


def from_color(hex_color: str) -> Palette:
    """Build a palette around one custom colour."""
    c = QColor(hex_color)
    if not c.isValid():
        return PRESETS["ocean"]
    return Palette(c.lighter(160).name(), c.name(), c.darker(170).name(), "Свой")


def resolve(style_key: str, choice: str | None) -> Palette:
    """Config value (preset key or '#rrggbb') -> Palette, falling back to the style default."""
    if choice and choice.startswith("#"):
        return from_color(choice)
    if choice in PRESETS:
        return PRESETS[choice]
    return PRESETS[STYLE_DEFAULTS.get(style_key, "ocean")]
