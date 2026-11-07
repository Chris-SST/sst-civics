"""Placeholder content without any AI call or network request, for `--dry-run` and for
building the site locally (`scripts/articles.py preview --dry-run`). It passes the contract
checks, so the site can be built from it, and it says plainly that it is a placeholder."""

from __future__ import annotations

from typing import Any

from app.articles.constants import WORDS

_PARA = (
    "This paragraph is placeholder text for a dry run of the article pipeline. It stands in "
    "for the real text, which is written from the sources listed below and checked against "
    "them before anything is published. Rules can differ by canton and commune, so the real "
    "article tells readers to check with their commune or canton."
)


def placeholder(plan: dict[str, Any], *, kind: str) -> dict[str, Any]:
    low = WORDS.get(kind, WORDS["article"])[0]
    words_per_para = len(_PARA.split())
    paras = low // words_per_para + 3
    sections = []
    for i in range(1, 5):
        sections.append(f"## Section {i}")
        sections += [_PARA] * (paras // 4 + 1)
    sections.insert(2, "See the [overview](guide:overview) and the [free practice](try:).")
    body = "\n\n".join(sections)
    title = plan["title"][:90]
    description = (
        f"Placeholder for a dry run: {title}. The real description is written from the sources."
    )[:160]
    if len(description) < 70:
        description = description.ljust(70, ".")
    sources = [{"title": s["title"], "url": s["url"]} for s in plan.get("sources", [])][:12]
    return {
        "title": title,
        "slug": plan["key"],
        "description": description,
        "summary": [
            "This is placeholder text for a dry run.",
            "Nothing in it has been checked yet.",
            "The real article is written from the sources listed below.",
        ],
        "faq": [
            {"q": "Is this the real article?", "a": "No, this is placeholder text for a dry run."},
            {"q": "Where does the real text come from?", "a": "From the sources listed below."},
            {"q": "Is it checked?", "a": "Yes, the real text is checked against its sources."},
        ],
        "sources": sources,
        "related": [k for k in plan.get("related", [])][:4],
        "body": body,
    }
