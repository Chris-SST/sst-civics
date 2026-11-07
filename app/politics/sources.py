"""content/politics/sources.yaml: the discovery sources of each canton."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from app.content.files import content_root

TYPES = ("listing", "rss", "vote_list", "people")
FORMATS = (
    "zhweb_news",
    "rss",
    "html_dated",
    "lindas_votes",
    "parlament_votes",
    "page",
)
LEVELS = ("canton", "city", "federal")


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    format: str
    url: str
    level: str
    purpose: str = ""
    cite: str | None = None
    pages: int = 1
    include: str | None = None  # html_dated: keep links whose text matches
    title_match: str | None = None  # vote_list on a news feed: keep matching titles
    follow: str | None = None  # page: also read linked pages whose path matches
    seats: bool = False  # people: count the seats per party on this page


@dataclass(frozen=True)
class CantonSources:
    canton: str
    name: str
    item_hosts: tuple[str, ...]
    sources: tuple[Source, ...] = field(default_factory=tuple)

    def of_type(self, *types: str) -> list[Source]:
        return [s for s in self.sources if s.type in types]

    def host_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        return parts.scheme == "https" and any(
            host == h or host.endswith("." + h) for h in self.item_hosts
        )


def sources_path() -> Path:
    return content_root() / "politics" / "sources.yaml"


def _source(raw: dict[str, Any]) -> Source:
    s = Source(
        id=str(raw["id"]),
        type=str(raw["type"]),
        format=str(raw["format"]),
        url=str(raw["url"]),
        level=str(raw.get("level", "canton")),
        purpose=" ".join(str(raw.get("for", "")).split()),
        cite=raw.get("cite"),
        pages=int(raw.get("pages", 1)),
        include=raw.get("include"),
        title_match=raw.get("title_match"),
        follow=raw.get("follow"),
        seats=bool(raw.get("seats", False)),
    )
    if s.type not in TYPES or s.format not in FORMATS or s.level not in LEVELS:
        raise ValueError(f"source {s.id}: unknown type, format or level")
    if not s.url.startswith("https://"):
        raise ValueError(f"source {s.id}: the URL must start with https://")
    for pattern in (s.include, s.title_match, s.follow):
        if pattern:
            re.compile(pattern)
    return s


def parse(text: str) -> dict[str, CantonSources]:
    raw = yaml.safe_load(text) or {}
    out: dict[str, CantonSources] = {}
    for canton, block in raw.items():
        sources = tuple(_source(s) for s in block.get("sources") or [])
        ids = [s.id for s in sources]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{canton}: a source id is used twice")
        out[str(canton)] = CantonSources(
            canton=str(canton),
            name=str(block.get("name", canton)),
            item_hosts=tuple(str(h).lower() for h in block.get("item_hosts") or []),
            sources=sources,
        )
    return out


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict[str, CantonSources]:
    return parse(Path(path).read_text(encoding="utf-8"))


def load(path: Path | None = None) -> dict[str, CantonSources]:
    path = path or sources_path()
    return _load(str(path), path.stat().st_mtime)


def for_canton(canton: str) -> CantonSources | None:
    return load().get(canton)
