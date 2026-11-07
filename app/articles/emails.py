"""Emails to Chris about articles: the proposal (full English text and three signed links),
needs attention, publication failed and published. Plain text and HTML. They go to
ARTICLES_REVIEW_TO, else to the digest recipients (DIGEST_TO, else every active admin).

They contain article text, titles, URLs and figures only. A failed send is logged and
reported to the caller; the proposal is then retried on the next tick."""

from __future__ import annotations

import html
import logging
import smtplib
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import render, research, tokens
from app.articles.constants import LANGUAGE_NAMES
from app.config import get_settings
from app.email import backend
from app.email.backend import OutgoingEmail
from app.models import Article

log = logging.getLogger(__name__)

WRAP = (
    '<div style="font-family:system-ui,sans-serif;color:#1F1B2D;max-width:680px;line-height:1.5">'
)
BUTTON = (
    'style="display:inline-block;padding:9px 16px;margin:0 8px 8px 0;border-radius:6px;'
    'text-decoration:none;font-weight:600;{}"'
)


async def recipients(db: AsyncSession) -> list[str]:
    configured = [a.strip() for a in get_settings().articles_review_to.split(",") if a.strip()]
    if configured:
        return configured
    from app.ops.digest import recipients as digest_recipients

    return await digest_recipients(db)


def send_all(msgs: list[OutgoingEmail]) -> bool:
    try:
        for m in msgs:
            backend.send(m)
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("Article email failed: %s", exc.__class__.__name__)
        return False
    return True


def translation_lines(a: Article) -> list[str]:
    lines = []
    for lang in get_settings().article_languages:
        t = (a.translations or {}).get(lang)
        name = LANGUAGE_NAMES[lang]
        if not t:
            lines.append(f"{name}: not translated")
        elif t.get("status") == "ok":
            lines.append(f"{name}: translated and reviewed")
        else:
            last = next(
                (
                    n
                    for n in reversed(t.get("notes") or [])
                    if n.get("findings") or n.get("problems")
                ),
                {},
            )
            why = "; ".join(
                [f.get("problem", "") for f in last.get("findings") or []][:2]
                + list(last.get("problems") or [])[:2]
            ) or next((n.get("error") for n in t.get("notes") or [] if n.get("error")), "")
            lines.append(f"{name}: skipped, the review did not pass ({why[:240]})")
    return lines


def latest_review(a: Article) -> dict[str, Any] | None:
    rev = a.revision
    return next(
        (
            r
            for r in reversed(a.reviews or [])
            if r.get("kind") == "fact_review" and r.get("revision") == rev
        ),
        None,
    )


def latest_changes(a: Article) -> list[str]:
    return [
        c
        for r in a.reviews or []
        if r.get("kind") == "fix" and r.get("revision") == a.revision
        for c in r.get("changes") or []
    ]


def applied_feedback(a: Article) -> list[str]:
    return [f["text"] for f in a.feedback or [] if f.get("applied_revision") == a.revision]


def _button(url: str, label: str, colours: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}" {BUTTON.format(colours)}>{label}</a>'


async def proposal_emails(db: AsyncSession, a: Article, now: datetime) -> list[OutgoingEmail]:
    from app.articles.workflow import planned_publication, zurich_time

    content = a.english or {}
    when = planned_publication(a, now)
    when_text = zurich_time(when)
    publish_url = tokens.review_url(a, "publish")
    hold_url = tokens.review_url(a, "hold")
    suggest_url = tokens.review_url(a, "suggest")
    is_update = a.published_at is not None
    review = latest_review(a)
    minor = [f for f in (review or {}).get("findings") or [] if f.get("severity") == "minor"]
    changes = latest_changes(a)
    asked = applied_feedback(a)
    langs = translation_lines(a)
    read = research.public_list(a.sources_read or [])

    if is_update:
        intro = (
            f"This corrected version will replace the live article on {when_text} "
            "(Zurich time) unless you act."
        )
    else:
        intro = (
            f"This article will be published on {when_text} (Zurich time) unless you act. "
            "If you do nothing, it goes out as it is."
        )
    subject = (
        f"Viapunt {'correction' if is_update else 'article'} for {when_text}: "
        f"{content.get('title', a.key)}"
    )
    text: list[str] = [intro, ""]
    text += [f"Publish now: {publish_url}", f"Hold: {hold_url}", f"Suggest changes: {suggest_url}"]
    text.append("")
    if asked:
        text += ["Your suggestions in this version:"] + [f"- {t}" for t in asked] + [""]
    if changes:
        text += ["What changed:"] + [f"- {c}" for c in changes] + [""]
    text.append(
        "Fact check: passed against the sources"
        + (f", with {len(minor)} minor note(s):" if minor else ".")
    )
    text += [f"- {f.get('claim', '')}: {f.get('problem', '')}" for f in minor]
    text += ["", "Translations (published without human review, as agreed):"]
    text += [f"- {line}" for line in langs] or ["- none configured"]
    text += ["", "Sources read:"]
    text += [f"- {'read' if s['ok'] else 'NOT READ'}: {s['title']} ({s['url']})" for s in read]
    text += ["", f"Cost of this article so far: CHF {a.cost_chf:.2f}", "", "-" * 60, ""]
    text.append(render.article_text(content))

    e = html.escape
    parts = [f"<p>{e(intro)}</p>"]
    parts.append(
        "<p>"
        + _button(publish_url, "Publish now", "background:#0E6E6B;color:#fff")
        + _button(hold_url, "Hold", "background:#F4B740;color:#1F1B2D")
        + _button(suggest_url, "Suggest changes", "background:#DCEFEC;color:#0E3F3D")
        + "</p>"
    )
    if asked:
        parts.append(
            "<p><strong>Your suggestions in this version</strong></p><ul>"
            + "".join(f"<li>{e(t)}</li>" for t in asked)
            + "</ul>"
        )
    if changes:
        parts.append(
            "<p><strong>What changed</strong></p><ul>"
            + "".join(f"<li>{e(c)}</li>" for c in changes)
            + "</ul>"
        )
    notes = "".join(f"<li>{e(f.get('claim', ''))}: {e(f.get('problem', ''))}</li>" for f in minor)
    parts.append(
        "<p><strong>Fact check:</strong> passed against the sources"
        + (f", with {len(minor)} minor note(s):</p><ul>{notes}</ul>" if minor else ".</p>")
    )
    parts.append(
        "<p><strong>Translations</strong> (published without human review, as agreed)</p><ul>"
        + "".join(f"<li>{e(line)}</li>" for line in langs)
        + "</ul>"
    )
    parts.append(
        "<p><strong>Sources read</strong></p><ul>"
        + "".join(
            f"<li>{'' if s['ok'] else '<strong>NOT READ</strong> '}"
            f'<a href="{e(s["url"], quote=True)}">{e(s["title"])}</a></li>'
            for s in read
        )
        + "</ul>"
    )
    parts.append(f'<p style="color:#666">Cost of this article so far: CHF {a.cost_chf:.2f}</p>')
    parts.append('<hr style="border:none;border-top:1px solid #ddd;margin:20px 0">')
    parts.append(render.article_html(content))
    body = WRAP + "".join(parts) + "</div>"
    return [
        OutgoingEmail(to=to, subject=subject[:200], text="\n".join(text), html=body)
        for to in await recipients(db)
    ]


