"""The owner's daily digest (D-072): yesterday's figures, website visits from Umami, service
checks, and a short written summary from the fast model, sent by email each morning.

Everything in the report is an aggregate count, an amount, a page path or a check result.
No email address, name or account id is collected, so nothing identifying reaches the AI
provider or the email. Each section is gathered on its own: a failing check or an unreachable
analytics database is reported in the email, never allowed to stop it."""

from __future__ import annotations

import asyncio
import html
import logging
import shutil
import socket
import ssl
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.db import utcnow
from app.email.backend import OutgoingEmail
from app.models import (
    ROLE_ADMIN,
    ROLE_LEARNER,
    Attempt,
    Entitlement,
    LlmCall,
    MockRun,
    Payment,
    QuestionReport,
    Session,
    StripeEvent,
    User,
)
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

CERT_WARN_DAYS = 14
BACKUP_MAX_AGE_HOURS = 26
DISK_MIN_FREE_PCT = 15
STRIPE_STUCK_MINUTES = 60
HTTP_TIMEOUT = 10


def day_window(day: date) -> tuple[datetime, datetime]:
    """Start and end (UTC) of a Zurich calendar day."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=ZURICH)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=ZURICH)
    return start.astimezone(UTC), end.astimezone(UTC)


# --- Figures from our own database ------------------------------------------------------------


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar_one() or 0)


async def app_figures(db: AsyncSession, start: datetime, end: datetime) -> dict[str, Any]:
    """Counts and amounts for one window. Impersonated sessions are not sign-ins."""

    def between(col):
        return (col >= start) & (col < end)

    paid = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                between(Payment.paid_at)
            )
        )
    ).one()
    refunded = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Payment.amount_refunded_cents), 0)).where(
                between(Payment.refunded_at)
            )
        )
    ).one()
    ai = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(LlmCall.cost_chf), 0.0)).where(
                between(LlmCall.created_at)
            )
        )
    ).one()
    by_product = (
        await db.execute(
            select(Payment.product, func.count())
            .where(between(Payment.paid_at))
            .group_by(Payment.product)
        )
    ).all()
    return {
        "signups": await _count(
            db,
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_LEARNER, between(User.created_at)),
        ),
        "emails_verified": await _count(
            db, select(func.count()).select_from(User).where(between(User.email_verified_at))
        ),
        "sign_ins": await _count(
            db,
            select(func.count())
            .select_from(Session)
            .where(between(Session.created_at), Session.impersonator_user_id.is_(None)),
        ),
        "learners_signed_in": await _count(
            db,
            select(func.count(distinct(Session.user_id))).where(
                between(Session.created_at), Session.impersonator_user_id.is_(None)
            ),
        ),
        "learners_practising": await _count(
            db, select(func.count(distinct(Attempt.user_id))).where(between(Attempt.created_at))
        ),
        "answers": await _count(
            db, select(func.count()).select_from(Attempt).where(between(Attempt.created_at))
        ),
        "mock_tests_started": await _count(
            db, select(func.count()).select_from(MockRun).where(between(MockRun.started_at))
        ),
        "passes_sold": int(paid[0]),
        "revenue_chf": round(int(paid[1]) / 100, 2),
        "passes_by_product": {p: int(n) for p, n in by_product},
        "refunds": int(refunded[0]),
        "refunded_chf": round(int(refunded[1]) / 100, 2),
        "ai_calls": int(ai[0]),
        "ai_cost_chf": round(float(ai[1]), 2),
        "ai_errors": await _count(
            db,
            select(func.count())
            .select_from(LlmCall)
            .where(between(LlmCall.created_at), LlmCall.status != "ok"),
        ),
        "question_reports": await _count(
            db,
            select(func.count())
            .select_from(QuestionReport)
            .where(between(QuestionReport.created_at)),
        ),
    }


async def totals(db: AsyncSession, now: datetime) -> dict[str, Any]:
    month_start = now.astimezone(ZURICH).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start = month_start.astimezone(UTC)
    settings = get_settings()
    month_ai = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(LlmCall.cost_chf), 0.0)).where(
                    LlmCall.created_at >= month_start
                )
            )
        ).scalar_one()
    )
    month_revenue = int(
        (
            await db.execute(
                select(
                    func.coalesce(func.sum(Payment.amount_cents - Payment.amount_refunded_cents), 0)
                ).where(Payment.paid_at >= month_start)
            )
        ).scalar_one()
    )
    return {
        "learner_accounts": await _count(
            db,
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_LEARNER, User.is_active.is_(True)),
        ),
        "active_paid_passes": await _count(
            db,
            select(func.count())
            .select_from(Entitlement)
            .where(Entitlement.source == "stripe", Entitlement.expires_at > now),
        ),
        "passes_expiring_7_days": await _count(
            db,
            select(func.count())
            .select_from(Entitlement)
            .where(
                Entitlement.source == "stripe",
                Entitlement.expires_at > now,
                Entitlement.expires_at <= now + timedelta(days=7),
            ),
        ),
        "open_question_reports": await _count(
            db,
            select(func.count())
            .select_from(QuestionReport)
            .where(QuestionReport.resolved_at.is_(None)),
        ),
        "month_revenue_chf": round(month_revenue / 100, 2),
        "month_ai_cost_chf": round(month_ai, 2),
        "ai_monthly_budget_chf": settings.ai_monthly_budget_chf,
    }


# --- Website visits (Umami) ---------------------------------------------------------------------

# Umami 3 tables: website_event (one row per page view, event_type 1, or custom event, 2)
# and session (one row per visitor and day; Umami salts the id daily).
_UMAMI_HOSTS = """
SELECT hostname,
       COUNT(*) FILTER (WHERE event_type = 1) AS pageviews,
       COUNT(DISTINCT session_id) AS visitors,
       COUNT(DISTINCT visit_id) AS visits
