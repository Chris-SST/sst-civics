"""The politics file format (docs/politics-contract.md "Files" and "Body"): item counts,
word ranges, body structure, allowed source hosts and the extra frontmatter fields, checked
the way the site's build checks them."""

from __future__ import annotations

import json
from datetime import date

from app.articles.validate import validate_article, validate_politics_frontmatter
from tests.politics_helpers import ITEM_URLS, roundup_reply, vote_reply


def _roundup(n: int = 4) -> dict:
    sources = [{"url": u} for u in ITEM_URLS[:n]]
    return roundup_reply(json.dumps({"sources": sources}))


def _vote(result: bool = False) -> dict:
    sections = [
        "What it is about", "What would change", "Arguments in favour", "Arguments against",
        "Who recommends what",
    ] + (["Result"] if result else [])  # fmt: skip
    return vote_reply(
        json.dumps({"page": {"sections": sections}, "sources": [{"url": ITEM_URLS[0]}]})
    )


def problems(content: dict, kind: str, **kw) -> list[str]:
    urls = {s["url"] for s in content["sources"]}
    return validate_article(content, kind=kind, lang="en", plan_keys=set(), read_urls=urls, **kw)


def test_valid_roundup_and_vote():
    assert problems(_roundup(), "roundup") == []
    assert problems(_vote(), "vote") == []
    assert problems(_vote(result=True), "vote", has_result=True) == []


def test_roundup_rules():
    assert any("4-6 items" in p for p in problems(_roundup(3), "roundup"))
    c = _roundup()
    c["body"] = c["body"].replace("Source: [Canton of Zurich: item 2]", "See: [x]", 1)
    assert any("must end with a line 'Source:" in p for p in problems(c, "roundup"))
    c = _roundup()
    c["body"] = c["body"].rsplit("\n\n", 1)[0]  # no closing line about the commune
    assert any("commune" in p for p in problems(c, "roundup"))


def test_vote_sections_and_result():
    assert any("exactly these ## sections" in p for p in problems(_vote(), "vote", has_result=True))
    c = _vote()
    c["body"] = c["body"].replace("## Arguments against", "## Criticism")
    assert any("exactly these ## sections" in p for p in problems(c, "vote"))


def test_counts_differ_from_articles():
    c = _roundup()
    c["summary"] = [f"Sentence {i}." for i in range(6)]
    c["faq"] = []
    assert problems(c, "roundup") == []
    c["summary"] = [f"Sentence {i}." for i in range(7)]
    assert any("3-6" in p for p in problems(c, "roundup"))


def test_sources_only_from_the_authorities():
    c = _vote()
    c["sources"].append({"title": "A newspaper", "url": "https://www.nzz.ch/zuerich/x"})
    c["body"] += "\n\nSee [the paper](https://www.nzz.ch/zuerich/x)."
    found = problems(c, "vote")
    assert any("not an authority's page this section may cite" in p for p in found)
    assert any("link https://www.nzz.ch" in p for p in found)


def test_related_may_hold_article_keys():
    c = _vote()
    c["related"] = ["topicDemocracy", "dual-citizenship"]
    urls = {s["url"] for s in c["sources"]}
    assert (
        validate_article(c, kind="vote", lang="en", plan_keys={"dual-citizenship"}, read_urls=urls)
        == []
    )


def fm(**over) -> dict:
    base = {"key": "k", "kind": "vote", "category": "politics", "canton": "zh",
            "vote_date": date(2027, 2, 28), "vote_level": "cantonal", "related": []}  # fmt: skip
    base.update(over)
    return {k: v for k, v in base.items() if v is not None}


def test_politics_frontmatter_like_the_site():
    assert validate_politics_frontmatter(fm()) == []
    assert validate_politics_frontmatter(fm(category="cantons"))
    assert validate_politics_frontmatter(fm(vote_level="federal"))  # federal needs ch
    assert validate_politics_frontmatter(fm(vote_level="federal", canton="ch")) == []
    assert validate_politics_frontmatter(fm(canton="ch"))  # cantonal forbids ch
    assert validate_politics_frontmatter(fm(vote_date=None))
    assert validate_politics_frontmatter(fm(period_start=date(2026, 11, 6)))
    good = {"yes_percent": 54.2, "turnout_percent": 41.7, "accepted": True}
    assert validate_politics_frontmatter(fm(result=good)) == []
    assert validate_politics_frontmatter(fm(result={**good, "yes_percent": 140}))
    assert validate_politics_frontmatter(fm(result={**good, "accepted": "yes"}))
    roundup = fm(kind="roundup", vote_date=None, vote_level=None,
                 period_start=date(2026, 11, 6), period_end=date(2026, 11, 12))  # fmt: skip
    assert validate_politics_frontmatter(roundup) == []
    assert validate_politics_frontmatter({**roundup, "period_end": date(2026, 11, 1)})
    assert validate_politics_frontmatter({**roundup, "vote_level": "cantonal"})
    assert validate_politics_frontmatter({**roundup, "related": ["Bad Key"]})
    assert validate_politics_frontmatter({**roundup, "related": ["topicZurich", "x-y"]}) == []
