"""The owner's daily digest (D-072): figures, checks, the written summary and the email."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import timedelta

import pytest

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.email.backend import memory_outbox
from app.llm.client import FakeProvider, LLMError, set_provider
from app.models import ROLE_ADMIN, LlmCall, Payment, Session, StripeEvent, User
from app.ops import digest
from app.study.clock import ZURICH
from worker import tasks

SUMMARY = {
    "headline": "Two sign-ups and one pass sold.",
    "summary": "A quiet day with one purchase.",
    "actions": ["Look at the failed Stripe event."],
}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    provider = FakeProvider(json_replies={"digest": dict(SUMMARY)})
    set_provider(provider)

    async def ok_http(client, name, url):
        return digest._check(name, True, f"HTTP 200 ({url})")

    async def ok_cert(host):
        return digest._check(f"Certificate {host}", True, "expires in 80 days")

    monkeypatch.setattr(digest, "_http_check", ok_http)
    monkeypatch.setattr(digest, "_cert_check", ok_cert)
    backup = tmp_path / "civics-20261103.sql.gz.gpg"
    backup.write_bytes(b"x" * 2048)
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "digest_to", "")
    yield provider
    set_provider(None)


def yesterday_noon():
    day = utcnow().astimezone(ZURICH).date() - timedelta(days=1)
    start, _ = digest.day_window(day)
    return start + timedelta(hours=12)


async def seed():
    t = yesterday_noon()
    async with SessionLocal() as db:
        admin = User(email="owner@example.ch", role=ROLE_ADMIN)
        a = User(email="learner-a@example.ch", created_at=t, email_verified_at=t)
        b = User(email="learner-b@example.ch", created_at=t)
        old = User(email="old@example.ch", created_at=t - timedelta(days=30))
        db.add_all([admin, a, b, old])
        await db.flush()
        for u in (a, b, a):
            db.add(
                Session(
                    id=uuid.uuid4().hex,
                    user_id=u.id,
                    created_at=t,
                    expires_at=t + timedelta(days=14),
                )
            )
        db.add(
            Payment(
                user_id=a.id,
                product="civics_pass_zh",
                canton="zh",
                months=12,
                stripe_checkout_session_id="cs_test_1",
                amount_cents=2900,
                currency="chf",
                paid_at=t,
            )
        )
        db.add(
            LlmCall(purpose="tutor_reply", model="claude-haiku-5-5", cost_chf=0.12, created_at=t)
        )
        await db.commit()


async def test_figures_for_yesterday_count_only_that_day(fake):
    await seed()
    async with SessionLocal() as db:
        report = await digest.build_report(db)
    y = report["yesterday"]
    assert y["signups"] == 2
    assert y["emails_verified"] == 1
    assert y["sign_ins"] == 3
    assert y["learners_signed_in"] == 2
    assert y["passes_sold"] == 1
    assert y["revenue_chf"] == 29.0
    assert y["passes_by_product"] == {"civics_pass_zh": 1}
    assert y["ai_cost_chf"] == 0.12
    assert report["totals"]["learner_accounts"] == 3
    assert report["previous_7_day_average"]["signups"] == 0
    assert report["visits"] == {"status": "not configured"}


async def test_report_holds_no_email_address_or_id(fake):
    await seed()
    async with SessionLocal() as db:
        report = await digest.build_report(db)
    dumped = json.dumps(report)
    assert "@example.ch" not in dumped
    assert "cs_test_1" not in dumped


async def test_email_goes_to_admins_with_summary_and_figures(fake):
    await seed()
    async with SessionLocal() as db:
        _, emails = await digest.run_digest(db)
    assert [m.to for m in memory_outbox.messages] == ["owner@example.ch"]
    msg = memory_outbox.messages[0]
    assert msg.subject.startswith("Viapunt ")
    assert "2 sign-ups, 1 passes, all systems OK" in msg.subject
    assert SUMMARY["headline"] in msg.text
    assert "- Look at the failed Stripe event." in msg.text
    assert "Revenue CHF" in msg.text and "29" in msg.text
    assert "OK   Nightly backup" in msg.text
    assert msg.html and "<table" in msg.html
    # The model saw the report as JSON, without addresses.
    sent = fake.calls[-1]
    assert "@example.ch" not in json.dumps(sent.__dict__, default=str)
    async with SessionLocal() as db:
        logged = (
            (await db.execute(digest.select(LlmCall).where(LlmCall.purpose == "ops_digest")))
            .scalars()
            .all()
        )
    assert len(logged) == 1 and logged[0].user_id is None


async def test_digest_to_overrides_admins(fake, monkeypatch):
    await seed()
    monkeypatch.setattr(get_settings(), "digest_to", "a@example.org, b@example.org")
    async with SessionLocal() as db:
        await digest.run_digest(db)
    assert [m.to for m in memory_outbox.messages] == ["a@example.org", "b@example.org"]


async def test_email_still_sent_when_the_summary_fails(fake):
    fake.json_replies["digest"] = [LLMError("timeout")]
    await seed()
    async with SessionLocal() as db:
        await digest.run_digest(db)
    msg = memory_outbox.messages[0]
    assert "Written summary unavailable" in msg.text
    assert "Sign-ups" in msg.text


async def test_failed_checks_show_in_subject(fake, monkeypatch):
    await seed()
    async with SessionLocal() as db:
        db.add(StripeEvent(id="evt_1", type="checkout.session.completed", payload={}, error="boom"))
        await db.commit()

    async def down(client, name, url):
        return digest._check(name, False, "ConnectError")

    monkeypatch.setattr(digest, "_http_check", down)
    async with SessionLocal() as db:
        report, emails = await digest.run_digest(db, send=False)
    failing = {c["name"] for c in digest.problems(report)}
    assert {"Guide site", "App and API", "Stripe webhooks"} <= failing
    assert "3 check(s) failing" in emails[0].subject
    assert "FAIL Stripe webhooks: 1 with an error" in emails[0].text
    assert memory_outbox.messages == []  # send=False


async def test_old_or_missing_backup_fails(fake, monkeypatch, tmp_path):
    old = time.time() - 30 * 3600
    for f in tmp_path.glob("civics-*"):
        os.utime(f, (old, old))
    assert digest._backup_check()["ok"] is False
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path / "missing"))
    assert digest._backup_check()["ok"] is None


async def test_worker_job_respects_the_switch(fake, monkeypatch):
    await seed()
    monkeypatch.setattr(get_settings(), "digest_enabled", False)
    assert await tasks.send_daily_digest({}) == 0
    assert memory_outbox.messages == []
    monkeypatch.setattr(get_settings(), "digest_enabled", True)
    assert await tasks.send_daily_digest({}) == 1
