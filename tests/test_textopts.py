from PySide6.QtGui import QFont

from typeless.overlay.text import TextLook
from typeless.overlay.textopts import TextOptions


def base_look():
    f = QFont("Segoe UI")
    f.setPointSizeF(10)
    f.setItalic(True)
    return TextLook(font=f, max_lines=3)


def test_defaults_keep_style_look():
    look = TextOptions().look(base_look())
    assert look.font.pointSizeF() == 10 and look.font.italic() and look.max_lines == 3


def test_size_lines_and_face():
    look = TextOptions(size="xl", lines=1, face="bold").look(base_look())
    assert abs(look.font.pointSizeF() - 14.5) < 0.01
    assert look.max_lines == 1
    assert look.font.weight() == QFont.Weight.Bold and not look.font.italic()


def test_from_dict_sanitises_garbage():
    opts = TextOptions.from_dict({"size": "huge", "lines": 9, "face": "wild", "family": "Comic"})
    assert opts == TextOptions(size="m", lines=4, face="style", family="")
