"""Deterministic checks of an article version against the contract (section 1), run before
any review and before a file is written. Returns plain-English problems; empty means valid.

`content` is the model's output plus the fields the pipeline fills: title, slug,
description, summary, faq, sources, related and body. Frontmatter dates and fixed fields
are added when the file is written (app/articles/files.py).

The politics kinds (docs/politics-contract.md, D-074) have their own item counts, word
ranges, body structure and allowed source hosts; `validate_politics_frontmatter` repeats the
site's build check of their extra frontmatter fields."""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from app.articles.constants import (
    CANTON_CODES,
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    FAQ_MAX,
    FAQ_MIN,
    GUIDE_KEYS,
    KEY_RE,
    POLITICS_CATEGORY,
    POLITICS_FAQ,
    POLITICS_KINDS,
    POLITICS_SOURCE_HOSTS,
    POLITICS_SOURCES,
    POLITICS_SUMMARY,
    RELATED_MAX,
    ROUNDUP_ITEMS,
    SLUG_MAX,
    SLUG_RE,
    SOURCES_MAX,
    SOURCES_MIN,
    SUMMARY_MAX,
    SUMMARY_MIN,
    TITLE_MAX,
    VOTE_LEVELS,
    VOTE_RESULT_SECTION,
    VOTE_SECTIONS,
    WORDS,
)

LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]*)(?:\s+\"[^\"]*\")?\)")
IMAGE_RE = re.compile(r"!\[")
HTML_RE = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")
H1_RE = re.compile(r"^#\s", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’-]*")
MARKDOWN_IN_TEXT = re.compile(r"\*\*|__|\]\(|^#|`|<[a-z]", re.MULTILINE)
# Boxes the site adds itself: the body must not repeat them (English headings).
SITE_BOXES = re.compile(r"^(in brief|sources?|faqs?|frequently asked questions)\b", re.I)
# Wording rules (CLAUDE.md): no claim of official status, no AI attribution.
BANNED_EN = (
    (re.compile(r"\bofficial(?:ly|s)?\b", re.I), "uses the word 'official'"),
    (re.compile(r"\b(?:generated|written) (?:by|with) (?:an? )?(?:ai\b|artificial)", re.I),
     "AI attribution"),
    (re.compile(r"\bas an ai\b", re.I), "AI attribution"),
    (re.compile(r"\blegal advice\b", re.I), "mentions legal advice"),
)  # fmt: skip
# A round-up item ends with "Source: [title](https://...)" (contract "Body").
SOURCE_LINE_RE = re.compile(r"^\s*\*{0,2}Source:\*{0,2}\s*\[[^\]]+\]\(https://[^)\s]+\)")
COMMUNE_RE = re.compile(r"\bcommune\b", re.I)


def links(body: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in LINK_RE.finditer(body)]


def link_targets(body: str) -> list[str]:
    return sorted(t for _, t in links(body))


def headings(body: str) -> list[str]:
    return [m.group(1) for m in HEADING_RE.finditer(body)]


def section_titles(body: str) -> list[str]:
    """The `##` headings of a body, in order."""
    return [m.group(2).strip() for m in HEADING_RE.finditer(body) if m.group(1) == "##"]


def word_count(body: str) -> int:
    text = LINK_RE.sub(lambda m: m.group(1), body)
    return len(WORD_RE.findall(text))


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def limits(kind: str) -> dict[str, tuple[int, int]]:
    """Item counts per kind: the articles keep theirs, the politics kinds differ."""
    if kind in POLITICS_KINDS:
        return {"summary": POLITICS_SUMMARY, "faq": POLITICS_FAQ, "sources": POLITICS_SOURCES}
    return {
        "summary": (SUMMARY_MIN, SUMMARY_MAX),
        "faq": (FAQ_MIN, FAQ_MAX),
        "sources": (SOURCES_MIN, SOURCES_MAX),
    }


