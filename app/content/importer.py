"""Import on deploy: fill the database from the content files (the master copy).

Run by `scripts/import_content.py` after `alembic upgrade head`. The whole import is one
transaction: if the files fail validation, or a question changed without a version bump,
nothing is written.

- Topics: one row per entry of each canton file, matched on (canton, code); entries gone
  from the files are deleted.
- Questions: matched on id. A higher version replaces the row (and clears any admin changes
  waiting for write-back); the same version with the same content is an error. The content
  hash leaves out the workflow fields (status, the pipeline's checks, the review note and
  the dates sources were checked), which the pipeline changes without a new version: with
  the same version and content, the file's status and sources are taken over unless an
  admin change is still waiting for write-back, so that status survives. A question whose
  file is gone is retired, never deleted, so attempts survive.
- Translations: matched on (id, lang), replaced when their content hash changes. A
  translation made from an older German version is imported but hidden.
- Glossary: matched on (term, lang); entries gone from the files are deleted. An entry with an
  admin edit waiting for write-back (`file_sync_pending`) keeps its edited text and status."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.files import content_hash, question_content_hash
from app.content.schema import QuestionFile
from app.content.validate import Report, validate_content
from app.db import utcnow
from app.models import Q_RETIRED, GlossaryTerm, Question, QuestionTranslation, Topic

FILE_MISSING = "missing"  # file_status of a question whose file was removed


@dataclass
class ImportResult:
    report: Report
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.report.ok and not self.errors

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def summary_lines(self) -> list[str]:
        order = (
            "topics_added",
            "topics_updated",
            "topics_removed",
            "questions_added",
            "questions_updated",
            "questions_unchanged",
            "questions_retired_missing",
            "translations_added",
            "translations_updated",
            "translations_removed",
            "translations_hidden",
            "glossary_terms",
        )
        lines = [f"{k.replace('_', ' ')}: {self.counts.get(k, 0)}" for k in order]
        lines += [f"note: {n}" for n in self.notes]
        lines += [f"error: {e}" for e in self.errors]
        return lines


async def _import_topics(db: AsyncSession, result: ImportResult) -> None:
    cs = result.report.content
    now = utcnow()
    existing = {(t.canton, t.code): t for t in (await db.execute(select(Topic))).scalars()}
    wanted: set[tuple[str, str]] = set()
    for canton, tf in cs.topic_files.items():
        for position, entry in enumerate(tf.topics):
            key = (canton, entry.code)
            wanted.add(key)
            digest = content_hash(entry)
            row = existing.get(key)
            if row is None:
                row = Topic(canton=canton, code=entry.code)
                db.add(row)
                result.bump("topics_added")
            elif row.content_hash != digest or row.position != position:
                result.bump("topics_updated")
            else:
                continue
            row.scope = entry.scope
            row.name_de = entry.name_de
            row.name_en = entry.name_en
            row.target_questions = entry.target_questions
            row.sources = list(entry.sources)
            row.position = position
            row.content_hash = digest
            row.imported_at = now
    for key, row in existing.items():
        if key not in wanted:
            await db.delete(row)
            result.bump("topics_removed")


async def _import_questions(db: AsyncSession, result: ImportResult) -> None:
    cs = result.report.content
    now = utcnow()
    existing = {q.id: q for q in (await db.execute(select(Question))).scalars()}
    for qid, qf in cs.questions.items():
        digest = question_content_hash(qf)
        row = existing.get(qid)
        if row is not None:
            if qf.version == row.version and row.content_hash == content_hash(qf):
                row.content_hash = digest  # imported before the workflow fields were left out
            if qf.version == row.version and digest == row.content_hash:
                _take_workflow_fields(row, qf)
                result.bump("questions_unchanged")
                continue
            if qf.version == row.version:
                result.errors.append(
                    f"{cs.question_paths[qid]}: content changed but version is still "
                    f"{qf.version}; raise the version"
                )
                continue
            if qf.version < row.version:
                result.errors.append(
                    f"{cs.question_paths[qid]}: version {qf.version} is lower than the "
                    f"imported version {row.version}"
                )
                continue
            if row.file_sync_pending:
                result.notes.append(
                    f"{qid}: admin changes not yet written to the file were replaced by "
                    f"version {qf.version} (see the audit log)"
                )
            result.bump("questions_updated")
        else:
            row = Question(id=qid)
            db.add(row)
            result.bump("questions_added")
        row.version = qf.version
        row.scope = qf.scope
        row.canton = qf.canton
        row.topic_code = qf.topic
        row.question_de = qf.question_de
        row.options_de = dict(qf.options_de)
        row.correct = qf.correct
        row.explanation_de = qf.explanation_de
        row.sources = [{"url": s.url, "checked": s.checked.isoformat()} for s in qf.sources]
        row.glossary = list(qf.glossary)
        row.difficulty = qf.difficulty
        row.translations_missing = qf.translations_missing
        row.status = qf.status
        row.file_status = qf.status
        row.content_hash = digest
        row.imported_at = now
        row.file_sync_pending = False
        row.pending_changes = None
    for qid, row in existing.items():
        if qid not in cs.questions and row.file_status != FILE_MISSING:
            row.status = Q_RETIRED
            row.file_status = FILE_MISSING
            row.file_sync_pending = False
            result.bump("questions_retired_missing")
            result.notes.append(f"{qid}: its file is gone, so it is retired")
    await db.flush()


def _take_workflow_fields(row: Question, qf: QuestionFile) -> None:
    """Same version and content: the file may still have a new status (set by the pipeline
    or written back from review) or new source dates. An admin change that is not yet in the
    file keeps its status (D-046)."""
    if row.file_status == FILE_MISSING:  # the file came back unchanged
        row.status = row.file_status = qf.status
    elif row.file_status != qf.status:
        row.file_status = qf.status
        if not row.file_sync_pending:
            row.status = qf.status
    sources = [{"url": s.url, "checked": s.checked.isoformat()} for s in qf.sources]
    if row.sources != sources:
        row.sources = sources


async def _import_translations(db: AsyncSession, result: ImportResult) -> None:
    cs = result.report.content
    now = utcnow()
    versions = dict((await db.execute(select(Question.id, Question.version))).all())
    existing = {
        (t.lang, t.question_id): t
        for t in (await db.execute(select(QuestionTranslation))).scalars()
    }
    for key, tf in cs.translations.items():
        lang, qid = key
        if qid not in versions:  # cannot happen after validation; keep the import safe
            continue
        digest = content_hash(tf)
        row = existing.get(key)
        if row is None:
            row = QuestionTranslation(question_id=qid, lang=lang)
            db.add(row)
            result.bump("translations_added")
        elif row.content_hash != digest:
            result.bump("translations_updated")
        if row.content_hash != digest:
            row.source_version = tf.source_version
            row.question = tf.question
            row.options = dict(tf.options)
            row.explanation = tf.explanation
            row.status = tf.status
            row.reviewed_by = tf.reviewed_by
            row.reviewed_at = tf.reviewed_at
            row.content_hash = digest
            row.imported_at = now
        # Hidden while it lags behind the German version (plan, translation pipeline step 5).
        row.hidden = row.source_version < versions[qid]
        if row.hidden:
            result.bump("translations_hidden")
    for key, row in existing.items():
        if key not in cs.translations:
            await db.delete(row)
            result.bump("translations_removed")


async def _import_glossary(db: AsyncSession, result: ImportResult) -> None:
    cs = result.report.content
    now = utcnow()
    existing = {(g.term, g.lang): g for g in (await db.execute(select(GlossaryTerm))).scalars()}
    wanted: set[tuple[str, str]] = set()
    for lang, gf in cs.glossary.items():
        for entry in gf.terms:
            key = (entry.term_de, lang)
            if key in wanted:
                continue
            wanted.add(key)
            row = existing.get(key)
            if row is None:
                row = GlossaryTerm(term=entry.term_de, lang=lang)
                db.add(row)
            row.source = entry.source
            row.keep_german = entry.keep_german
            row.imported_at = now
            if row.file_sync_pending:
                continue  # an admin edit waits for write-back; keep it (D-052)
            row.translation = entry.translation
            row.note = entry.note
            row.status = entry.status
            row.reviewed_by = entry.reviewed_by
            row.reviewed_at = entry.reviewed_at
    for key, row in existing.items():
        if key not in wanted:
            await db.delete(row)
    result.bump("glossary_terms", len(wanted))


async def import_content(
    db: AsyncSession, root: Path | None = None, *, today: date | None = None
) -> ImportResult:
    """Validate, then upsert. Commits on success, rolls back on any error."""
    result = ImportResult(report=validate_content(root, today=today))
    if not result.report.ok:
        return result
    await _import_topics(db, result)
    await _import_questions(db, result)
    if result.errors:
        await db.rollback()
        return result
    await _import_translations(db, result)
    await _import_glossary(db, result)
    await db.commit()
    return result
