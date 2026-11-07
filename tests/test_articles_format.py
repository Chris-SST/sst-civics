"""Article pipeline (D-073): plan import, the deterministic checks, the file format and the
build status, against docs/articles-contract.md."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import select

from app.articles import files, workflow
from app.articles.constants import GUIDE_KEYS
from app.articles.plan import import_plan, load_plan
from app.articles.validate import validate_article, validate_translation, word_count
from app.db import SessionLocal
from app.models import ART_DRAFTING, ART_PLANNED, Article
from tests.articles_helpers import FEDLEX, PLAN, SEM, SPOUSE, article, body, load

PAGES_MJS = Path(__file__).resolve().parents[1] / "site" / "src" / "i18n" / "pages.mjs"
KEYS = {"spouse-facilitated", "dual-citizenship", "canton-ag"}
READ = {SEM, FEDLEX}


def check(content, **kw):
    return validate_article(
        content,
        kind=kw.get("kind", "article"),
        lang=kw.get("lang", "en"),
        plan_keys=KEYS,
        read_urls=kw.get("read", READ),
    )


# --- guide keys -------------------------------------------------------------------------------


def test_guide_keys_match_the_site_slug_table():
    text = PAGES_MJS.read_text(encoding="utf-8")
    block = text.split("export const SLUGS = {", 1)[1].split("\n};", 1)[0]
    keys = re.findall(r"^\s{2}([A-Za-z]\w*):\s*\{", block, re.MULTILINE)
    assert keys, "SLUGS not found in pages.mjs"
    assert set(keys) == set(GUIDE_KEYS), (
        "app/articles/constants.py GUIDE_KEYS is out of step with site/src/i18n/pages.mjs: "
        f"missing {set(keys) - set(GUIDE_KEYS)}, extra {set(GUIDE_KEYS) - set(keys)}"
    )


# --- plan --------------------------------------------------------------------------------------


def test_fixture_plan_parses():
    entries, errors = load_plan(PLAN)
    assert errors == []
    assert [e.key for e in entries] == ["spouse-facilitated", "dual-citizenship", "canton-ag"]
    assert entries[2].canton == "ag"


def write_plan(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


def plan_entries() -> list[dict]:
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


async def test_import_creates_planned_articles_and_only_updates_planned(tmp_path):
    async with SessionLocal() as db:
        report = await import_plan(db, PLAN)
    assert sorted(report.created) == sorted(KEYS) and not report.errors
    a = await load()
    assert a.status == ART_PLANNED
    assert a.publish_at == datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
    assert a.plan["must_cover"] == ["Five years of residence in total", "Three years of marriage"]
    assert len(a.review_nonce) == 32

    # A changed publish_at applies while planned ...
    entries = plan_entries()
    entries[0]["publish_at"] = "2026-11-17T07:00:00+01:00"
    entries[1]["publish_at"] = "2026-11-24T07:00:00+01:00"
    async with SessionLocal() as db:
        dual = await workflow.get_by_key(db, "dual-citizenship")
        dual.status = ART_DRAFTING  # ... but not once production has started
        await db.commit()
        report = await import_plan(db, write_plan(tmp_path, entries))
    assert report.updated == [SPOUSE]
    assert (await load()).publish_at == datetime(2026, 11, 17, 6, 0, tzinfo=UTC)
    assert (await load("dual-citizenship")).publish_at == datetime(2026, 11, 23, 6, 0, tzinfo=UTC)

    # Removing a planned key from the plan removes the row; one in production stays.
    async with SessionLocal() as db:
        report = await import_plan(db, write_plan(tmp_path, [entries[2]]))
    assert report.removed == [SPOUSE]
    assert await load() is None
    assert await load("dual-citizenship") is not None


async def test_invalid_entries_are_skipped_and_nothing_is_removed(tmp_path):
    async with SessionLocal() as db:
        await import_plan(db, PLAN)
    entries = plan_entries()
    entries[0]["category"] = "news"
    entries[1]["publish_at"] = "2026-11-24T07:00:00"  # no offset
    entries.append(dict(entries[2]))  # duplicate key
    async with SessionLocal() as db:
        report = await import_plan(db, write_plan(tmp_path, entries))
    assert len(report.errors) == 3
    assert report.removed == []
    async with SessionLocal() as db:
        assert len((await db.execute(select(Article))).scalars().all()) == 3


async def test_missing_plan_file_is_not_an_error(tmp_path):
    async with SessionLocal() as db:
        report = await import_plan(db, tmp_path / "nothing.yaml")
    assert not report.found and "No plan file" in report.summary()


# --- validator ------------------------------------------------------------------------------------


def test_valid_article_passes():
    content = article()
    assert 800 <= word_count(content["body"]) <= 1450
    assert check(content) == []


def test_each_rule_is_checked():
    cases = {
        "title must be": article(title="x" * 91),
        "slug must be": article(slug="Married_To"),
        "description must be": article(description="Too short."),
        "summary must have": article(summary=["One."]),
        "faq must have": article(faq=[{"q": "Q?", "a": "A."}]),
        "plain text": article(
            faq=[{"q": "Q?", "a": "See **this**."}, {"q": "R?", "a": "B."}, {"q": "S?", "a": "C."}]
        ),
        "was not read": article(
            sources=[
                {"title": "SEM", "url": SEM},
                {"title": "Somewhere", "url": "https://example.org/page"},
            ]
        ),
        "sources must list": article(sources=[{"title": "SEM", "url": SEM}]),
        "unknown guide page key": article(related=["nowhere"]),
        "H1": article(body="# Title\n\n" + article()["body"]),
        "raw HTML": article(body=article()["body"] + "\n\n<div>x</div>"),
        "images": article(body=article()["body"] + "\n\n![x](https://example.org/a.png)"),
        "unknown guide page placeholder": article(body=article()["body"] + " [x](guide:nope)"),
        "not in the plan": article(body=article()["body"] + " [x](article:unknown-key)"),
        "is not allowed": article(body=article()["body"] + " [x](/en/overview/)"),
        "words": article(body="## One\n\nShort text."),
        "official": article(
            description="The official guide to facilitated naturalisation for "
            "people married to a Swiss citizen."
        ),  # fmt: skip
        "the site adds it": article(body=article()["body"] + "\n\n## Sources\n\nSEM."),
    }
    for expected, content in cases.items():
        problems = check(content)
        assert any(expected in p for p in problems), (expected, problems)


def test_canton_guides_are_longer():
    short = article(body=body(700))
    assert check(short) == []
    assert any("words" in p for p in check(short, kind="canton"))


def test_translation_must_keep_links_and_structure():
    en = article()
    de = {**article(), "slug": "verheiratet-mit-einer-schweizerin", "title": "Verheiratet?" * 3}
    assert validate_translation(de, en, kind="article", lang="de", plan_keys=KEYS) == []
    broken = {**de, "body": de["body"].replace("guide:calculator", "guide:fees")}
    problems = validate_translation(broken, en, kind="article", lang="de", plan_keys=KEYS)
    assert any("placeholders differ" in p for p in problems)
    fewer = {**de, "faq": de["faq"][:2] + [{"q": "Q?", "a": "A."}, {"q": "R?", "a": "B."}]}
    problems = validate_translation(fewer, en, kind="article", lang="de", plan_keys=KEYS)
    assert any("as many items" in p for p in problems)


# --- files ----------------------------------------------------------------------------------------------


def make_article(kind: str = "article", **kw) -> Article:
    en = {**article(), "checked": "2026-11-14"}
    de = {**article(), "slug": "verheiratet-mit-schweizer", "title": "Verheiratet mit Schweizer"}
    return Article(
        key="canton-ag" if kind == "canton" else SPOUSE,
        kind=kind,
        category="cantons" if kind == "canton" else "eligibility",
        canton="ag" if kind == "canton" else None,
        publish_at=datetime(2026, 11, 16, 6, 0, tzinfo=UTC),
        plan={},
        english=en,
        translations={
            "de": {"status": "ok", "content": de, "notes": []},
            "tr": {"status": "failed", "content": None, "notes": []},
        },
        live_files={},
        **kw,
    )


def test_files_match_the_contract_frontmatter():
    now = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
    texts, pages = workflow.build_files(make_article(), now)
    assert set(texts) == {"en/married-to-a-swiss-citizen.md", "de/verheiratet-mit-schweizer.md"}
    assert pages == {
        "en": "/en/articles/married-to-a-swiss-citizen/",
        "de": "/de/ratgeber/verheiratet-mit-schweizer/",
    }
    text = texts["en/married-to-a-swiss-citizen.md"]
    assert text.startswith("---\nkey: spouse-facilitated\nkind: article\nlang: en\n")
    fm, body = files.parse_file(text)
    assert list(fm) == [
        "key", "kind", "lang", "slug", "title", "description", "category", "published",
        "updated", "checked", "summary", "sources", "faq", "related", "machine_translated",
    ]  # fmt: skip
    assert fm["published"] == date(2026, 11, 16) and fm["updated"] == date(2026, 11, 16)
    assert fm["checked"] == date(2026, 11, 14)
    assert fm["machine_translated"] is False
    assert fm["sources"][0] == {"title": "SEM: Facilitated naturalisation for spouses (German)",
                                "url": SEM}  # fmt: skip
    assert fm["faq"][0]["q"] == "Do I need to take a test?"
    assert body.startswith("## Who it is for")
    assert "](guide:overview)" in body and "](try:)" in body
    de, _ = files.parse_file(texts["de/verheiratet-mit-schweizer.md"])
    assert de["machine_translated"] is True and de["lang"] == "de" and de["key"] == SPOUSE
    assert re.search(r"^published: 2026-11-16$", text, re.MULTILINE)  # a YAML date, unquoted


def test_canton_guide_has_canton_and_its_segment():
    texts, pages = workflow.build_files(make_article("canton"), datetime(2026, 11, 30, tzinfo=UTC))
    fm, _ = files.parse_file(texts["en/married-to-a-swiss-citizen.md"])
    assert fm["kind"] == "canton" and fm["canton"] == "ag"
    assert list(fm).index("canton") == list(fm).index("category") + 1
    assert pages["de"].startswith("/de/kantone/")


def test_update_keeps_published_and_bumps_updated():
    a = make_article(published_at=datetime(2026, 11, 16, 6, 0, tzinfo=UTC))
    texts, _ = workflow.build_files(a, datetime(2026, 11, 20, 9, 0, tzinfo=UTC))
    fm, _ = files.parse_file(texts["en/married-to-a-swiss-citizen.md"])
    assert fm["published"] == date(2026, 11, 16) and fm["updated"] == date(2026, 11, 20)


def test_atomic_write_and_stale_files_removed(tmp_path):
    previous = {"en": "en/old-slug.md", "fr": "fr/ancien.md"}
    for rel in previous.values():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("old", encoding="utf-8")
    live = files.write_article_files(tmp_path, {"en/new-slug.md": "new"}, previous)
    assert live == {"en": "en/new-slug.md"}
    assert (tmp_path / "en/new-slug.md").read_text(encoding="utf-8") == "new"
    assert not (tmp_path / "en/old-slug.md").exists() and not (tmp_path / "fr/ancien.md").exists()
    assert not list(tmp_path.rglob("*.tmp"))


# --- build status -----------------------------------------------------------------------------------


def test_build_request_and_status(tmp_path):
    now = datetime(2026, 11, 16, 6, 0, 0, 123456, tzinfo=UTC)
    requested = files.request_build(tmp_path, "publish spouse-facilitated", now)
    req = json.loads((tmp_path / ".build-request").read_text(encoding="utf-8"))
    assert req == {"requested_at": requested, "reason": "publish spouse-facilitated"}
    status = tmp_path / "status.json"

    def write(**data):
        status.write_text(json.dumps(data), encoding="utf-8")

    assert not files.read_build_status(status, now).done  # no file yet
    write(ok=True, building=True, requested_at=requested, finished_at=None)
    assert not files.read_build_status(status, now).done  # still building
    older = (now - timedelta(minutes=1)).isoformat()
    write(ok=True, requested_at=older, finished_at=older)
    assert not files.read_build_status(status, now).done  # an earlier build
    write(ok=True, requested_at=requested, finished_at=requested, release="r7", error=None)
    r = files.read_build_status(status, now)
    assert r.done and r.ok and r.release == "r7"
    later = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    write(ok=False, requested_at=later, finished_at=later, error="astro build failed")
    r = files.read_build_status(status, now)
    assert r.done and not r.ok and "astro" in r.error
    status.write_text("{not json", encoding="utf-8")
    assert not files.read_build_status(status, now).done
