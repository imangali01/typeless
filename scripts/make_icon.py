"""Write packaging/typeless.ico (multi-size) and docs/screenshots/logo.png from typeless/logo.py."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless import logo  # noqa: E402

app = QApplication([])
ico = Path("packaging/typeless.ico")
ico.parent.mkdir(exist_ok=True)
logo.write_ico(str(ico))
print("saved", ico)
png = Path("docs/screenshots/logo.png")
png.parent.mkdir(parents=True, exist_ok=True)
logo.pixmap(256).save(str(png))
print("saved", png)
