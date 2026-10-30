"""Content pipeline (task 1.5): the scripts under scripts/content/ with the FakeProvider and
httpx mock transports. Nothing here reaches the AI provider or the internet.

The fixture tree (tests/fixtures/content) has two approved federal questions and one draft
for Zurich; each test works on a copy."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import httpx
import pytest
import yaml
from sqlalchemy import select

from app.content import fetch, store
from app.content.importer import import_content
from app.content.links import run_link_check
from app.content.validate import validate_content
from app.db import SessionLocal, utcnow
from app.llm import client as llm_client
from app.llm.client import FakeProvider
from app.models import LlmCall, Question
from scripts.content import (
    _common,
    answer,
    back_translate,
    draft,
    promote,
    recheck_sources,
    source_check,
    stats,
    sync_reviews,
    translate,
)
from tests.conftest import CONTENT_TODAY, FIXTURE_CONTENT, admin_logged_in

Q1 = "beispiel-staatsebenen"  # federal, approved, translations in every language (sq draft)
Q2 = "beispiel-anzahl-kantone"  # federal, approved, English only
Q3 = "beispiel-kantonsparlament"  # zh, draft
TODAY = CONTENT_TODAY.isoformat()


@pytest.fixture
def content(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "content"
    shutil.copytree(FIXTURE_CONTENT, root)
    monkeypatch.setattr(_common, "STATE_DIR", tmp_path / "batches")
    return root


@pytest.fixture
def fake():
    provider = FakeProvider()
    llm_client.set_provider(provider)
    yield provider
    llm_client.set_provider(None)


def read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def qfile(root: Path, qid: str, scope: str = "federal") -> dict:
    return read(root / "questions" / scope / f"{qid}.yaml")


def tfile(root: Path, lang: str, qid: str) -> dict:
    return read(root / "translations" / lang / f"{qid}.yaml")


def check_ok(root: Path) -> None:
    report = validate_content(root, today=CONTENT_TODAY)
    assert report.ok, [f"{i.path}: {i.message}" for i in report.errors]


def add_draft(root: Path, qid: str, *, correct: str = "a", url: str, **extra) -> None:
    store.write_question(
        root,
        {
            "id": qid,
            "version": 1,
            "scope": "federal",
            "canton": None,
            "topic": "bund.demokratie.foederalismus",
            "question_de": f"Testfrage {qid}: welche Ebene erhebt die Bundessteuer?",
            "options_de": {
                "a": "Der Bund",
                "b": "Der Kanton",
                "c": "Die Gemeinde",
                "d": "Der Bezirk",
            },
            "correct": correct,
            "explanation_de": "Die direkte Bundessteuer erhebt der Bund. Die Kantone ziehen sie ein.",
            "sources": [{"url": url, "checked": date(2026, 10, 30)}],
            "glossary": [],
            "status": "draft",
            "difficulty": 2,
            **extra,
        },
    )


def item(question: str, *, correct: str = "a", sources=None, slug: str = "") -> dict:
    return {
        "slug": slug,
        "question_de": question,
        "options_de": {
            "a": "Die Kantone und der Bund",
            "b": "Nur die Gemeinden",
            "c": "Nur der Bund",
            "d": "Das Bundesgericht",
        },
        "correct": correct,
        "explanation_de": "Die Aufgaben sind zwischen Bund und Kantonen geteilt. Das regelt die "
        "Bundesverfassung.",
        "difficulty": 2,
        "sources": sources or ["https://www.fedlex.admin.ch/eli/cc/1999/404/de"],
        "glossary": ["Bund", "Kanton"],
    }


# --- Draft -----------------------------------------------------------------------------------


async def test_draft_writes_valid_files_skips_duplicates_and_logs_cost(content, fake, capsys):
    fake.json_replies["content/draft"] = {
        "questions": [
            item("Wer teilt sich in der Schweiz die staatlichen Aufgaben?", slug="aufgaben-teilen"),
            # near-duplicate of the fixture question beispiel-staatsebenen
            item("Auf wie vielen staatlichen Ebenen ist die Schweiz heute organisiert?"),
            item("Welche Quelle ist das?", sources=["http://example.com/x"]),
            item("Wer beschliesst über die Strasse vor dem Gemeindehaus? Grösse ß", slug=""),
        ]
    }
    code = await draft.run(
        ["--root", str(content), "--canton", "zh", "--topic", "bund.demokratie.foederalismus"]
        + ["--count", "3", "--today", TODAY]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "skipped near-duplicate of beispiel-staatsebenen" in out
    assert "no official https source" in out
    assert "2 written, 1 near-duplicate(s) skipped, 1 rejected" in out

    first = qfile(content, "aufgaben-teilen")
    assert first["status"] == "draft" and first["version"] == 1 and first["canton"] is None
    assert first["sources"] == [
        {"url": "https://www.fedlex.admin.ch/eli/cc/1999/404/de", "checked": CONTENT_TODAY}
    ]
    assert first["options_de"][first["correct"]] == "Die Kantone und der Bund"  # shuffled
    files = sorted(p.stem for p in (content / "questions" / "federal").glob("*.yaml"))
    assert len(files) == 4  # two fixtures and two new drafts
    fourth = next(f for f in files if f.startswith("wer-beschliesst"))
    assert "ß" not in qfile(content, fourth)["question_de"]
    check_ok(content)

    # The batch API is the default: one request for three questions, logged at batch price.
    assert len(fake.batches) == 1 and len(next(iter(fake.batches.values()))) == 1
    async with SessionLocal() as db:
        calls = (await db.execute(select(LlmCall))).scalars().all()
    assert [c.purpose for c in calls] == ["content_draft"]
    assert calls[0].prompt_version == "content/draft@v1" and calls[0].cost_usd > 0


async def test_draft_default_count_fills_the_gap_and_direct_mode(content, fake, capsys):
    fake.json_replies["content/draft"] = {"questions": []}
    args = ["--root", str(content), "--canton", "zh", "--topic", "bund.demokratie.foederalismus"]
    assert await draft.run([*args, "--direct"]) == 0
    # target 14, one question on the topic already: 13 questions in requests of 5
    assert "drafting 13 question(s) in 3 request(s)" in capsys.readouterr().out
    assert [c.kind for c in fake.calls] == ["structured"] * 3 and not fake.batches
    sent = fake.calls[0].messages[0]["content"]
    assert "Auf wie vielen staatlichen Ebenen" in sent and "Anfrage 1 von 3" in sent
    async with SessionLocal() as db:
        n = len((await db.execute(select(LlmCall))).scalars().all())
    assert n == 3


async def test_draft_stops_when_the_target_is_reached(content, fake, capsys):
    path = content / "topics" / "zh.yaml"
    data = read(path)
    for t in data["topics"]:
        if t["code"] == "bund.demokratie.kantone_rolle":
            t["target_questions"] = 1
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    args = ["--root", str(content), "--canton", "zh", "--topic", "bund.demokratie.kantone_rolle"]
    assert await draft.run(args) == 0
    assert "none drafted" in capsys.readouterr().out and not fake.calls


# --- Independent answer --------------------------------------------------------------------


async def test_answer_agreement_and_disagreement(content, fake, capsys):
    add_draft(content, "steuer-ebene", correct="a", url="https://www.ch.ch/de/steuern/")
    fake.json_replies["content/answer"] = lambda text: (
        {"option": "b", "reasoning": "Das Parlament des Kantons heisst Kantonsrat."}
        if "Zürich" in text
        else {"option": "c", "reasoning": "Die Gemeinde erhebt die Steuer, meint das Modell."}
    )
    assert await answer.run(["--root", str(content), "--today", TODAY]) == 0
    agreed = qfile(content, Q3, "zh")
    assert agreed["status"] == "draft"
    assert agreed["checks"]["independent_answer"] == {
        "option": "b",
        "agrees": True,
        "model": "fake-batch-model",
        "at": CONTENT_TODAY,
        "version": 1,
        "reasoning": "Das Parlament des Kantons heisst Kantonsrat.",
    }
    disagreed = qfile(content, "steuer-ebene")
    assert disagreed["status"] == "needs_fix"
    assert disagreed["checks"]["independent_answer"]["agrees"] is False
    assert "meint das Modell" in disagreed["checks"]["independent_answer"]["reasoning"]
    check_ok(content)

    # The answering call never sees the key or the explanation.
    sent = [r.messages[0]["content"] for b in fake.batches.values() for r in b]
    assert len(sent) == 2
    assert all("Kantone ziehen sie ein" not in s and "Andere Kantone" not in s for s in sent)
    assert all("richtig" not in s.lower() for s in sent)
    # Already answered for this version: nothing to do on a second run.
    assert await answer.run(["--root", str(content)]) == 0
    assert "No draft questions waiting" in capsys.readouterr().out


# --- Source check --------------------------------------------------------------------------

PAGE = (
    "<html><head><title>Politik und Staat</title><script>var x = 1;</script></head><body>"
    "<nav>Menü</nav><p>Der Kantonsrat ist das Parlament des Kantons Zürich. Er hat 180 "
    "Mitglieder und wird alle vier Jahre vom Volk gewählt.</p>"
    "<p>Die direkte Bundessteuer wird vom Bund erhoben und von den Kantonen eingezogen. "
    "Die Kantone und Gemeinden erheben eigene Steuern auf Einkommen und Vermögen.</p>"
    "</body></html>"
)


def transport(dead: tuple[str, ...] = ()) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if any(d in str(request.url) for d in dead):
            return httpx.Response(404)
        return httpx.Response(200, html=PAGE)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


async def test_source_check_supported_not_supported_and_dead_link(content, fake, capsys):
    add_draft(content, "steuer-contra", url="https://www.admin.ch/contra")
    add_draft(content, "steuer-tot", url="https://www.ch.ch/de/gibt-es-nicht")
    fake.json_replies["content/source_check"] = lambda text: (
        {"verdict": "not_supported", "supported_by": [], "note": "Die Seite sagt etwas anderes."}
        if "admin.ch/contra" in text
        else {"verdict": "supported", "supported_by": [1], "note": "Absatz 1 nennt den Kantonsrat."}
    )
    async with transport(dead=("gibt-es-nicht",)) as client:
        code = await source_check.run(["--root", str(content), "--today", TODAY], client=client)
    assert code == 0

    ok = qfile(content, Q3, "zh")
    assert ok["checks"]["source"]["verdict"] == "supported" and ok["status"] == "draft"
    assert ok["sources"][0]["checked"] == CONTENT_TODAY  # was 2026-10-30
    contra = qfile(content, "steuer-contra")
    assert (
        contra["status"] == "needs_fix" and contra["checks"]["source"]["verdict"] == "not_supported"
    )
    assert contra["sources"][0]["checked"] == date(2026, 10, 30)  # not refreshed
    dead = qfile(content, "steuer-tot")
    assert dead["status"] == "needs_fix" and dead["checks"]["source"]["verdict"] == "dead_link"
    assert "HTTP 404" in dead["checks"]["source"]["note"]
    check_ok(content)

    # The dead link never reached the model; the page text did, without script or markup.
    requests = [r for b in fake.batches.values() for r in b]
    assert len(requests) == 2
    sent = requests[0].messages[0]["content"]
    assert "180 Mitglieder" in sent and "var x" not in sent and "<p>" not in sent


async def test_fetch_page_reads_text_with_a_size_cap_and_user_agent():
    client = fetch.new_client()
    assert client.headers["user-agent"] == fetch.USER_AGENT and client.timeout.read == 20
    await client.aclose()
    big = "<p>" + "Gemeindeversammlung " * 200_000 + "</p>"  # about 4 MB

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pdf":
            return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        return httpx.Response(200, html=big if request.url.path == "/big" else PAGE)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        page = await fetch.fetch_page(c, "https://www.ch.ch/big")
        assert page.ok and page.truncated and len(page.text) <= fetch.MAX_BYTES
        page = await fetch.fetch_page(c, "https://www.zh.ch/small")
        assert page.text.startswith("Politik und Staat") and "var x" not in page.text
        assert page.readable
        page = await fetch.fetch_page(c, "https://www.ch.ch/pdf")
        assert page.ok and not page.readable
    assert fetch.is_official_url("https://www.fedlex.admin.ch/eli/cc/1999/404/de")
    assert not fetch.is_official_url("https://example.com/") and not fetch.is_official_url(
        "http://www.ch.ch/"
    )
    assert fetch.is_official_url("https://www.winterthur.ch/", commune=True)
    text = "Anfang\n" + "Füllung\n" * 5000 + "Kantonsrat hat 180 Sitze"
    excerpt = fetch.excerpt(text, "Kantonsrat Sitze", 300)
    assert "Kantonsrat hat 180 Sitze" in excerpt and len(excerpt) <= 300


async def test_unreadable_page_is_unclear_without_an_ai_call(content, fake):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body><div id='app'></div></body></html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await source_check.run(["--root", str(content), "--ids", Q3], client=client)
    assert qfile(content, Q3, "zh")["checks"]["source"]["verdict"] == "unclear"
    assert not fake.batches and not fake.calls


async def test_recheck_sources_picks_old_checks_only(content, fake, capsys):
    fake.json_replies["content/source_check"] = {
        "verdict": "supported",
        "supported_by": [1],
        "note": "Gestützt.",
    }
    later = "2027-09-30"  # 335 days after the fixtures' check on 2026-10-30
    path = content / "questions" / "federal" / f"{Q2}.yaml"
    data = read(path)
    data["sources"][0]["checked"] = date(2027, 9, 1)  # recent: not re-checked
    store.write_question(content, data)
    async with transport() as client:
        await recheck_sources.run(
            ["--root", str(content), "--today", later, "--older-than", "300"], client=client
        )
    assert "2 question(s) last checked before 2026-12-04" in capsys.readouterr().out
    assert qfile(content, Q1)["sources"][0]["checked"] == date(2027, 9, 30)
    assert qfile(content, Q1)["status"] == "approved"
    assert qfile(content, Q2)["sources"][0]["checked"] == date(2027, 9, 1)


# --- Promote -------------------------------------------------------------------------------


async def test_promote_moves_only_fully_checked_drafts(content, capsys):
    good = {
        "independent_answer": {"option": "a", "agrees": True, "model": "m", "at": CONTENT_TODAY},
        "source": {"verdict": "supported", "note": "", "at": CONTENT_TODAY, "version": 1},
    }
    unclear = {
        "independent_answer": {"option": "a", "agrees": True, "model": "m", "at": CONTENT_TODAY},
        "source": {"verdict": "unclear", "note": "", "at": CONTENT_TODAY},
    }
    old = {
        "independent_answer": {
            "option": "a",
            "agrees": True,
            "model": "m",
            "at": CONTENT_TODAY,
            "version": 1,
        },
        "source": {"verdict": "supported", "note": "", "at": CONTENT_TODAY, "version": 1},
    }
    add_draft(content, "fertig", url="https://www.ch.ch/a", checks=good)
    add_draft(content, "unklar", url="https://www.ch.ch/b", checks=unclear)
    add_draft(content, "alte-pruefung", url="https://www.ch.ch/c", checks=old, version=2)
    assert await promote.run(["--root", str(content), "--dry-run"]) == 0
    assert qfile(content, "fertig")["status"] == "draft"
    assert await promote.run(["--root", str(content)]) == 0
    out = capsys.readouterr().out
    assert qfile(content, "fertig")["status"] == "in_review"
    assert qfile(content, "unklar")["status"] == "draft" and "source check: unclear" in out
    assert qfile(content, "alte-pruefung")["status"] == "draft"
    assert "no independent answer for this version" in out
    assert qfile(content, Q3, "zh")["status"] == "draft"  # never checked
    check_ok(content)


# --- Write-back of review actions ----------------------------------------------------------


async def test_sync_reviews_applies_each_action_and_the_import_agrees(api, content, capsys):
    async with SessionLocal() as db:
        assert (await import_content(db, content, today=CONTENT_TODAY)).ok
    await admin_logged_in(api)
    edits = {
        "question_de": "Wie heisst das Parlament im Kanton Zürich?",
        "explanation_de": "Es heisst Kantonsrat. Er hat 180 Mitglieder.",
    }
    r = await api.patch(f"/api/review/questions/{Q3}", json={"action": "approve", "edits": edits})
    assert r.status_code == 200, r.text
    r = await api.patch(
        f"/api/review/questions/{Q1}", json={"action": "send_back", "note": "Quelle veraltet"}
    )
    assert r.status_code == 200, r.text
    r = await api.patch(f"/api/review/questions/{Q2}", json={"action": "retire"})
    assert r.status_code == 200, r.text

    assert await sync_reviews.run(["--root", str(content), "--dry-run"]) == 0
    assert qfile(content, Q1)["status"] == "approved"  # dry run wrote nothing
    assert await sync_reviews.run(["--root", str(content), "--today", TODAY]) == 0
    out = capsys.readouterr().out
    assert "3 file(s) written, 0 skipped" in out

    q3 = qfile(content, Q3, "zh")
    assert q3["status"] == "approved" and q3["version"] == 2
    assert q3["explanation_de"] == edits["explanation_de"]
    assert q3["question_de"] == edits["question_de"]
    assert q3["review"]["action"] == "approve"
    q1 = qfile(content, Q1)
    assert q1["status"] == "needs_fix" and q1["version"] == 1
    # the date of the review action, not the day of the write-back
    assert q1["review"] == {"action": "send_back", "note": "Quelle veraltet", "at": utcnow().date()}
    q2 = qfile(content, Q2)
    assert q2["status"] == "retired" and q2["version"] == 1

    async with SessionLocal() as db:
        rows = {q.id: q for q in (await db.execute(select(Question))).scalars()}
    assert not any(q.file_sync_pending or q.pending_changes for q in rows.values())
    assert rows[Q3].version == 2 and rows[Q1].status == rows[Q1].file_status == "needs_fix"

    # Q3 is approved now and needs translations or the flag before the content check passes.
    data = qfile(content, Q3, "zh")
    data["translations_missing"] = True
    data["version"] = 3  # the flag is content: a new version
    store.write_question(content, data)
    async with SessionLocal() as db:
        result = await import_content(db, content, today=CONTENT_TODAY)
    assert result.ok, (result.errors, [i.message for i in result.report.errors])
    async with SessionLocal() as db:
        assert (await db.get(Question, Q1)).status == "needs_fix"  # the file's status, no bump
        assert (await db.get(Question, Q2)).status == "retired"
        assert (await db.get(Question, Q3)).version == 3
    # Nothing left to write back.
    assert await sync_reviews.run(["--root", str(content)]) == 0
    assert "No review actions waiting" in capsys.readouterr().out


async def test_sync_reviews_skips_a_file_changed_since_the_import(api, content, capsys):
    async with SessionLocal() as db:
        await import_content(db, content, today=CONTENT_TODAY)
    await admin_logged_in(api)
    await api.patch(f"/api/review/questions/{Q3}", json={"action": "retire"})
    data = qfile(content, Q3, "zh")
    data["version"] = 2
    data["difficulty"] = 3
    store.write_question(content, data)
    assert await sync_reviews.run(["--root", str(content)]) == 1
    assert "import the files first" in capsys.readouterr().out
    assert qfile(content, Q3, "zh")["status"] == "draft"
    async with SessionLocal() as db:
        assert (await db.get(Question, Q3)).file_sync_pending is True


# --- Link check (worker job) ---------------------------------------------------------------


async def test_link_check_flags_questions_and_writes_a_report(content):
    async with SessionLocal() as db:
        await import_content(db, content, today=CONTENT_TODAY)

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        if "zh.ch" in str(request.url):
            return httpx.Response(404)
        if request.method == "HEAD":
            return httpx.Response(405)  # some servers refuse HEAD: GET is tried
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        async with SessionLocal() as db:
            report = await run_link_check(db, content, client=client, today=CONTENT_TODAY)
            again = await run_link_check(db, content, client=client, today=CONTENT_TODAY)
    assert report.checked_urls == 2 and list(report.broken) == [
        "https://www.zh.ch/de/politik-staat.html"
    ]
    assert report.flagged == [Q3] and again.flagged == []  # not flagged twice
    assert "GET" in seen and "POST" not in seen
    text = (content / "reports" / "link-check-2026-11-01.md").read_text(encoding="utf-8")
    assert "politik-staat.html | HTTP 404 | beispiel-kantonsparlament" in text
    async with SessionLocal() as db:
        row = await db.get(Question, Q3)
        assert row.file_sync_pending and row.pending_changes[-1]["action"] == "broken_links"
        assert row.status == "draft"  # still the same status; the source check decides

    assert await sync_reviews.run(["--root", str(content), "--today", TODAY]) == 0
    q3 = qfile(content, Q3, "zh")
    assert q3["checks"]["links"] == {
        "broken": ["https://www.zh.ch/de/politik-staat.html"],
        "at": utcnow().date(),
    }
    assert q3["status"] == "draft" and q3["review"]["action"] == "broken_links"
    check_ok(content)
    assert validate_content(content, today=CONTENT_TODAY).content.questions[Q3].checks


def test_link_check_is_a_weekly_worker_job():
    from worker import tasks
    from worker.main import WorkerSettings

    assert tasks.check_source_links in WorkerSettings.functions
    job = next(c for c in WorkerSettings.cron_jobs if c.coroutine is tasks.check_source_links)
    assert job.weekday == 0


# --- Translation ---------------------------------------------------------------------------


def fr_reply(text: str) -> dict:
    return {
        "question": "Combien de cantons la Suisse compte-t-elle ?",
        "options": {"a": "20", "b": "23", "c": "26", "d": "30"},
        "explanation": "La Suisse compte 26 cantons. Six d'entre eux ont un siège au Conseil "
        "des États (Ständerat).",
    }


async def test_translate_skips_reviewed_work_and_writes_drafts(content, fake, capsys):
    path = content / "translations" / "fr" / f"{Q1}.yaml"
    data = read(path)
    data["status"] = "in_review"
    data["reviewed_by"] = data["reviewed_at"] = None
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    (content / "glossary" / "fr.yaml").write_text(
        "lang: fr\nterms:\n- term_de: Ständerat\n  translation: Conseil des États\n"
        "  keep_german: true\n",
        encoding="utf-8",
    )
    fake.json_replies["content/translate"] = fr_reply
    assert await translate.run(["--root", str(content), "--lang", "fr"]) == 0
    out = capsys.readouterr().out
    assert f"fr/{Q1}: in_review; never overwritten, skipped" in out
    assert tfile(content, "fr", Q1)["status"] == "in_review"
    written = tfile(content, "fr", Q2)
    assert written["status"] == "draft" and written["source_version"] == 1
    assert written["options"]["c"] == "26"
    sent = next(iter(fake.batches.values()))[0].messages[0]["content"]
    assert "Ständerat = Conseil des États; deutschen Begriff beibehalten" in sent
    assert "Zielsprache: Französisch (fr)" in sent

    # A current draft is kept unless --redo; the German draft question is never translated.
    fake.batches.clear()
    assert await translate.run(["--root", str(content), "--lang", "sq", "--ids", Q1, Q3]) == 0
    out = capsys.readouterr().out
    assert f"sq/{Q1}: a current draft translation exists" in out
    assert f"{Q3}: status draft; only approved questions are translated" in out
    assert not fake.batches

    # The German moves on: approved translations stay untouched (stale), drafts are redone.
    q = qfile(content, Q1)
    q["version"] = 2
    q["question_de"] = "Auf wie vielen staatlichen Ebenen ist die Schweiz aufgebaut?"
    store.write_question(content, q)
    before = (content / "translations" / "en" / f"{Q1}.yaml").read_text(encoding="utf-8")
    assert await translate.run(["--root", str(content), "--lang", "all", "--ids", Q1]) == 0
    out = capsys.readouterr().out
    assert f"en/{Q1}: approved, stale (from version 1); never overwritten" in out
    assert (content / "translations" / "en" / f"{Q1}.yaml").read_text(encoding="utf-8") == before
    assert tfile(content, "sq", Q1)["source_version"] == 2  # the stale draft was refreshed
    assert tfile(content, "sq", Q1)["status"] == "draft"
    assert tfile(content, "fr", Q1)["status"] == "in_review"


def test_glossary_terms_match_inflections_and_whole_abbreviations():
    from app.content.schema import GlossaryEntry, QuestionFile

    q = QuestionFile.model_validate(
        {**qfile(FIXTURE_CONTENT, Q2), "question_de": "Wer wählt die Mitglieder des Bundesrates?"}
    )
    entries = [
        GlossaryEntry(term_de="Bundesrat", translation="Federal Council"),
        GlossaryEntry(term_de="IV", translation="invalidity insurance"),
        GlossaryEntry(term="Kanton", translation="canton"),  # the older key still loads
        GlossaryEntry(term_de="Gemeinde", translation="commune"),
    ]
    found = [e.term_de for e in translate.glossary_for(q, entries)]
    assert found == ["Bundesrat", "Kanton"]  # "IV" is not matched inside "Initiative"


# --- Back-translation ----------------------------------------------------------------------


async def test_back_translate_flags_a_difference(content, fake, capsys):
    store.write_translation(
        content,
        {
            "id": Q2,
            "lang": "fr",
            "source_version": 1,
            "question": "Combien de cantons la Suisse compte-t-elle ?",
            "options": {"a": "20", "b": "23", "c": "26", "d": "30"},
            "explanation": "La Suisse compte 26 cantons.",
            "status": "draft",
        },
    )

    def back(text: str) -> dict:
        lang = text.split("\n", 1)[0].removeprefix("Sprache: ")
        return {
            "question_de": f"Wie viele Kantone hat die Schweiz? ({lang})",
            "options_de": {"a": "20", "b": "23", "c": "26", "d": "30"},
            "explanation_de": "Die Schweiz hat 26 Kantone.",
        }

    fake.json_replies["content/back_translate"] = back
    fake.json_replies["content/compare"] = lambda text: (
        {"verdict": "different", "reason": "Die Erklärung lässt die Halbkantone weg."}
        if "(fr)" in text
        else {"verdict": "same", "reason": "gleiche Bedeutung"}
    )
    assert (
        await back_translate.run(["--root", str(content), "--lang", "all", "--today", TODAY]) == 0
    )
    out = capsys.readouterr().out
    assert "1 same, 1 flagged, 0 without a result" in out  # fr/Q2 and the sq draft of Q1
    fr = tfile(content, "fr", Q2)
    assert fr["status"] == "flagged"
    bt = fr["checks"]["back_translation"]
    assert bt["verdict"] == "different" and bt["source_version"] == 1
    assert bt["question_de"].startswith("Wie viele Kantone") and bt["at"] == CONTENT_TODAY
    sq = tfile(content, "sq", Q1)
    assert sq["status"] == "draft" and sq["checks"]["back_translation"]["verdict"] == "same"
    # the back-translation request saw only the translation, not the German original
    first = [r for b in fake.batches.values() for r in b][0].messages[0]["content"]
    assert "Kantone" not in first and "Ebenen" not in first
    check_ok(content)
    report = validate_content(content, today=CONTENT_TODAY)
    assert report.translation_counts()["fr"]["flagged"] == 1
    assert report.content.translations[("fr", Q2)].status == "flagged"


# --- Stats ---------------------------------------------------------------------------------


async def test_stats_by_status_language_and_topic_gap(content, capsys):
    assert await stats.run(["--root", str(content)]) == 0
    out = capsys.readouterr().out
    assert "== ZH: 3 question(s)" in out
    lines = out.splitlines()
    row = next(line for line in lines if line.startswith("bund.demokratie.foederalismus"))
    assert row.split() == ["bund.demokratie.foederalismus", "14", "1", "1", "13"]
    row = next(line for line in lines if line.startswith("kanton.demokratie.kantonsrat"))
    assert row.split()[1:] == ["8", "1", "0", "7"]
    en = next(line for line in lines if line.startswith("en "))
    assert en.split() == ["en", "0", "0", "0", "2", "0", "0"]
    sq = next(line for line in lines if line.startswith("sq "))
    assert sq.split() == ["sq", "1", "0", "0", "0", "0", "1"]
