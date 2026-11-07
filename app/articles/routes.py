"""Chris's review page on the app host: `/api/articles/review/<token>`.

Server-rendered HTML with plain forms and no JavaScript. The signed token in the URL is the
only credential (app/articles/tokens.py), so the path is exempt from the session CSRF check
(app/main.py); instead every POST must carry the article revision shown on the page (so a
stale page never publishes a newer version unseen) and, when the browser sends an Origin
header, it must be the app's own. GET never changes anything, because mail scanners open
links. After an action the page redirects to itself (303) with a short confirmation.

The API container has no ARTICLES_DIR: the page only changes the article's state and asks
the worker to act (immediately when a queue is available, else on its next 15-minute tick)."""

from __future__ import annotations

import html
import logging
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import render, tokens, workflow
from app.articles.emails import translation_lines
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import ART_PRODUCING, ART_PUBLISHED, Article

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles/review", include_in_schema=False)

MAX_FORM_BYTES = 64 * 1024

STATUS_TEXT = {
    "planned": "Planned, not written yet.",
    "researching": "Being written (reading the sources).",
    "drafting": "Being written or revised.",
    "reviewing": "Being fact-checked.",
    "translating": "Being translated.",
    "ready": "Ready; the proposal email goes out shortly.",
    "proposed": "Proposed. It will be published at the time below unless you act.",
    "changes_requested": "Your suggestion is being worked in. A new proposal will follow.",
    "approved": "Approved; publication starts within a few minutes.",
    "publishing": "Being published.",
    "published": "Published.",
    "held": "On hold. Nothing happens until you choose Publish now or suggest a change.",
    "needs_attention": "Stopped: it needs your decision (see below).",
    "publish_failed": "Publishing failed; the live site is unchanged.",
}

DONE_TEXT = {
    "published": "Thank you. Publication starts within a few minutes; you will get an email.",
    "held": "The article is on hold.",
    "suggested": "Thank you. Your suggestion is saved; a revised version will be emailed to you.",
    "stale": "The article changed after you opened this page. Please check this version.",
    "refused": "That action is not possible in the article's current state.",
    "empty": "Please write your suggestion in the box.",
}

CSS = """
body{margin:0;background:#FBF6EE;color:#1F1B2D;font:16px/1.55 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}
.card{background:#fff;border-radius:10px;padding:16px 20px;margin:0 0 16px;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
.note{background:#DCEFEC;border-radius:8px;padding:10px 14px;margin:0 0 16px}
.warn{background:#F8DDD5;color:#7D3220}
button{font:inherit;font-weight:600;border:0;border-radius:6px;padding:9px 16px;cursor:pointer}
.primary{background:#0E6E6B;color:#fff}.hold{background:#F4B740;color:#1F1B2D}
textarea{width:100%;box-sizing:border-box;min-height:140px;font:inherit;padding:8px;
border:1px solid #ccc;border-radius:6px}
form{margin:0 0 12px}.muted{color:#666;font-size:14px}
article h1{font-size:26px;line-height:1.25}table{max-width:100%}
"""


