"""User settings persisted as JSON in %APPDATA%\\typeless\\config.json."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

ENGINE_WINDOWS = "windows"  # proxies to built-in Windows voice typing (Win+H)
ENGINE_WHISPER = "whisper"  # local faster-whisper

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
    engine: str = ENGINE_WHISPER
    language_mode: str = "ru_en"
    profile: str = "general"
    whisper_model: str = "base"  # ~0.8 s per pass on i5-13420H; "small" is ~2.5 s
    live_typing: bool = True
    clipboard: str = CLIPBOARD_FALLBACK
    show_overlay: bool = True
    overlay_style: str = "line"
    overlay_colors: dict[str, str] = field(default_factory=dict)  # style -> preset key or "#rrggbb"
    autostart: bool = False
    dictionary: list[str] = field(default_factory=list)  # terms that hint spelling to Whisper
    corrections: dict[str, str] = field(default_factory=dict)  # wrong -> right
    suggested_terms: list[str] = field(default_factory=list)
    ignored_terms: list[str] = field(default_factory=list)

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
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or app_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
