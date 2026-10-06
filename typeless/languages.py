"""Language modes and the prompt that steers Whisper's spelling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageMode:
    key: str
    title: str
    hint: str
    whisper: str | None  # None = auto-detect
    # A sample sentence in the expected style: Whisper imitates the prompt's script/spelling.
    seed: str


LANGUAGE_MODES: dict[str, LanguageMode] = {m.key: m for m in (
    LanguageMode("ru_en", "Русский + English", "Русская речь, термины латиницей",
                 "ru", "Сделал commit в GitHub, открыл pull request и обновил README."),
    LanguageMode("ru", "Только русский", "Всё пишется кириллицей",
                 "ru", "Привет! Сегодня обсудим план работы на неделю."),
    LanguageMode("en", "English only", "Speech and text in English",
                 "en", "Hi! Let's review the plan for this week."),
    LanguageMode("kk", "Қазақша", "Казахский; на модели base качество низкое — лучше small",
                 "kk", "Сәлеметсіз бе! Бүгін апталық жұмыс жоспарын талқылаймыз."),
    LanguageMode("auto", "Автоопределение", "Язык определяется по каждой фразе",
                 None, ""),
)}
DEFAULT_LANGUAGE = "ru_en"

PROFILE_GENERAL, PROFILE_CODER = "general", "coder"
PROFILES = {
    PROFILE_GENERAL: ("Обычный", "Письма, сообщения, документы"),
    PROFILE_CODER: ("Программист", "Термины кода латиницей: commit, deploy, API, React…"),
}

CODER_TERMS = [
    "API", "REST", "JSON", "YAML", "SQL", "HTTP", "URL", "UI", "UX", "CI/CD", "README",
    "Git", "GitHub", "GitLab", "commit", "push", "pull request", "merge", "rebase", "branch",
    "deploy", "release", "build", "backend", "frontend", "endpoint", "middleware", "framework",
    "Python", "JavaScript", "TypeScript", "React", "Node.js", "Docker", "Kubernetes", "Postgres",
    "Redis", "Kafka", "ClickHouse", "FastAPI", "Django", "VS Code", "Claude", "LLM", "prompt",
    "bug", "fix", "refactor", "debug", "test", "unit test", "mock", "staging", "production",
]

PROMPT_LIMIT = 700  # chars; Whisper only reads ~224 tokens of prompt


def build_prompt(mode_key: str, profile: str, dictionary: list[str], recent: str = "") -> str:
    mode = LANGUAGE_MODES.get(mode_key, LANGUAGE_MODES[DEFAULT_LANGUAGE])
    terms: list[str] = list(dictionary)
    if profile == PROFILE_CODER and mode.key != "ru":
        terms += [t for t in CODER_TERMS if t.lower() not in {d.lower() for d in dictionary}]
    parts = [mode.seed]
    if terms:
        parts.append(", ".join(terms) + ".")
    head = " ".join(p for p in parts if p)
    # Recent context goes last (closest to the audio) and is cut first when too long.
    room = PROMPT_LIMIT - len(head) - 1
    if len(head) > PROMPT_LIMIT:
        head = head[:PROMPT_LIMIT]
        room = 0
    tail = recent[-room:] if room > 0 and recent else ""
    return " ".join(p for p in (head, tail) if p)
