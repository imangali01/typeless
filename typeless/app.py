"""Entry point: tray app with the global hotkey, dictation controller and settings.

Only one instance runs. Launching Typeless again (Start menu shortcut) asks the running
instance to open its settings window; `--background` starts silently in the tray.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import autostart, logo
from . import winapi as w
from .config import Config, app_dir
from .controller import Controller, State
from .hotkey import GlobalHotkey
from .keys import Hotkey
from .toast import Toast
from .ui.settings_window import SettingsWindow

log = logging.getLogger("typeless")

TERMS_TOAST_MS = 5000  # long enough to read and click
IPC_NAME = f"typeless-{os.environ.get('USERNAME', 'user')}"


def make_icon(recording: bool, size: int = 64) -> QIcon:
    return logo.icon(recording)


class TrayApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.config = Config.load()
        self.config.autostart = autostart.is_enabled()

        self.hotkey = GlobalHotkey(Hotkey.parse(self.config.hotkey))
        self.controller = Controller(self.config)
        # Queued: the hook callback must return at once, or Windows silently drops the hook.
        self.hotkey.triggered.connect(self.controller.toggle, Qt.ConnectionType.QueuedConnection)
        self.hotkey.enter_pressed.connect(self.controller.submit, Qt.ConnectionType.QueuedConnection)

        self.icons = {False: make_icon(False), True: make_icon(True)}
        app.setWindowIcon(self.icons[False])
        self.tray = QSystemTrayIcon(self.icons[False])
        menu = QMenu()
        self.toggle_action = QAction()
        self.toggle_action.triggered.connect(self.controller.toggle)
        menu.addAction(self.toggle_action)
        menu.addAction("Настройки…", self.open_settings)
        menu.addAction("Словарь и исправления…", lambda: self.open_settings("dictionary"))
        menu.addSeparator()
        menu.addAction("Выход", self.quit)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.messageClicked.connect(lambda: self.open_settings(self._message_page))
        self._message_page = "general"

        self.controller.state_changed.connect(self._on_state)
        self.controller.notify.connect(self._notify)
        self.controller.terms_suggested.connect(self._on_terms)
        self.terms_toast = Toast(clickable=True)
        self.terms_toast.clicked.connect(lambda: self.open_settings("dictionary"))
        self.controller.dictated.connect(self._on_dictated)
        self._settings: SettingsWindow | None = None
        self._on_state(State.IDLE)

        self.server = QLocalServer()
        QLocalServer.removeServer(IPC_NAME)
        self.server.listen(IPC_NAME)
        self.server.newConnection.connect(self._on_ipc)

    def run(self, background: bool) -> None:
        self.hotkey.install()
        self.tray.show()
        QTimer.singleShot(0, self.controller.warm_up)
        if background:
            self._notify("Typeless работает", f"Нажмите {self.config.hotkey}, чтобы начать диктовку.")
        else:
            self.open_settings()

    # --- tray --------------------------------------------------------------------
    def _notify(self, title: str, message: str, page: str = "general") -> None:
        self._message_page = page
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _on_state(self, state: State) -> None:
        recording = state is not State.IDLE
        self.hotkey.matcher.intercept_enter = state is State.RECORDING
        self.tray.setIcon(self.icons[recording])
        verb = "Остановить" if recording else "Начать"
        self.toggle_action.setText(f"{verb} диктовку ({self.config.hotkey})")
        self.tray.setToolTip("Typeless — идёт диктовка" if recording else f"Typeless — {self.config.hotkey}")

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.open_settings()

    def _on_terms(self, words: list[str]) -> None:
        settings = self._ensure_settings()
        before = list(settings.config.suggested_terms)
        settings.add_suggestions(words)
        if settings.config.suggested_terms != before:
            shown = ", ".join(words[:3]) + ("…" if len(words) > 3 else "")
            self.terms_toast.show_message(f"Новые термины: {shown} — нажмите, чтобы добавить в словарь",
                                          TERMS_TOAST_MS)

    def _on_dictated(self, text: str) -> None:
        if self._settings is not None:
            self._settings.set_last_text(text)

    # --- settings ----------------------------------------------------------------
    def _ensure_settings(self) -> SettingsWindow:
        if self._settings is None:
            self._settings = SettingsWindow(self.config, self.hotkey, self.icons[False], self.controller.last_text)
            self._settings.changed.connect(self._apply)
            self._settings.style_demo.connect(self.controller.demo_style)
        return self._settings

    def open_settings(self, page: str = "") -> None:
        settings = self._ensure_settings()
        if page:
            settings.open_page(page)
        settings.showNormal()
        settings.raise_()
        settings.activateWindow()

    def _apply(self, config: Config) -> None:
        if config.autostart != self.config.autostart:
            autostart.set_enabled(config.autostart)
        if config.hotkey != self.config.hotkey:
            self.hotkey.set_hotkey(Hotkey.parse(config.hotkey))
        self.controller.apply_config(config)
        config.save()
        self.config = config
        self._on_state(self.controller.state)

    def _on_ipc(self) -> None:
        conn = self.server.nextPendingConnection()
        conn.waitForReadyRead(500)
        command = bytes(conn.readAll()).decode(errors="ignore").strip()
        conn.disconnectFromServer()
        if command != "background":
            self.open_settings()

    def quit(self) -> None:
        self.hotkey.uninstall()
        self.controller.shutdown()
        self.tray.hide()
        self.server.close()
        self.app.quit()


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.FileHandler(app_dir() / "typeless.log", encoding="utf-8")]
    if sys.stderr is not None:  # pythonw / windowed exe have no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("faster_whisper", "onnx_asr", "httpx", "huggingface_hub", "comtypes"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _signal_running_instance(command: str) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(IPC_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(command.encode())
    sock.waitForBytesWritten(300)
    sock.disconnectFromServer()
    return True


def main() -> int:
    _setup_logging()
    background = "--background" in sys.argv
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Typeless")
    if _signal_running_instance("background" if background else "settings"):
        log.info("already running, asked it to %s", "stay" if background else "open settings")
        return 0
    # Lets the installer/uninstaller detect and close a running Typeless (AppMutex in typeless.iss).
    app.setProperty("mutex", w.kernel32.CreateMutexW(None, False, "TypelessAppMutex"))
    tray = TrayApp(app)
    tray.run(background)
    return app.exec()