def _page(title: str, inner: str, status: int = 200) -> HTMLResponse:
    doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{inner}</main></body></html>"
    )
    return HTMLResponse(
        doc,
        status_code=status,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


def _not_found() -> HTMLResponse:
    return _page(
        "Link not valid",
        '<div class="card"><h1>This link is not valid</h1><p>It may have been replaced by a '
        "newer email, or the article is no longer open for changes.</p></div>",
        404,
    )


async def _article(db: AsyncSession, token: str) -> Article | None:
    article_id = tokens.parse_token(token)
    if article_id is None:
        return None
    a = await db.get(Article, article_id)
    if a is None or not tokens.verify(token, a):
        return None
    return a


def _closed(a: Article) -> HTMLResponse:
    return _page(
        "Closed",
        '<div class="card"><h1>This article is closed for changes</h1><p>It was published '
        "more than 14 days ago. Changes now go through the normal content routine.</p></div>",
        410,
    )


def _form(token: str, action: str, revision: int, inner: str) -> str:
    return (
        f'<form method="post" action="/api/articles/review/{html.escape(token)}/{action}">'
        f'<input type="hidden" name="revision" value="{revision}">{inner}</form>'
    )


@router.get("/{token}")
async def review_page(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    a = await _article(db, token)
    if a is None:
        return _not_found()
    now = utcnow()
    if tokens.expired(a, now):
        return _closed(a)
    e = html.escape
    focus = request.query_params.get("action", "")
    done = request.query_params.get("done", "")
    content = a.english or {}
    title = content.get("title") or a.plan.get("title") or a.key
    parts = [f'<p class="muted">Viapunt article review &middot; {e(a.key)}</p>']
    if done in DONE_TEXT:
        cls = "note warn" if done in ("stale", "refused", "empty") else "note"
        parts.append(f'<div class="{cls}">{e(DONE_TEXT[done])}</div>')
    status = STATUS_TEXT.get(a.status, a.status)
    info = [f"<p><strong>Status:</strong> {e(status)}</p>"]
    if a.status not in (ART_PUBLISHED, "publishing") and content:
        when = workflow.planned_publication(a, now)
        info.append(
            f"<p><strong>Planned publication:</strong> {e(workflow.zurich_time(when))} "
            "(Zurich time)</p>"
        )
    if a.status == ART_PUBLISHED and a.live_urls:
        info.append(
            "<p><strong>Live:</strong> "
            + ", ".join(
                f'<a href="{e(u, quote=True)}">{e(lang)}</a>' for lang, u in a.live_urls.items()
            )
            + "</p>"
        )
    if a.status == "needs_attention" and a.last_error:
        info.append(f'<p class="note warn">{e(a.last_error)}</p>')
    if a.status == "publish_failed" and a.last_error:
        info.append(f'<p class="note warn">{e(a.last_error[:1500])}</p>')
    if content:
        info.append(
            '<p class="muted">' + "<br>".join(e(line) for line in translation_lines(a)) + "</p>"
        )
    parts.append('<div class="card">' + "".join(info) + "</div>")

    actions = []
    if content and a.status in workflow.CAN_PUBLISH_NOW:
        actions.append(
            _form(
                token,
                "publish",
                a.revision,
                '<button class="primary" type="submit">Publish now</button>',
            )
        )
    if a.status in workflow.CAN_HOLD:
        actions.append(
            _form(token, "hold", a.revision, '<button class="hold" type="submit">Hold</button>')
        )
    if content and a.status in workflow.CAN_SUGGEST:
        label = "Suggest a correction" if a.status == ART_PUBLISHED else "Suggest changes"
        autofocus = " autofocus" if focus == "suggest" else ""
        actions.append(
            _form(
                token,
                "suggest",
                a.revision,
                f'<label for="text"><strong>{label}</strong></label>'
                '<p class="muted">Write what should change, as you would to an editor. The '
                "text is revised, fact-checked and translated again, and the new version is "
                "emailed to you; the 24-hour clock starts again from that email.</p>"
                f'<textarea id="text" name="text" maxlength="8000"{autofocus}></textarea>'
                '<p><button class="primary" type="submit">Send suggestion</button></p>',
            )
        )
    if a.status in ART_PRODUCING:
        actions.append(
            '<p class="muted">A new version is being prepared; you can still add a '
            "suggestion and it will be worked in next.</p>"
        )
    if actions:
        hint = {
            "publish": "You chose Publish now. Confirm with the button below.",
            "hold": "You chose Hold. Confirm with the button below.",
        }.get(focus)
        parts.append(
            '<div class="card">'
            + (f'<p class="note">{e(hint)}</p>' if hint else "")
            + "".join(actions)
            + "</div>"
        )
    if content:
        parts.append(f'<div class="card"><article>{render.article_html(content)}</article></div>')
    return _page(f"Review: {title}", "".join(parts))


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        return origin is None
    app = urlsplit(get_settings().app_base_url)
    mine = f"{app.scheme}://{app.netloc}"
    return origin.rstrip("/") == mine or origin == f"{request.url.scheme}://{request.url.netloc}"


async def _form_data(request: Request) -> dict[str, str]:
    raw = await request.body()
    if len(raw) > MAX_FORM_BYTES:
        return {}
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {k: v[0] for k, v in parsed.items() if v}


def _back(token: str, done: str) -> RedirectResponse:
    return RedirectResponse(f"/api/articles/review/{token}?done={done}", status_code=303)


async def _kick(job: str, key: str) -> None:
    """Ask the worker to act now instead of on its next tick. Best effort."""
    if get_settings().jobs_inline:
        return
    try:
        from app.jobs import _get_pool

        pool = await _get_pool()
        await pool.enqueue_job(job, key, _job_id=f"{job}:{key}")
    except Exception as exc:  # noqa: BLE001  the tick does it anyway
        log.warning("Could not queue %s for an article: %s", job, exc.__class__.__name__)


@router.post("/{token}/{action}")
async def review_action(
    token: str, action: str, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    a = await _article(db, token)
    if a is None or action not in ("publish", "hold", "suggest"):
        return _not_found()
    if not _origin_ok(request):
        return _page("Not allowed", '<div class="card"><p>Request refused.</p></div>', 403)
    now = utcnow()
    if tokens.expired(a, now):
        return _closed(a)
    form = await _form_data(request)
    if form.get("revision") != str(a.revision):
        return _back(token, "stale")
    try:
        if action == "publish":
            await workflow.publish_now(db, a, now)
            log.info("Article %s: Publish now from the review page", a.key)
            await _kick("publish_article", a.key)
            return _back(token, "published")
        if action == "hold":
            await workflow.hold(db, a)
            log.info("Article %s: held from the review page", a.key)
            return _back(token, "held")
        text = form.get("text", "")
        if not text.strip():
            return _back(token, "empty")
        await workflow.suggest_changes(db, a, text, now)
        log.info("Article %s: suggestion received from the review page", a.key)
        if a.status not in ART_PRODUCING:
            await _kick("produce_article", a.key)
        return _back(token, "suggested")
    except workflow.ActionRefused:
        return _back(token, "refused")
