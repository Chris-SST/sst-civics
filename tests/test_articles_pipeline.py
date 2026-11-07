"""Article pipeline (D-073): production with the scripted provider, the state machine and its
timing, publication through the builder's status file, the digest section, the worker switch
and the command line. No network, no AI provider."""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select

from app.articles import files, workflow
from app.articles.produce import pending_feedback
from app.config import get_settings
from app.db import SessionLocal
from app.email.backend import memory_outbox
from app.llm.client import LLMError
from app.models import (
    ART_APPROVED,
    ART_CHANGES_REQUESTED,
    ART_HELD,
    ART_NEEDS_ATTENTION,
    ART_PLANNED,
    ART_PROPOSED,
    ART_PUBLISH_FAILED,
    ART_PUBLISHED,
    ART_PUBLISHING,
    ART_READY,
    Article,
    LlmCall,
)
from app.ops import digest
from scripts import articles as cli
from tests.articles_helpers import (
    FAIL,
    PASS,
    PUBLISH_AT,
    REVIEW_TO,
    SPOUSE,
    imported,
    load,
)
from worker import tasks

LEAD = PUBLISH_AT - timedelta(days=4)
PROPOSAL = PUBLISH_AT - timedelta(hours=24)


async def produce(key: str = SPOUSE, now=LEAD):
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, key)
        return await workflow.run_production(db, a, now)


async def tick(now):
    async with SessionLocal() as db:
        return await workflow.tick(db, now)


async def produced(now=LEAD):
    await imported()
    assert await produce(now=now) == ART_READY
    return await load()


# --- production ---------------------------------------------------------------------------------


async def test_production_writes_reviews_and_translates(pipeline):
    a = await produced()
    assert a.revision == 1
    assert a.english["slug"] == "married-to-a-swiss-citizen"
    assert a.english["checked"] == "2026-11-12"
    assert set(a.translations) == set(get_settings().article_languages)
    assert all(t["status"] == "ok" for t in a.translations.values())
    assert a.translations["de"]["content"]["slug"] == "married-to-a-swiss-citizen-de"
    assert [s["ok"] for s in a.sources_read] == [True, True]
    assert a.cost_chf > 0 and a.production_started_at is None
    async with SessionLocal() as db:
        calls = (await db.execute(select(LlmCall))).scalars().all()
    purposes = sorted({c.purpose for c in calls})
    assert purposes == [
        "article_review", "article_translate", "article_translation_review", "article_write",
    ]  # fmt: skip
    assert all(c.user_id is None for c in calls)
    assert abs(sum(c.cost_chf for c in calls) - a.cost_chf) < 1e-9
    # Writer and reviewer are different calls with different prompts; the writer got the
    # plan and the sources, never an email address.
    sent = json.dumps([c.messages for c in pipeline["fake"].calls])
    assert "@" not in sent.replace("@v1", "")
    assert "Five years of residence in total" in sent


async def test_a_failing_translation_is_skipped_not_blocking(pipeline):
    def review(text):
        return FAIL if json.loads(text)["lang"] == "tr" else PASS

    pipeline["fake"].json_replies["articles/translation_review"] = review
    a = await produced()
    assert a.translations["tr"]["status"] == "failed"
    assert len(a.translations["tr"]["notes"]) == 2  # first try and one fix round
    assert a.translations["de"]["status"] == "ok"
    texts, _ = workflow.build_files(a, PUBLISH_AT)
    assert not any(rel.startswith("tr/") for rel in texts) and "en/" in "".join(texts)


async def test_fact_review_failing_after_two_fixes_needs_attention(pipeline):
    pipeline["fake"].json_replies["articles/review"] = dict(FAIL)
    await imported()
    assert await produce() == ART_NEEDS_ATTENTION
    a = await load()
    assert "fact review" in a.last_error
    # The last draft is kept for Chris to read, unchecked and untranslated.
    assert a.english["slug"] == "married-to-a-swiss-citizen" and "checked" not in a.english
    assert a.translations == {} and a.revision == 1
    fixes = [c for c in pipeline["fake"].calls if "current_version" in str(c.messages)]
    assert len(fixes) == 2
    msg = memory_outbox.messages[-1]
    assert msg.to == REVIEW_TO and "needs attention" in msg.subject
    assert "not in the sources" in msg.text and "/api/articles/review/" in msg.text
    # Chris may publish it anyway: English only.
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    await tick(LEAD)
    assert [p.name for p in pipeline["articles"].glob("*/*.md")] == [
        "married-to-a-swiss-citizen.md"
    ]


