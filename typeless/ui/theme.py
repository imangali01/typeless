"""Typeless look: a keyboard deck.

Graphite deck, plates for sections, light keycaps for navigation and buttons, an
indicator LED for "on". Headings and key legends in Bahnschrift (DIN-like, as on
keycap legends); body text in Segoe UI.
"""

from __future__ import annotations

import ctypes

from PySide6.QtGui import QFont, QFontDatabase

DECK = "#1b1c20"  # window background: the keyboard case
PLATE = "#24262b"  # section plates
PLATE_EDGE = "#2f3137"  # top highlight / dividers on plates
WELL = "#16171a"  # recessed fields (inputs, combo boxes)
TEXT = "#eceef2"
MUTED = "#8f939c"
CAP_TOP = "#eceef1"  # keycap top surface
CAP_TOP_PRESSED = "#d9dbe1"
CAP_WALL = "#a9adb8"  # keycap side wall
CAP_TEXT = "#1b1c20"
LED = "#2fd6ff"  # indicator light: "on", selection, focus
LED_GLOW = "rgba(47, 214, 255, 0.35)"

TITLE_FAMILY = "Bahnschrift"


def title_font(size: float, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    family = TITLE_FAMILY if TITLE_FAMILY in QFontDatabase.families() else "Segoe UI"
    f = QFont(family)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


STYLESHEET = f"""
QWidget {{ background: {DECK}; color: {TEXT}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 10pt; }}
QLabel {{ background: transparent; }}
QLabel#pageTitle {{ font-family: '{TITLE_FAMILY}'; font-size: 22pt; font-weight: 600; }}
QLabel#plateTitle {{ font-family: '{TITLE_FAMILY}'; font-size: 11.5pt; font-weight: 600; color: {TEXT}; }}
QLabel#rowTitle {{ font-size: 10.5pt; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#brand {{ font-family: '{TITLE_FAMILY}'; font-size: 14pt; font-weight: 600; }}
QFrame#plate {{ background: {PLATE}; border: 1px solid {PLATE_EDGE}; border-radius: 12px; }}
QFrame#divider {{ background: {PLATE_EDGE}; border: none; max-height: 1px; min-height: 1px; }}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {WELL}; border: 1px solid #0e0f11; border-top-color: #09090b; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {LED}; selection-color: {DECK};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {LED}; }}
QComboBox {{ min-width: 200px; padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {PLATE}; border: 1px solid {PLATE_EDGE}; border-radius: 8px; padding: 4px; outline: none;
    selection-background-color: {PLATE_EDGE}; selection-color: {TEXT};
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {PLATE_EDGE}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {PLATE}; color: {TEXT}; border: 1px solid {PLATE_EDGE}; padding: 4px 8px; }}
"""


def dark_title_bar(win_id: int) -> None:
    try:
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 20, ctypes.byref(value), ctypes.sizeof(value))
        caption = ctypes.c_int(0x00201C1B)  # COLORREF of DECK (0x00BBGGRR)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(win_id), 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except Exception:
        pass
