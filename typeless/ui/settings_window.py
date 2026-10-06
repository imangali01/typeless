"""Settings window: calm and simple. Four sections, short labels, changes apply at once."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__, logo
from ..config import (
    CLIPBOARD_ALWAYS, CLIPBOARD_FALLBACK, CLIPBOARD_NEVER, ENGINE_GIGAAM, ENGINE_PARAKEET, ENGINE_WHISPER, Config,
    app_dir,
)
from ..hotkey import GlobalHotkey
from ..keys import DEFAULT_HOTKEY, Hotkey
from ..languages import LANGUAGE_MODES, PROFILES
from ..overlay import STYLES, palettes
from ..overlay.palettes import PRESETS
from ..overlay.textopts import FACES, FAMILIES, SIZES, TextOptions
from . import theme
from .widgets import (
    Chip, Combo, KeyButton, KeyCaps, NavKey, Plate, StylePreview, Swatch, Toggle, label, transparent_holder,
)

VK_ESCAPE = 0x1B
ENGINES = [
    (ENGINE_PARAKEET, "Parakeet — рекомендуется"),
    (ENGINE_GIGAAM, "GigaAM — только русский"),
    (ENGINE_WHISPER, "Whisper — медленнее"),
]
ENGINE_NOTES = {
    ENGINE_PARAKEET: "Русский и английский, термины латиницей, пунктуация. Быстрый и точный. "
                     "Модель скачивается один раз, около 670 МБ.",
    ENGINE_GIGAAM: "Лучше всех понимает русскую речь и быстрее всех, но английские слова пишет "
                   "с ошибками. Модель скачивается один раз, около 230 МБ.",
    ENGINE_WHISPER: "Прежний движок: нагружает процессор сильнее и печатает с задержкой. "
                    "Словарь подсказывает ему написание терминов.",
}
MODELS = [
    ("base", "base — быстрее"),
    ("small", "small — точнее, медленно"),
]
CLIPBOARD_MODES = [
    (CLIPBOARD_FALLBACK, "Если некуда печатать"),
    (CLIPBOARD_ALWAYS, "Всегда"),
    (CLIPBOARD_NEVER, "Никогда"),
]
LINES = [("0", "Авто"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")]
PAGES = [  # key, title, monochrome glyph (Segoe Fluent Icons)
    ("general", "Основное", ""),
    ("recognition", "Распознавание", ""),
    ("look", "Индикатор", ""),
    ("dictionary", "Словарь", ""),
]


class SettingsWindow(QWidget):
    changed = Signal(object)  # Config
    style_demo = Signal(str)  # play the overlay style on screen

    def __init__(self, config: Config, hotkey: GlobalHotkey, icon: QIcon, last_text: str = "") -> None:
        super().__init__()
        self.t = theme.init()
        self.setWindowTitle("Typeless")
        self.setWindowIcon(icon)
        self.resize(900, 640)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(theme.stylesheet(self.t))
        self.config = config
        self._hook = hotkey
        self._hook.captured.connect(self._on_captured, Qt.ConnectionType.QueuedConnection)
        self._style_key = config.overlay_style
        self._last_custom = "#3fa7ff"

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        builders = {
            "general": self._page_general,
            "recognition": self._page_recognition,
            "look": self._page_look,
            "dictionary": lambda: self._page_dictionary(last_text),
        }
        for key, *_ in PAGES:
            self.stack.addWidget(self._scroll(builders[key]()))
        self.open_page("general")

    # --- frame -------------------------------------------------------------------
    def showEvent(self, event) -> None:
        theme.title_bar(self.winId(), self.t)
        super().showEvent(event)

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(200)
        col = QVBoxLayout(side)
        col.setContentsMargins(12, 20, 12, 16)
        col.setSpacing(2)
        head = QHBoxLayout()
        head.setContentsMargins(8, 0, 0, 0)
        mark = label("")
        mark.setPixmap(logo.pixmap(22))
        head.addWidget(mark)
        head.addSpacing(6)
        head.addWidget(label("Typeless", "appName"))
        head.addStretch()
        col.addLayout(head)
        col.addSpacing(18)
        self._nav = QButtonGroup(self)
        self._nav_buttons: dict[str, NavKey] = {}
        for key, title, glyph in PAGES:
            b = NavKey(title, glyph)
            b.clicked.connect(lambda _=False, k=key: self.open_page(k))
            self._nav.addButton(b)
            self._nav_buttons[key] = b
            col.addWidget(b)
        col.addStretch()
        col.addWidget(label(f"Версия {__version__}", "secondary"))
        for text, action in (("Папка настроек", lambda: os.startfile(app_dir())),
                             ("GitHub", lambda: webbrowser.open("https://github.com/imangali01/typeless"))):
            link = QPushButton(text)
            link.setObjectName("link")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.clicked.connect(action)
            col.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        return side

    def _scroll(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        return area

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(32, 26, 32, 28)
        body = QWidget()
        body.setMaximumWidth(640)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(22)
        col.addWidget(label(title, "pageTitle"))
        outer.addWidget(body, 10)
        outer.addStretch(1)
        return page, col

    def open_page(self, key: str) -> None:
        if key not in self._nav_buttons:
            key = "general"
        index = [k for k, *_ in PAGES].index(key)
        self.stack.setCurrentIndex(index)
        self._nav_buttons[key].setChecked(True)

    def _set(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self.changed.emit(self.config)

    def _combo(self, items, value: str, field: str) -> Combo:
        combo = Combo(items, value)
        combo.currentIndexChanged.connect(lambda _: self._set(**{field: combo.currentData()}))
        return combo

    def _toggle(self, value: bool, field: str) -> Toggle:
        toggle = Toggle(value)
        toggle.toggled.connect(lambda v: self._set(**{field: v}))
        return toggle

    # --- general ------------------------------------------------------------------
    def _page_general(self) -> QWidget:
        page, col = self._page("Основное")

        group = Plate()
        self.keycaps = KeyCaps(self.config.hotkey)
        self.change_btn = KeyButton("Изменить")
        self.change_btn.clicked.connect(self._start_capture)
        reset = KeyButton("Сбросить")
        reset.clicked.connect(lambda: self._apply_hotkey(DEFAULT_HOTKEY))
        group.row("Горячая клавиша", "", self.keycaps, self.change_btn, reset)
        group.row("Печатать во время речи", "", self._toggle(self.config.live_typing, "live_typing"))
        group.row("Копировать в буфер", "", self._combo(CLIPBOARD_MODES, self.config.clipboard, "clipboard"))
        group.row("Запускать с Windows", "", self._toggle(self.config.autostart, "autostart"))
        col.addWidget(group)
        col.addWidget(label("Enter во время диктовки допечатывает текст и отправляет.", "footnote", wrap=True))

        self._rules_holder = QVBoxLayout()
        self._rules_holder.setSpacing(6)
        col.addLayout(self._rules_holder)
        self._render_rules()
        col.addStretch()
        return page

    def _render_rules(self) -> None:
        while self._rules_holder.count():
            item = self._rules_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        group = Plate("Своя диктовка в приложениях")
        for app, keys in self.config.app_rules.items():
            remove = KeyButton("Убрать")
            remove.clicked.connect(lambda _=False, a=app: self._remove_rule(a))
            group.row(app, f"нажимает {keys}", remove)
        row = QHBoxLayout()
        self._rule_app = QLineEdit()
        self._rule_app.setPlaceholderText("Code.exe")
        self._rule_keys = QLineEdit()
        self._rule_keys.setPlaceholderText("Ctrl+D")
        self._rule_keys.returnPressed.connect(self._add_rule)
        add = KeyButton("Добавить", default=True)
        add.clicked.connect(self._add_rule)
        row.addWidget(self._rule_app, 1)
        row.addWidget(self._rule_keys, 1)
        row.addWidget(add)
        group.add(layout=row)
        self._rules_holder.addWidget(group)
        self._rule_error = label("В этих программах клавиша нажимает их собственное сочетание вместо Typeless.",
                                 "footnote", wrap=True)
        self._rules_holder.addWidget(self._rule_error)

    def _add_rule(self) -> None:
        app, keys = self._rule_app.text().strip(), self._rule_keys.text().strip()
        if not app or not keys:
            return
        try:
            keys = str(Hotkey.parse(keys))
        except ValueError:
            self._rule_error.setText(f"Не понял сочетание «{keys}». Пример: Ctrl+D, Ctrl+Alt+V, F13.")
            return
        if not app.lower().endswith(".exe"):
            app += ".exe"
        self._set(app_rules={**self.config.app_rules, app: keys})
        self._render_rules()

    def _remove_rule(self, app: str) -> None:
        self._set(app_rules={k: v for k, v in self.config.app_rules.items() if k != app})
        self._render_rules()

    # --- recognition -------------------------------------------------------------
    def _page_recognition(self) -> QWidget:
        page, col = self._page("Распознавание")
        group = Plate()
        group.row("Язык", "", self._combo([(m.key, m.title) for m in LANGUAGE_MODES.values()],
                                          self.config.language_mode, "language_mode"))
        group.row("Профиль", "", self._combo([(k, t) for k, (t, _) in PROFILES.items()],
                                             self.config.profile, "profile"))
        col.addWidget(group)
        col.addWidget(label("«Программист» исправляет написание терминов кода: commit, deploy, API.",
                            "footnote", wrap=True))

        group = Plate()
        engine = self._combo(ENGINES, self.config.engine, "engine")
        group.row("Движок", "", engine)
        col.addWidget(group)
        note = label("", "footnote", wrap=True)
        col.addWidget(note)
        whisper = Plate()
        whisper.row("Модель Whisper", "", self._combo(MODELS, self.config.whisper_model, "whisper_model"))
        col.addWidget(whisper)

        def show_engine(_=None) -> None:
            key = engine.currentData()
            note.setText(ENGINE_NOTES.get(key, "") + " Всё распознаётся на компьютере, звук никуда не уходит.")
            whisper.setVisible(key == ENGINE_WHISPER)

        engine.currentIndexChanged.connect(show_engine)
        show_engine()
        col.addStretch()
        return page

    # --- indicator -------------------------------------------------------------------
    def _page_look(self) -> QWidget:
        page, col = self._page("Индикатор")
        group = Plate()
        group.row("Показывать на экране", "", self._toggle(self.config.show_overlay, "show_overlay"))
        col.addWidget(group)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._style_cards: dict[str, StylePreview] = {}
        text_opts = TextOptions.from_dict(self.config.overlay_text)
        for i, (key, style) in enumerate(STYLES.items()):
            c = StylePreview(style)
            c.set_color(self.config.overlay_colors.get(key))
            c.set_text_options(text_opts)
            c.clicked.connect(lambda k=key: self._pick_style(k))
            grid.addWidget(c, i // 3, i % 3)
            self._style_cards[key] = c
        col.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._swatches: dict[str, Swatch] = {}
        for key, pal in PRESETS.items():
            s = Swatch(pal.light, pal.main, pal.deep, pal.title)
            s.clicked.connect(lambda _=False, k=key: self._pick_color(k))
            row.addWidget(s)
            self._swatches[key] = s
        self._custom_swatch = Swatch("#ffffff", "#888888", "#333333", "Свой цвет")
        self._custom_swatch.clicked.connect(self._choose_custom_color)
        row.addWidget(self._custom_swatch)
        row.addStretch()
        col.addLayout(row)

        group = Plate()
        opts = text_opts
        group.row("Размер текста", "", self._text_combo([(k, v[0]) for k, v in SIZES.items()], opts.size, "size"))
        group.row("Строк", "", self._text_combo(LINES, str(opts.lines), "lines"))
        group.row("Начертание", "", self._text_combo(list(FACES.items()), opts.face, "face"))
        group.row("Шрифт", "", self._text_combo(list(FAMILIES.items()), opts.family, "family"))
        col.addWidget(group)
        col.addStretch()
        self._pick_style(self.config.overlay_style, emit=False)
        return page

    def _text_combo(self, items, value: str, key: str) -> Combo:
        combo = Combo(items, value)

        def changed(_: int) -> None:
            data = {**self.config.overlay_text, key: combo.currentData()}
            self._set(overlay_text=data)
            opts = TextOptions.from_dict(data)
            for c in self._style_cards.values():
                c.set_text_options(opts)
            self.style_demo.emit(self._style_key)

        combo.currentIndexChanged.connect(changed)
        return combo

    def _pick_style(self, key: str, emit: bool = True) -> None:
        for k, c in self._style_cards.items():
            c.set_selected(k == key)
        self._style_key = key
        self._sync_swatches()
        if emit:
            self._set(overlay_style=key)
            self.style_demo.emit(key)

    def _sync_swatches(self) -> None:
        choice = self.config.overlay_colors.get(self._style_key) or palettes.STYLE_DEFAULTS.get(self._style_key)
        for k, s in self._swatches.items():
            s.setChecked(k == choice)
        custom = choice if choice and choice.startswith("#") else self._last_custom
        pal = palettes.from_color(custom)
        self._custom_swatch.colors = (pal.light, pal.main, pal.deep)
        self._custom_swatch.setChecked(bool(choice and choice.startswith("#")))
        self._custom_swatch.update()

    def _pick_color(self, choice: str) -> None:
        if choice.startswith("#"):
            self._last_custom = choice
        self._set(overlay_colors={**self.config.overlay_colors, self._style_key: choice})
        self._style_cards[self._style_key].set_color(choice)
        self._sync_swatches()
        self.style_demo.emit(self._style_key)

    def _choose_custom_color(self) -> None:
        current = self.config.overlay_colors.get(self._style_key, "")
        start = current if current.startswith("#") else self._last_custom
        color = QColorDialog.getColor(QColor(start), self, "Цвет индикатора")
        if color.isValid():
            self._pick_color(color.name())
        else:
            self._sync_swatches()

    # --- dictionary ------------------------------------------------------------
    def _page_dictionary(self, last_text: str) -> QWidget:
        page, col = self._page("Словарь")

        group = Plate("Термины")
        row = QHBoxLayout()
        self._term_input = QLineEdit()
        self._term_input.setPlaceholderText("Добавить термин, например Terraform")
        self._term_input.returnPressed.connect(self._add_term_from_input)
        row.addWidget(self._term_input, 1)
        group.add(layout=row)
        holder, self._terms_flow = transparent_holder()
        group.add(holder)
        col.addWidget(group)

        self._suggest_group = Plate("Предложения")
        holder, self._suggest_flow = transparent_holder()
        self._suggest_group.add(holder)
        col.addWidget(self._suggest_group)

        group = Plate("Исправления")
        row = QHBoxLayout()
        self._wrong = QLineEdit()
        self._wrong.setPlaceholderText("ттермен")
        self._right = QLineEdit()
        self._right.setPlaceholderText("термин")
        self._right.returnPressed.connect(self._add_correction)
        row.addWidget(self._wrong, 1)
        row.addWidget(label("→", "secondary"))
        row.addWidget(self._right, 1)
        group.add(layout=row)
        holder, self._fix_flow = transparent_holder()
        group.add(holder)
        col.addWidget(group)

        self._last = QTextEdit()
        self._last.setReadOnly(True)
        self._last.setFixedHeight(72)
        self._last.setPlaceholderText("Последняя диктовка появится здесь. Выделите слово, чтобы исправить его.")
        self._last.selectionChanged.connect(self._on_last_selection)
        col.addWidget(self._last)
        col.addStretch()

        self.set_last_text(last_text)
        self._render_chips()
        return page

    def add_suggestions(self, words: list[str]) -> None:
        known = {w.lower() for w in self.config.suggested_terms + self.config.dictionary + self.config.ignored_terms}
        fresh = [w for w in words if w.lower() not in known]
        if fresh:
            self._set(suggested_terms=(self.config.suggested_terms + fresh)[-30:])
            self._render_chips()

    def set_last_text(self, text: str) -> None:
        self._last.setPlainText(text)

    def _on_last_selection(self) -> None:
        selected = self._last.textCursor().selectedText().strip(" ,.!?;:")
        if selected and len(selected) < 40:
            self._wrong.setText(selected)
            self._right.setFocus()

    def _add_term(self, term: str) -> None:
        term = term.strip()
        if not term:
            return
        dictionary = self.config.dictionary + ([term] if term.lower() not in
                                               {d.lower() for d in self.config.dictionary} else [])
        suggested = [s for s in self.config.suggested_terms if s.lower() != term.lower()]
        self._set(dictionary=dictionary, suggested_terms=suggested)
        self._render_chips()

    def _add_term_from_input(self) -> None:
        for part in self._term_input.text().split(","):
            self._add_term(part)
        self._term_input.clear()

    def _ignore_term(self, term: str) -> None:
        self._set(suggested_terms=[s for s in self.config.suggested_terms if s != term],
                  ignored_terms=self.config.ignored_terms + [term])
        self._render_chips()

    def _remove_term(self, term: str) -> None:
        self._set(dictionary=[d for d in self.config.dictionary if d != term])
        self._render_chips()

    def _add_correction(self) -> None:
        wrong, right = self._wrong.text().strip(), self._right.text().strip()
        if not wrong or not right:
            return
        self._set(corrections={**self.config.corrections, wrong: right})
        self._wrong.clear()
        self._right.clear()
        self._render_chips()

    def _remove_correction(self, wrong: str) -> None:
        self._set(corrections={k: v for k, v in self.config.corrections.items() if k != wrong})
        self._render_chips()

    def _render_chips(self) -> None:
        for flow in (self._suggest_flow, self._terms_flow, self._fix_flow):
            flow.clear()
        for term in self.config.suggested_terms:
            self._suggest_flow.addWidget(Chip(term, [
                ("+", "Добавить в словарь", lambda t=term: self._add_term(t)),
                ("×", "Не предлагать", lambda t=term: self._ignore_term(t)),
            ]))
        self._suggest_group.setVisible(bool(self.config.suggested_terms))
        for term in self.config.dictionary:
            self._terms_flow.addWidget(Chip(term, [("×", "Удалить", lambda t=term: self._remove_term(t))]))
        for wrong, right in self.config.corrections.items():
            self._fix_flow.addWidget(Chip(f"{wrong} → {right}",
                                          [("×", "Удалить", lambda w=wrong: self._remove_correction(w))]))
        for flow in (self._suggest_flow, self._terms_flow, self._fix_flow):
            flow.parentWidget().updateGeometry()
            flow.invalidate()

    # --- hotkey capture ------------------------------------------------------------
    def _start_capture(self) -> None:
        self.keycaps.set_waiting()
        self.change_btn.setEnabled(False)
        self._hook.start_capture()

    def _on_captured(self, hotkey: Hotkey) -> None:
        self.change_btn.setEnabled(True)
        if hotkey.vk == VK_ESCAPE and not hotkey.modifiers:
            self.keycaps.set_text(self.config.hotkey)
        else:
            self._apply_hotkey(hotkey)

    def _apply_hotkey(self, hotkey: Hotkey) -> None:
        self.keycaps.set_text(str(hotkey))
        self._set(hotkey=str(hotkey))

    def closeEvent(self, event) -> None:
        self._hook.cancel_capture()
        super().closeEvent(event)