async def test_cost_cap_stops_the_run(pipeline, monkeypatch):
    monkeypatch.setattr(get_settings(), "articles_cost_cap_chf", 0.000001)
    await imported()
    assert await produce() == ART_NEEDS_ATTENTION
    assert "cost cap" in (await load()).last_error


async def test_unreadable_sources_stop_before_any_ai_call(pipeline, monkeypatch):
    async def none_readable(plan, now):
        return [{"url": s["url"], "title": s["title"], "fetched_at": "", "ok": False,
                 "error": "HTTP 404", "text": ""} for s in plan["sources"]]  # fmt: skip

    monkeypatch.setattr("app.articles.research.fetch_sources", none_readable)
    await imported()
    assert await produce() == ART_NEEDS_ATTENTION
    assert "seed source" in (await load()).last_error
    assert pipeline["fake"].calls == []


async def test_provider_error_needs_attention(pipeline):
    pipeline["fake"].json_replies["articles/write"] = [LLMError("timeout")]
    await imported()
    assert await produce() == ART_NEEDS_ATTENTION
    assert "article_write failed: timeout" in (await load()).last_error


async def test_invalid_draft_gets_a_format_fix(pipeline):
    from tests.articles_helpers import article

    pipeline["fake"].json_replies["articles/write"] = lambda text: article(slug="Bad Slug!")
    pipeline["fake"].json_replies["articles/fix"] = lambda text: {
        **article(), "changes": ["Fixed the slug"]
    }  # fmt: skip
    a = await produced()
    assert a.english["slug"] == "married-to-a-swiss-citizen"
    assert any(r["kind"] == "validation" for r in a.reviews)


async def test_only_one_production_at_a_time(pipeline):
    await imported()
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        assert await workflow.start_production(db, a, LEAD)
    async with SessionLocal() as db:
        again = await workflow.get_by_key(db, SPOUSE)
        assert await workflow.run_production(db, again, LEAD) is None


# --- timing -----------------------------------------------------------------------------------------


async def test_due_actions_follow_the_contract_timing(pipeline):
    await imported()
    a = await load()
    assert workflow.due_action(a, LEAD - timedelta(minutes=1)) is None
    assert workflow.due_action(a, LEAD) == "produce"
    a.status = ART_READY
    assert workflow.due_action(a, PROPOSAL - timedelta(minutes=1)) is None
    assert workflow.due_action(a, PROPOSAL) == "propose"
    a.status, a.proposal_sent_at = ART_PROPOSED, PROPOSAL
    assert workflow.due_action(a, PUBLISH_AT - timedelta(minutes=1)) is None
    assert workflow.due_action(a, PUBLISH_AT) == "approve"
    # A late proposal moves publication to 24 hours after the email.
    late = PUBLISH_AT + timedelta(hours=3)
    a.proposal_sent_at = late
    assert workflow.publish_due_at(a) == late + timedelta(hours=24)
    assert workflow.due_action(a, PUBLISH_AT + timedelta(hours=20)) is None
    a.status = ART_HELD
    assert workflow.due_action(a, late + timedelta(days=3)) is None


async def test_tick_runs_the_whole_cycle(pipeline):
    builder = pipeline["builder"]
    await imported()
    assert (await tick(LEAD - timedelta(hours=1))).actions == []
    await tick(LEAD)
    assert (await load()).status == ART_READY
    assert memory_outbox.messages == []  # not before publish_at - 24 h

    await tick(PROPOSAL)
    a = await load()
    assert a.status == ART_PROPOSED and a.proposal_sent_at == PROPOSAL
    msg = memory_outbox.messages[-1]
    assert msg.to == REVIEW_TO
    assert "Monday 16 November 2026, 07:00" in msg.subject
    assert msg.text.count("/api/articles/review/") == 3
    for action in ("publish", "hold", "suggest"):
        assert f"?action={action}" in msg.text
    assert "## Who it is for" in msg.text and "<h2>Who it is for</h2>" in msg.html
    assert "German: translated and reviewed" in msg.text

    await tick(PUBLISH_AT - timedelta(minutes=5))
    assert (await load()).status == ART_PROPOSED
    await tick(PUBLISH_AT)
    a = await load()
    assert a.status == ART_PUBLISHING
    root = pipeline["articles"]
    assert (root / "en" / "married-to-a-swiss-citizen.md").is_file()
    assert (root / "de" / "married-to-a-swiss-citizen-de.md").is_file()
    assert len(list(root.glob("*/*.md"))) == 8
    assert builder.request()["reason"] == "publish spouse-facilitated"

    await tick(PUBLISH_AT + timedelta(minutes=1))  # builder not finished yet
    assert (await load()).status == ART_PUBLISHING
    builder.finish(ok=True)
    memory_outbox.clear()
    await tick(PUBLISH_AT + timedelta(minutes=2))
    a = await load()
    assert a.status == ART_PUBLISHED
    assert a.published_at == PUBLISH_AT and a.published_revision == 1
    assert a.live_urls["en"] == "https://viapunt.example/en/articles/married-to-a-swiss-citizen/"
    assert a.live_urls["de"] == "https://viapunt.example/de/ratgeber/married-to-a-swiss-citizen-de/"
    published = memory_outbox.messages[-1]
    assert "published" in published.subject and a.live_urls["fr"] in published.text


