"""Settings window in the keyboard-deck look. Every change is applied and saved at once."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QGridLayout, QHBoxLayout, QLineEdit, QScrollArea, QSizePolicy, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__, logo
from ..config import (
    CLIPBOARD_ALWAYS, CLIPBOARD_FALLBACK, CLIPBOARD_NEVER, ENGINE_WHISPER, ENGINE_WINDOWS, Config, app_dir,
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
MODELS = [
    ("tiny", "tiny — мгновенно, много ошибок"),
    ("base", "base — быстро (рекомендуется)"),
    ("small", "small — точнее, задержка ≈5 с"),
    ("medium", "medium — точно, очень медленно"),
]
CLIPBOARD_MODES = [
    (CLIPBOARD_FALLBACK, "Если некуда печатать"),
    (CLIPBOARD_ALWAYS, "Всегда"),
    (CLIPBOARD_NEVER, "Никогда"),
]
LINES = [("0", "Как в стиле"), ("1", "1 строка"), ("2", "2 строки"), ("3", "3 строки"), ("4", "4 строки")]
PAGES = [
    ("general", "Диктовка"),
    ("recognition", "Распознавание"),
    ("look", "Индикатор"),
    ("dictionary", "Словарь"),
    ("apps", "Приложения"),
    ("about", "О Typeless"),
]


class SettingsWindow(QWidget):
    changed = Signal(object)  # Config
    style_demo = Signal(str)  # play the overlay style on screen

    def __init__(self, config: Config, hotkey: GlobalHotkey, icon: QIcon, last_text: str = "") -> None:
        super().__init__()
        self.setWindowTitle("Typeless")
        self.setWindowIcon(icon)
        self.resize(1040, 720)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(theme.STYLESHEET)
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
            "apps": self._page_apps,
            "about": self._page_about,
        }
        for key, _ in PAGES:
            self.stack.addWidget(self._scroll(builders[key]()))
        self.open_page("general")

    # --- frame -----------------------------------------------------------------
    def showEvent(self, event) -> None:
        theme.dark_title_bar(self.winId())
        super().showEvent(event)

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(230)
        col = QVBoxLayout(side)
        col.setContentsMargins(18, 22, 14, 18)
        col.setSpacing(6)
        head = QHBoxLayout()
        mark = label("")
        mark.setPixmap(logo.pixmap(30))
        head.addWidget(mark)
        head.addSpacing(8)
        head.addWidget(label("Typeless", "brand"))
        head.addStretch()
        col.addLayout(head)
        col.addSpacing(22)
        self._nav = QButtonGroup(self)
        self._nav_buttons: dict[str, NavKey] = {}
        for key, title in PAGES:
            b = NavKey(title)
            b.clicked.connect(lambda _=False, k=key: self.open_page(k))
            self._nav.addButton(b)
            self._nav_buttons[key] = b
            col.addWidget(b)
        col.addStretch()
        return side

    def _scroll(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        return area

    def _page(self, title: str, lead: str = "") -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(26, 24, 30, 30)
        body = QWidget()
        body.setMaximumWidth(860)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        col.addWidget(label(title, "pageTitle"))
        if lead:
            col.addWidget(label(lead, "muted", wrap=True))
        col.addSpacing(4)
        outer.addWidget(body, 10)
        outer.addStretch(1)
        return page, col

    def open_page(self, key: str) -> None:
        index = [k for k, _ in PAGES].index(key)
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

    # --- dictation ---------------------------------------------------------------
    def _page_general(self) -> QWidget:
        page, col = self._page("Диктовка", "Нажмите клавишу и говорите — текст печатается там, где стоит курсор.")

        plate = Plate("Горячая клавиша", "Клавиша микрофона на Keychron K8 отправляет Win+C. "
                                         "Кнопку мыши можно назначить на то же сочетание в Logi Options+.")
        self.keycaps = KeyCaps(self.config.hotkey)
        self.change_btn = KeyButton("Изменить")
        self.change_btn.clicked.connect(self._start_capture)
        reset = KeyButton("Сбросить")
        reset.clicked.connect(lambda: self._apply_hotkey(DEFAULT_HOTKEY))
        keys_row = QHBoxLayout()
        keys_row.addWidget(self.keycaps, 1)
        keys_row.addWidget(self.change_btn)
        keys_row.addWidget(reset)
        plate.add(layout=keys_row)
        plate.row("Enter во время диктовки", "Допечатывает текст и отправляет. Shift+Enter — обычный перенос строки.")
        col.addWidget(plate)

        plate = Plate("Ввод текста")
        plate.row("Живой ввод", "Слова печатаются, пока вы говорите. Выключите — и текст вставится целиком "
                                "после остановки.", self._toggle(self.config.live_typing, "live_typing"))
        plate.row("Буфер обмена", "Если курсор не в поле ввода, текст не потеряется",
                  self._combo(CLIPBOARD_MODES, self.config.clipboard, "clipboard"))
        col.addWidget(plate)

        plate = Plate("Запуск")
        plate.row("Вместе с Windows", "Typeless тихо стартует в трее и ждёт клавишу",
                  self._toggle(self.config.autostart, "autostart"))
        col.addWidget(plate)
        col.addStretch()
        return page

    # --- recognition -------------------------------------------------------------
    def _page_recognition(self) -> QWidget:
        page, col = self._page("Распознавание", "Как Typeless понимает речь.")
        plate = Plate("Речь")
        mode = LANGUAGE_MODES.get(self.config.language_mode)
        plate.row("Язык", mode.hint if mode else "",
                  self._combo([(m.key, m.title) for m in LANGUAGE_MODES.values()],
                              self.config.language_mode, "language_mode"))
        plate.row("Профиль", "«Программист» подсказывает модели термины кода: commit, deploy, API, React…",
                  self._combo([(k, t) for k, (t, _) in PROFILES.items()], self.config.profile, "profile"))
        col.addWidget(plate)

        plate = Plate("Движок")
        plate.row("Распознавание", "Whisper — локально и бесплатно. Диктовка Windows — облако Microsoft.",
                  self._combo([(ENGINE_WHISPER, "Whisper (локально)"), (ENGINE_WINDOWS, "Диктовка Windows")],
                              self.config.engine, "engine"))
        plate.row("Модель Whisper", "Больше — точнее, но медленнее. Скачивается один раз.",
                  self._combo(MODELS, self.config.whisper_model, "whisper_model"))
        col.addWidget(plate)
        col.addStretch()
        return page

    # --- indicator -----------------------------------------------------------------
    def _page_look(self) -> QWidget:
        page, col = self._page("Индикатор", "Что видно на экране, пока вы говорите. При выборе стиль "
                                            "на несколько секунд появляется внизу экрана.")
        plate = Plate()
        plate.row("Показывать индикатор", "Анимация и живой текст поверх окон",
                  self._toggle(self.config.show_overlay, "show_overlay"))
        col.addWidget(plate)

        plate = Plate("Стиль")
        grid = QGridLayout()
        grid.setSpacing(14)
        self._style_cards: dict[str, StylePreview] = {}
        text_opts = TextOptions.from_dict(self.config.overlay_text)
        for i, (key, style) in enumerate(STYLES.items()):
            c = StylePreview(style)
            c.set_color(self.config.overlay_colors.get(key))
            c.set_text_options(text_opts)
            c.clicked.connect(lambda k=key: self._pick_style(k))
            grid.addWidget(c, i // 3, i % 3)
            self._style_cards[key] = c
        plate.add(layout=grid)
        col.addWidget(plate)

        plate = Plate("Цвет")
        self._color_hint = label("", "muted")
        plate.add(self._color_hint)
        row = QHBoxLayout()
        row.setSpacing(6)
        self._swatches: dict[str, Swatch] = {}
        for key, pal in PRESETS.items():
            s = Swatch(pal.light, pal.main, pal.deep, pal.title)
            s.clicked.connect(lambda _=False, k=key: self._pick_color(k))
            row.addWidget(s)
            self._swatches[key] = s
        self._custom_swatch = Swatch("#ffffff", "#888888", "#333333", "Свой цвет")
        self._custom_swatch.clicked.connect(lambda: self._pick_color(self._custom_value()))
        row.addWidget(self._custom_swatch)
        row.addSpacing(12)
        custom = KeyButton("Свой цвет…")
        custom.clicked.connect(self._choose_custom_color)
        row.addWidget(custom)
        row.addStretch()
        plate.add(layout=row)
        col.addWidget(plate)

        plate = Plate("Текст")
        opts = text_opts
        plate.row("Размер", "", self._text_combo([(k, v[0]) for k, v in SIZES.items()], opts.size, "size"))
        plate.row("Строк на экране", "Сколько последних строк видно одновременно",
                  self._text_combo(LINES, str(opts.lines), "lines"))
        plate.row("Начертание", "", self._text_combo(list(FACES.items()), opts.face, "face"))
        plate.row("Шрифт", "", self._text_combo(list(FAMILIES.items()), opts.family, "family"))
        col.addWidget(plate)
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

    def _custom_value(self) -> str:
        current = self.config.overlay_colors.get(self._style_key, "")
        return current if current.startswith("#") else self._last_custom

    def _sync_swatches(self) -> None:
        choice = self.config.overlay_colors.get(self._style_key) or palettes.STYLE_DEFAULTS.get(self._style_key)
        self._color_hint.setText(f"Для стиля «{STYLES[self._style_key].title}». У каждого стиля свой цвет.")
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
        color = QColorDialog.getColor(QColor(self._custom_value()), self, "Цвет индикатора")
        if color.isValid():
            self._pick_color(color.name())

    # --- dictionary ------------------------------------------------------------
    def _page_dictionary(self, last_text: str) -> QWidget:
        page, col = self._page("Словарь", "Термины подсказывают модели написание, исправления заменяют "
                                          "слова, которые она путает.")

        plate = Plate("Предложенные термины", "Латинские слова из ваших диктовок. ＋ — в словарь, × — не предлагать.")
        holder, self._suggest_flow = transparent_holder()
        plate.add(holder)
        col.addWidget(plate)

        plate = Plate("Мои термины")
        row = QHBoxLayout()
        self._term_input = QLineEdit()
        self._term_input.setPlaceholderText("Например: Terraform, Jira, ClickHouse")
        self._term_input.returnPressed.connect(self._add_term_from_input)
        add = KeyButton("Добавить")
        add.clicked.connect(self._add_term_from_input)
        row.addWidget(self._term_input, 1)
        row.addWidget(add)
        plate.add(layout=row)
        holder, self._terms_flow = transparent_holder()
        plate.add(holder)
        col.addWidget(plate)

        plate = Plate("Исправления", "Модель пишет «ттермен» вместо «термин»? Добавьте замену — или выделите "
                                     "слово в последней диктовке.")
        row = QHBoxLayout()
        self._wrong = QLineEdit()
        self._wrong.setPlaceholderText("Как распозналось")
        self._right = QLineEdit()
        self._right.setPlaceholderText("Как должно быть")
        self._right.returnPressed.connect(self._add_correction)
        add = KeyButton("Добавить")
        add.clicked.connect(self._add_correction)
        row.addWidget(self._wrong, 1)
        row.addWidget(label("→", "muted"))
        row.addWidget(self._right, 1)
        row.addWidget(add)
        plate.add(layout=row)
        holder, self._fix_flow = transparent_holder()
        plate.add(holder)
        self._last = QTextEdit()
        self._last.setReadOnly(True)
        self._last.setFixedHeight(80)
        self._last.setPlaceholderText("Здесь появится текст последней диктовки")
        self._last.selectionChanged.connect(self._on_last_selection)
        plate.add(label("Последняя диктовка", "rowTitle"))
        plate.add(self._last)
        col.addWidget(plate)
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
        if not self.config.suggested_terms:
            self._suggest_flow.addWidget(label("Пока пусто — продиктуйте что-нибудь с английскими терминами.",
                                               "muted"))
        for term in self.config.dictionary:
            self._terms_flow.addWidget(Chip(term, [("×", "Удалить", lambda t=term: self._remove_term(t))]))
        for wrong, right in self.config.corrections.items():
            self._fix_flow.addWidget(Chip(f"{wrong} → {right}",
                                          [("×", "Удалить", lambda w=wrong: self._remove_correction(w))]))
        for flow in (self._suggest_flow, self._terms_flow, self._fix_flow):
            flow.parentWidget().updateGeometry()
            flow.invalidate()

    # --- apps -----------------------------------------------------------------------
    def _page_apps(self) -> QWidget:
        page, col = self._page("Приложения", "В этих программах горячая клавиша не запускает Typeless, а нажимает "
                                             "их собственное сочетание — например, встроенную диктовку VS Code.")
        self._rules_plate_holder = QVBoxLayout()
        col.addLayout(self._rules_plate_holder)

        plate = Plate("Новое правило")
        row = QHBoxLayout()
        self._rule_app = QLineEdit()
        self._rule_app.setPlaceholderText("Программа, например Code.exe")
        self._rule_keys = QLineEdit()
        self._rule_keys.setPlaceholderText("Сочетание, например Ctrl+D")
        self._rule_keys.returnPressed.connect(self._add_rule)
        add = KeyButton("Добавить")
        add.clicked.connect(self._add_rule)
        row.addWidget(self._rule_app, 1)
        row.addWidget(self._rule_keys, 1)
        row.addWidget(add)
        plate.add(layout=row)
        self._rule_error = label("", "muted")
        plate.add(self._rule_error)
        col.addWidget(plate)
        col.addStretch()
        self._render_rules()
        return page

    def _render_rules(self) -> None:
        while self._rules_plate_holder.count():
            item = self._rules_plate_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        plate = Plate("Правила")
        if not self.config.app_rules:
            plate.row("Правил нет", "Горячая клавиша везде запускает диктовку Typeless")
        for app, keys in self.config.app_rules.items():
            remove = KeyButton("Удалить")
            remove.clicked.connect(lambda _=False, a=app: self._remove_rule(a))
            plate.row(app, f"Вместо диктовки нажимает {keys}", remove)
        self._rules_plate_holder.addWidget(plate)

    def _add_rule(self) -> None:
        app, keys = self._rule_app.text().strip(), self._rule_keys.text().strip()
        if not app or not keys:
            self._rule_error.setText("Укажите программу и сочетание клавиш.")
            return
        try:
            keys = str(Hotkey.parse(keys))
        except ValueError:
            self._rule_error.setText(f"Не понял сочетание «{keys}». Пример: Ctrl+D, Ctrl+Alt+V, F13.")
            return
        if not app.lower().endswith(".exe"):
            app += ".exe"
        self._rule_error.setText("")
        self._set(app_rules={**self.config.app_rules, app: keys})
        self._rule_app.clear()
        self._rule_keys.clear()
        self._render_rules()

    def _remove_rule(self, app: str) -> None:
        self._set(app_rules={k: v for k, v in self.config.app_rules.items() if k != app})
        self._render_rules()

    # --- about ------------------------------------------------------------------------
    def _page_about(self) -> QWidget:
        page, col = self._page("О Typeless")
        plate = Plate()
        head = QHBoxLayout()
        mark = label("")
        mark.setPixmap(logo.pixmap(64))
        head.addWidget(mark)
        head.addSpacing(12)
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(label("Typeless", "brand"))
        names.addWidget(label(f"Версия {__version__}", "muted"))
        head.addLayout(names)
        head.addStretch()
        plate.add(layout=head)
        plate.add(label("Голосовой ввод в любое поле. Распознавание на faster-whisper, локально: аудио не "
                        "покидает компьютер (кроме движка «Диктовка Windows»).", "muted", wrap=True))
        col.addWidget(plate)

        plate = Plate()
        folder = KeyButton("Открыть")
        folder.clicked.connect(lambda: os.startfile(app_dir()))
        plate.row("Настройки и лог", str(app_dir()), folder)
        repo = KeyButton("Открыть")
        repo.clicked.connect(lambda: webbrowser.open("https://github.com/imangali01/typeless"))
        plate.row("Исходный код", "github.com/imangali01/typeless", repo)
        col.addWidget(plate)
        col.addStretch()
        return page

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
