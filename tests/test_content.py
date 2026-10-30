"""Content files: validator, import on deploy, the content API and the admin review queue.

The fixture tree in tests/fixtures/content holds three example questions written for these
tests (two federal and approved, one for Zurich in draft) and their translations."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.content.importer import import_content
from app.content.validate import validate_content
from app.db import SessionLocal
from app.models import (
    AuditLog,
    GlossaryTerm,
    Question,
    QuestionProgress,
    QuestionReport,
    QuestionTranslation,
    Topic,
)
from scripts import validate_content as validate_script
from tests.conftest import (
    CONTENT_TODAY,
    FIXTURE_CONTENT,
    admin_logged_in,
    learner_logged_in,
)

Q1 = "beispiel-staatsebenen"  # federal, approved, seven translations (sq a draft)
Q2 = "beispiel-anzahl-kantone"  # federal, approved, translations_missing, English only
Q3 = "beispiel-kantonsparlament"  # zh, draft


@pytest.fixture
def content(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    shutil.copytree(FIXTURE_CONTENT, root)
    return root


def read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def qpath(root: Path, qid: str = Q1, scope: str = "federal") -> Path:
    return root / "questions" / scope / f"{qid}.yaml"


def edit(root: Path, qid: str = Q1, scope: str = "federal", **changes) -> None:
    data = read(qpath(root, qid, scope))
    data.update(changes)
    write(qpath(root, qid, scope), data)


def check(root: Path):
    return validate_content(root, today=CONTENT_TODAY)


async def do_import(root: Path):
    async with SessionLocal() as db:
        return await import_content(db, root, today=CONTENT_TODAY)


# --- Validator -----------------------------------------------------------------------------


def test_fixture_content_is_valid_and_summarised(content, capsys):
    report = check(content)
    assert report.ok, report.errors
    assert report.warnings == []
    assert set(report.content.questions) == {Q1, Q2, Q3}
    counts = report.translation_counts()
    assert counts["en"] == {
        "approved": 2,
        "draft": 0,
        "flagged": 0,
        "in_review": 0,
        "stale": 0,
        "missing": 0,
    }
    assert counts["sq"]["draft"] == 1 and counts["sq"]["missing"] == 1
    assert validate_script.main(["--root", str(content), "--today", "2026-11-01"]) == 0
    out = capsys.readouterr().out
    assert "federal" in out and "0 error(s), 0 warning(s)" in out


def test_repository_content_passes_the_check():
    """The real files under content/ (the CI step runs the same check)."""
    report = validate_content()
    assert report.ok, [f"{i.path}: {i.message}" for i in report.errors]
    assert "zh" in report.content.topic_files


@pytest.mark.parametrize(
    ("changes", "kind"),
    [
        (
            {"options_de": {"a": "Bund", "b": "Bund", "c": "Kanton", "d": "Gemeinde"}},
            "options_not_distinct",
        ),
        ({"options_de": {"a": "Bund", "b": "Kanton", "c": "Gemeinde"}}, "schema"),
        ({"options_de": {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}}, "schema"),
        ({"correct": "e"}, "schema"),
        ({"explanation_de": "   "}, "empty_explanation"),
        ({"sources": []}, "schema"),
        (
            {"sources": [{"url": "https://www.ch.ch/de/", "checked": date(2025, 10, 31)}]},
            "source_outdated",
        ),
        (
            {"sources": [{"url": "https://www.ch.ch/de/", "checked": date(2027, 1, 1)}]},
            "source_date",
        ),
        ({"sources": [{"url": "http://www.ch.ch/de/", "checked": date(2026, 10, 30)}]}, "schema"),
        ({"topic": "bund.gibt_es_nicht"}, "unknown_topic"),
        ({"topic": "kanton.demokratie.kantonsrat"}, "unknown_topic"),  # not a federal topic
        ({"canton": "zh"}, "schema"),
        ({"difficulty": 5}, "schema"),
        ({"status": "auto_verified"}, "schema"),
        ({"version": 0}, "schema"),
        ({"surprise": "field"}, "schema"),
    ],
)
def test_each_question_error_is_reported(content, changes, kind):
    edit(content, **changes)
    report = check(content)
    assert not report.ok
    assert kind in {i.kind for i in report.errors}, report.errors
    assert validate_script.main(["--root", str(content), "--today", "2026-11-01", "--quiet"]) == 1


def test_source_exactly_365_days_old_still_counts(content):
    edit(content, sources=[{"url": "https://www.ch.ch/de/", "checked": date(2025, 11, 1)}])
    assert check(content).ok
    edit(content, sources=[{"url": "https://www.ch.ch/de/", "checked": date(2025, 10, 31)}])
    assert "source_outdated" in check(content).kinds()


def test_pipeline_statuses_checks_and_review_blocks_are_accepted(content):
    """Task 1.5: needs_fix and flagged are valid, non-served statuses; the pipeline's checks
    and the review note are part of the schema."""
    checks = {
        "independent_answer": {
            "option": "c",
            "agrees": False,
            "model": "claude-sonnet-5-5",
            "at": date(2026, 10, 31),
            "version": 1,
            "reasoning": "Antwort c scheint zu stimmen.",
        },
        "source": {"verdict": "dead_link", "note": "HTTP 404", "at": date(2026, 10, 31)},
        "links": {"broken": ["https://www.zh.ch/alt"], "at": date(2026, 10, 31)},
    }
    review = {"action": "send_back", "note": "Quelle fehlt", "at": date(2026, 10, 31)}
    edit(content, Q3, "zh", status="needs_fix", checks=checks, review=review)
    path = content / "translations" / "sq" / f"{Q1}.yaml"
    back = {
        "verdict": "different",
        "reason": "Antwort b bedeutet etwas anderes.",
        "model": "m",
        "at": date(2026, 10, 31),
        "source_version": 1,
    }
    write(path, {**read(path), "status": "flagged", "checks": {"back_translation": back}})
    report = check(content)
    assert report.ok, report.errors
    assert report.content.questions[Q3].checks.independent_answer.agrees is False
    assert report.translation_counts()["sq"]["flagged"] == 1
    # An outdated source on a question waiting for a fix is a warning, not an error.
    old = [{"url": "https://www.ch.ch/de/", "checked": date(2025, 1, 1)}]
    edit(content, Q3, "zh", sources=old)
    report = check(content)
    assert report.ok and "source_outdated" in {i.kind for i in report.warnings}
    edit(content, Q3, "zh", status="draft")
    assert "source_outdated" in {i.kind for i in check(content).errors}

    for bad in (
        {"checks": {"source": {"verdict": "maybe", "at": date(2026, 10, 31)}}},
        {"checks": {"independent_answer": {"option": "e", "agrees": True}}},
        {"review": {"action": "approve"}},
        {"checks": {"surprise": {}}},
    ):
        edit(
            content,
            Q3,
            "zh",
            sources=[{"url": "https://www.ch.ch/", "checked": date(2026, 10, 30)}],
            **bad,
        )
        assert "schema" in check(content).kinds(), bad
        edit(content, Q3, "zh", checks=None, review=None)
    write(path, {**read(path), "status": "rejected"})
    assert "schema" in check(content).kinds()


def test_one_fresh_source_is_enough_and_retired_questions_skip_age_checks(content):
    old = {"url": "https://www.ch.ch/de/", "checked": date(2020, 1, 1)}
    fresh = {"url": "https://www.admin.ch/", "checked": date(2026, 10, 1)}
    edit(content, sources=[old, fresh])
    assert check(content).ok
    edit(content, Q3, "zh", sources=[old], status="retired", topic="kanton.entfernt")
    assert check(content).ok


def test_canton_question_cannot_use_a_federal_topic(content):
    edit(content, Q3, "zh", topic="bund.demokratie.foederalismus")
    assert "topic_scope" in check(content).kinds()


def test_commune_question_needs_a_commune_topic(content):
    data = read(qpath(content, Q3, "zh"))
    data.update(id="beispiel-gemeinde", scope="zh-winterthur", topic="gemeinde.leistungen")
    write(qpath(content, "beispiel-gemeinde", "zh-winterthur"), data)
    assert check(content).ok
    data["topic"] = "kanton.demokratie.kantonsrat"
    write(qpath(content, "beispiel-gemeinde", "zh-winterthur"), data)
    assert "topic_scope" in check(content).kinds()


def test_canton_without_topic_file_and_bad_scope(content):
    data = read(qpath(content, Q3, "zh"))
    data.update(id="beispiel-aargau", scope="ag", canton="ag")
    write(qpath(content, "beispiel-aargau", "ag"), data)
    assert "unknown_topic" in check(content).kinds()  # no topics/ag.yaml
    write(qpath(content, "beispiel-aargau", "zh"), data)
    assert "file_name" in check(content).kinds()  # scope ag filed under questions/zh


def test_duplicate_ids_and_file_names(content):
    data = read(qpath(content, Q3, "zh"))
    data.update(id=Q1)
    write(qpath(content, Q1, "zh"), data)
    assert "duplicate_id" in check(content).kinds()
    qpath(content, Q1, "zh").unlink()
    write(qpath(content, "anderer-name", "zh"), read(qpath(content, Q3, "zh")))
    assert "file_name" in check(content).kinds()


def test_approved_question_needs_every_translation_or_the_flag(content):
    (content / "translations" / "tr" / f"{Q1}.yaml").unlink()
    report = check(content)
    missing = [i for i in report.errors if i.kind == "translation_missing"]
    assert len(missing) == 1 and "translation for tr (" in missing[0].message
    edit(content, translations_missing=True)
    assert check(content).ok
    # A draft needs no translations at all; Q3 has none.
    assert not any(Q3 in i.path for i in check(content).issues)


def test_stale_translations_are_warnings_and_ahead_or_orphan_are_errors(content):
    edit(content, version=2)
    report = check(content)
    assert report.ok
    stale = [i for i in report.warnings if i.kind == "stale_translation"]
    assert len(stale) == 7
    assert report.translation_counts()["fr"]["stale"] == 1
    tr = read(content / "translations" / "fr" / f"{Q1}.yaml")
    tr["source_version"] = 3
    write(content / "translations" / "fr" / f"{Q1}.yaml", tr)
    assert "translation_ahead" in check(content).kinds()
    tr["source_version"] = 2
    tr["id"] = "gibt-es-nicht"
    write(content / "translations" / "fr" / "gibt-es-nicht.yaml", tr)
    assert "orphan_translation" in check(content).kinds()


def test_translation_shape_errors(content):
    path = content / "translations" / "it" / f"{Q1}.yaml"
    tr = read(path)
    write(path, {**tr, "status": "approved", "reviewed_by": None})
    assert "schema" in check(content).kinds()  # approved needs a reviewer and date
    write(path, {**tr, "options": {"a": "x", "b": "x", "c": "y", "d": "z"}})
    assert "options_not_distinct" in check(content).kinds()
    write(path, {**tr, "lang": "de"})
    assert "schema" in check(content).kinds()
    write(path, tr)
    write(content / "translations" / "it" / "falsch.yaml", tr)
    assert "file_name" in check(content).kinds()


def test_topic_file_errors(content):
    path = content / "topics" / "zh.yaml"
    data = read(path)
    bad = dict(data)
    bad["topics"] = [*data["topics"], data["topics"][0]]
    write(path, bad)
    assert "schema" in check(content).kinds()  # duplicate code
    bad["topics"] = [{**data["topics"][0], "code": "Bund Demokratie"}]
    write(path, bad)
    assert "schema" in check(content).kinds()
    bad["topics"] = [{**data["topics"][0], "scope": "canton"}]  # bund.* is not a canton code
    write(path, bad)
    assert "schema" in check(content).kinds()
    path.write_text("canton: zh\ntopics: [\n", encoding="utf-8")
    assert "yaml" in check(content).kinds()


# --- Import ----------------------------------------------------------------------------------


async def test_import_inserts_topics_questions_translations_and_glossary(content):
    result = await do_import(content)
    assert result.ok, result.errors
    assert result.counts["topics_added"] == 4
    assert result.counts["questions_added"] == 3
    assert result.counts["translations_added"] == 8
    assert result.counts.get("translations_hidden", 0) == 0
    async with SessionLocal() as db:
        topics = (await db.execute(select(Topic).order_by(Topic.position))).scalars().all()
        assert [t.code for t in topics][:2] == [
            "bund.demokratie.foederalismus",
            "bund.demokratie.kantone_rolle",
        ]
        q1 = await db.get(Question, Q1)
        assert q1.version == 1 and q1.status == "approved" and q1.canton is None
        assert q1.options_de["b"].startswith("Auf drei Ebenen") and q1.correct == "b"
        assert q1.sources == [
            {"url": "https://www.bk.admin.ch/bund-kurz-erklaert", "checked": "2026-10-30"}
        ]
        assert len(q1.content_hash) == 64 and q1.imported_at is not None
        q3 = await db.get(Question, Q3)
        assert q3.scope == "zh" and q3.canton == "zh" and q3.status == "draft"
        glossary = (await db.execute(select(GlossaryTerm))).scalars().all()
        assert {g.term for g in glossary} == {"Bund", "Ständerat"}

    again = await do_import(content)
    assert again.ok and again.counts["questions_unchanged"] == 3
    assert "questions_added" not in again.counts and "translations_updated" not in again.counts


async def test_version_bump_updates_and_hides_stale_translations(content):
    await do_import(content)
    edit(content, version=2, question_de="Auf wie vielen Ebenen ist der Schweizer Staat aufgebaut?")
    result = await do_import(content)
    assert result.ok, result.errors
    assert result.counts["questions_updated"] == 1 and result.counts["translations_hidden"] == 7
    async with SessionLocal() as db:
        q1 = await db.get(Question, Q1)
        assert q1.version == 2 and q1.question_de.startswith("Auf wie vielen Ebenen ist der")
        trs = (
            (
                await db.execute(
                    select(QuestionTranslation).where(QuestionTranslation.question_id == Q1)
                )
            )
            .scalars()
            .all()
        )
        assert len(trs) == 7 and all(t.hidden for t in trs)
    # The translator refreshes French against version 2: it is shown again.
    path = content / "translations" / "fr" / f"{Q1}.yaml"
    write(path, {**read(path), "source_version": 2})
    result = await do_import(content)
    assert result.counts["translations_updated"] == 1 and result.counts["translations_hidden"] == 6
    async with SessionLocal() as db:
        fr = (
            await db.execute(
                select(QuestionTranslation).where(
                    QuestionTranslation.question_id == Q1, QuestionTranslation.lang == "fr"
                )
            )
        ).scalar_one()
        assert fr.hidden is False and fr.source_version == 2


async def test_change_without_version_bump_rolls_back(content):
    await do_import(content)
    edit(content, question_de="Geändert, aber ohne neue Version?")
    edit(content, Q2, explanation_de="Neue Erklärung. Sie hat zwei Sätze.", version=2)
    result = await do_import(content)
    assert not result.ok and "raise the version" in result.errors[0]
    async with SessionLocal() as db:
        assert (await db.get(Question, Q1)).question_de.startswith("Auf wie vielen")
        assert (await db.get(Question, Q2)).version == 1  # the valid change was rolled back too


async def test_invalid_files_import_nothing(content):
    edit(content, options_de={"a": "x", "b": "x", "c": "y", "d": "z"})
    result = await do_import(content)
    assert not result.ok and not result.report.ok
    async with SessionLocal() as db:
        assert (await db.execute(select(Question))).first() is None
        assert (await db.execute(select(Topic))).first() is None


async def test_removed_files_retire_questions_and_delete_translations_and_topics(content):
    await do_import(content)
    qpath(content, Q3, "zh").unlink()
    (content / "translations" / "en" / f"{Q2}.yaml").unlink()  # Q2 may lack translations
    data = read(content / "topics" / "zh.yaml")
    data["topics"] = [t for t in data["topics"] if t["code"] != "gemeinde.leistungen"]
    write(content / "topics" / "zh.yaml", data)
    result = await do_import(content)
    assert result.ok, result.errors
    assert result.counts["questions_retired_missing"] == 1
    assert result.counts["translations_removed"] == 1 and result.counts["topics_removed"] == 1
    async with SessionLocal() as db:
        assert (await db.get(Question, Q3)).status == "retired"
    shutil.copy(FIXTURE_CONTENT / "questions" / "zh" / f"{Q3}.yaml", qpath(content, Q3, "zh"))
    await do_import(content)
    async with SessionLocal() as db:
        assert (await db.get(Question, Q3)).status == "draft"  # back with its file


def test_import_script_refuses_a_missing_directory(tmp_path, capsys):
    from scripts import import_content as import_script

    assert import_script.main(["--root", str(tmp_path / "nowhere")]) == 1
    assert "not found" in capsys.readouterr().err


# --- Content API -----------------------------------------------------------------------------


async def test_topics_are_public_with_approved_counts(api, content):
    await do_import(content)
    r = await api.get("/api/content/topics?canton=zh")
    assert r.status_code == 200, r.text
    data = r.json()
    topics = {t["code"]: t for t in data["topics"]}
    assert list(topics)[0] == "bund.demokratie.foederalismus"
    assert topics["bund.demokratie.foederalismus"]["approved_questions"] == 1
    assert topics["kanton.demokratie.kantonsrat"]["approved_questions"] == 0  # Q3 is a draft
    assert topics["gemeinde.leistungen"]["scope"] == "commune"
    assert data["approved_questions"] == 2
    assert (await api.get("/api/content/topics?canton=xx")).status_code == 400
    assert (await api.get("/api/content/topics?canton=ag")).json()["topics"] == []


async def test_question_with_translation_status(api, api2, content):
    await do_import(content)
    r = await api.get(f"/api/content/questions/{Q1}?lang=fr")
    assert r.status_code == 401
    await learner_logged_in(api, "lena@example.ch", access=True)
    r = await api.get(f"/api/content/questions/{Q1}?lang=fr")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["de"]["question"].startswith("Auf wie vielen") and body["correct"] == "b"
    assert [o["key"] for o in body["de"]["options"]] == ["a", "b", "c", "d"]
    assert body["translation_status"] == "approved"
    assert body["translation"]["question"].startswith("À combien")
    assert body["topic_name_en"].startswith("Federalism")
    r = await api.get(f"/api/content/questions/{Q1}?lang=sq")  # a draft is not shown
    assert r.json()["translation_status"] == "draft" and r.json()["translation"] is None
    r = await api.get(f"/api/content/questions/{Q2}?lang=it")
    assert r.json()["translation_status"] == "missing"
    r = await api.get(f"/api/content/questions/{Q1}?lang=de")
    assert r.json()["translation_status"] == "source" and r.json()["translation"] is None
    r = await api.get(f"/api/content/questions/{Q1}")  # the study language (en) by default
    assert r.json()["lang"] == "en" and r.json()["translation"] is not None
    assert (await api.get(f"/api/content/questions/{Q1}?lang=ru")).status_code == 400
    assert (await api.get(f"/api/content/questions/{Q3}")).status_code == 404  # draft

    edit(content, version=2, question_de="Auf wie vielen Ebenen ist der Staat aufgebaut?")
    await do_import(content)
    r = await api.get(f"/api/content/questions/{Q1}?lang=fr")
    assert r.json()["translation_status"] == "stale" and r.json()["translation"] is None

    await learner_logged_in(api2, "olaf@example.ch")  # no Civics Pass
    assert (await api2.get(f"/api/content/questions/{Q1}")).status_code == 403


async def test_admin_sees_drafts_through_the_content_api(api, content):
    await do_import(content)
    await admin_logged_in(api)
    r = await api.get(f"/api/content/questions/{Q3}?lang=en")
    assert r.status_code == 200 and r.json()["translation_status"] == "missing"


# --- Admin review queue -------------------------------------------------------------------------


async def test_review_queue_filters(api, api2, content):
    await do_import(content)
    await admin_logged_in(api)
    meta = (await api.get("/api/review/meta")).json()
    assert meta["cantons"] == ["zh"] and len(meta["topics"]) == 4
    assert meta["languages"] == ["en", "fr", "it", "pt", "es", "sq", "tr"]
    r = await api.get("/api/review/queue")
    assert [q["id"] for q in r.json()] == [Q3]  # drafts and questions in review
    r = await api.get("/api/review/queue?status=approved&canton=federal")
    assert {q["id"] for q in r.json()} == {Q1, Q2}
    r = await api.get("/api/review/queue?status=approved&canton=zh")
    assert r.json() == []
    r = await api.get("/api/review/queue?status=approved&topic=bund.demokratie.kantone_rolle")
    assert [q["id"] for q in r.json()] == [Q2]
    full = (await api.get(f"/api/review/questions/{Q1}")).json()
    assert full["options_de"]["b"].startswith("Auf drei") and full["file_status"] == "approved"
    states = {t["lang"]: t["state"] for t in full["translations"]}
    assert states["fr"] == "approved" and states["sq"] == "draft"
    await learner_logged_in(api2, "lena@example.ch", access=True)
    assert (await api2.get("/api/review/queue")).status_code == 403


async def test_review_transitions_are_recorded_for_the_pipeline(api, content):
    await do_import(content)
    admin = await admin_logged_in(api)
    url = f"/api/review/questions/{Q3}"
    r = await api.patch(url, json={"action": "send_back"})
    assert r.status_code == 400 and r.json()["detail"] == "note_required"
    r = await api.patch(url, json={"action": "retire", "edits": {"difficulty": 1}})
    assert r.status_code == 400 and r.json()["detail"] == "edits_need_approve"
    bad = {"a": "Kantonsrat", "b": "Kantonsrat", "c": "Landrat", "d": "Grosser Rat"}
    r = await api.patch(url, json={"action": "approve", "edits": {"options_de": bad}})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_options"
    r = await api.patch(url, json={"action": "approve", "edits": {"topic_code": "bund.x"}})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_topic"

    r = await api.patch(
        url,
        json={
            "action": "approve",
            "edits": {"difficulty": 1, "explanation_de": "Es heisst Kantonsrat. Er hat 180 Sitze."},
            "note": "Kürzer erklärt",
            "minutes": 4,
        },
    )
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["status"] == "approved" and q["file_status"] == "draft"
    assert q["difficulty"] == 1 and q["file_sync_pending"] is True
    change = q["pending_changes"][-1]
    assert change["action"] == "approve" and change["from"] == "draft"
    assert set(change["edits"]) == {"difficulty", "explanation_de"}

    r = await api.patch(url, json={"action": "send_back", "note": "Quelle fehlt"})
    assert r.json()["status"] == "draft" and len(r.json()["pending_changes"]) == 2
    r = await api.patch(url, json={"action": "retire"})
    assert r.json()["status"] == "retired"
    for action in ("retire", "approve"):
        r = await api.patch(url, json={"action": action, "note": "x"})
        assert r.status_code == 409 and r.json()["detail"] == "invalid_transition"

    stats = (await api.get("/api/review/stats")).json()
    assert stats["pending_file_updates"] == 1 and stats["my_review_minutes"] == 10
    federal = next(s for s in stats["scopes"] if s["scope"] == "federal")
    assert federal["by_status"] == {"approved": 2}
    async with SessionLocal() as db:
        actions = (
            (await db.execute(select(AuditLog.action).where(AuditLog.target_id == Q3)))
            .scalars()
            .all()
        )
        assert sorted(actions) == ["question.approve", "question.retire", "question.send_back"]
        stored = await db.get(Question, Q3)
        assert stored.reviewer_id == admin.id

    # The file is unchanged, so the next import keeps the admin's status...
    result = await do_import(content)
    assert result.ok and result.counts["questions_unchanged"] == 3
    async with SessionLocal() as db:
        assert (await db.get(Question, Q3)).status == "retired"
    # ...until the file moves on to a new version, which wins.
    edit(content, Q3, "zh", version=2, status="in_review")
    result = await do_import(content)
    assert any("admin changes" in n for n in result.notes)
    async with SessionLocal() as db:
        stored = await db.get(Question, Q3)
        assert stored.status == "in_review" and stored.file_sync_pending is False


async def test_learner_reports_reach_the_queue_and_approval_resolves_them(api, api2, content):
    await do_import(content)
    await learner_logged_in(api2, "lena@example.ch", access=True)
    r = await api2.post(f"/api/questions/{Q1}/report", json={"comment": "Tippfehler"})
    assert r.status_code == 201 and r.json()["report_count"] == 1
    r = await api2.post(f"/api/questions/{Q1}/report", json={"lang": "fr"})
    assert r.json()["report_count"] == 2
    await admin_logged_in(api)
    queue = (await api.get("/api/review/queue")).json()
    assert queue[0]["id"] == Q1 and queue[0]["status"] == "in_review"
    reports = (await api.get("/api/review/reports")).json()
    assert {r["lang"] for r in reports} == {None, "fr"}
    full = (await api.get(f"/api/review/questions/{Q1}")).json()
    assert len(full["reports"]) == 2
    r = await api.patch(f"/api/review/questions/{Q1}", json={"action": "approve"})
    assert r.json()["status"] == "approved" and r.json()["report_count"] == 0
    async with SessionLocal() as db:
        open_reports = (
            (await db.execute(select(QuestionReport).where(QuestionReport.resolved_at.is_(None))))
            .scalars()
            .all()
        )
        assert open_reports == []


async def test_translation_status_screen(api, content):
    await do_import(content)
    await admin_logged_in(api)
    data = (await api.get("/api/review/translations")).json()
    assert data["approved_questions"] == 2 and data["flagged_missing"] == 1
    langs = {row["lang"]: row for row in data["languages"]}
    assert langs["en"] == {
        "lang": "en",
        "approved": 2,
        "in_review": 0,
        "draft": 0,
        "flagged": 0,
        "stale": 0,
        "missing": 0,
    }
    assert langs["fr"]["approved"] == 1 and langs["fr"]["missing"] == 1
    assert langs["sq"]["draft"] == 1 and langs["sq"]["missing"] == 1
    edit(content, version=2, question_de="Auf wie vielen Ebenen ist der Staat aufgebaut?")
    await do_import(content)
    langs = {
        row["lang"]: row for row in (await api.get("/api/review/translations")).json()["languages"]
    }
    assert langs["fr"]["stale"] == 1 and langs["fr"]["approved"] == 0
    assert langs["en"]["stale"] == 1 and langs["en"]["approved"] == 1
    zh_only = (await api.get("/api/review/translations?canton=zh")).json()
    assert zh_only["approved_questions"] == 0


async def test_progress_is_kept_per_user_and_question(api, content):
    await do_import(content)
    await learner_logged_in(api, "lena@example.ch", access=True)
    for qid, answer in ((Q1, "b"), (Q2, "a")):
        r = await api.post("/api/study/answer", json={"question_id": qid, "answer": answer})
        assert r.status_code == 200, r.text
    assert r.json()["correct"] is False and r.json()["answer"] == "c"
    assert r.json()["mastery"]["topic_code"] == "bund.demokratie.kantone_rolle"
    async with SessionLocal() as db:
        rows = (await db.execute(select(QuestionProgress))).scalars().all()
        assert {p.question_id for p in rows} == {Q1, Q2}
        assert sorted((p.correct_own, p.wrong) for p in rows) == [(0, 1), (1, 0)]
