"""User options for the overlay text, applied on top of each style's own look."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtGui import QFont

from .text import TextLook

SIZES = {"s": ("S", 0.85), "m": ("M", 1.0), "l": ("L", 1.2), "xl": ("XL", 1.45)}
FACES = {
    "style": "Как в стиле",
    "regular": "Обычный",
    "bold": "Жирный",
    "italic": "Курсив",
    "bold_italic": "Жирный курсив",
}
FAMILIES = {
    "": "Как в стиле",
    "Segoe UI Variable Text": "Segoe UI",
    "Bahnschrift": "Bahnschrift",
    "Cascadia Code": "Cascadia Code",
    "Georgia": "Georgia",
    "Consolas": "Consolas",
}


@dataclass(frozen=True)
class TextOptions:
    size: str = "m"
    lines: int = 0  # 0 = the style's default
    face: str = "style"
    family: str = ""

    @classmethod
    def from_dict(cls, data: dict | None) -> TextOptions:
        data = data or {}
        opts = cls(
            size=data.get("size", "m") if data.get("size") in SIZES else "m",
            lines=int(data.get("lines", 0)) if str(data.get("lines", 0)).isdigit() else 0,
            face=data.get("face", "style") if data.get("face") in FACES else "style",
            family=data.get("family", "") if data.get("family", "") in FAMILIES else "",
        )
        return replace(opts, lines=max(0, min(4, opts.lines)))

    def font(self, base: QFont) -> QFont:
        f = QFont(base)
        f.setPointSizeF(base.pointSizeF() * SIZES[self.size][1])
        if self.family:
            f.setFamilies([self.family, "Segoe UI"])
        if self.face != "style":
            f.setWeight(QFont.Weight.Bold if "bold" in self.face else QFont.Weight.Normal)
            f.setItalic("italic" in self.face)
        return f

    def look(self, base: TextLook) -> TextLook:
        return replace(base, font=self.font(base.font), max_lines=self.lines or base.max_lines)
