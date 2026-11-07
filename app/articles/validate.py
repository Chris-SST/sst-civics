"""Deterministic checks of an article version against the contract (section 1), run before
any review and before a file is written. Returns plain-English problems; empty means valid.

`content` is the model's output plus the fields the pipeline fills: title, slug,
description, summary, faq, sources, related and body. Frontmatter dates and fixed fields
are added when the file is written (app/articles/files.py)."""

from __future__ import annotations

import re
from typing import Any

from app.articles.constants import (
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    FAQ_MAX,
    FAQ_MIN,
    GUIDE_KEYS,
    RELATED_MAX,
    SLUG_MAX,
    SLUG_RE,
    SOURCES_MAX,
    SOURCES_MIN,
    SUMMARY_MAX,
    SUMMARY_MIN,
    TITLE_MAX,
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


def links(body: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in LINK_RE.finditer(body)]


def link_targets(body: str) -> list[str]:
    return sorted(t for _, t in links(body))


def headings(body: str) -> list[str]:
    return [m.group(1) for m in HEADING_RE.finditer(body)]


def word_count(body: str) -> int:
    text = LINK_RE.sub(lambda m: m.group(1), body)
    return len(WORD_RE.findall(text))


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


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


def validate_article(
    content: dict[str, Any],
    *,
    kind: str,
    lang: str,
    plan_keys: set[str],
    read_urls: set[str],
) -> list[str]:
    """Problems of one language version. `read_urls`: the sources that were actually read."""
    p: list[str] = []
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
    if not _strings(summary) or not (SUMMARY_MIN <= len(summary) <= SUMMARY_MAX):
        p.append(f"summary must have {SUMMARY_MIN}-{SUMMARY_MAX} sentences")
    elif any(len(s) > 300 for s in summary):
        p.append("each summary sentence must be short (at most 300 characters)")
    faq = content.get("faq")
    if (
        not isinstance(faq, list)
        or not (FAQ_MIN <= len(faq) <= FAQ_MAX)
        or not all(
            isinstance(f, dict)
            and isinstance(f.get("q"), str)
            and f["q"].strip()
            and isinstance(f.get("a"), str)
            and f["a"].strip()
            for f in faq
        )
    ):
        p.append(f"faq must have {FAQ_MIN}-{FAQ_MAX} items with a question and an answer")
    else:
        for f in faq:
            if MARKDOWN_IN_TEXT.search(f["a"]) or MARKDOWN_IN_TEXT.search(f["q"]):
                p.append(f"FAQ item {f['q'][:40]!r} must be plain text without Markdown")
            if len(f["a"]) > 900 or len(f["q"]) > 200:
                p.append(f"FAQ item {f['q'][:40]!r} is too long")
    sources = content.get("sources")
    if (
        not isinstance(sources, list)
        or not (SOURCES_MIN <= len(sources) <= SOURCES_MAX)
        or not all(
            isinstance(s, dict)
            and isinstance(s.get("title"), str)
            and isinstance(s.get("url"), str)
            for s in sources
        )
    ):
        p.append(f"sources must list {SOURCES_MIN}-{SOURCES_MAX} pages with title and url")
    else:
        urls = [s["url"] for s in sources]
        if len(set(urls)) != len(urls):
            p.append("a source is listed twice")
        for s in sources:
            if not s["title"].strip():
                p.append(f"source {s['url']} has no title")
            if s["url"] not in read_urls:
                p.append(f"source {s['url']} was not read; cite only the pages provided")
    related = content.get("related")
    if not isinstance(related, list) or len(related) > RELATED_MAX:
        p.append(f"related must list at most {RELATED_MAX} guide page keys")
    else:
        unknown = [k for k in related if k not in GUIDE_KEYS]
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
    if lang == "en":
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
    content: dict[str, Any], english: dict[str, Any], *, kind: str, lang: str, plan_keys: set[str]
) -> list[str]:
    """A translation must pass the contract checks and keep the English structure: the same
    links and placeholders, section count, numbers of summary and FAQ items, and sources."""
    p = validate_article(
        content,
        kind=kind,
        lang=lang,
        plan_keys=plan_keys,
        read_urls={s["url"] for s in english.get("sources", [])},
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
