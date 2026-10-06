"""macOS System Settings look: sidebar with coloured icons, grouped inset lists.

Light/dark follows the system colour scheme. SF Pro isn't on Windows, so text uses
Segoe UI Variable, the closest match in metrics and tone.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication


@dataclass(frozen=True)
class Tokens:
    dark: bool
    window: str  # content area
    sidebar: str
    group: str  # grouped list background
    separator: str
    control: str  # pop-up buttons, push buttons
    control_border: str
    field: str  # text fields
    text: str
    secondary: str
    tertiary: str
    accent: str
    switch_off: str
    selection_text: str


DARK = Tokens(True, "#1e1e1e", "#28282a", "#2c2c2e", "#3a3a3c", "#3a3a3c", "#4a4a4d", "#1c1c1e",
              "#f5f5f7", "#98989d", "#6e6e73", "#0a84ff", "#39393d", "#ffffff")
LIGHT = Tokens(False, "#f5f5f7", "#e8e8ed", "#ffffff", "#e5e5ea", "#ffffff", "#d1d1d6", "#ffffff",
               "#1d1d1f", "#86868b", "#aeaeb2", "#007aff", "#e9e9eb", "#ffffff")

T = DARK


def init() -> Tokens:
    """Pick tokens for the current system scheme (needs a QApplication)."""
    global T
    T = LIGHT if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else DARK
    return T


ICON_FONT = "Segoe Fluent Icons"


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


# Sidebar icon colours, as in macOS System Settings.
ICON_COLORS = {
    "blue": "#0a84ff",
    "purple": "#bf5af2",
    "orange": "#ff9f0a",
    "green": "#30d158",
    "gray": "#8e8e93",
    "indigo": "#5e5ce6",
}


def title_bar(win_id: int, t: Tokens) -> None:
    """Native Windows frame, tinted to match the window (dark/light)."""
    import ctypes

    try:
        dark = ctypes.c_int(1 if t.dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        r, g, b = (int(t.sidebar[i:i + 2], 16) for i in (1, 3, 5))
        caption = ctypes.c_int(r | (g << 8) | (b << 16))  # COLORREF 0x00BBGGRR
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except Exception:
        pass


def stylesheet(t: Tokens) -> str:
    return f"""
QWidget {{ background: {t.window}; color: {t.text}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 10pt; }}
QWidget#sidebar {{ background: {t.sidebar}; border-right: 1px solid {t.separator}; }}
QLabel {{ background: transparent; }}
QLabel#pageTitle {{ font-size: 17pt; font-weight: 600; }}
QPushButton#link {{ background: transparent; border: none; color: {t.secondary}; padding: 2px 0; font-size: 9pt; }}
QPushButton#link:hover {{ color: {t.text}; }}
QLabel#groupHeader {{ font-size: 9.5pt; font-weight: 600; color: {t.text}; padding-left: 10px; }}
QLabel#footnote {{ font-size: 8.5pt; color: {t.secondary}; padding-left: 10px; }}
QLabel#rowTitle {{ font-size: 10pt; }}
QLabel#secondary {{ font-size: 8.5pt; color: {t.secondary}; }}
QLabel#appName {{ font-size: 15pt; font-weight: 700; }}
QFrame#group {{ background: {t.group}; border: 1px solid {t.separator if t.dark else "#e2e2e7"}; border-radius: 10px; }}
QFrame#separator {{ background: {t.separator}; border: none; max-height: 1px; min-height: 1px; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {t.field}; border: 1px solid {t.control_border}; border-radius: 6px; padding: 4px 8px;
    selection-background-color: {t.accent}; selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {t.accent}; padding: 3px 7px; }}
QComboBox {{
    background: {t.control}; border: 1px solid {t.control_border}; border-radius: 6px;
    padding: 3px 30px 3px 9px; min-width: 170px; min-height: 20px;
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {t.group}; border: 1px solid {t.separator}; border-radius: 8px; padding: 4px; outline: none;
    selection-background-color: {t.accent}; selection-color: #ffffff;
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 3px 1px; }}
QScrollBar::handle:vertical {{ background: {t.tertiary}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {t.group}; color: {t.text}; border: 1px solid {t.separator}; padding: 3px 7px; }}
"""