async def _simple(
    db: AsyncSession, subject: str, lines: list[str], links: list[tuple[str, str]]
) -> None:
    text = "\n".join(lines + [""] + [f"{label}: {url}" for label, url in links])
    e = html.escape
    body = (
        WRAP
        + "".join(f"<p>{e(line)}</p>" if line else "" for line in lines)
        + "<ul>"
        + "".join(f'<li><a href="{e(u, quote=True)}">{e(label)}</a></li>' for label, u in links)
        + "</ul></div>"
    )
    msgs = [
        OutgoingEmail(to=to, subject=subject[:200], text=text, html=body)
        for to in await recipients(db)
    ]
    send_all(msgs)


def _title(a: Article) -> str:
    return (a.english or {}).get("title") or a.plan.get("title") or a.key


async def send_needs_attention(
    db: AsyncSession, a: Article, reason: str, findings: list[dict[str, Any]], now: datetime
) -> None:
    lines = [
        f"The article “{_title(a)}” ({a.key}) has stopped and needs you: {reason}.",
        "Nothing will be published until you act. "
        + (
            "On the review page you can read the last version, suggest changes (the text is "
            "then revised and checked again) or publish it anyway."
            if a.english
            else "There is no usable text yet; the plan entry or its sources need a look "
            f"(then: python -m scripts.articles produce {a.key} --force)."
        ),
    ]
    lines += [
        f"- {f.get('severity', '')}: {f.get('claim', '')}: {f.get('problem', '')}"
        for f in findings[:8]
    ]
    links = [("Open the review page", tokens.review_url(a))] if a.english else []
    await _simple(db, f"Viapunt article needs attention: {_title(a)}", lines, links)


async def send_publish_failed(db: AsyncSession, a: Article, reason: str, now: datetime) -> None:
    lines = [
        f"Publishing “{_title(a)}” ({a.key}) failed. The live site is unchanged.",
        reason[:3000],
        "Use Publish now on the review page to try again once the cause is fixed, or run "
        f"python -m scripts.articles publish {a.key} in the worker.",
    ]
    await _simple(
        db,
        f"Viapunt article not published: {_title(a)}",
        lines,
        [("Open the review page", tokens.review_url(a))],
    )


async def send_published(
    db: AsyncSession, a: Article, now: datetime, *, update: bool, indexnow: bool
) -> None:
    skipped = [
        LANGUAGE_NAMES[lang]
        for lang, t in (a.translations or {}).items()
        if t.get("status") != "ok"
    ]
    lines = [
        f"“{_title(a)}” is {'updated' if update else 'live'} in {len(a.live_urls)} "
        f"language(s) and answers on every address below.",
        f"Not published in: {', '.join(skipped)}." if skipped else "",
        "Search engines were notified through IndexNow." if indexnow else "",
        "To correct it in the next 14 days, use Suggest changes on the review page.",
    ]
    links = [(LANGUAGE_NAMES[lang], url) for lang, url in a.live_urls.items()]
    links.append(("Review page (corrections)", tokens.review_url(a)))
    await _simple(
        db, f"Viapunt article {'updated' if update else 'published'}: {_title(a)}", lines, links
    )
