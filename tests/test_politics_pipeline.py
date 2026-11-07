"""Politics in your canton (D-074): the schedule, production with the scripted provider,
publication without a proposal email, the file format, the neutrality blocker, the
who's-who change check, results, the digest section and the command line. No network."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.articles import files, workflow
from app.articles.validate import validate_politics_frontmatter
from app.db import SessionLocal
from app.email.backend import memory_outbox
from app.models import (
    ART_HELD,
    ART_NEEDS_ATTENTION,
    ART_PLANNED,
    ART_PUBLISHED,
    ART_READY,
    Article,
    CurrentAffairsQuestion,
    LlmCall,
    PoliticsItem,
)
from app.ops import digest
from app.politics import schedule
from app.politics.discover import ensure_vote
from scripts import politics as cli
from tests.articles_helpers import REVIEW_TO
from tests.politics_helpers import (
    BLOCKER,
    FRIDAY,
    WEEK,
    add_week_items,
    people_reader,
)


async def tick(now):
    async with SessionLocal() as db:
        return await schedule.tick(db, now)


async def page(key: str) -> Article | None:
    async with SessionLocal() as db:
        return await workflow.get_by_key(db, key)


KEY = "zh-week-2026-46"
WHOSWHO_DUE = schedule.whoswho_due


# --- schedule (pure) -------------------------------------------------------------------------------


def test_roundup_is_due_on_friday_at_seven_for_friday_to_thursday():
    thursday = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)
    friday_early = datetime(2026, 11, 13, 5, 50, tzinfo=UTC)  # 06:50 Zurich
    friday = datetime(2026, 11, 13, 6, 0, tzinfo=UTC)  # 07:00 Zurich
    assert schedule.roundup_friday(thursday) == date(2026, 11, 6)
    assert schedule.roundup_friday(friday_early) == date(2026, 11, 6)
    assert schedule.roundup_friday(friday) == date(2026, 11, 13)
    assert schedule.roundup_period(date(2026, 11, 13)) == WEEK
    assert schedule.roundup_key("zh", date(2026, 11, 13)) == KEY
    # Summer time: 07:00 Zurich is 05:00 UTC.
    assert schedule.roundup_friday(datetime(2026, 6, 5, 5, 0, tzinfo=UTC)) == date(2026, 6, 5)


def test_whoswho_is_checked_on_the_first_of_the_month():
    first = datetime(2026, 12, 1, 6, 30, tzinfo=UTC)  # 07:30 Zurich
    assert schedule.whoswho_due(first, "2026-11-01")
    assert not schedule.whoswho_due(first, "2026-12-01")  # once that day
    assert not schedule.whoswho_due(datetime(2026, 12, 2, 6, 30, tzinfo=UTC), "2026-12-01")
    assert not schedule.whoswho_due(datetime(2026, 12, 1, 5, 0, tzinfo=UTC), "2026-11-01")
    assert schedule.whoswho_due(datetime(2026, 12, 9, 6, 30, tzinfo=UTC), None)  # first run


async def test_discovery_runs_each_morning_and_before_the_roundup(politics, monkeypatch):
    calls = []

    async def counting(db, cs, now, *, use_ai=True):
        from app.politics.discover import DiscoveryReport

        calls.append(now)
        return DiscoveryReport(cs.canton)

    monkeypatch.setattr("app.politics.discover.discover", counting)
    await add_week_items()  # discovery has run before (items are known)
    await tick(datetime(2026, 11, 10, 9, 0, tzinfo=UTC))  # Tuesday 10:00: not due
    assert calls == []
    await tick(datetime(2026, 11, 11, 5, 1, tzinfo=UTC))  # Wednesday 06:01 Zurich
    assert len(calls) == 1
    await tick(FRIDAY)  # the round-up: discovery first
    assert len(calls) == 2
    assert (await page(KEY)) is not None


# --- the round-up end to end --------------------------------------------------------------------


async def test_roundup_is_written_published_without_proposal_and_makes_questions(politics):
    await add_week_items()
    memory_outbox.clear()
    await tick(FRIDAY)  # created and produced
    a = await page(KEY)
    assert a.status == ART_READY, a.last_error
    assert a.plan["period_start"] == "2026-11-06" and a.plan["period_end"] == "2026-11-12"
    assert len(a.sources_read) == 4  # the selection's four items
    purposes = await _purposes()
    assert {
        "politics_select",
        "politics_write",
        "politics_neutrality",
        "politics_review",
    } <= purposes
    assert "article_translate" in purposes and "article_translation_review" in purposes

    await tick(FRIDAY + timedelta(minutes=15))  # ready -> approved -> files and build request
    a = await page(KEY)
    assert a.status == "publishing"
    root = politics["articles"]
    text = (root / "en" / "canton-of-zurich-week-46-2026.md").read_text(encoding="utf-8")
    fm, body = files.parse_file(text)
    assert fm["kind"] == "roundup" and fm["category"] == "politics" and fm["canton"] == "zh"
    assert fm["period_start"] == date(2026, 11, 6) and fm["period_end"] == date(2026, 11, 12)
    assert "vote_date" not in fm and fm["faq"] == []
    assert list(fm)[:10] == [
        "key", "kind", "lang", "slug", "title", "description", "category", "canton",
        "period_start", "period_end",
    ]  # fmt: skip
    assert validate_politics_frontmatter(fm) == []
    assert body.rstrip().endswith("best place to look.")
    de = files.parse_file(next((root / "de").glob("*.md")).read_text(encoding="utf-8"))[0]
    assert de["machine_translated"] is True and de["key"] == KEY and de["canton"] == "zh"

    politics["builder"].finish()
    await tick(FRIDAY + timedelta(minutes=30))
    a = await page(KEY)
    assert a.status == ART_PUBLISHED
    assert a.live_urls["en"] == (
        "https://viapunt.example/en/politics/zh/canton-of-zurich-week-46-2026/"
    )
    assert a.live_urls["de"].startswith("https://viapunt.example/de/politik/zh/")
    # No proposal and no "published" email: politics pages go to the digest only.
    assert memory_outbox.messages == []

    await tick(FRIDAY + timedelta(minutes=45))  # the practice questions
    a = await page(KEY)
    assert a.plan["questions"] == 2 and a.plan["questions_revision"] == a.published_revision
    async with SessionLocal() as db:
        qs = (await db.execute(select(CurrentAffairsQuestion))).scalars().all()
    assert len(qs) == 2  # the third failed the independent check
    q = qs[0]
    assert q.canton == "zh" and q.page_key == KEY and q.refers_to == date(2026, 11, 12)
    assert q.expires_at.date() >= date(2027, 5, 13)  # six months after the week
    assert q.page_paths["en"] == "/en/politics/zh/canton-of-zurich-week-46-2026/"
    assert set(q.translations) == {"en", "fr", "it", "pt", "es", "sq", "tr"}
    # Once made, not made again.
    n_calls = len(politics["fake"].calls)
    await tick(FRIDAY + timedelta(hours=1))
    assert len(politics["fake"].calls) == n_calls


async def _purposes() -> set[str]:
    async with SessionLocal() as db:
        return {c.purpose for c in (await db.execute(select(LlmCall))).scalars()}


async def test_quiet_week_is_skipped(politics):
    await add_week_items(n=2)
    await tick(FRIDAY)
    a = await page(KEY)
    assert a.status == ART_HELD and "quiet week" in a.last_error
    assert memory_outbox.messages == []  # not an error


async def test_items_outside_the_week_are_not_used(politics):
    await add_week_items(day=date(2026, 11, 2))
    await tick(FRIDAY)
    assert (await page(KEY)).status == ART_HELD


async def test_a_roundup_missed_by_days_is_not_backfilled(politics):
    await add_week_items()
    await tick(FRIDAY + timedelta(days=3))
    assert await page(KEY) is None


# --- neutrality --------------------------------------------------------------------------------------


async def test_neutrality_blocker_stops_publication(politics):
    politics["fake"].json_replies["politics/neutrality_review"] = dict(BLOCKER)
    await add_week_items()
    await tick(FRIDAY)
    a = await page(KEY)
    assert a.status == ART_NEEDS_ATTENTION
    assert "neutrality review" in a.last_error
    assert "checked" not in (a.english or {})  # the kept draft is not passed
    assert not any(politics["articles"].glob("*/*.md"))
    # One email, and nothing published on the following ticks.
    assert len(memory_outbox.messages) == 1
    assert memory_outbox.messages[0].to == REVIEW_TO
    assert "needs attention" in memory_outbox.messages[0].subject
    await tick(FRIDAY + timedelta(minutes=15))
    await tick(FRIDAY + timedelta(minutes=30))
    assert (await page(KEY)).status == ART_NEEDS_ATTENTION
    assert not any(politics["articles"].glob("*/*.md"))
    assert len(memory_outbox.messages) == 1
    # The fact review never ran on a text that failed neutrality.
    assert "politics_review" not in await _purposes()


# --- votes ---------------------------------------------------------------------------------------------


async def make_vote(now, vote_date=date(2027, 2, 28), level="cantonal", canton="zh") -> str:
    async with SessionLocal() as db:
        return await ensure_vote(
            db,
            set_canton="zh",
            canton=canton,
            level=level,
            vote_date=vote_date,
            title_de="Glattalbahnverlängerung Kloten",
            name="Glattalbahn Kloten",
            data={"announcements": ["https://www.zh.ch/de/news-uebersicht/x.html"]},
            now=now,
        )


async def test_vote_explainer_four_weeks_ahead_then_result(politics):
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    await add_week_items()
    key = await make_vote(now)
    assert key == "vote-zh-2027-02-28-glattalbahn-kloten"
    await tick(now)
    assert (await page(key)).status == ART_PLANNED  # not yet: 28 days before the vote
    due = datetime(2027, 1, 31, 6, 0, tzinfo=UTC)
    await tick(due - timedelta(minutes=15))
    assert (await page(key)).status == ART_PLANNED
    await tick(due)
    a = await page(key)
    assert a.status == ART_READY, a.last_error
    await tick(due + timedelta(minutes=15))
    fm, body = files.parse_file(
        (politics["articles"] / "en" / f"{a.english['slug']}.md").read_text(encoding="utf-8")
    )
    assert fm["vote_date"] == date(2027, 2, 28) and fm["vote_level"] == "cantonal"
    assert "result" not in fm and "period_start" not in fm
    assert validate_politics_frontmatter(fm) == []
    assert "## Arguments in favour" in body and "## Result" not in body
    politics["builder"].finish()
    await tick(due + timedelta(minutes=30))
    assert (await page(key)).status == ART_PUBLISHED

    # After the vote: the result notice is found and the page is written again.
    after = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
    politics["fake"].json_replies["politics/results"] = {
        "results": [
            {
                "title_de": "Glattalbahnverlängerung Kloten",
                "yes_percent": 54.2,
                "turnout_percent": 41.7,
                "accepted": True,
            }  # fmt: skip
        ]
    }
    async with SessionLocal() as db:
        db.add(
            PoliticsItem(
                canton="zh",
                source_id="zh-cantonal-votes",
                source_type="vote_list",
                level="canton",
                url="https://www.zh.ch/de/news-uebersicht/ausgang.html",
                title="Ausgang Abstimmungen vom 28. Februar 2027",
                item_date=date(2027, 2, 28),
                data={},
            )  # fmt: skip
        )
        await db.commit()
    await tick(after)
    a = await page(key)
    assert a.plan["result"]["yes_percent"] == 54.2
    assert a.status == ART_READY and a.english["result"] == {
        "yes_percent": 54.2, "turnout_percent": 41.7, "accepted": True,
    }  # fmt: skip
    await tick(after + timedelta(minutes=15))
    fm, body = files.parse_file(
        (politics["articles"] / "en" / f"{a.english['slug']}.md").read_text(encoding="utf-8")
    )
    assert fm["result"] == {"yes_percent": 54.2, "turnout_percent": 41.7, "accepted": True}
    assert body.count("## Result") == 1
    assert validate_politics_frontmatter(fm) == []
    politics["builder"].finish()
    await tick(after + timedelta(minutes=30))
    a = await page(key)
    assert a.status == ART_PUBLISHED and a.published_at < a.last_published_at
    assert memory_outbox.messages == []


async def test_federal_vote_uses_canton_ch(politics):
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    key = await make_vote(now, date(2026, 11, 29), level="federal", canton="ch")
    a = await page(key)
    assert key.startswith("vote-ch-2026-11-29-") and a.canton == "ch"
    assert a.publish_at == now  # less than four weeks ahead: as soon as possible
    a.english = {"slug": "x"}
    extra = workflow.politics_extra(a)
    assert extra["vote_level"] == "federal" and extra["result"] is None
    assert files.page_path("vote", "fr", "x", "ch") == "/fr/politique/ch/x/"


def test_a_passed_vote_without_result_is_not_produced():
    a = Article(
        key="vote-zh-2026-09-27-x", kind="vote", status=ART_PLANNED,
        publish_at=datetime(2026, 8, 30, 5, 0, tzinfo=UTC),
        plan={"vote_date": "2026-09-27", "result": None},
    )  # fmt: skip
    assert schedule.due_action(a, datetime(2026, 9, 26, 5, 0, tzinfo=UTC)) == "produce"
    assert schedule.due_action(a, datetime(2026, 9, 28, 5, 0, tzinfo=UTC)) is None


# --- who's who ------------------------------------------------------------------------------------------


async def test_whoswho_monthly_republishes_only_when_something_changed(politics, monkeypatch):
    monkeypatch.setattr(schedule, "whoswho_due", WHOSWHO_DUE)
    first_run = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    await add_week_items()
    await tick(first_run)  # first run: read, written
    key = "zh-whos-who"
    a = await page(key)
    assert a.status == ART_READY, a.last_error
    assert a.plan["seats"] == {"SVP": 43, "SP": 35}
    await tick(first_run + timedelta(minutes=15))
    politics["builder"].finish()
    await tick(first_run + timedelta(minutes=30))
    assert (await page(key)).status == ART_PUBLISHED
    n_calls = len(politics["fake"].calls)

    december = datetime(2026, 12, 1, 6, 1, tzinfo=UTC)  # 07:01 Zurich on the 1st
    await tick(december)
    a = await page(key)
    assert a.status == ART_PUBLISHED and a.plan["last_check"] == "2026-12-01"
    assert len(politics["fake"].calls) == n_calls + 1  # the roster call only, no rewrite
    await tick(december + timedelta(minutes=15))
    assert len(politics["fake"].calls) == n_calls + 1  # once a day

    # January: a seat moved, so the page is written again.
    monkeypatch.setattr(schedule, "read_people", people_reader({"SVP": 42, "SP": 36}))
    await tick(datetime(2027, 1, 1, 6, 1, tzinfo=UTC))
    a = await page(key)
    assert a.status == ART_READY and a.plan["seats"] == {"SVP": 42, "SP": 36}


# --- digest, articles untouched, CLI -----------------------------------------------------------------


async def test_digest_lists_politics_and_actions(politics):
    politics["fake"].json_replies["politics/neutrality_review"] = dict(BLOCKER)
    await add_week_items()
    await tick(FRIDAY)
    async with SessionLocal() as db:
        report = await digest.build_report(db, FRIDAY + timedelta(days=1))
    section = report["politics"]
    assert section["status"] == "ok"
    assert section["needs_action"][0]["key"] == KEY
    email = digest.render_email(report, None, "chris@example.org")
    assert "Politics:" in email.text and "ACTION (needs_attention)" in email.text
    # The articles section does not list politics pages.
    assert all(x["key"] != KEY for x in (report["articles"].get("needs_action") or []))


async def test_digest_lists_yesterdays_politics_pages(politics):
    await add_week_items()
    for minutes in (0, 15):
        await tick(FRIDAY + timedelta(minutes=minutes))
    politics["builder"].finish()
    await tick(FRIDAY + timedelta(minutes=30))
    async with SessionLocal() as db:
        report = await digest.build_report(db, FRIDAY + timedelta(days=1))
    published = report["politics"]["published_yesterday"]
    assert [p["key"] for p in published] == [KEY]
    assert "Published yesterday (roundup)" in "\n".join(
        digest.render_email(report, None, "x@example.org").text.splitlines()
    )


async def test_articles_tick_ignores_politics_pages(politics):
    await add_week_items()
    await tick(FRIDAY)
    async with SessionLocal() as db:
        report = await workflow.tick(db, FRIDAY + timedelta(minutes=20))
    assert all(KEY not in line for line in report.actions)
    assert (await page(KEY)).status == ART_READY  # untouched by the article pipeline


async def test_cli_list_dry_run_tick_and_publish(politics, capsys):
    await add_week_items()
    assert await cli.main(["--dry-run", "tick"]) == 0
    assert await cli.main(["roundup", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would" in out
    await tick(FRIDAY)
    assert await cli.main(["list"]) == 0
    assert KEY in capsys.readouterr().out
    assert await cli.main(["publish", KEY, "--dry-run"]) == 0
    assert "en/canton-of-zurich-week-46-2026.md" in capsys.readouterr().out.replace("\\", "/")
    assert await cli.main(["produce", KEY, "--dry-run"]) == 0
    assert '"period_start": "2026-11-06"' in capsys.readouterr().out
    assert (await page(KEY)).status == ART_READY  # dry runs change nothing


async def test_worker_jobs_are_off_unless_enabled(politics, monkeypatch):
    from app.config import get_settings
    from worker import tasks

    await add_week_items()
    assert get_settings().politics_enabled is False
    assert await tasks.politics_tick({}) == 0
    assert await tasks.produce_politics_page({}, KEY) is None
    monkeypatch.setattr(get_settings(), "politics_enabled", True)
    monkeypatch.setattr("app.politics.schedule.utcnow", lambda: FRIDAY)
    assert await tasks.politics_tick({}) > 0  # no queue: runs inline
    assert (await page(KEY)).status == ART_READY
