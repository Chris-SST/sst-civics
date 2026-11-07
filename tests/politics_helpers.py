"""Shared set-up for the politics tests (D-074): scripted replies for every politics prompt
that pass the contract checks, item pages without network, and the stored items of a week."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.content import fetch
from app.db import SessionLocal
from app.models import PoliticsItem
from app.politics import discover, schedule

FIXTURES = Path(__file__).parent / "fixtures" / "politics"
# Friday 13 November 2026, 07:00 Zurich (06:00 UTC): the round-up of week 46.
FRIDAY = datetime(2026, 11, 13, 6, 5, tzinfo=UTC)
WEEK = (date(2026, 11, 6), date(2026, 11, 12))
ITEM_URLS = [
    f"https://www.zh.ch/de/news-uebersicht/medienmitteilungen/2026/11/item-{i}.html"
    for i in range(1, 7)
]

PARA = (
    "The cantonal government decided on the matter at its weekly meeting and sent the bill "
    "to the cantonal parliament, which will debate it next year. The press release gives "
    "the figures and the next steps, and it says when the change is planned to come into "
    "force. Both the government and the committee published their positions."
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def payload(text: str) -> dict[str, Any]:
    return json.loads(text)


def roundup_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    urls = [s["url"] for s in p["sources"]]
    parts = []
    for i, url in enumerate(urls, 1):
        parts += [f"## Decision number {i} of the cantonal government", PARA, PARA, PARA]
        parts.append(f"Source: [Canton of Zurich: item {i}]({url})")
    parts.append("For local matters, your own commune's news is the best place to look.")
    return {
        "title": "Canton of Zurich: politics in the week to 12 November 2026",
        "slug": "canton-of-zurich-week-46-2026",
        "description": (
            "What the government and the parliament of the canton of Zurich decided in the "
            "week to 12 November 2026."
        ),
        "summary": [f"The government took decision {i}." for i in range(1, len(urls) + 1)],
        "body": "\n\n".join(parts),
        "faq": [],
        "sources": [
            {"title": f"Canton of Zurich: item {i}", "url": u} for i, u in enumerate(urls, 1)
        ],
        "related": ["topicZurich"],
    }


def vote_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    sections = p["page"]["sections"]
    parts = []
    for name in sections:
        parts += [f"## {name}", PARA, PARA]
    url = p["sources"][0]["url"]
    parts.append(f"Read the [proposal page]({url}).")
    return {
        "title": "Vote on 28 February 2027: Glattalbahn extension explained",
        "slug": "vote-28-february-2027-glattalbahn-extension",
        "description": (
            "What the cantonal vote on the Glattalbahn extension to Kloten is about and what "
            "each side says."
        ),
        "summary": [
            "Voters decide on a tram extension.",
            "There was a referendum.",
            "Both sides argue.",
        ],
        "body": "\n\n".join(parts),
        "faq": [{"q": "Who can vote?", "a": "Swiss citizens living in the canton."}],
        "sources": [{"title": "Canton of Zurich: vote announcement (German)", "url": url}],
        "related": ["topicDemocracy"],
    }


def whoswho_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    urls = [s["url"] for s in p["sources"]][:3]
    body = "\n\n".join(
        [
            "## The cantonal government (Regierungsrat)",
            PARA,
            PARA,
            "## The cantonal parliament (Kantonsrat)",
            PARA,
            PARA,
            "## The city of Zurich",
            PARA,
            "## Winterthur",
            PARA,
        ]
    )
    return {
        "title": "Who's who in the canton of Zurich",
        "slug": "whos-who-canton-of-zurich",
        "description": (
            "The members of the government of the canton of Zurich, the parties in its "
            "parliament and the city executives."
        ),
        "summary": ["Seven members.", "180 seats.", "Two cities."],
        "body": body,
        "faq": [],
        "sources": [{"title": f"Page {i}", "url": u} for i, u in enumerate(urls, 1)],
        "related": [],
    }


def select_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    return {
        "items": [{"url": c["url"], "why": "decision"} for c in p["candidates"][:4]],
        "quiet_week": False,
    }


QUESTIONS = {
    "questions": [
        {
            "question_de": f"Welche Behörde fasste im November 2026 den Beschluss Nummer {i}?",
            "options_de": {
                "a": "Der Regierungsrat",
                "b": "Der Bundesrat",
                "c": "Der Stadtrat",
                "d": "Das Bezirksgericht",
            },  # fmt: skip
            "correct": "a",
            "explanation_de": "Der Regierungsrat hat entschieden.",
            "page_fact": "The cantonal government decided.",
        }
        for i in (1, 2, 3)
    ]
}


def check_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    checks = []
    for q in p["questions"]:
        wrong = q["n"] == 3  # the checker disagrees on the third: it must be dropped
        checks.append(
            {
                "n": q["n"],
                "answer": "b" if wrong else "a",
                "answerable_from_page": True,
                "single_correct": True,
                "neutral": True,
                "problem": "",
            }
        )
    assert "correct" not in json.dumps(p)  # the checker never sees the key
    return {"checks": checks}


def translate_questions_reply(text: str) -> dict[str, Any]:
    p = payload(text)
    out = []
    for q in p["questions"]:
        t = {
            "question": f"Which authority took decision {q['n']}?",
            "options": {
                "a": "The Regierungsrat",
                "b": "The Federal Council",
                "c": "The Stadtrat",
                "d": "The district court",
            },  # fmt: skip
            "explanation": "The cantonal government decided.",
        }
        out.append(
            {"n": q["n"], **{lang: t for lang in ("en", "fr", "it", "pt", "es", "sq", "tr")}}
        )
    return {"translations": out}


ROSTER = {
    "regierungsrat": [
        {"name": "Carmen Walker Späh", "office": "Volkswirtschaftsdirektion", "party": "FDP"}
    ],
    "president": "Carmen Walker Späh",
    "kantonsrat_groups": ["SVP", "SP"],
    "zurich_executive": [{"name": "Raphael Golta", "office": "Stadtpräsident", "party": "SP"}],
    "winterthur_executive": [
        {"name": "Stefan Fritschi", "office": "Stadtpräsident", "party": "FDP"}
    ],
}
PASS = {"verdict": "pass", "findings": []}
BLOCKER = {
    "verdict": "fix",
    "findings": [
        {
            "claim": "a welcome step",
            "problem": "judges the decision",
            "severity": "blocker",
            "fix": "Report it without judgement.",
        }  # fmt: skip
    ],
}


def replies() -> dict[str, Any]:
    from tests.articles_helpers import fix_reply

    return {
        "politics/select": select_reply,
        "politics/write_roundup": roundup_reply,
        "politics/write_vote": vote_reply,
        "politics/write_whoswho": whoswho_reply,
        "politics/fix": fix_reply,
        "politics/neutrality_review": dict(PASS),
        "politics/fact_review": dict(PASS),
        "politics/questions": QUESTIONS,
        "politics/question_check": check_reply,
        "politics/question_translate": translate_questions_reply,
        "politics/roster": ROSTER,
        "politics/proposals": {
            "vote_date": "2027-02-28",
            "proposals": [
                {"title_de": "Glattalbahnverlängerung Kloten", "short_name": "Glattalbahn Kloten"}
            ],
        },
        "politics/results": {"results": []},
        "politics/links": {"items": []},
    }


async def fake_fetch_page(client, url: str, max_bytes: int = 0) -> fetch.Page:
    text = f"Medienmitteilung zu {url}. " + "Der Regierungsrat hat beschlossen. " * 20
    return fetch.Page(url, True, 200, text=text)


async def fake_discover(db, cs, now, *, use_ai: bool = True):
    return discover.DiscoveryReport(cs.canton)


PEOPLE = [
    "https://www.zh.ch/de/regierungsrat.html",
    "https://www.kantonsrat.zh.ch/mitglieder/",
    "https://www.stadt-zuerich.ch/de/politik-und-verwaltung/behoerden-und-organe/stadtrat.html",
    "https://stadt.winterthur.ch/organisation/politik/stadtrat",
]


def people_reader(seats: dict[str, int] | None = None):
    async def read(cs, now):
        from app.politics.produce import source_record

        pages = [
            source_record(u, f"Page {u}", "Mitglieder und Parteien. " * 20, now) for u in PEOPLE
        ]
        return pages, dict(seats or {"SVP": 43, "SP": 35})

    return read


async def add_week_items(n: int = 6, day: date = date(2026, 11, 10)) -> None:
    async with SessionLocal() as db:
        for i, url in enumerate(ITEM_URLS[:n]):
            db.add(
                PoliticsItem(
                    canton="zh",
                    source_id="zh-regierungsrat",
                    source_type="listing",
                    level="canton",
                    url=url,
                    title=f"Regierungsrat beschliesst Vorlage {i}",
                    item_date=day,
                    data={},
                )
            )
        await db.commit()


def politics_env(monkeypatch, pipeline):
    """Behind the `politics` fixture: the article pipeline set-up plus the politics replies,
    item pages without network, no discovery requests and fixed people pages."""
    pipeline["fake"].json_replies.update(replies())
    monkeypatch.setattr(fetch, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(discover, "discover", fake_discover)
    monkeypatch.setattr(schedule, "read_people", people_reader())
    # The who's-who check runs on the first tick; only its own test switches it on.
    monkeypatch.setattr(schedule, "whoswho_due", lambda now, last: False)
    return pipeline
