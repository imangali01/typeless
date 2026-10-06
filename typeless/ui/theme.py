"""Dark theme for the settings window."""

from __future__ import annotations

import ctypes

BG = "#0f1014"
SIDEBAR = "#0a0b0e"
CARD = "#17181e"
CARD_HOVER = "#1d1f27"
BORDER = "#262833"
TEXT = "#ececf1"
MUTED = "#8d8f9c"
ACCENT = "#7c5cff"
ACCENT_SOFT = "#2a2250"
DANGER = "#ff5c6c"

STYLESHEET = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 10pt; }}
QWidget#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 18pt; font-weight: 600; }}
QLabel#h2 {{ font-size: 11pt; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#brand {{ font-size: 14pt; font-weight: 700; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}
QPushButton#nav {{
    background: transparent; border: none; border-radius: 10px; padding: 10px 14px;
    text-align: left; color: {MUTED}; font-size: 10.5pt;
}}
QPushButton#nav:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT_SOFT}; color: {TEXT}; font-weight: 600; }}
QPushButton {{
    background: {CARD_HOVER}; border: 1px solid {BORDER}; border-radius: 9px; padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #8d72ff; }}
QPushButton#ghost {{ background: transparent; border: none; color: {MUTED}; padding: 4px 6px; }}
QPushButton#ghost:hover {{ color: {TEXT}; }}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 9px; padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""


def dark_title_bar(win_id: int) -> None:
    """Ask DWM for a dark window frame (Windows 10 2004+ / 11)."""
    try:
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