def politics_host(url: str) -> bool:
    """An authority's own page that a politics page may cite (contract "Sources")."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == h or host.endswith("." + h) for h in POLITICS_SOURCE_HOSTS
    )


def check_links(body: str, plan_keys: set[str]) -> list[str]:
    problems = []
    for text, target in links(body):
        if not text.strip():
            problems.append(f"link to {target!r} has no text")
        if target.startswith("https://"):
            continue
        if target.startswith("guide:"):
            if target[6:] not in GUIDE_KEYS:
                problems.append(f"unknown guide page placeholder {target!r}")
        elif target.startswith("article:"):
            if target[8:] not in plan_keys:
                problems.append(f"article placeholder {target!r} is not in the plan")
        elif target != "try:":
            problems.append(
                f"link target {target!r} is not allowed (https://, guide:<key>, article:<key> "
                "or try:)"
            )
    return problems


def check_politics_body(body: str, *, kind: str, has_result: bool) -> list[str]:
    """Structure of the English body of a politics page (contract "Body")."""
    p: list[str] = []
    if kind == "roundup":
        low, high = ROUNDUP_ITEMS
        items = re.split(r"^##\s", body, flags=re.M)[1:]
        if not (low <= len(items) <= high):
            p.append(f"a round-up needs {low}-{high} items, one ## section each (has {len(items)})")
        for i, text in enumerate(items):
            lines = [line for line in text.strip().splitlines() if line.strip()]
            name = lines[0].strip() if lines else "?"
            tail = lines[1:]
            if i == len(items) - 1 and tail and COMMUNE_RE.search(tail[-1]):
                tail = tail[:-1]  # the closing line about the commune's news
            if not tail or not SOURCE_LINE_RE.match(tail[-1]):
                p.append(
                    f"item {name[:50]!r} must end with a line 'Source: [title](https://...)' "
                    "linking its page"
                )
        lines = [line for line in body.strip().splitlines() if line.strip()]
        if not lines or not COMMUNE_RE.search(lines[-1]):
            p.append(
                "a round-up ends with a short line saying that your own commune's news is the "
                "best place for local matters"
            )
    elif kind == "vote":
        wanted = list(VOTE_SECTIONS) + ([VOTE_RESULT_SECTION] if has_result else [])
        titles = section_titles(body)
        if titles != wanted:
            p.append(
                "a vote explainer has exactly these ## sections in this order: "
                + ", ".join(repr(t) for t in wanted)
                + f" (it has {', '.join(repr(t) for t in titles) or 'none'})"
            )
    return p


def validate_article(
    content: dict[str, Any],
    *,
    kind: str,
    lang: str,
    plan_keys: set[str],
    read_urls: set[str],
    has_result: bool = False,
) -> list[str]:
    """Problems of one language version. `read_urls`: the sources that were actually read.
    `has_result`: a vote explainer after the vote, which then needs its Result section."""
    p: list[str] = []
    politics = kind in POLITICS_KINDS
    lim = limits(kind)
    summary_min, summary_max = lim["summary"]
    faq_min, faq_max = lim["faq"]
    sources_min, sources_max = lim["sources"]
    title = content.get("title")
    if not isinstance(title, str) or not (10 <= len(title.strip()) <= TITLE_MAX):
        p.append(f"title must be 10-{TITLE_MAX} characters")
    slug = content.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.match(slug) or len(slug) > SLUG_MAX:
        p.append(f"slug must be ASCII a-z, 0-9 and single hyphens, at most {SLUG_MAX} characters")
    desc = content.get("description")
    if not isinstance(desc, str) or not (DESCRIPTION_MIN <= len(desc.strip()) <= DESCRIPTION_MAX):
        n = len(desc) if isinstance(desc, str) else 0
        p.append(f"description must be {DESCRIPTION_MIN}-{DESCRIPTION_MAX} characters (has {n})")
    summary = content.get("summary")
    if not _strings(summary) or not (summary_min <= len(summary) <= summary_max):
        p.append(f"summary must have {summary_min}-{summary_max} sentences")
    elif any(len(s) > 300 for s in summary):
        p.append("each summary sentence must be short (at most 300 characters)")
    faq = content.get("faq")
    if (
        not isinstance(faq, list)
        or not (faq_min <= len(faq) <= faq_max)
        or not all(
            isinstance(f, dict)
            and isinstance(f.get("q"), str)
            and f["q"].strip()
            and isinstance(f.get("a"), str)
            and f["a"].strip()
            for f in faq
        )
    ):
        p.append(f"faq must have {faq_min}-{faq_max} items with a question and an answer")
    else:
        for f in faq:
            if MARKDOWN_IN_TEXT.search(f["a"]) or MARKDOWN_IN_TEXT.search(f["q"]):
                p.append(f"FAQ item {f['q'][:40]!r} must be plain text without Markdown")
            if len(f["a"]) > 900 or len(f["q"]) > 200:
                p.append(f"FAQ item {f['q'][:40]!r} is too long")
    sources = content.get("sources")
    if (
        not isinstance(sources, list)
        or not (sources_min <= len(sources) <= sources_max)
        or not all(
            isinstance(s, dict)
            and isinstance(s.get("title"), str)
            and isinstance(s.get("url"), str)
            for s in sources
        )
    ):
        p.append(f"sources must list {sources_min}-{sources_max} pages with title and url")
    else:
        urls = [s["url"] for s in sources]
        if len(set(urls)) != len(urls):
            p.append("a source is listed twice")
        for s in sources:
            if not s["title"].strip():
                p.append(f"source {s['url']} has no title")
            if s["url"] not in read_urls:
                p.append(f"source {s['url']} was not read; cite only the pages provided")
            if politics and not politics_host(s["url"]):
                p.append(f"source {s['url']} is not an authority's page this section may cite")
    related = content.get("related")
    if not isinstance(related, list) or len(related) > RELATED_MAX:
        p.append(f"related must list at most {RELATED_MAX} guide page keys")
    else:
        # Politics pages may also relate to articles (a key in the database).
        unknown = [
            k
            for k in related
            if k not in GUIDE_KEYS and not (politics and isinstance(k, str) and k in plan_keys)
        ]
        if unknown:
            p.append(f"related has unknown guide page key(s): {', '.join(map(str, unknown))}")
        if len(set(related)) != len(related):
            p.append("related lists a page twice")
    body = content.get("body")
    if not isinstance(body, str) or not body.strip():
        p.append("body is empty")
        return p
    if H1_RE.search(body):
        p.append("body must not contain an H1 (# heading); sections are ## and ###")
    if HTML_RE.search(body):
        p.append("body must not contain raw HTML")
    if IMAGE_RE.search(body):
        p.append("body must not contain images")
    if "](http://" in body:
        p.append("external links must use https://")
    p += check_links(body, plan_keys)
    if "##" not in headings(body):
        p.append("body needs ## section headings")
    if politics:
        for _, target in links(body):
            if target.startswith("https://") and not politics_host(target):
                p.append(f"link {target} is not an authority's page; link only those")
    if lang == "en":
        if politics:
            p += check_politics_body(body, kind=kind, has_result=has_result)
        for m in HEADING_RE.finditer(body):
            if SITE_BOXES.match(m.group(2)):
                p.append(f"body must not contain the {m.group(2)!r} section; the site adds it")
        low, high = WORDS.get(kind, WORDS["article"])
        n = word_count(body)
        if not (low <= n <= high):
            p.append(f"body has {n} words; it should have {low}-{high}")
        texts = [title or "", desc or "", body]
        texts += summary if isinstance(summary, list) else []
        texts += [f.get("q", "") + " " + f.get("a", "") for f in faq or [] if isinstance(f, dict)]
        texts += [s.get("title", "") for s in sources or [] if isinstance(s, dict)]
        joined = "\n".join(t for t in texts if isinstance(t, str))
        for pattern, label in BANNED_EN:
            m = pattern.search(joined)
            if m:
                p.append(f"wording: {label} ({m.group(0)!r})")
    return p


def validate_translation(
    content: dict[str, Any],
    english: dict[str, Any],
    *,
    kind: str,
    lang: str,
    plan_keys: set[str],
    has_result: bool = False,
) -> list[str]:
    """A translation must pass the contract checks and keep the English structure: the same
    links and placeholders, section count, numbers of summary and FAQ items, and sources."""
    p = validate_article(
        content,
        kind=kind,
        lang=lang,
        plan_keys=plan_keys,
        read_urls={s["url"] for s in english.get("sources", [])},
        has_result=has_result,
    )
    body = content.get("body") or ""
    if link_targets(body) != link_targets(english["body"]):
        p.append("links and placeholders differ from the English version; keep every one")
    if len(headings(body)) != len(headings(english["body"])):
        p.append("the number of section headings differs from the English version")
    for name in ("summary", "faq"):
        if len(content.get(name) or []) != len(english.get(name) or []):
            p.append(f"{name} must have as many items as the English version")
    if [s.get("url") for s in content.get("sources") or []] != [
        s["url"] for s in english.get("sources", [])
    ]:
        p.append("sources must be the English sources in the same order")
    if content.get("related") != english.get("related"):
        p.append("related must be the same as in English")
    return p


# --- Politics frontmatter (the site's build check, docs/politics-contract.md "Files") -------


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _percent(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100


def validate_politics_frontmatter(fm: dict[str, Any]) -> list[str]:
    """The rules the site checks on a politics file, so that a page never breaks the build."""
    p: list[str] = []
    kind = fm.get("kind")
    if kind not in POLITICS_KINDS:
        return [f"kind {kind!r} is not a politics kind"]
    if fm.get("category") != POLITICS_CATEGORY:
        p.append("category must be politics")
    canton = fm.get("canton")
    if canton not in (*CANTON_CODES, "ch"):
        p.append("canton must be a two-letter code (ch for a federal vote)")
    has_period = "period_start" in fm or "period_end" in fm
    has_vote = any(k in fm for k in ("vote_date", "vote_level", "result"))
    if kind == "roundup":
        start, end = _date(fm.get("period_start")), _date(fm.get("period_end"))
        if start is None or end is None:
            p.append("a round-up needs period_start and period_end")
        elif end < start:
            p.append("period_end is before period_start")
    elif has_period:
        p.append("period_start and period_end are only for a round-up")
    if kind == "vote":
        if _date(fm.get("vote_date")) is None:
            p.append("a vote needs vote_date")
        level = fm.get("vote_level")
        if level not in VOTE_LEVELS:
            p.append("vote_level must be cantonal or federal")
        elif level == "federal" and canton != "ch":
            p.append("a federal vote uses canton ch")
        elif level == "cantonal" and canton == "ch":
            p.append("a cantonal vote cannot use canton ch")
        result = fm.get("result")
        if result is not None and not (
            isinstance(result, dict)
            and _percent(result.get("yes_percent"))
            and _percent(result.get("turnout_percent"))
            and isinstance(result.get("accepted"), bool)
        ):
            p.append("result needs yes_percent and turnout_percent (0-100) and accepted")
    elif has_vote:
        p.append("vote_date, vote_level and result are only for a vote")
    for k in fm.get("related") or []:
        if not (isinstance(k, str) and (k in GUIDE_KEYS or KEY_RE.match(k))):
            p.append(f"related key {k!r} is not valid")
    return p
