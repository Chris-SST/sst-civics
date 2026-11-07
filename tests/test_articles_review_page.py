"""Chris's review page (D-073): signed links, the three actions as plain forms, the stale
page guard, the Origin check, the CSRF exemption and the 14-day window after publication."""

from __future__ import annotations

from datetime import timedelta

from app.articles import tokens, workflow
from app.db import SessionLocal, utcnow
from app.models import (
    ART_APPROVED,
    ART_CHANGES_REQUESTED,
    ART_HELD,
    ART_PROPOSED,
    ART_PUBLISHED,
)
from tests.articles_helpers import (
    PUBLISH_AT,
    SPOUSE,
    imported,
    load,
)
from tests.conftest import learner_logged_in

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


async def proposed():
    await imported()
    async with SessionLocal() as db:
        a = await workflow.get_by_key(db, SPOUSE)
        await workflow.run_production(db, a, PUBLISH_AT - timedelta(days=4))
        await workflow.propose(db, a, PUBLISH_AT - timedelta(hours=24))
    a = await load()
    assert a.status == ART_PROPOSED
    return a, tokens.make_token(a)


def path(token: str, action: str = "") -> str:
    return f"/api/articles/review/{token}" + (f"/{action}" if action else "")


async def post(api, token, action, revision, text=None, headers=None):
    body = f"revision={revision}" + (f"&text={text}" if text is not None else "")
    return await api.client.post(
        path(token, action), content=body, headers={**FORM, **(headers or {})}
    )


async def test_page_shows_the_article_and_three_actions(pipeline, api):
    a, token = await proposed()
    r = await api.get(path(token) + "?action=suggest")
    assert r.status_code == 200
    page = r.text
    assert "Married to a Swiss citizen?" in page and "<h2>Who it is for</h2>" in page
    assert f'action="/api/articles/review/{token}/publish"' in page
    assert f'action="/api/articles/review/{token}/hold"' in page
    assert f'action="/api/articles/review/{token}/suggest"' in page
    assert "<script" not in page and "textarea" in page and "autofocus" in page
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "noindex" in r.headers["x-robots-tag"]
    # GET never acts, even with ?action=publish (mail scanners open links).
    await api.get(path(token) + "?action=publish")
    assert (await load()).status == ART_PROPOSED


async def test_bad_or_tampered_tokens_get_404(pipeline, api):
    a, token = await proposed()
    assert (await api.get(path("nonsense"))).status_code == 404
    assert (await api.get(path(token[:-2] + "xx"))).status_code == 404
    other = a.id.hex.replace(a.id.hex[0], "f" if a.id.hex[0] != "f" else "e", 1)
    assert (await api.get(path(other + token[32:]))).status_code == 404
    # A new nonce revokes the old link.
    async with SessionLocal() as db:
        row = await workflow.get_by_key(db, SPOUSE)
        row.review_nonce = "0" * 32
        await db.commit()
    assert (await api.get(path(token))).status_code == 404


async def test_publish_now(pipeline, api):
    a, token = await proposed()
    r = await post(api, token, "publish", a.revision)
    assert r.status_code == 303 and r.headers["location"].endswith("?done=published")
    a = await load()
    assert a.status == ART_APPROVED and a.approved_at is not None
    page = (await api.get(r.headers["location"])).text
    assert "Publication starts within a few minutes" in page


async def test_hold(pipeline, api):
    a, token = await proposed()
    r = await post(api, token, "hold", a.revision)
    assert r.headers["location"].endswith("?done=held")
    assert (await load()).status == ART_HELD
    page = (await api.get(path(token))).text
    assert "/hold" not in page.split("<article>")[0]  # no second Hold button
    assert "/publish" in page and "/suggest" in page


async def test_suggest_changes(pipeline, api):
    a, token = await proposed()
    r = await post(api, token, "suggest", a.revision, text="Add+the+interview%2C+please.")
    assert r.headers["location"].endswith("?done=suggested")
    a = await load()
    assert a.status == ART_CHANGES_REQUESTED
    assert a.feedback[-1]["text"] == "Add the interview, please."
    assert a.feedback[-1]["revision"] == 1 and a.feedback[-1]["applied_revision"] is None
    r = await post(api, token, "suggest", a.revision, text="++")
    assert r.headers["location"].endswith("?done=empty")


async def test_a_stale_page_never_acts(pipeline, api):
    a, token = await proposed()
    r = await post(api, token, "publish", a.revision - 1)
    assert r.headers["location"].endswith("?done=stale")
    assert (await load()).status == ART_PROPOSED


async def test_foreign_origin_is_refused_and_own_origin_allowed(pipeline, api):
    a, token = await proposed()
    r = await post(api, token, "hold", a.revision, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and (await load()).status == ART_PROPOSED
    r = await post(api, token, "hold", a.revision, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 303 and (await load()).status == ART_HELD


async def test_signed_in_browser_is_not_blocked_by_the_session_csrf_check(pipeline, api):
    await learner_logged_in(api, "someone@example.ch")
    a, token = await proposed()
    r = await post(api, token, "hold", a.revision)
    assert r.status_code == 303 and (await load()).status == ART_HELD


async def test_refused_in_the_wrong_state(pipeline, api):
    a, token = await proposed()
    async with SessionLocal() as db:
        row = await workflow.get_by_key(db, SPOUSE)
        row.status = ART_PUBLISHED
        row.last_published_at = utcnow()
        await db.commit()
    r = await post(api, token, "hold", a.revision)
    assert r.headers["location"].endswith("?done=refused")
    # A correction is still possible after publication ...
    r = await post(api, token, "suggest", a.revision, text="Fix+a+typo")
    assert (await load()).status == ART_CHANGES_REQUESTED


async def test_link_closes_14_days_after_publication(pipeline, api):
    a, token = await proposed()
    async with SessionLocal() as db:
        row = await workflow.get_by_key(db, SPOUSE)
        row.status = ART_PUBLISHED
        row.last_published_at = utcnow() - timedelta(days=15)
        await db.commit()
    assert (await api.get(path(token))).status_code == 410
    r = await post(api, token, "suggest", a.revision, text="Too+late")
    assert r.status_code == 410


async def test_proposal_links_open_this_page(pipeline, api):
    a, token = await proposed()
    assert tokens.review_url(a, "publish") == (
        f"http://localhost:5173/api/articles/review/{token}?action=publish"
    )
