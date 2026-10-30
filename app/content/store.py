"""Writing question and translation files (content/, D-041) for the content pipeline
(scripts/content/, task 1.5). Every write is checked against the schema first, so the
pipeline never leaves a file the validator would reject.

The files are rewritten from the parsed model in the schema's field order; comments in a
hand-written file are not kept."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.content.schema import QuestionFile, TranslationFile


def question_path(root: Path, scope: str, qid: str) -> Path:
    return root / "questions" / scope / f"{qid}.yaml"


def translation_path(root: Path, lang: str, qid: str) -> Path:
    return root / "translations" / lang / f"{qid}.yaml"


def _prune(value: Any) -> Any:
    """Drop None values inside the checks and review blocks (they only add noise)."""
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value


def question_data(q: QuestionFile) -> dict[str, Any]:
    """The file's mapping in schema order, ready to change and write back."""
    data = q.model_dump(mode="python")
    if data.get("checks") is None:
        data.pop("checks", None)
    else:
        data["checks"] = _prune(data["checks"])
    if data.get("review") is None:
        data.pop("review", None)
    else:
        data["review"] = _prune(data["review"])
    if not data.get("translations_missing"):
        data.pop("translations_missing", None)
    return data


def translation_data(tr: TranslationFile) -> dict[str, Any]:
    data = tr.model_dump(mode="python")
    if data.get("checks") is None:
        data.pop("checks", None)
    else:
        data["checks"] = _prune(data["checks"])
    return data


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    tmp.replace(path)


def write_question(root: Path, data: dict[str, Any]) -> QuestionFile:
    """Check `data` against the schema and write questions/<scope>/<id>.yaml."""
    q = QuestionFile.model_validate(data)
    _write(question_path(root, q.scope, q.id), _dump(question_data(q)))
    return q


def write_translation(root: Path, data: dict[str, Any]) -> TranslationFile:
    """Check `data` against the schema and write translations/<lang>/<id>.yaml."""
    tr = TranslationFile.model_validate(data)
    _write(translation_path(root, tr.lang, tr.id), _dump(translation_data(tr)))
    return tr
