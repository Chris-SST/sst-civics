"""Loads versioned prompt files from `prompts/`. No prompt text lives in code.

Layout (see prompts/README.md):

    prompts/base/vN.md                     persona, teaching method, safety rules
    prompts/courses/<module>/vN.md         course module (topics, notation, misconceptions)
    prompts/courses/<module>/topics.json   topic list shown to students and sent as context
    prompts/gatekeeper/vN.md               fast-model classification instructions
    prompts/summary/vN.md                  running-summary instructions
    prompts/replies/vN.json                fixed server replies in en, de, fr

The highest vN in a directory is the active version. Placeholders `{{TUTOR_NAME}}` and
`{{PROVIDER_DISCLOSURE}}` are filled from settings at load time, so the rendered text is
stable across requests and caches well."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

_VERSION_RE = re.compile(r"^v(\d+)\.(md|json)$")


@dataclass(frozen=True)
class PromptFile:
    name: str
    version: str
    text: str

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class Topic:
    code: str
    name: dict[str, str]
    levels: tuple[str, ...]  # ("sl", "hl") or a subset

    def display(self, locale: str) -> str:
        return self.name.get(locale) or self.name["en"]


@dataclass(frozen=True)
class CourseInfo:
    module_key: str
    name: dict[str, str]
    level_names: dict[str, dict[str, str]]  # level -> locale -> name
    topics: tuple[Topic, ...]

    def display(self, locale: str) -> str:
        return self.name.get(locale) or self.name["en"]

    def level_display(self, level: str | None, locale: str) -> str:
        if not level:
            return ""
        names = self.level_names.get(level, {})
        return names.get(locale) or names.get("en") or level.upper()

    def topics_for(self, level: str | None) -> list[Topic]:
        if not level:
            return list(self.topics)
        return [t for t in self.topics if level in t.levels]

    def topic(self, code: str) -> Topic | None:
        return next((t for t in self.topics if t.code == code), None)


def prompts_root() -> Path:
    """Absolute `PROMPTS_DIR` wins. A relative one is tried against the working directory
    (the containers run from /srv, where the Dockerfile copies prompts/), then against the
    repository root next to the `app` package (local development, tests)."""
    configured = Path(get_settings().prompts_dir)
    if configured.is_absolute():
        return configured
    candidates = [Path.cwd() / configured, Path(__file__).resolve().parents[2] / configured]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


def _latest(directory: Path, suffix: str) -> Path | None:
    best: tuple[int, Path] | None = None
    if not directory.is_dir():
        return None
    for path in directory.iterdir():
        m = _VERSION_RE.match(path.name)
        if m and m.group(2) == suffix:
            n = int(m.group(1))
            if best is None or n > best[0]:
                best = (n, path)
    return best[1] if best else None


def _render(text: str) -> str:
    settings = get_settings()
    if settings.disclose_model_provider:
        disclosure = (
            "If asked which AI you are or what you run on, say that you run on a model from "
            "Anthropic. Never deny or misstate this."
        )
    else:
        disclosure = (
            "If asked which AI you are or what you run on, say that you cannot share details "
            "of the underlying technology. Never deny being an AI and never name a different "
            "provider."
        )
    return text.replace("{{TUTOR_NAME}}", settings.tutor_name).replace(
        "{{PROVIDER_DISCLOSURE}}", disclosure
    )


@lru_cache(maxsize=64)
def load(name: str) -> PromptFile:
    """`name` is a path under prompts/, for example "base" or "courses/ib_maths_aa"."""
    directory = prompts_root() / name
    path = _latest(directory, "md")
    if path is None:
        raise FileNotFoundError(f"no prompt version in {directory}")
    version = path.stem
    return PromptFile(name=name, version=version, text=_render(path.read_text(encoding="utf-8")))


def course_module_key(course_key: str) -> str:
    """ib_maths_aa_hl -> ib_maths_aa. The level travels separately as student context."""
    for suffix in ("_sl", "_hl"):
        if course_key.endswith(suffix):
            return course_key[: -len(suffix)]
    return course_key


def course_level(course_key: str) -> str | None:
    for level in ("sl", "hl"):
        if course_key.endswith("_" + level):
            return level
    return None


@lru_cache(maxsize=64)
def course_info(module_key: str) -> CourseInfo | None:
    path = prompts_root() / "courses" / module_key / "topics.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    topics = tuple(
        Topic(code=t["code"], name=t["name"], levels=tuple(t.get("levels", ["sl", "hl"])))
        for t in data["topics"]
    )
    return CourseInfo(
        module_key=module_key,
        name=data["name"],
        level_names=data.get("levels", {}),
        topics=topics,
    )


def has_course_module(course_key: str) -> bool:
    module = course_module_key(course_key)
    return (
        course_info(module) is not None
        and _latest(prompts_root() / "courses" / module, "md") is not None
    )


def available_courses() -> list[str]:
    """Every course key with a topic list and a tutor prompt, e.g. ib_maths_aa_hl. Every
    learner may use every course until the canton modules replace them in Phase 1."""
    root = prompts_root() / "courses"
    if not root.is_dir():
        return []
    out: list[str] = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        info = course_info(directory.name)
        if info is None or _latest(directory, "md") is None:
            continue
        levels = list(info.level_names)
        if levels:
            out.extend(f"{directory.name}_{lvl}" for lvl in levels)
        else:
            out.append(directory.name)
    return out


@lru_cache(maxsize=4)
def _replies() -> tuple[str, dict[str, dict[str, str]]]:
    path = _latest(prompts_root() / "replies", "json")
    if path is None:
        raise FileNotFoundError("no replies file in prompts/replies")
    return path.stem, json.loads(path.read_text(encoding="utf-8"))


def fixed_reply(kind: str, locale: str) -> str:
    _, table = _replies()
    entry = table[kind]
    return _render(entry.get(locale) or entry["en"])


def clear_cache() -> None:
    load.cache_clear()
    course_info.cache_clear()
    _replies.cache_clear()
