"""Build-time content check (PLAN.md, Testing and quality): run by
`scripts/validate_content.py` in CI before the tests, and by the importer before it writes
anything.

Errors: four distinct options with exactly one correct key, a source checked in the last
365 days, a known topic code, a non-empty explanation, unique ids, and for approved
questions a translation per launch language or `translations_missing: true`.
Warnings: translations made from an older German version (stale; the app hides them).
Retired questions skip the source-age and topic checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from app.content.files import ERROR, WARNING, ContentSet, Issue, load_content
from app.content.schema import QuestionFile, TopicEntry
from app.models import QUESTION_STATUSES, TRANSLATION_LANGUAGES

SOURCE_MAX_AGE = timedelta(days=365)  # "under 366 days old"


@dataclass
class Report:
    content: ContentSet
    today: date

    @property
    def issues(self) -> list[Issue]:
        return self.content.issues

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def kinds(self) -> set[str]:
        return {i.kind for i in self.issues}

    def translation_counts(self) -> dict[str, dict[str, int]]:
        """Per language, over approved German questions: approved, draft, in_review, stale,
        missing. A stale translation counts only as stale, whatever its own status."""
        approved = [q for q in self.content.questions.values() if q.status == "approved"]
        out: dict[str, dict[str, int]] = {}
        for lang in TRANSLATION_LANGUAGES:
            row = {"approved": 0, "draft": 0, "in_review": 0, "stale": 0, "missing": 0}
            for q in approved:
                tr = self.content.translations.get((lang, q.id))
                if tr is None:
                    row["missing"] += 1
                elif tr.source_version < q.version:
                    row["stale"] += 1
                else:
                    row[tr.status] += 1
            out[lang] = row
        return out

    def summary_lines(self) -> list[str]:
        cs = self.content
        lines = [f"Content check of {cs.root} on {self.today.isoformat()}"]
        topics = ", ".join(f"{c} {len(t.topics)}" for c, t in sorted(cs.topic_files.items()))
        lines.append(f"Topic files: {topics or 'none'}")
        scopes = sorted({q.scope for q in cs.questions.values()})
        head = f"{'scope':<16}{'total':>7}" + "".join(f"{s:>11}" for s in QUESTION_STATUSES)
        lines.append(head)
        for scope in scopes:
            qs = [q for q in cs.questions.values() if q.scope == scope]
            counts = "".join(
                f"{sum(1 for q in qs if q.status == s):>11}" for s in QUESTION_STATUSES
            )
            lines.append(f"{scope:<16}{len(qs):>7}{counts}")
        if not scopes:
            lines.append(f"{'(no questions)':<16}{0:>7}")
        cols = ("approved", "draft", "in_review", "stale", "missing")
        lines.append(f"{'translations':<16}" + "".join(f"{c:>11}" for c in cols))
        for lang, row in self.translation_counts().items():
            lines.append(f"{lang:<16}" + "".join(f"{row[c]:>11}" for c in cols))
        lines.append(f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return lines


def _topic_index(cs: ContentSet) -> tuple[dict[str, TopicEntry], dict[str, dict[str, TopicEntry]]]:
    """Federal topics from every canton file, and each canton's own topics."""
    federal: dict[str, TopicEntry] = {}
    by_canton: dict[str, dict[str, TopicEntry]] = {}
    for canton, tf in cs.topic_files.items():
        by_canton[canton] = {t.code: t for t in tf.topics}
        for t in tf.topics:
            if t.scope != "federal":
                continue
            other = federal.get(t.code)
            if other is not None and (other.name_de, other.name_en) != (t.name_de, t.name_en):
                cs.warn(
                    "topic_names_differ",
                    f"topics/{canton}.yaml",
                    f"federal topic {t.code} has different names in another canton file",
                )
            federal.setdefault(t.code, t)
    return federal, by_canton


def _check_topic(
    cs: ContentSet,
    path: str,
    q: QuestionFile,
    federal: dict[str, TopicEntry],
    by_canton: dict[str, dict[str, TopicEntry]],
) -> None:
    if q.scope == "federal":
        topic = federal.get(q.topic)
        if topic is None:
            cs.error("unknown_topic", path, f"{q.topic} is not a federal topic in any topic file")
        return
    assert q.canton is not None
    own = by_canton.get(q.canton)
    if own is None:
        cs.error("unknown_topic", path, f"there is no topic file topics/{q.canton}.yaml")
        return
    topic = own.get(q.topic)
    if topic is None:
        cs.error("unknown_topic", path, f"{q.topic} is not in topics/{q.canton}.yaml")
        return
    allowed = ("commune",) if q.is_commune else ("canton", "commune")
    if topic.scope not in allowed:
        cs.error(
            "topic_scope",
            path,
            f"a {q.scope} question cannot use the {topic.scope} topic {q.topic}",
        )


def _check_question(cs: ContentSet, path: str, q: QuestionFile, today: date) -> None:
    texts = [q.options_de[k].casefold() for k in q.options_de]
    if len(set(texts)) != len(texts):
        cs.error("options_not_distinct", path, "the four options must all differ")
    if q.correct not in q.options_de:
        cs.error("correct_key", path, "the correct key is not one of the options")
    if not q.explanation_de.strip():
        cs.error("empty_explanation", path, "explanation_de is empty")
    future = [s for s in q.sources if s.checked > today]
    if future:
        cs.error("source_date", path, f"a source has a checked date in the future: {future[0].url}")
    fresh = [s for s in q.sources if today - SOURCE_MAX_AGE <= s.checked <= today]
    if not fresh and q.status != "retired":
        cs.error(
            "source_outdated",
            path,
            "no source was checked in the last 365 days; check the source again",
        )
    if q.status == "approved" and not q.translations_missing:
        missing = [lang for lang in TRANSLATION_LANGUAGES if (lang, q.id) not in cs.translations]
        if missing:
            cs.error(
                "translation_missing",
                path,
                f"approved but no translation for {', '.join(missing)} "
                "(add them or set translations_missing: true)",
            )


def _check_translations(cs: ContentSet) -> None:
    for key, tr in cs.translations.items():
        path = cs.translation_paths[key]
        q = cs.questions.get(tr.id)
        if q is None:
            cs.error("orphan_translation", path, f"there is no question {tr.id}")
            continue
        if tr.source_version > q.version:
            cs.error(
                "translation_ahead",
                path,
                f"source_version {tr.source_version} is newer than the question ({q.version})",
            )
        elif tr.source_version < q.version:
            cs.warn(
                "stale_translation",
                path,
                f"translated from version {tr.source_version}, the German is at {q.version}; "
                "hidden in the app until refreshed",
            )
        texts = [tr.options[k].casefold() for k in tr.options]
        if len(set(texts)) != len(texts):
            cs.error("options_not_distinct", path, "the four options must all differ")
        if q.status in ("draft", "in_review"):
            cs.warn(
                "translation_of_unapproved",
                path,
                "the German question is not approved; translations follow approval",
            )


def validate_content(root: Path | None = None, today: date | None = None) -> Report:
    cs = load_content(root)
    today = today or date.today()
    federal, by_canton = _topic_index(cs)
    for qid, q in cs.questions.items():
        path = cs.question_paths[qid]
        _check_question(cs, path, q, today)
        if q.status != "retired":  # a retired question may keep a topic that was removed
            _check_topic(cs, path, q, federal, by_canton)
    _check_translations(cs)
    return Report(content=cs, today=today)
