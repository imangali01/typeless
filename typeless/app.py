"""Entry point: tray app with the global hotkey, dictation controller and settings."""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import autostart
from . import winapi as w
from .config import Config, app_dir
from .controller import Controller, State
from .hotkey import GlobalHotkey
from .keys import Hotkey
from .settings_window import SettingsWindow

log = logging.getLogger("typeless")


def make_icon(recording: bool) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ff4d5e" if recording else "#2f6bff"))
    p.drawEllipse(2, 2, 60, 60)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(24, 12, 16, 26, 8, 8)  # microphone capsule
    pen = QPen(QColor("white"), 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(17, 18, 30, 28, 200 * 16, 140 * 16)
    p.drawLine(QPointF(32, 46), QPointF(32, 53))
    p.end()
    return QIcon(pix)


class TrayApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.config = Config.load()
        self.config.autostart = autostart.is_enabled()

        self.hotkey = GlobalHotkey(Hotkey.parse(self.config.hotkey))
        self.controller = Controller(self.config)
        # Queued: the hook callback must return at once, or Windows silently drops the hook.
        self.hotkey.triggered.connect(self.controller.toggle, Qt.ConnectionType.QueuedConnection)

        self.icons = {False: make_icon(False), True: make_icon(True)}
        self.tray = QSystemTrayIcon(self.icons[False])
        menu = QMenu()
        self.toggle_action = QAction()
        self.toggle_action.triggered.connect(self.controller.toggle)
        menu.addAction(self.toggle_action)
        menu.addAction("Настройки…", self.open_settings)
        menu.addAction("Открыть папку с логом", lambda: os.startfile(app_dir()))
        menu.addSeparator()
        menu.addAction("Выход", self.quit)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.controller.state_changed.connect(self._on_state)
        self.controller.notify.connect(
            lambda title, msg: self.tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 4000))
        self._settings: SettingsWindow | None = None
        self._on_state(State.IDLE)

    def run(self) -> None:
        self.hotkey.install()
        self.tray.show()
        self.tray.showMessage("Typeless запущен",
                              f"Нажмите {self.config.hotkey}, чтобы начать диктовку.",
                              QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_state(self, state: State) -> None:
        recording = state is not State.IDLE
        self.tray.setIcon(self.icons[recording])
        verb = "Остановить" if recording else "Начать"
        self.toggle_action.setText(f"{verb} диктовку ({self.config.hotkey})")
        self.tray.setToolTip("Typeless — идёт диктовка" if recording else "Typeless")

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def open_settings(self) -> None:
        if self._settings is not None:
            self._settings.raise_()
            self._settings.activateWindow()
            return
        self._settings = SettingsWindow(self.config, self.hotkey)
        self._settings.saved.connect(self._apply)
        self._settings.finished.connect(self._settings_closed)
        self._settings.show()
        self._settings.activateWindow()

    def _settings_closed(self) -> None:
        self._settings.deleteLater()
        self._settings = None

    def _apply(self, config: Config) -> None:
        if config.autostart != self.config.autostart:
            autostart.set_enabled(config.autostart)
        self.hotkey.set_hotkey(Hotkey.parse(config.hotkey))
        self.controller.apply_config(config)
        config.save()
        self.config = config
        self._on_state(self.controller.state)

    def quit(self) -> None:
        self.hotkey.uninstall()
        self.controller.shutdown()
        self.tray.hide()
        self.app.quit()


def _setup_logging() -> None:
    handlers = [logging.FileHandler(app_dir() / "typeless.log", encoding="utf-8")]
    if sys.stderr is not None:  # pythonw has no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("faster_whisper", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> int:
    _setup_logging()
    mutex = w.kernel32.CreateMutexW(None, False, "Local\\TypelessSingleInstance")
    if mutex and w.ctypes.get_last_error() == w.ERROR_ALREADY_EXISTS:
        log.info("already running, exiting")
        return 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Typeless")
    tray = TrayApp(app)
    tray.run()
    return app.exec()
