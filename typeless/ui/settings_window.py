"""Settings window: sidebar navigation, pages, every change is applied and saved at once."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QComboBox, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__
from ..config import (
    CLIPBOARD_ALWAYS, CLIPBOARD_FALLBACK, CLIPBOARD_NEVER, ENGINE_WHISPER, ENGINE_WINDOWS, Config,
)
from ..hotkey import GlobalHotkey
from ..keys import DEFAULT_HOTKEY, Hotkey
from ..languages import LANGUAGE_MODES, PROFILES
from ..overlay import STYLES, palettes
from ..overlay.palettes import PRESETS
from . import theme
from .widgets import (
    Chip, FlowLayout, KeyCaps, OptionGroup, SettingRow, StylePreview, Swatch, Toggle, card, label,
)

VK_ESCAPE = 0x1B
MODELS = [
    ("tiny", "tiny — мгновенно, но много ошибок"),
    ("base", "base — быстро, задержка ≈1.5 с  (рекомендуется)"),
    ("small", "small — точнее, задержка ≈5 с на этом ПК"),
    ("medium", "medium — точно, но очень медленно на CPU"),
]
CLIPBOARD_MODES = [
    (CLIPBOARD_FALLBACK, "Если некуда печатать", "Курсор не в поле ввода → текст в буфере"),
    (CLIPBOARD_ALWAYS, "Всегда", "Каждая диктовка копируется в буфер"),
    (CLIPBOARD_NEVER, "Никогда", "Буфер обмена не трогаем"),
]
PAGES = [("general", "Основное"), ("recognition", "Распознавание"), ("look", "Внешний вид"),
         ("dictionary", "Словарь"), ("about", "О программе")]


class SettingsWindow(QWidget):
    changed = Signal(object)  # Config
    style_demo = Signal(str)  # play the overlay style on screen

    def __init__(self, config: Config, hotkey: GlobalHotkey, icon: QIcon, last_text: str = "") -> None:
        super().__init__()
        self.setWindowTitle("Typeless")
        self.setWindowIcon(icon)
        self.resize(980, 680)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(theme.STYLESHEET)
        self.config = config
        self._hook = hotkey
        self._hook.captured.connect(self._on_captured, Qt.ConnectionType.QueuedConnection)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self._pages = {
            "general": self._page_general(),
            "recognition": self._page_recognition(),
            "look": self._page_look(),
            "dictionary": self._page_dictionary(last_text),
            "about": self._page_about(),
        }
        for key, _ in PAGES:
            self.stack.addWidget(self._scroll(self._pages[key]))
        self.open_page("general")

    # --- frame -----------------------------------------------------------------
    def showEvent(self, event) -> None:
        theme.dark_title_bar(self.winId())
        super().showEvent(event)

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        col = QVBoxLayout(side)
        col.setContentsMargins(16, 22, 16, 18)
        col.setSpacing(4)
        brand = QHBoxLayout()
        dot = label("●")
        dot.setStyleSheet(f"color: {theme.ACCENT}; font-size: 16pt;")
        brand.addWidget(dot)
        brand.addWidget(label("Typeless", "brand"))
        brand.addStretch()
        col.addLayout(brand)
        col.addSpacing(18)
        self._nav = QButtonGroup(self)
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, title in PAGES:
            b = QPushButton(title)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.open_page(k))
            self._nav.addButton(b)
            self._nav_buttons[key] = b
            col.addWidget(b)
        col.addStretch()
        self._status = label("", "muted", wrap=True)
        col.addWidget(self._status)
        self._update_status()
        return side

    def _scroll(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        return area

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(36, 30, 36, 30)
        col.setSpacing(16)
        col.addWidget(label(title, "h1"))
        col.addWidget(label(subtitle, "muted", wrap=True))
        col.addSpacing(4)
        return page, col

    def open_page(self, key: str) -> None:
        index = [k for k, _ in PAGES].index(key)
        self.stack.setCurrentIndex(index)
        self._nav_buttons[key].setChecked(True)

    def _update_status(self) -> None:
        engine = "Whisper, локально" if self.config.engine == ENGINE_WHISPER else "Диктовка Windows"
        self._status.setText(f"Горячая клавиша: {self.config.hotkey}\nДвижок: {engine}\nВерсия {__version__}")

    def _set(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self._update_status()
        self.changed.emit(self.config)

    # --- pages -----------------------------------------------------------------
    def _page_general(self) -> QWidget:
        page, col = self._page("Основное", "Как запускать диктовку и что делать с текстом.")

        frame, box = card()
        box.addWidget(label("Горячая клавиша", "h2"))
        box.addWidget(label("Клавиша микрофона на Keychron K8 отправляет Win+C. Кнопку мыши можно "
                            "назначить на то же сочетание в Logi Options+.", "muted", wrap=True))
        row = QHBoxLayout()
        self.keycaps = KeyCaps(self.config.hotkey)
        row.addWidget(self.keycaps, 1)
        self.change_btn = QPushButton("Изменить")
        self.change_btn.setObjectName("primary")
        self.change_btn.clicked.connect(self._start_capture)
        reset = QPushButton("Сбросить")
        reset.clicked.connect(lambda: self._apply_hotkey(DEFAULT_HOTKEY))
        row.addWidget(self.change_btn)
        row.addWidget(reset)
        box.addLayout(row)
        box.addWidget(label("Во время диктовки: Enter — допечатать и отправить, Shift+Enter — обычный перенос.",
                            "muted", wrap=True))
        col.addWidget(frame)

        frame, box = card()
        live = Toggle(self.config.live_typing)
        live.toggled.connect(lambda v: self._set(live_typing=v))
        box.addWidget(SettingRow("Живой режим", "Слова печатаются, пока вы говорите. "
                                 "Если выключить — текст вставится целиком после остановки.", live))
        auto = Toggle(self.config.autostart)
        auto.toggled.connect(lambda v: self._set(autostart=v))
        box.addWidget(SettingRow("Запускать вместе с Windows", "Typeless тихо стартует в трее.", auto))
        col.addWidget(frame)

        frame, box = card()
        box.addWidget(label("Буфер обмена", "h2"))
        clip = OptionGroup([(k, t, h) for k, t, h in CLIPBOARD_MODES], self.config.clipboard, columns=3)
        clip.changed.connect(lambda v: self._set(clipboard=v))
        box.addWidget(clip)
        col.addWidget(frame)
        col.addStretch()
        return page

    def _page_recognition(self) -> QWidget:
        page, col = self._page("Распознавание", "Язык, словарь профиля и движок распознавания речи.")

        frame, box = card()
        box.addWidget(label("Язык", "h2"))
        langs = OptionGroup([(m.key, m.title, m.hint) for m in LANGUAGE_MODES.values()],
                            self.config.language_mode, columns=3)
        langs.changed.connect(lambda v: self._set(language_mode=v))
        box.addWidget(langs)
        col.addWidget(frame)

        frame, box = card()
        box.addWidget(label("Профиль", "h2"))
        profiles = OptionGroup([(k, t, h) for k, (t, h) in PROFILES.items()], self.config.profile)
        profiles.changed.connect(lambda v: self._set(profile=v))
        box.addWidget(profiles)
        col.addWidget(frame)

        frame, box = card()
        box.addWidget(label("Движок", "h2"))
        engines = OptionGroup([
            (ENGINE_WHISPER, "Whisper — локально", "Бесплатно, без интернета, свой оверлей и живой текст"),
            (ENGINE_WINDOWS, "Диктовка Windows", "Встроенная Win+H: облако Microsoft, своя панель"),
        ], self.config.engine)
        engines.changed.connect(lambda v: self._set(engine=v))
        box.addWidget(engines)
        model = QComboBox()
        for key, title in MODELS:
            model.addItem(title, key)
        model.setCurrentIndex(max(0, model.findData(self.config.whisper_model)))
        model.currentIndexChanged.connect(lambda _: self._set(whisper_model=model.currentData()))
        box.addWidget(SettingRow("Модель Whisper", "Больше — точнее, но медленнее. Скачивается один раз.", model))
        col.addWidget(frame)
        col.addStretch()
        return page

    def _page_look(self) -> QWidget:
        page, col = self._page("Внешний вид", "Как выглядит индикатор диктовки. Превью живые.")
        frame, box = card()
        show = Toggle(self.config.show_overlay)
        show.toggled.connect(lambda v: self._set(show_overlay=v))
        box.addWidget(SettingRow("Показывать индикатор", "Анимация и живой текст во время диктовки.", show))
        col.addWidget(frame)

        frame, box = card()
        self._color_title = label("", "h2")
        box.addWidget(self._color_title)
        box.addWidget(label("Цвет запоминается отдельно для каждого стиля. При выборе стиль "
                            "показывается внизу экрана.", "muted", wrap=True))
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
        custom = QPushButton("Свой цвет…")
        custom.clicked.connect(self._choose_custom_color)
        row.addSpacing(8)
        row.addWidget(custom)
        row.addStretch()
        box.addLayout(row)
        col.addWidget(frame)

        grid = QGridLayout()
        grid.setSpacing(14)
        self._style_cards: dict[str, StylePreview] = {}
        for i, (key, style) in enumerate(STYLES.items()):
            c = StylePreview(style)
            c.set_color(self.config.overlay_colors.get(key))
            c.clicked.connect(lambda k=key: self._pick_style(k))
            grid.addWidget(c, i // 2, i % 2)
            self._style_cards[key] = c
        self._pick_style(self.config.overlay_style, emit=False)
        col.addLayout(grid)
        col.addStretch()
        return page

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

    _last_custom = "#3fa7ff"

    def _sync_swatches(self) -> None:
        choice = self.config.overlay_colors.get(self._style_key) or palettes.STYLE_DEFAULTS.get(self._style_key)
        self._color_title.setText(f"Цвет: {STYLES[self._style_key].title}")
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

    def _page_dictionary(self, last_text: str) -> QWidget:
        page, col = self._page("Словарь", "Термины подсказывают модели написание, исправления заменяют "
                                          "слова, которые она путает.")

        frame, box = card()
        box.addWidget(label("Предложенные термины", "h2"))
        box.addWidget(label("Новые латинские слова из ваших диктовок. ＋ — в словарь, × — больше не предлагать.",
                            "muted", wrap=True))
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self._suggest_flow = FlowLayout(holder)
        box.addWidget(holder)
        col.addWidget(frame)

        frame, box = card()
        box.addWidget(label("Мои термины", "h2"))
        row = QHBoxLayout()
        self._term_input = QLineEdit()
        self._term_input.setPlaceholderText("Например: Terraform, Jira, ClickHouse")
        self._term_input.returnPressed.connect(self._add_term_from_input)
        add = QPushButton("Добавить")
        add.setObjectName("primary")
        add.clicked.connect(self._add_term_from_input)
        row.addWidget(self._term_input, 1)
        row.addWidget(add)
        box.addLayout(row)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self._terms_flow = FlowLayout(holder)
        box.addWidget(holder)
        col.addWidget(frame)

        frame, box = card()
        box.addWidget(label("Исправления", "h2"))
        box.addWidget(label("Если модель пишет «ттермен» вместо «термин» — добавьте замену. "
                            "Можно выделить слово в последней диктовке ниже.", "muted", wrap=True))
        row = QHBoxLayout()
        self._wrong = QLineEdit()
        self._wrong.setPlaceholderText("Как распозналось")
        self._right = QLineEdit()
        self._right.setPlaceholderText("Как должно быть")
        self._right.returnPressed.connect(self._add_correction)
        arrow = label("→", "muted")
        add = QPushButton("Добавить")
        add.setObjectName("primary")
        add.clicked.connect(self._add_correction)
        row.addWidget(self._wrong, 1)
        row.addWidget(arrow)
        row.addWidget(self._right, 1)
        row.addWidget(add)
        box.addLayout(row)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self._fix_flow = FlowLayout(holder)
        box.addWidget(holder)
        box.addWidget(label("Последняя диктовка", "h2"))
        self._last = QTextEdit()
        self._last.setReadOnly(True)
        self._last.setFixedHeight(90)
        self._last.setPlaceholderText("Здесь появится текст последней диктовки")
        self._last.selectionChanged.connect(self._on_last_selection)
        box.addWidget(self._last)
        col.addWidget(frame)
        col.addStretch()

        self.set_last_text(last_text)
        self._render_chips()
        return page

    def _page_about(self) -> QWidget:
        page, col = self._page("О программе", f"Typeless {__version__} — диктовка в любое поле ввода.")
        frame, box = card()
        box.addWidget(label("Локальное распознавание речи на faster-whisper. Аудио не покидает компьютер "
                            "(кроме движка «Диктовка Windows»).", "", wrap=True))
        row = QHBoxLayout()
        logs = QPushButton("Папка с логом и настройками")
        logs.clicked.connect(self._open_app_dir)
        repo = QPushButton("GitHub")
        repo.clicked.connect(lambda: __import__("webbrowser").open("https://github.com/imangali01/typeless"))
        row.addWidget(logs)
        row.addWidget(repo)
        row.addStretch()
        box.addLayout(row)
        col.addWidget(frame)
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

    # --- dictionary --------------------------------------------------------------
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
                ("＋", "Добавить в словарь", lambda _=False, t=term: self._add_term(t)),
                ("×", "Не предлагать", lambda _=False, t=term: self._ignore_term(t)),
            ]))
        if not self.config.suggested_terms:
            self._suggest_flow.addWidget(label("Пока пусто — продиктуйте что-нибудь с английскими терминами.", "muted"))
        for term in self.config.dictionary:
            self._terms_flow.addWidget(Chip(term, [("×", "Удалить", lambda _=False, t=term: self._remove_term(t))]))
        for wrong, right in self.config.corrections.items():
            self._fix_flow.addWidget(Chip(f"{wrong} → {right}",
                                          [("×", "Удалить", lambda _=False, w=wrong: self._remove_correction(w))]))
        for flow in (self._suggest_flow, self._terms_flow, self._fix_flow):
            flow.parentWidget().updateGeometry()
            flow.invalidate()

    def _open_app_dir(self) -> None:
        import os

        from ..config import app_dir

        os.startfile(app_dir())

    def closeEvent(self, event) -> None:
        self._hook.cancel_capture()
        super().closeEvent(event)
