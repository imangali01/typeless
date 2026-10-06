"""Settings dialog: hotkey, engine, model, language, behaviour, dictionary."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .config import ENGINE_WHISPER, ENGINE_WINDOWS, Config
from .hotkey import GlobalHotkey
from .keys import DEFAULT_HOTKEY, Hotkey

ENGINES = [
    (ENGINE_WHISPER, "Whisper — локально, бесплатно (свой оверлей)"),
    (ENGINE_WINDOWS, "Диктовка Windows (Win+H, через облако Microsoft)"),
]
MODELS = [
    ("tiny", "tiny — самая быстрая, слабое качество"),
    ("base", "base — быстро, лаг ≈1.5 с (рекомендуется)"),
    ("small", "small — точнее, лаг ≈5 с на этом ПК"),
    ("medium", "medium — точно, но очень медленно на CPU"),
]
LANGUAGES = [("ru", "Русский (+ английские термины)"), ("en", "English")]
VK_ESCAPE = 0x1B


def _fill(combo: QComboBox, items, current: str) -> None:
    for value, label in items:
        combo.addItem(label, value)
    index = combo.findData(current)
    combo.setCurrentIndex(max(index, 0))


class SettingsWindow(QDialog):
    saved = Signal(object)  # Config

    def __init__(self, config: Config, hotkey: GlobalHotkey, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Typeless — настройки")
        self.setMinimumWidth(500)
        self._config = config
        self._hook = hotkey
        self._hotkey = Hotkey.parse(config.hotkey)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.hotkey_label = QLabel(str(self._hotkey))
        self.hotkey_label.setStyleSheet("font-weight: 600; padding: 4px 8px; border: 1px solid #888; border-radius: 4px;")
        self.change_btn = QPushButton("Изменить…")
        self.change_btn.clicked.connect(self._start_capture)
        reset_btn = QPushButton("Сбросить")
        reset_btn.setToolTip(f"Вернуть {DEFAULT_HOTKEY}")
        reset_btn.clicked.connect(lambda: self._set_hotkey(DEFAULT_HOTKEY))
        row = QHBoxLayout()
        row.addWidget(self.hotkey_label, 1)
        row.addWidget(self.change_btn)
        row.addWidget(reset_btn)
        form.addRow("Горячая клавиша:", row)

        self.engine = QComboBox()
        _fill(self.engine, ENGINES, config.engine)
        self.engine.currentIndexChanged.connect(self._sync_enabled)
        form.addRow("Движок:", self.engine)

        self.model = QComboBox()
        _fill(self.model, MODELS, config.whisper_model)
        form.addRow("Модель Whisper:", self.model)

        self.language = QComboBox()
        _fill(self.language, LANGUAGES, config.language)
        form.addRow("Язык:", self.language)

        self.live = QCheckBox("Печатать слова сразу, пока я говорю")
        self.live.setChecked(config.live_typing)
        form.addRow("Живой режим:", self.live)

        self.overlay = QCheckBox("Показывать «таблетку» с текстом")
        self.overlay.setChecked(config.show_overlay)
        form.addRow("Оверлей:", self.overlay)

        self.autostart = QCheckBox("Запускать вместе с Windows")
        self.autostart.setChecked(config.autostart)
        form.addRow("Автозапуск:", self.autostart)

        self.dictionary = QPlainTextEdit("\n".join(config.dictionary))
        self.dictionary.setPlaceholderText("Kubernetes\npull request\nREADME\n…по одному термину в строке")
        self.dictionary.setFixedHeight(110)
        form.addRow("Словарь терминов:", self.dictionary)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._hook.captured.connect(self._on_captured, Qt.ConnectionType.QueuedConnection)
        self._sync_enabled()

    # --- hotkey capture ----------------------------------------------------
    def _start_capture(self) -> None:
        self.hotkey_label.setText("Нажмите новое сочетание… (Esc — отмена)")
        self.change_btn.setEnabled(False)
        self._hook.start_capture()

    def _on_captured(self, hotkey: Hotkey) -> None:
        self.change_btn.setEnabled(True)
        if hotkey.vk == VK_ESCAPE and not hotkey.modifiers:
            self._set_hotkey(self._hotkey)
        else:
            self._set_hotkey(hotkey)

    def _set_hotkey(self, hotkey: Hotkey) -> None:
        self._hotkey = hotkey
        self.hotkey_label.setText(str(hotkey))

    # --- misc ----------------------------------------------------------------
    def _sync_enabled(self) -> None:
        whisper = self.engine.currentData() == ENGINE_WHISPER
        for widget in (self.model, self.language, self.live, self.overlay, self.dictionary):
            widget.setEnabled(whisper)

    def _save(self) -> None:
        terms = [t.strip() for t in self.dictionary.toPlainText().splitlines() if t.strip()]
        config = replace(
            self._config,
            hotkey=str(self._hotkey),
            engine=self.engine.currentData(),
            whisper_model=self.model.currentData(),
            language=self.language.currentData(),
            live_typing=self.live.isChecked(),
            show_overlay=self.overlay.isChecked(),
            autostart=self.autostart.isChecked(),
            dictionary=terms,
        )
        self.saved.emit(config)
        self.accept()

    def done(self, result: int) -> None:
        self._hook.cancel_capture()
        self._hook.captured.disconnect(self._on_captured)
        super().done(result)

    def keyPressEvent(self, event) -> None:
        # Esc during capture is handled by the hook; don't let it close the dialog.
        if event.key() == Qt.Key.Key_Escape and not self.change_btn.isEnabled():
            return
        super().keyPressEvent(event)