async def test_suggestion_restarts_the_clock(pipeline):
    await produced()
    await tick(PROPOSAL)
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        await workflow.suggest_changes(db, a, "Please mention the commune's interview.", PROPOSAL)
    a = await load()
    assert a.status == ART_CHANGES_REQUESTED and len(pending_feedback(a)) == 1
    assert workflow.due_action(a, PUBLISH_AT) == "produce"

    later = PROPOSAL + timedelta(hours=10)
    await tick(later)  # revises, re-reviews, re-translates
    a = await load()
    assert a.status == ART_READY and a.revision == 2 and not pending_feedback(a)
    fix_call = next(
        c for c in pipeline["fake"].calls if "commune's interview" in c.messages[0]["content"]
    )
    assert fix_call.model == get_settings().articles_write_model

    await tick(later + timedelta(minutes=15))  # proposal due at once: publish_at - 24h has passed
    a = await load()
    assert a.status == ART_PROPOSED and a.proposal_sent_at == later + timedelta(minutes=15)
    assert "Please mention the commune's interview." in memory_outbox.messages[-1].text
    assert "Applied: Please mention" in memory_outbox.messages[-1].text  # what changed
    assert workflow.publish_due_at(a) == later + timedelta(minutes=15, hours=24)
    await tick(PUBLISH_AT)
    assert (await load()).status == ART_PROPOSED  # publish_at passed, but the clock restarted


async def test_hold_waits_until_publish_now(pipeline):
    await produced()
    await tick(PROPOSAL)
    async with SessionLocal() as db:
        await workflow.hold(db, await workflow.get_by_key(db, SPOUSE))
    await tick(PUBLISH_AT + timedelta(days=2))
    assert (await load()).status == ART_HELD
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), PUBLISH_AT)
    assert (await load()).status == ART_APPROVED
    await tick(PUBLISH_AT + timedelta(days=2))
    assert (await load()).status == ART_PUBLISHING


async def test_failed_build_marks_publish_failed_and_emails(pipeline):
    await produced()
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    await tick(LEAD + timedelta(minutes=1))
    pipeline["builder"].finish(ok=False, error="astro: schema error in en/married.md")
    await tick(LEAD + timedelta(minutes=2))
    a = await load()
    assert a.status == ART_PUBLISH_FAILED and "schema error" in a.last_error
    assert "not published" in memory_outbox.messages[-1].subject


async def test_build_timeout_marks_publish_failed(pipeline):
    await produced()
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    await tick(LEAD)
    await tick(LEAD + timedelta(minutes=get_settings().articles_build_timeout_minutes + 1))
    assert (await load()).status == ART_PUBLISH_FAILED


async def test_failed_live_check_marks_publish_failed(pipeline, monkeypatch):
    async def one_missing(urls):
        return {"de": f"{urls['de']}: HTTP 404"}

    monkeypatch.setattr(workflow, "live_check", one_missing)
    await produced()
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    await tick(LEAD)
    pipeline["builder"].finish(ok=True)
    await tick(LEAD + timedelta(minutes=1))
    a = await load()
    assert a.status == ART_PUBLISH_FAILED and "HTTP 404" in a.last_error


async def test_correction_after_publication_republishes_with_updated_bumped(pipeline):
    await produced()
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), PUBLISH_AT)
    await tick(PUBLISH_AT)
    pipeline["builder"].finish()
    await tick(PUBLISH_AT + timedelta(minutes=1))
    assert (await load()).status == ART_PUBLISHED

    fix_day = PUBLISH_AT + timedelta(days=3)
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        await workflow.suggest_changes(db, a, "Correct the fee range.", fix_day)
    await tick(fix_day)  # revise
    await tick(fix_day + timedelta(minutes=15))  # propose
    assert (await load()).status == ART_PROPOSED
    assert "correction" in memory_outbox.messages[-1].subject
    publish = fix_day + timedelta(minutes=15, hours=24)
    await tick(publish)
    pipeline["builder"].finish()
    await tick(publish + timedelta(minutes=1))
    a = await load()
    assert a.status == ART_PUBLISHED and a.published_revision == 2
    assert a.published_at == PUBLISH_AT and a.last_published_at > fix_day
    fm, _ = files.parse_file(
        (pipeline["articles"] / "en" / "married-to-a-swiss-citizen.md").read_text(encoding="utf-8")
    )
    assert str(fm["published"]) == "2026-11-16" and str(fm["updated"]) == "2026-11-20"


