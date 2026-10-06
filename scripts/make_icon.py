"""Write packaging/typeless.ico from the same drawing as the tray icon."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless.app import make_pixmap  # noqa: E402

app = QApplication([])
out = Path("packaging/typeless.ico")
out.parent.mkdir(exist_ok=True)
ok = make_pixmap(False, 256).save(str(out), "ICO")
print("saved" if ok else "FAILED", out)
