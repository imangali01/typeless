"""User settings persisted as JSON in %APPDATA%\\typeless\\config.json."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

ENGINE_PARAKEET = "parakeet"  # NVIDIA Parakeet TDT v3: Russian + English, fast and accurate
ENGINE_GIGAAM = "gigaam"  # Sber GigaAM v3: Russian only, fastest
ENGINE_WHISPER = "whisper"  # faster-whisper: slower, steered by the dictionary prompt
ENGINES = (ENGINE_PARAKEET, ENGINE_GIGAAM, ENGINE_WHISPER)
CONFIG_VERSION = 2  # 2: Parakeet became the default engine, Windows voice typing was removed

CLIPBOARD_FALLBACK = "fallback"  # copy only when there is no text field to type into
CLIPBOARD_ALWAYS = "always"
CLIPBOARD_NEVER = "never"


def app_dir() -> Path:
    path = Path(os.environ.get("APPDATA", Path.home())) / "typeless"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    hotkey: str = "Win+C"
    engine: str = ENGINE_PARAKEET
    language_mode: str = "ru_en"
    profile: str = "general"
    whisper_model: str = "base"  # Whisper engine only: ~0.8 s per pass on i5-13420H; "small" is ~2.5 s
    live_typing: bool = True
    clipboard: str = CLIPBOARD_FALLBACK
    show_overlay: bool = True
    overlay_style: str = "line"
    overlay_colors: dict[str, str] = field(default_factory=dict)  # style -> preset key or "#rrggbb"
    overlay_text: dict = field(default_factory=dict)  # size / lines / face / family, see TextOptions
    autostart: bool = False
    dictionary: list[str] = field(default_factory=list)  # terms: Whisper prompt / spelling fixes
    corrections: dict[str, str] = field(default_factory=dict)  # wrong -> right
    suggested_terms: list[str] = field(default_factory=list)
    ignored_terms: list[str] = field(default_factory=list)
    # process name -> shortcut sent instead of dictating (the app's own dictation)
    app_rules: dict[str, str] = field(default_factory=lambda: {"Code.exe": "Ctrl+D"})
    version: int = CONFIG_VERSION

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or app_dir() / "config.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError):
            log.exception("broken config at %s, using defaults", path)
            return cls()
        if "language" in data and "language_mode" not in data:  # v0.1 config
            data["language_mode"] = {"ru": "ru_en", "en": "en"}.get(data["language"], "ru_en")
        if data.get("version", 1) < 2:  # Whisper/Win+H users move to the much faster Parakeet
            data["engine"] = ENGINE_PARAKEET
            data["version"] = 2
        if data.get("engine") not in ENGINES:
            data["engine"] = ENGINE_PARAKEET
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or app_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
