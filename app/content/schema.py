"""Schema of the content files under content/ (D-041). content/README.md describes the same
fields for people writing the files; keep the two in step.

Pydantic checks the shape of each file. Rules that need more than one file (topic codes,
translations per language, stale translations) live in app.content.validate."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import CANTONS, OPTION_KEYS, TRANSLATION_LANGUAGES

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Dotted, lower case, stable: bund.demokratie.volksrechte
TOPIC_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
# federal, a canton code (zh) or a canton code and a commune slug (zh-winterthur)
SCOPE_RE = re.compile(r"^(federal|[a-z]{2}|[a-z]{2}-[a-z0-9]+(?:-[a-z0-9]+)*)$")
TOPIC_PREFIX = {"federal": "bund.", "canton": "kanton.", "commune": "gemeinde."}

Status = Literal["draft", "in_review", "approved", "retired"]
TranslationStatus = Literal["draft", "in_review", "approved"]
OptionKey = Literal["a", "b", "c", "d"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _https(url: str) -> str:
    if not url.startswith("https://"):
        raise ValueError("source URLs must start with https://")
    return url


# --- Topics ----------------------------------------------------------------------------


class TopicEntry(_Strict):
    code: str
    scope: Literal["federal", "canton", "commune"]
    name_de: str = Field(min_length=1, max_length=200)
    name_en: str = Field(min_length=1, max_length=200)
    target_questions: int = Field(ge=0)
    sources: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        if not TOPIC_CODE_RE.match(v) or len(v) > 80:
            raise ValueError("topic codes are dotted, lower case, e.g. bund.demokratie")
        return v

    @field_validator("sources")
    @classmethod
    def _sources(cls, v: list[str]) -> list[str]:
        return [_https(u) for u in v]

    @model_validator(mode="after")
    def _prefix_matches_scope(self) -> TopicEntry:
        prefix = TOPIC_PREFIX[self.scope]
        if not self.code.startswith(prefix):
            raise ValueError(f"a {self.scope} topic code starts with '{prefix}'")
        return self


class MockTestFormat(_Strict):
    """The canton's test format, read by the mock test (task 1.9)."""

    questions: int = Field(gt=0)
    minutes: int = Field(gt=0)
    pass_mark: int | None = Field(default=None, gt=0)
    proportions: dict[Literal["federal", "canton", "commune"], float] = Field(default_factory=dict)


class TopicFile(_Strict):
    canton: str
    test: MockTestFormat | None = None
    topics: list[TopicEntry] = Field(min_length=1)

    @field_validator("canton")
    @classmethod
    def _canton(cls, v: str) -> str:
        if v not in CANTONS:
            raise ValueError("unknown canton code")
        return v

    @model_validator(mode="after")
    def _unique_codes(self) -> TopicFile:
        seen: set[str] = set()
        for t in self.topics:
            if t.code in seen:
                raise ValueError(f"topic code {t.code} appears twice")
            seen.add(t.code)
        return self


# --- Questions ---------------------------------------------------------------------------


class SourceRef(_Strict):
    url: str
    checked: date

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _https(v)


def _four_options(v: dict[str, str]) -> dict[str, str]:
    keys = set(v)
    if keys != set(OPTION_KEYS):
        raise ValueError("exactly four options, keyed a, b, c and d")
    if any(not str(text).strip() for text in v.values()):
        raise ValueError("an option is empty")
    return {k: str(v[k]).strip() for k in OPTION_KEYS}


class QuestionFile(_Strict):
    id: str = Field(max_length=80)
    version: int = Field(ge=1)
    scope: str
    canton: str | None
    topic: str
    question_de: str = Field(min_length=1)
    options_de: dict[str, str]
    correct: OptionKey
    explanation_de: str
    sources: list[SourceRef] = Field(min_length=1)
    glossary: list[str] = Field(default_factory=list)
    status: Status
    difficulty: Literal[1, 2, 3]
    translations_missing: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError("ids are lower-case slugs: letters, digits and hyphens")
        return v

    @field_validator("options_de", mode="before")
    @classmethod
    def _options_shape(cls, v: object) -> object:
        if not isinstance(v, dict):
            raise ValueError("options_de is a mapping a, b, c, d")
        return {str(k): ("" if t is None else str(t)) for k, t in v.items()}

    @field_validator("options_de")
    @classmethod
    def _options(cls, v: dict[str, str]) -> dict[str, str]:
        return _four_options(v)

    @model_validator(mode="after")
    def _scope_and_canton(self) -> QuestionFile:
        if not SCOPE_RE.match(self.scope):
            raise ValueError("scope is federal, a canton code (zh) or zh-<commune>")
        if self.scope == "federal":
            if self.canton is not None:
                raise ValueError("canton is null for federal questions")
        else:
            expected = self.scope[:2]
            if expected not in CANTONS:
                raise ValueError("unknown canton in scope")
            if self.canton != expected:
                raise ValueError(f"canton must be '{expected}' for scope {self.scope}")
        return self

    @property
    def is_commune(self) -> bool:
        return "-" in self.scope


# --- Translations ------------------------------------------------------------------------


class TranslationFile(_Strict):
    id: str
    lang: str
    source_version: int = Field(ge=1)
    question: str = Field(min_length=1)
    options: dict[str, str]
    explanation: str = Field(min_length=1)
    status: TranslationStatus
    reviewed_by: str | None = Field(default=None, max_length=120)
    reviewed_at: date | None = None

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in TRANSLATION_LANGUAGES:
            raise ValueError(f"lang is one of {', '.join(TRANSLATION_LANGUAGES)}")
        return v

    @field_validator("options", mode="before")
    @classmethod
    def _options_shape(cls, v: object) -> object:
        if not isinstance(v, dict):
            raise ValueError("options is a mapping a, b, c, d")
        return {str(k): ("" if t is None else str(t)) for k, t in v.items()}

    @field_validator("options")
    @classmethod
    def _options(cls, v: dict[str, str]) -> dict[str, str]:
        return _four_options(v)

    @model_validator(mode="after")
    def _review(self) -> TranslationFile:
        if self.status == "approved" and not (self.reviewed_by and self.reviewed_at):
            raise ValueError("an approved translation names reviewed_by and reviewed_at")
        return self


# --- Glossary ------------------------------------------------------------------------------


class GlossaryEntry(_Strict):
    term: str = Field(min_length=1, max_length=120)
    translation: str = Field(min_length=1, max_length=200)
    note: str | None = None


class GlossaryFile(_Strict):
    lang: str
    terms: list[GlossaryEntry] = Field(default_factory=list)

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in TRANSLATION_LANGUAGES:
            raise ValueError(f"lang is one of {', '.join(TRANSLATION_LANGUAGES)}")
        return v
