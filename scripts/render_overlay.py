"""Render the overlay to a PNG for visual checks: python scripts/render_overlay.py out.png"""

import random
import sys

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless.overlay import Overlay  # noqa: E402

app = QApplication([])
o = Overlay()
o.active = True
random.seed(1)
o._levels.extend(random.uniform(0.2, 1.0) for _ in range(15))
o.confirmed = ("Получается, вот пример, как это делается: пример текста с opacity, "
               "который должен выходить снизу из микрофона, и")
o.tentative = "диктованный текст"
o._known_words = 10**6
pix = QPixmap(o.size())
pix.fill(QColor("#3a3a3a"))  # stand-in desktop
o.render(pix)
pix.save(sys.argv[1])
