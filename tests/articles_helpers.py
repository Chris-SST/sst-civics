"""Shared set-up for the article pipeline tests: the fixture plan, a scripted provider whose
replies pass the contract checks, readable sources without network, and a site builder
stand-in that writes the status file."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.articles import research, workflow
from app.articles.plan import import_plan
from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import FakeProvider, set_provider

PLAN = Path(__file__).parent / "fixtures" / "articles" / "plan.yaml"
SPOUSE = "spouse-facilitated"
PUBLISH_AT = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)  # 07:00 Zurich
SEM = "https://www.sem.admin.ch/sem/de/home/integration-einbuergerung/schweizer-werden/verheiratet.html"
FEDLEX = "https://www.fedlex.admin.ch/eli/cc/2016/404/de"
REVIEW_TO = "chris@example.org"

PARA = (
    "If you are married to a Swiss citizen, you may be able to apply for facilitated "
    "naturalisation instead of the ordinary route. The federal rules set the conditions, "
    "and the State Secretariat for Migration decides, after the canton has checked your "
    "file. Rules on documents and fees can differ, so check with your canton before you "
    "send anything. Keep copies of everything you submit and note the dates."
)


def body(words: int = 950) -> str:
    n = len(PARA.split())
    per_section = max(1, words // n // 4 + 1)
    parts = []
    for i, title in enumerate(["Who it is for", "The conditions", "How to apply", "Next steps"]):
        parts.append(f"## {title}")
        parts += [PARA] * per_section
        if i == 0:
            parts.append(
                "See the [overview](guide:overview), the [calculator](guide:calculator) and "
                f"the [SEM page]({SEM})."
            )
        if i == 3:
            parts.append("You can also try the [free questions](try:).")
    return "\n\n".join(parts)


def article(**overrides: Any) -> dict[str, Any]:
    data = {
        "title": "Married to a Swiss citizen? Facilitated naturalisation explained",
        "slug": "married-to-a-swiss-citizen",
        "description": (
            "Who can use facilitated naturalisation after marrying a Swiss citizen, which "
            "years count and how to apply."
        ),
        "summary": [
            "Spouses of Swiss citizens can apply for facilitated naturalisation.",
            "You need five years of residence in total.",
            "The marriage must have lasted three years.",
        ],
        "body": body(),
        "faq": [
            {"q": "Do I need to take a test?", "a": "Usually not at federal level; check."},
            {"q": "Who decides?", "a": "The State Secretariat for Migration decides."},
            {"q": "How long does it take?", "a": "It often takes about a year or more."},
        ],
        "sources": [
            {"title": "SEM: Facilitated naturalisation for spouses (German)", "url": SEM},
            {"title": "Federal Act on Swiss Citizenship (German)", "url": FEDLEX},
        ],
        "related": ["overview", "calculator"],
    }
    data.update(overrides)
    return data


def payload(text: str) -> dict[str, Any]:
    return json.loads(text)


def translate_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    en = p["english"]
    lang = p["lang"]
    return {
        "title": f"[{lang}] {en['title']}"[:90],
        "slug": f"{en['slug']}-{lang}",
        "description": en["description"],
        "summary": list(en["summary"]),
        "body": en["body"],
        "faq": list(en["faq"]),
        "source_titles": list(en["source_titles"]),
    }


def fix_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    current = dict(p["current_version"])
    current.pop("checked", None)
    note = "; ".join(p.get("owner_feedback") or []) or "review findings"
    return {**current, "changes": [f"Applied: {note}"]}


PASS = {"verdict": "pass", "findings": []}
FAIL = {
    "verdict": "fix",
    "findings": [
        {"claim": "five years", "problem": "not in the sources", "severity": "major", "fix": "x"}
    ],
}


def provider(**overrides: Any) -> FakeProvider:
    replies: dict[str, Any] = {
        "articles/write": lambda text: article(),
        "articles/review": dict(PASS),
        "articles/fix": fix_reply,
        "articles/translate": translate_reply,
        "articles/translation_review": dict(PASS),
    }
    replies.update(overrides)
    return FakeProvider(json_replies=replies)


async def fake_sources(plan: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "url": s["url"],
            "title": s["title"],
            "fetched_at": now.isoformat(),
            "ok": True,
            "error": None,
            "text": "Readable page text. " * 40,
        }
        for s in plan["sources"]
    ]


class Builder:
    """Stand-in for the site builder: writes the status file for the latest request."""

    def __init__(self, status_file: Path, articles_dir: Path):
        self.status_file = status_file
        self.articles_dir = articles_dir

    def request(self) -> dict[str, Any]:
        return json.loads((self.articles_dir / ".build-request").read_text(encoding="utf-8"))

    def finish(self, ok: bool = True, error: str | None = None, **extra: Any) -> None:
        req = self.request()
        status = {
            "ok": ok,
            "started_at": req["requested_at"],
            "finished_at": req["requested_at"],
            "release": "r1",
            "requested_at": req["requested_at"],
            "reason": req["reason"],
            "source_rev": "abc",
            "error": error,
            **extra,
        }
        self.status_file.write_text(json.dumps(status), encoding="utf-8")


def pipeline_env(monkeypatch, tmp_path):
    """Generator behind the `pipeline` fixture in conftest.py. Settings for the pipeline, the fixture plan, the scripted provider and no network."""
    s = get_settings()
    articles = tmp_path / "articles"
    status = tmp_path / "site-releases" / "build-status.json"
    status.parent.mkdir(parents=True)
    monkeypatch.setattr(s, "articles_dir", str(articles))
    monkeypatch.setattr(s, "sitebuild_status_file", str(status))
    monkeypatch.setattr(s, "articles_review_to", REVIEW_TO)
    monkeypatch.setattr(s, "articles_enabled", True)
    monkeypatch.setattr(s, "articles_cost_cap_chf", 6.0)
    monkeypatch.setattr(s, "guide_base_url", "https://viapunt.example")
    monkeypatch.setattr("app.articles.plan.plan_path", lambda: PLAN)
    monkeypatch.setattr(research, "fetch_sources", fake_sources)

    async def all_live(urls):
        return {}

    monkeypatch.setattr(workflow, "live_check", all_live)
    fake = provider()
    set_provider(fake)
    yield {"fake": fake, "articles": articles, "builder": Builder(status, articles)}
    set_provider(None)


async def imported():
    async with SessionLocal() as db:
        return await import_plan(db, PLAN)


async def load(key: str = SPOUSE):
    async with SessionLocal() as db:
        return await workflow.get_by_key(db, key)
