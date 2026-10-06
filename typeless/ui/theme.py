"""Code-editor look (in the spirit of Cursor): graphite, thin borders, compact rows,
monochrome icons, monospace key chips, one restrained blue accent. Always dark.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase


@dataclass(frozen=True)
class Tokens:
    dark: bool
    window: str  # content area (the "editor")
    sidebar: str
    group: str  # bordered setting cards
    separator: str  # borders and dividers
    control: str  # inputs, selects, secondary buttons
    control_border: str
    field: str
    text: str
    secondary: str
    tertiary: str
    accent: str
    switch_off: str
    selection_text: str


T = Tokens(
    dark=True,
    window="#181818",
    sidebar="#141414",
    group="#1e1e1e",
    separator="#2a2a2a",
    control="#252525",
    control_border="#333333",
    field="#202020",
    text="#e4e4e4",
    secondary="#8b8b8b",
    tertiary="#5a5a5a",
    accent="#3b82f6",
    switch_off="#3a3a3a",
    selection_text="#ffffff",
)


def init() -> Tokens:
    return T


ICON_FONT = "Segoe Fluent Icons"
MONO = ["Cascadia Code", "Cascadia Mono", "Consolas"]


def icon_font(size: float) -> QFont:
    family = ICON_FONT if ICON_FONT in QFontDatabase.families() else "Segoe MDL2 Assets"
    f = QFont(family)
    f.setPointSizeF(size)
    return f


def font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont("Segoe UI Variable Text")
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def mono(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(MONO[0])
    f.setFamilies(MONO)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def title_bar(win_id: int, t: Tokens) -> None:
    """Dark native frame tinted to the sidebar colour."""
    try:
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        r, g, b = (int(t.sidebar[i:i + 2], 16) for i in (1, 3, 5))
        caption = ctypes.c_int(r | (g << 8) | (b << 16))  # COLORREF 0x00BBGGRR
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except Exception:
        pass


def stylesheet(t: Tokens) -> str:
    return f"""
QWidget {{ background: {t.window}; color: {t.text}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 9.5pt; }}
QWidget#sidebar {{ background: {t.sidebar}; border-right: 1px solid {t.separator}; }}
QLabel {{ background: transparent; }}
QLabel#pageTitle {{ font-size: 15pt; font-weight: 600; }}
QLabel#groupHeader {{ font-size: 9.5pt; font-weight: 600; color: {t.text}; }}
QLabel#footnote {{ font-size: 8.5pt; color: {t.secondary}; }}
QLabel#rowTitle {{ font-size: 9.5pt; }}
QLabel#secondary {{ font-size: 8.5pt; color: {t.secondary}; }}
QLabel#appName {{ font-size: 10.5pt; font-weight: 600; }}
QFrame#group {{ background: {t.group}; border: 1px solid {t.separator}; border-radius: 8px; }}
QPushButton#link {{ background: transparent; border: none; color: {t.secondary}; padding: 2px 0; font-size: 8.5pt; }}
QPushButton#link:hover {{ color: {t.text}; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {t.field}; border: 1px solid {t.control_border}; border-radius: 6px; padding: 5px 9px;
    selection-background-color: {t.accent}; selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {t.accent}; }}
QComboBox {{
    background: {t.control}; border: 1px solid {t.control_border}; border-radius: 6px;
    padding: 4px 28px 4px 10px; min-width: 160px;
}}
QComboBox:hover {{ border-color: #444444; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {t.group}; border: 1px solid {t.control_border}; border-radius: 6px; padding: 4px; outline: none;
    selection-background-color: #2c2c2c; selection-color: {t.text};
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333333; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {t.group}; color: {t.text}; border: 1px solid {t.control_border}; padding: 3px 7px; }}
"""
