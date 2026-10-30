"""Loads versioned prompt files from `prompts/`. No prompt text lives in code.

Layout (see prompts/README.md):

    prompts/base/vN.md                     persona, teaching method, safety rules
    prompts/civics/vN.md                   civics-trainer context (test, levels of government)
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
    """`name` is a path under prompts/, for example "base" or "civics"."""
    directory = prompts_root() / name
    path = _latest(directory, "md")
    if path is None:
        raise FileNotFoundError(f"no prompt version in {directory}")
    version = path.stem
    return PromptFile(name=name, version=version, text=_render(path.read_text(encoding="utf-8")))


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
    _replies.cache_clear()
