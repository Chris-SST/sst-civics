"""The topic queue content/articles/plan.yaml (contract section 5) and its import.

New keys become `planned` articles. An article still `planned` takes every change of its
plan entry (publish_at included); once production has started the plan entry no longer
changes it. A `planned` article whose key has left the plan is removed (it has no content
yet); any other article stays. Invalid entries are skipped and reported, never fatal."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.constants import CANTON_CODES, CATEGORIES, GUIDE_KEYS, KEY_RE, KINDS
from app.content.files import content_root
from app.models import ART_PLANNED, Article

log = logging.getLogger(__name__)


class PlanSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    url: str

    @field_validator("url")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("source URLs must start with https://")
        return v


class PlanEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str = Field(max_length=80)
    kind: str = "article"
    category: str
    publish_at: datetime
    title: str = Field(min_length=10, max_length=90)
    brief: str = Field(min_length=10)
    outline: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)
    sources: list[PlanSource] = Field(min_length=2, max_length=12)
    related: list[str] = Field(default_factory=list, max_length=4)
    links_to: list[str] = Field(default_factory=list)
    canton: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not KEY_RE.match(v):
            raise ValueError("key must be lower-case letters, digits and single hyphens")
        return v

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        return v

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
        return v

    @field_validator("publish_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("publish_at needs a time zone offset, e.g. +01:00")
        return v

    @field_validator("related")
    @classmethod
    def _related(cls, v: list[str]) -> list[str]:
        unknown = [k for k in v if k not in GUIDE_KEYS]
        if unknown:
            raise ValueError(f"unknown guide page key(s): {', '.join(unknown)}")
        return v

    @model_validator(mode="after")
    def _canton(self) -> PlanEntry:
        if self.kind == "canton":
            if self.canton not in CANTON_CODES:
                raise ValueError("a canton guide needs a two-letter lower-case canton code")
        elif self.canton is not None:
            raise ValueError("canton is only for kind canton")
        return self

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass
class ImportReport:
    path: Path
    found: bool = False
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.found:
            return f"No plan file at {self.path}"
        return (
            f"Plan {self.path}: {len(self.created)} new, {len(self.updated)} updated, "
            f"{len(self.removed)} removed, {self.unchanged} unchanged, {len(self.errors)} error(s)"
        )


def plan_path() -> Path:
    return content_root() / "articles" / "plan.yaml"


def load_plan(path: Path) -> tuple[list[PlanEntry], list[str]]:
    """Parse the plan file. Returns the valid entries and one message per invalid entry."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return [], []
    if isinstance(raw, dict) and "articles" in raw:
        raw = raw["articles"]
    if not isinstance(raw, list):
        return [], ["the plan must be a YAML list of entries"]
    entries: list[PlanEntry] = []
    errors: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(raw, 1):
        label = item.get("key", f"entry {i}") if isinstance(item, dict) else f"entry {i}"
        try:
            entry = PlanEntry.model_validate(item)
        except (ValidationError, ValueError) as exc:
            first = exc.errors()[0] if isinstance(exc, ValidationError) else None
            msg = f"{first['loc']}: {first['msg']}" if first else str(exc)
            errors.append(f"{label}: {msg}")
            continue
        if entry.key in seen:
            errors.append(f"{entry.key}: duplicate key, the first entry is used")
            continue
        seen.add(entry.key)
        entries.append(entry)
    return entries, errors


def new_nonce() -> str:
    return secrets.token_hex(16)


async def import_plan(db: AsyncSession, path: Path | None = None) -> ImportReport:
    """Bring the database in line with the plan file (see the module notes). Commits."""
    path = path or plan_path()
    report = ImportReport(path=path)
    if not path.is_file():
        return report
    report.found = True
    try:
        entries, report.errors = load_plan(path)
    except yaml.YAMLError as exc:
        report.errors.append(f"not valid YAML: {exc.__class__.__name__}")
        return report
    # Only the planned kinds: the politics pages (D-074) are not in the plan file.
    existing = {
        a.key: a
        for a in (await db.execute(select(Article).where(Article.kind.in_(KINDS)))).scalars()
    }
    keys = set()
    for entry in entries:
        keys.add(entry.key)
        snap = entry.snapshot()
        row = existing.get(entry.key)
        if row is None:
            db.add(
                Article(
                    key=entry.key,
                    kind=entry.kind,
                    category=entry.category,
                    canton=entry.canton,
                    publish_at=entry.publish_at.astimezone(UTC),
                    status=ART_PLANNED,
                    plan=snap,
                    translations={},
                    reviews=[],
                    feedback=[],
                    sources_read=[],
                    live_urls={},
                    live_files={},
                    review_nonce=new_nonce(),
                )
            )
            report.created.append(entry.key)
        elif row.status == ART_PLANNED and row.english is None and row.plan != snap:
            row.plan = snap
            row.kind = entry.kind
            row.category = entry.category
            row.canton = entry.canton
            row.publish_at = entry.publish_at.astimezone(UTC)
            report.updated.append(entry.key)
        else:
            report.unchanged += 1
    if not report.errors:
        # Only a plan without errors removes anything: a broken entry must not drop its row.
        for key, row in existing.items():
            if key not in keys and row.status == ART_PLANNED and row.english is None:
                await db.delete(row)
                report.removed.append(key)
    await db.commit()
    for msg in report.errors:
        log.warning("Article plan: %s", msg)
    return report