async def test_unpublish_removes_files_and_requests_a_build(pipeline):
    await produced()
    async with SessionLocal() as db:
        await workflow.publish_now(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    await tick(LEAD)
    async with SessionLocal() as db:
        removed = await workflow.unpublish(db, await workflow.get_by_key(db, SPOUSE), LEAD)
    assert len(removed) == 8 and not list(pipeline["articles"].glob("*/*.md"))
    assert pipeline["builder"].request()["reason"] == "unpublish spouse-facilitated"
    assert (await load()).status == ART_HELD


async def test_stale_production_is_retried_then_stopped(pipeline):
    await imported()
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        await workflow.start_production(db, a, LEAD)
    await tick(LEAD + timedelta(hours=1))
    assert (await load()).status != ART_PLANNED  # still running
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        assert workflow.due_action(a, LEAD + timedelta(hours=3)) == "recover"
        await workflow.recover_stale(db, a, LEAD + timedelta(hours=3))
    a = await load()
    assert a.status == ART_PLANNED and a.attempts == 1


# --- digest, worker, CLI ------------------------------------------------------------------------------


async def test_digest_has_an_articles_section(pipeline, monkeypatch):
    async def ok_http(client, name, url):
        return digest._check(name, True, "HTTP 200")

    async def ok_cert(host):
        return digest._check(f"Certificate {host}", True, "fine")

    monkeypatch.setattr(digest, "_http_check", ok_http)
    monkeypatch.setattr(digest, "_cert_check", ok_cert)
    pipeline["fake"].json_replies["digest"] = {"headline": "h", "summary": "s", "actions": []}
    await imported()
    async with SessionLocal() as db:
        rows = {a.key: a for a in (await db.execute(select(Article))).scalars()}
        rows["dual-citizenship"].status = ART_NEEDS_ATTENTION
        rows["dual-citizenship"].last_error = "the fact review still finds problems"
        rows["canton-ag"].status = ART_PROPOSED
        rows["canton-ag"].english = {"title": "Naturalisation in Aargau"}
        await db.commit()
        report, emails = await digest.run_digest(db, send=False, to=["owner@example.org"])
    section = report["articles"]
    assert section["status"] == "ok"
    assert section["next_scheduled"]["key"] == SPOUSE
    assert [w["key"] for w in section["waiting_on_owner"]] == ["canton-ag"]
    assert section["needs_action"][0]["key"] == "dual-citizenship"
    text = emails[0].text
    assert "Articles:" in text and "ACTION (needs_attention)" in text
    assert "Proposed to you" in text and "<strong>Articles</strong>" in emails[0].html


async def test_digest_without_articles_has_no_section(pipeline, monkeypatch):
    async with SessionLocal() as db:
        section = await digest.articles_section(db, LEAD, LEAD, LEAD)
    assert section == {"status": "none"}


async def test_worker_tick_respects_the_switch(pipeline, monkeypatch):
    monkeypatch.setattr(get_settings(), "articles_enabled", False)
    assert await tasks.articles_tick({}) == 0
    async with SessionLocal() as db:
        assert (await db.execute(select(Article))).first() is None


async def test_worker_tick_queues_jobs_with_one_id_per_article(pipeline, monkeypatch):
    queued = []

    class Redis:
        async def enqueue_job(self, name, *args, _job_id=None):
            queued.append((name, args, _job_id))

    monkeypatch.setattr(workflow, "utcnow", lambda: LEAD)
    assert await tasks.articles_tick({"redis": Redis()}) == 1
    assert queued == [("produce_article", (SPOUSE,), f"produce_article:{SPOUSE}")]


async def test_cli_dry_run_changes_nothing(pipeline, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(workflow, "utcnow", lambda: LEAD)
    await imported()
    assert await cli.main(["--dry-run", "produce", SPOUSE]) == 0
    assert await cli.main(["tick", "--dry-run"]) == 0
    assert (await load()).status == ART_PLANNED
    assert pipeline["fake"].calls == []
    out = tmp_path / "preview"
    assert await cli.main(["preview", SPOUSE, "--out", str(out)]) == 0
    fm, _ = files.parse_file(next((out / "en").glob("*.md")).read_text(encoding="utf-8"))
    assert fm["key"] == SPOUSE and fm["lang"] == "en"
    assert await cli.main(["list"]) == 0
    printed = capsys.readouterr().out
    assert "would produce" in printed and "spouse-facilitated" in printed
