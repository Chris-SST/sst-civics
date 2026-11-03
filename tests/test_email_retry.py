"""A failed email send is retried by the worker instead of being lost."""

from __future__ import annotations

import smtplib

import pytest
from arq import Retry

from worker import tasks


def failing(_msg) -> None:
    raise smtplib.SMTPServerDisconnected("connection lost")


@pytest.mark.parametrize(("tries", "delay"), [(1, 10), (2, 30), (3, 60), (4, 120), (5, 120)])
async def test_failed_send_is_retried_with_backoff(monkeypatch, tries, delay):
    monkeypatch.setattr(tasks.backend, "send", failing)
    with pytest.raises(Retry) as caught:
        await tasks.send_email(
            {"job_try": tries}, "verify_email", "en", "a@example.ch", {"link": "https://x"}
        )
    assert caught.value.defer_score == delay * 1000


async def test_inline_jobs_raise_the_error(monkeypatch):
    monkeypatch.setattr(tasks.backend, "send", failing)
    with pytest.raises(smtplib.SMTPServerDisconnected):
        await tasks.send_email({}, "verify_email", "en", "a@example.ch", {"link": "https://x"})


def test_message_id_and_date_use_the_sender_domain():
    from app.email.backend import OutgoingEmail, _build

    em = _build(OutgoingEmail(to="a@example.ch", subject="Hi", text="Hello"))
    assert em["Message-ID"].endswith("@viapunt.ch>")
    assert em["Date"]
