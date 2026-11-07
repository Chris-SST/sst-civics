"""The published files (contract sections 1 to 3): `<ARTICLES_DIR>/<lang>/<slug>.md` with YAML
frontmatter, the build request the site builder polls, and the builder's status file.

Every file is written atomically (`<name>.tmp`, then rename). All languages of an article are
written before the build is requested."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from app.articles.constants import SEGMENTS
from app.config import get_settings

BUILD_REQUEST = ".build-request"


def articles_dir() -> Path:
    return Path(get_settings().articles_dir)


def frontmatter(
    content: dict[str, Any],
    *,
    key: str,
    kind: str,
    category: str,
    canton: str | None,
    lang: str,
    published: date,
    updated: date,
    checked: date,
) -> dict[str, Any]:
    """The frontmatter in the contract's field order."""
    fm: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "lang": lang,
        "slug": content["slug"],
        "title": content["title"].strip(),
        "description": content["description"].strip(),
        "category": category,
    }
    if kind == "canton":
        fm["canton"] = canton
    fm.update(
        {
            "published": published,
            "updated": updated,
            "checked": checked,
            "summary": [s.strip() for s in content["summary"]],
            "sources": [{"title": s["title"].strip(), "url": s["url"]} for s in content["sources"]],
            "faq": [{"q": f["q"].strip(), "a": f["a"].strip()} for f in content["faq"]],
            "related": list(content.get("related") or []),
            "machine_translated": lang != "en",
        }
    )
    return fm


def render_file(fm: dict[str, Any], body: str) -> str:
    head = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{head}---\n\n{body.strip()}\n"


def parse_file(text: str) -> tuple[dict[str, Any], str]:
    """Frontmatter and body of a file written by render_file (used by tests and preview)."""
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter")
    head, _, body = text[4:].partition("\n---\n")
    return yaml.safe_load(head), body.lstrip("\n")


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def relative_path(lang: str, slug: str) -> str:
    return f"{lang}/{slug}.md"


def page_path(kind: str, lang: str, slug: str) -> str:
    return f"/{lang}/{SEGMENTS[kind][lang]}/{slug}/"


def write_article_files(
    root: Path, files: dict[str, str], previous: dict[str, str]
) -> dict[str, str]:
    """Write `files` ({relative path: text}) and remove the article's earlier files that are
    no longer part of it (a language that failed review this time, or a changed slug).
    Returns {lang: relative path}."""
    for rel, text in files.items():
        write_atomic(root / rel, text)
    keep = set(files)
    for rel in previous.values():
        if rel not in keep:
            (root / rel).unlink(missing_ok=True)
    return {rel.split("/", 1)[0]: rel for rel in files}


def remove_article_files(root: Path, live_files: dict[str, str]) -> list[str]:
    removed = []
    for rel in live_files.values():
        path = root / rel
        if path.is_file():
            path.unlink()
            removed.append(rel)
    return removed


def request_build(root: Path, reason: str, now: datetime) -> str:
    """Write the build request; returns its `requested_at`."""
    requested_at = now.isoformat()
    write_atomic(
        root / BUILD_REQUEST, json.dumps({"requested_at": requested_at, "reason": reason}) + "\n"
    )
    return requested_at


@dataclass
class BuildResult:
    done: bool  # a finished build that covers our request
    ok: bool = False
    release: str | None = None
    error: str | None = None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def read_build_status(path: Path, requested_at: datetime) -> BuildResult:
    """Whether the builder has finished a build that includes the files written for the
    request at `requested_at`: a status that is not `building`, has `finished_at`, and whose
    copied `requested_at` is the same as or later than ours. Anything else is "not yet"."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return BuildResult(done=False)
    if not isinstance(data, dict) or data.get("building") or not data.get("finished_at"):
        return BuildResult(done=False)
    theirs = _parse_time(data.get("requested_at"))
    if theirs is None or theirs < requested_at:
        return BuildResult(done=False)
    error = data.get("error")
    return BuildResult(
        done=True,
        ok=data.get("ok") is True,
        release=data.get("release"),
        error=str(error)[-4000:] if error else None,
    )
