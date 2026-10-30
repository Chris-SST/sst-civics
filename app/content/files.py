"""Reading the content files (content/, D-041) into checked models. Nothing here touches the
database; the importer and the validator both start from `load_content`."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.content.schema import GlossaryFile, QuestionFile, TopicFile, TranslationFile

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    level: str  # error | warning
    kind: str  # short machine name, e.g. stale_translation
    path: str  # file the issue is about, relative to the content root
    message: str


@dataclass
class ContentSet:
    root: Path
    topic_files: dict[str, TopicFile] = field(default_factory=dict)
    questions: dict[str, QuestionFile] = field(default_factory=dict)
    question_paths: dict[str, str] = field(default_factory=dict)
    translations: dict[tuple[str, str], TranslationFile] = field(default_factory=dict)  # (lang, id)
    translation_paths: dict[tuple[str, str], str] = field(default_factory=dict)
    glossary: dict[str, GlossaryFile] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def error(self, kind: str, path: str, message: str) -> None:
        self.issues.append(Issue(ERROR, kind, path, message))

    def warn(self, kind: str, path: str, message: str) -> None:
        self.issues.append(Issue(WARNING, kind, path, message))


def content_root() -> Path:
    """Absolute `CONTENT_DIR` wins; a relative one is tried against the working directory
    (the containers run from /srv), then against the repository root."""
    configured = Path(get_settings().content_dir)
    if configured.is_absolute():
        return configured
    candidates = [Path.cwd() / configured, Path(__file__).resolve().parents[2] / configured]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


def content_hash(model: BaseModel) -> str:
    """SHA-256 of the file's parsed content, so formatting and comments do not count."""
    data = model.model_dump(mode="json")
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# Workflow fields of a question file: the pipeline and the review write-back change them
# without raising the version (task 1.5), so they are not part of the question's content.
QUESTION_WORKFLOW_FIELDS = frozenset({"status", "checks", "review"})


def question_content_hash(q: QuestionFile) -> str:
    """SHA-256 of what the learner sees and what was checked: everything except the status,
    the pipeline's checks, the review note and the dates sources were checked. A change to
    any of these needs no new version; any other change does."""
    data = q.model_dump(mode="json", exclude=set(QUESTION_WORKFLOW_FIELDS))
    data["sources"] = [s["url"] for s in data["sources"]]
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _yaml_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix in (".yaml", ".yml") and not p.name.startswith(("_", "."))
    )


def _subdirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_dir() and not p.name.startswith("."))


def _schema_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err.get("loc", ())) or "file"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts)


def _parse(cs: ContentSet, path: Path, model: type[BaseModel]) -> Any | None:
    rel = path.relative_to(cs.root).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        cs.error("yaml", rel, f"cannot be read as YAML: {exc}".splitlines()[0])
        return None
    if not isinstance(data, dict):
        cs.error("yaml", rel, "the file must hold a YAML mapping")
        return None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        cs.error("schema", rel, _schema_message(exc))
        return None


def load_content(root: Path | None = None) -> ContentSet:
    root = (root or content_root()).resolve()
    cs = ContentSet(root=root)

    for path in _yaml_files(root / "topics"):
        topics = _parse(cs, path, TopicFile)
        if topics is None:
            continue
        rel = path.relative_to(root).as_posix()
        if topics.canton != path.stem:
            cs.error(
                "file_name", rel, f"the file for canton {topics.canton} is {topics.canton}.yaml"
            )
            continue
        cs.topic_files[topics.canton] = topics

    seen_ids: dict[str, str] = {}
    for directory in _subdirs(root / "questions"):
        for path in _yaml_files(directory):
            q = _parse(cs, path, QuestionFile)
            if q is None:
                continue
            rel = path.relative_to(root).as_posix()
            if q.id != path.stem:
                cs.error("file_name", rel, f"the file name must be the id: {q.id}.yaml")
                continue
            if q.scope != directory.name:
                cs.error("file_name", rel, f"scope {q.scope} belongs in questions/{q.scope}/")
                continue
            if q.id in seen_ids:
                cs.error("duplicate_id", rel, f"id {q.id} is also used by {seen_ids[q.id]}")
                continue
            seen_ids[q.id] = rel
            cs.questions[q.id] = q
            cs.question_paths[q.id] = rel

    for directory in _subdirs(root / "translations"):
        for path in _yaml_files(directory):
            tr = _parse(cs, path, TranslationFile)
            if tr is None:
                continue
            rel = path.relative_to(root).as_posix()
            if tr.id != path.stem or tr.lang != directory.name:
                cs.error("file_name", rel, f"belongs at translations/{tr.lang}/{tr.id}.yaml")
                continue
            cs.translations[(tr.lang, tr.id)] = tr
            cs.translation_paths[(tr.lang, tr.id)] = rel

    for path in _yaml_files(root / "glossary"):
        gl = _parse(cs, path, GlossaryFile)
        if gl is None:
            continue
        if gl.lang != path.stem:
            cs.error("file_name", path.relative_to(root).as_posix(), f"belongs at {gl.lang}.yaml")
            continue
        cs.glossary[gl.lang] = gl
    return cs