FROM website_event
WHERE website_id = CAST(:w AS uuid) AND created_at >= :s AND created_at < :e
GROUP BY hostname ORDER BY pageviews DESC
"""
_UMAMI_PAGES = """
SELECT hostname, url_path, COUNT(*) AS views
FROM website_event
WHERE website_id = CAST(:w AS uuid) AND created_at >= :s AND created_at < :e AND event_type = 1
GROUP BY hostname, url_path ORDER BY views DESC LIMIT 8
"""
_UMAMI_REFERRERS = """
SELECT referrer_domain, COUNT(DISTINCT session_id) AS visitors
FROM website_event
WHERE website_id = CAST(:w AS uuid) AND created_at >= :s AND created_at < :e
  AND referrer_domain IS NOT NULL AND referrer_domain <> '' AND NOT (referrer_domain = ANY(:own))
GROUP BY referrer_domain ORDER BY visitors DESC LIMIT 6
"""
_UMAMI_COUNTRIES = """
SELECT s.country, COUNT(DISTINCT e.session_id) AS visitors
FROM website_event e JOIN session s ON s.session_id = e.session_id
WHERE e.website_id = CAST(:w AS uuid) AND e.created_at >= :s AND e.created_at < :e
GROUP BY s.country ORDER BY visitors DESC LIMIT 6
"""
_UMAMI_EVENTS = """
SELECT event_name, COUNT(*) AS n
FROM website_event
WHERE website_id = CAST(:w AS uuid) AND created_at >= :s AND created_at < :e AND event_type = 2
GROUP BY event_name ORDER BY n DESC LIMIT 10
"""
_UMAMI_DAILY = """
SELECT DATE(created_at AT TIME ZONE 'Europe/Zurich') AS day, COUNT(DISTINCT session_id) AS visitors
FROM website_event
WHERE website_id = CAST(:w AS uuid) AND created_at >= :s AND created_at < :e
GROUP BY day ORDER BY day
"""


def _own_hosts() -> list[str]:
    s = get_settings()
    return sorted(
        {h for h in (urlparse(s.guide_base_url).hostname, urlparse(s.app_base_url).hostname) if h}
    )


async def visit_figures(start: datetime, end: datetime, week_start: datetime) -> dict[str, Any]:
    """Yesterday's visits, top pages, referrers, countries and custom events, plus visitors
    per day for the week before. Returns {"status": "not configured" | "unavailable"} when
    the analytics database is not set up or not reachable."""
    settings = get_settings()
    if not (settings.umami_database_url and settings.umami_website_id):
        return {"status": "not configured"}
    engine = create_async_engine(settings.umami_database_url, pool_pre_ping=True)
    params = {"w": settings.umami_website_id, "s": start, "e": end}
    out: dict[str, Any] = {"status": "ok"}
    try:
        async with engine.connect() as conn:
            hosts = (await conn.execute(text(_UMAMI_HOSTS), params)).all()
            out["by_host"] = [
                {"host": h or "(unknown)", "pageviews": pv, "visitors": v, "visits": vi}
                for h, pv, v, vi in hosts
            ]
            out["pageviews"] = sum(r["pageviews"] for r in out["by_host"])
            out["visitors"] = sum(r["visitors"] for r in out["by_host"])
            out["top_pages"] = [
                {"host": h, "path": p, "views": n}
                for h, p, n in (await conn.execute(text(_UMAMI_PAGES), params)).all()
            ]
            out["referrers"] = [
                {"domain": d, "visitors": n}
                for d, n in (
                    await conn.execute(text(_UMAMI_REFERRERS), {**params, "own": _own_hosts()})
                ).all()
            ]
            out["countries"] = [
                {"country": c or "unknown", "visitors": n}
                for c, n in (await conn.execute(text(_UMAMI_COUNTRIES), params)).all()
            ]
            out["events"] = {
                name: n for name, n in (await conn.execute(text(_UMAMI_EVENTS), params)).all()
            }
            daily = (
                await conn.execute(text(_UMAMI_DAILY), {**params, "s": week_start, "e": start})
            ).all()
            out["visitors_per_day_previous_7"] = [int(n) for _, n in daily]
            out["visitors_avg_previous_7"] = round(sum(int(n) for _, n in daily) / 7, 1)
    except Exception as exc:  # any driver, network or schema error
        log.warning("Digest: Umami query failed: %s", exc.__class__.__name__)
        return {"status": "unavailable", "error": exc.__class__.__name__}
    finally:
        await engine.dispose()
    return out


# --- Service checks ------------------------------------------------------------------------------


def _check(name: str, ok: bool | None, detail: str) -> dict[str, Any]:
    """ok: True passed, False failed, None could not be checked."""
    return {"name": name, "ok": ok, "detail": detail}


async def _http_check(client: httpx.AsyncClient, name: str, url: str) -> dict[str, Any]:
    try:
        r = await client.get(url)
        ms = int(r.elapsed.total_seconds() * 1000)
        return _check(name, r.status_code == 200, f"HTTP {r.status_code} in {ms} ms ({url})")
    except httpx.HTTPError as exc:
        return _check(name, False, f"{exc.__class__.__name__} ({url})")


def _cert_days_left(host: str) -> int:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=HTTP_TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            not_after = tls.getpeercert()["notAfter"]
    expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), tz=UTC)
    return (expires - utcnow()).days


async def _cert_check(host: str) -> dict[str, Any]:
    try:
        days = await asyncio.to_thread(_cert_days_left, host)
        return _check(f"Certificate {host}", days >= CERT_WARN_DAYS, f"expires in {days} days")
    except (OSError, ssl.SSLError, KeyError, ValueError) as exc:
        return _check(f"Certificate {host}", False, exc.__class__.__name__)


def _backup_check() -> dict[str, Any]:
    folder = Path(get_settings().backup_dir)
    if not folder.is_dir():
        return _check("Nightly backup", None, "backup folder not mounted in this container")
    files = [p for p in folder.glob("civics-*.sql.gz*") if p.is_file()]
    if not files:
        return _check("Nightly backup", False, "no backup file found")
    newest = max(files, key=lambda p: p.stat().st_mtime)
    age_h = (utcnow().timestamp() - newest.stat().st_mtime) / 3600
    size_mb = newest.stat().st_size / 1_048_576
    return _check(
        "Nightly backup",
        age_h <= BACKUP_MAX_AGE_HOURS,
        f"newest {age_h:.0f} h old, {size_mb:.1f} MB",
    )


def _disk_check() -> dict[str, Any]:
    usage = shutil.disk_usage("/")
    free_pct = usage.free / usage.total * 100
    return _check(
        "Disk space",
        free_pct >= DISK_MIN_FREE_PCT,
        f"{free_pct:.0f}% free ({usage.free / 1e9:.1f} GB)",
    )


async def service_checks(db: AsyncSession, now: datetime) -> list[dict[str, Any]]:
    settings = get_settings()
    checks: list[dict[str, Any]] = [_check("Database", True, "queries answered")]
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        http = [
            _http_check(client, "Guide site", settings.guide_base_url.rstrip("/") + "/"),
            _http_check(client, "App and API", settings.app_base_url.rstrip("/") + "/api/health"),
        ]
        if settings.umami_website_id:
            http.append(_http_check(client, "Analytics (Umami)", settings.umami_heartbeat_url))
        checks += await asyncio.gather(*http)
    hosts = [
        urlparse(u).hostname
        for u in (settings.guide_base_url, settings.app_base_url)
        if urlparse(u).scheme == "https"
    ]
    checks += await asyncio.gather(*(_cert_check(h) for h in dict.fromkeys(hosts) if h))

    failed = await _count(
        db, select(func.count()).select_from(StripeEvent).where(StripeEvent.error.is_not(None))
    )
    stuck = await _count(
        db,
        select(func.count())
        .select_from(StripeEvent)
        .where(
            StripeEvent.processed_at.is_(None),
            StripeEvent.received_at < now - timedelta(minutes=STRIPE_STUCK_MINUTES),
        ),
    )
    checks.append(
        _check(
            "Stripe webhooks",
            failed == 0 and stuck == 0,
            "all events processed"
            if not (failed or stuck)
            else f"{failed} with an error, {stuck} not processed after {STRIPE_STUCK_MINUTES} min",
        )
    )
    checks.append(_backup_check())
    checks.append(_disk_check())
    return checks


# --- Report, email -------------------------------------------------------------------------------


async def build_report(db: AsyncSession, now: datetime | None = None) -> dict[str, Any]:
    """Everything the email shows, for yesterday (Zurich calendar day)."""
    now = now or utcnow()
    day = now.astimezone(ZURICH).date() - timedelta(days=1)
    start, end = day_window(day)
    week_start, _ = day_window(day - timedelta(days=7))
    previous = await app_figures(db, week_start, start)
    report = {
        "day": day.isoformat(),
        "yesterday": await app_figures(db, start, end),
        "previous_7_day_average": {
            k: round(v / 7, 2) if isinstance(v, (int, float)) else v
            for k, v in previous.items()
            if k != "passes_by_product"
        },
        "totals": await totals(db, now),
        "visits": await visit_figures(start, end, week_start),
        "checks": await service_checks(db, now),
    }
    t = report["totals"]
    if t["ai_monthly_budget_chf"]:
        t["month_ai_budget_used_pct"] = round(
            t["month_ai_cost_chf"] / t["ai_monthly_budget_chf"] * 100, 1
        )
    return report


def problems(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in report["checks"] if c["ok"] is False]


def _rows(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    y, a, t, v = (
        report["yesterday"],
        report["previous_7_day_average"],
        report["totals"],
        report["visits"],
    )

    def num(x: float) -> str:
        return f"{x:g}" if isinstance(x, (int, float)) else str(x)

    rows: list[tuple[str, str, str]] = []
    if v.get("status") == "ok":
        rows += [
            ("Website visitors", num(v["visitors"]), num(v["visitors_avg_previous_7"])),
            ("Page views", num(v["pageviews"]), ""),
        ]
    else:
        rows.append(("Website visits", v.get("status", "unavailable"), ""))
    for key, label in [
        ("signups", "Sign-ups"),
        ("emails_verified", "Emails verified"),
        ("sign_ins", "Sign-ins"),
        ("learners_signed_in", "Learners who signed in"),
        ("learners_practising", "Learners practising"),
        ("answers", "Questions answered"),
        ("mock_tests_started", "Mock tests started"),
        ("passes_sold", "Passes sold"),
        ("revenue_chf", "Revenue CHF"),
        ("refunds", "Refunds"),
        ("ai_calls", "AI calls"),
        ("ai_cost_chf", "AI cost CHF"),
        ("question_reports", "Question reports"),
    ]:
        rows.append((label, num(y[key]), num(a[key])))
    rows += [
        ("Learner accounts (total)", num(t["learner_accounts"]), ""),
        ("Active paid passes", num(t["active_paid_passes"]), ""),
        ("Revenue this month CHF", num(t["month_revenue_chf"]), ""),
        (
            "AI cost this month CHF",
            num(t["month_ai_cost_chf"]),
            f"budget {num(t['ai_monthly_budget_chf'])}",
        ),
    ]
    return rows


def _status_mark(ok: bool | None) -> str:
    return {True: "OK", False: "FAIL", None: "n/a"}[ok]


def render_email(report: dict[str, Any], summary: dict[str, Any] | None, to: str) -> OutgoingEmail:
    issues = problems(report)
    y, v = report["yesterday"], report["visits"]
    visitors = f"{v['visitors']} visitors, " if v.get("status") == "ok" else ""
    state = "all systems OK" if not issues else f"{len(issues)} check(s) failing"
    subject = (
        f"Viapunt {report['day']}: {visitors}{y['signups']} sign-ups, "
        f"{y['passes_sold']} passes, {state}"
    )

    lines: list[str] = []
    if summary:
        lines += [summary["headline"], "", summary["summary"], ""]
        if summary["actions"]:
            lines += ["To do today:"] + [f"- {a}" for a in summary["actions"]] + [""]
    else:
        lines += ["(Written summary unavailable today; the figures below are complete.)", ""]
    lines.append(f"{'':28} {'yesterday':>10} {'7-day avg':>10}")
    lines += [f"{label:28} {val:>10} {avg:>10}" for label, val, avg in _rows(report)]
    lines += ["", "Service checks:"]
    lines += [f"- {_status_mark(c['ok']):4} {c['name']}: {c['detail']}" for c in report["checks"]]
    if v.get("status") == "ok":
        if v["top_pages"]:
            lines += ["", "Top pages:"]
            lines += [f"- {p['views']:>4}  {p['host']}{p['path']}" for p in v["top_pages"]]
        if v["referrers"]:
            lines += ["", "Referrers:"]
            lines += [f"- {r['visitors']:>4}  {r['domain']}" for r in v["referrers"]]
        if v["events"]:
            lines += ["", "Tracked events:"]
            lines += [f"- {n:>4}  {name}" for name, n in v["events"].items()]

    e = html.escape
    parts = []
    if summary:
        parts.append(
            f"<p><strong>{e(summary['headline'])}</strong></p><p>{e(summary['summary'])}</p>"
        )
        if summary["actions"]:
            items = "".join(f"<li>{e(a)}</li>" for a in summary["actions"])
            parts.append(f"<p><strong>To do today</strong></p><ul>{items}</ul>")
    else:
        parts.append(
            "<p><em>Written summary unavailable today; the figures below are complete.</em></p>"
        )
    cell = 'style="padding:3px 10px;border-bottom:1px solid #eee"'
    num_cell = 'style="padding:3px 10px;border-bottom:1px solid #eee;text-align:right"'
    trs = "".join(
        f"<tr><td {cell}>{e(label)}</td><td {num_cell}><strong>{e(val)}</strong></td>"
        f"<td {num_cell}>{e(avg)}</td></tr>"
        for label, val, avg in _rows(report)
    )
    parts.append(
        '<table style="border-collapse:collapse;font-size:14px">'
        f"<tr><th {cell}></th><th {num_cell}>Yesterday</th><th {num_cell}>7-day avg</th></tr>"
        f"{trs}</table>"
    )
    colour = {True: "#1a7f37", False: "#c62828", None: "#777"}
    checks = "".join(
        f'<li><span style="color:{colour[c["ok"]]};font-weight:600">{_status_mark(c["ok"])}</span> '
        f"{e(c['name'])}: {e(c['detail'])}</li>"
        for c in report["checks"]
    )
    parts.append(f"<p><strong>Service checks</strong></p><ul>{checks}</ul>")
    if v.get("status") == "ok" and v["top_pages"]:
        pages = "".join(
            f"<li>{p['views']} &middot; {e(p['host'] + p['path'])}</li>" for p in v["top_pages"]
        )
        parts.append(f"<p><strong>Top pages</strong></p><ul>{pages}</ul>")
    body = (
        '<div style="font-family:system-ui,sans-serif;color:#222;max-width:640px">'
        f'<h2 style="margin:0 0 8px">Viapunt, {e(report["day"])}</h2>{"".join(parts)}</div>'
    )
    return OutgoingEmail(to=to, subject=subject, text="\n".join(lines), html=body)


async def recipients(db: AsyncSession) -> list[str]:
    configured = [a.strip() for a in get_settings().digest_to.split(",") if a.strip()]
    if configured:
        return configured
    rows = await db.execute(
        select(User.email).where(
            User.role == ROLE_ADMIN, User.is_active.is_(True), User.email.is_not(None)
        )
    )
    return [e for (e,) in rows if e]


async def run_digest(
    db: AsyncSession, *, send: bool = True, to: list[str] | None = None
) -> tuple[dict[str, Any], list[OutgoingEmail]]:
    """Build the report, ask the fast model for the summary, and send one email per
    recipient. Returns the report and the emails (sent unless `send` is False)."""
    from app.email import backend
    from app.llm.service import write_ops_digest

    report = await build_report(db)
    summary = await write_ops_digest(db, report)
    await db.commit()  # the AI call log
    emails = [render_email(report, summary, addr) for addr in (to or await recipients(db))]
    if send:
        for em in emails:
            backend.send(em)
    log.info(
        "Digest for %s: %d recipient(s), %d failing check(s), summary %s",
        report["day"],
        len(emails),
        len(problems(report)),
        "ok" if summary else "unavailable",
    )
    return report, emails
