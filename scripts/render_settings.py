"""Render every settings page to PNGs: python scripts/render_settings.py out_dir"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, ".")
from typeless.app import make_icon  # noqa: E402
from typeless.config import Config  # noqa: E402
from typeless.hotkey import GlobalHotkey  # noqa: E402
from typeless.keys import DEFAULT_HOTKEY  # noqa: E402
from typeless.ui.settings_window import PAGES, SettingsWindow  # noqa: E402

app = QApplication([])
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
config = Config(dictionary=["Kubernetes", "Terraform", "ClickHouse"], corrections={"ттермен": "термин"},
                suggested_terms=["Helm", "Grafana"])
win = SettingsWindow(config, GlobalHotkey(DEFAULT_HOTKEY), make_icon(False),
                     "Сегодня обсудим ттермен и деплой на кубернитис.")
win.show()
for key, _ in PAGES:
    win.open_page(key)
    for _ in range(5):
        app.processEvents()
    win.grab().save(str(out / f"settings_{key}.png"))
    print("saved", key)
