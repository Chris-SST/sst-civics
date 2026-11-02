"""The guide site's public API (D-067): the limited help chat for visitors who are not signed in,
and the question of the day."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import FakeProvider, set_provider
from app.models import LlmCall, QuestionTranslation
from app.questions.daily import pick_index
from tests.conftest import make_question

GUIDE = {"Origin": "https://viapunt.ch"}
URL = "/api/public/help"


@pytest.fixture
def fake() -> FakeProvider:
    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


def ask(text: str = "Which documents do I need?", lang: str = "en", history=()):
    return {"lang": lang, "messages": [*history, {"role": "user", "content": text}]}


async def test_reply_from_the_fast_model_with_the_reference_and_nothing_stored(api, fake):
    fake.replies = ["Two documents. More: [Documents](https://viapunt.ch/en/documents/)"]
    r = await api.post(URL, json=ask(), headers=GUIDE, csrf=False)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "assistant" and body["content"].startswith("Two documents")
    assert body["remaining"] == get_settings().public_help_per_ip_daily - 1
    call = next(c for c in fake.calls if c.kind == "stream")
    assert call.model == "claude-haiku-5-5"
    assert "# Reference material" in call.system[2]["text"]
    assert "public guide site" in call.system[3]["text"]
    async with SessionLocal() as db:
        rows = (await db.execute(select(LlmCall))).scalars().all()
    reply = next(c for c in rows if c.purpose == "public_help")
    assert reply.user_id is None and reply.conversation_id is None
    assert reply.prompt_version.endswith("+help@v1")


async def test_history_is_trimmed_and_alternates(api, fake):
    history = []
    for i in range(5):
        history += [
            {"role": "user", "content": f"Question {i}"},
            {"role": "assistant", "content": f"Answer {i}"},
        ]
    r = await api.post(URL, json=ask("And the fees?", history=history), headers=GUIDE, csrf=False)
    assert r.status_code == 200
    sent = next(c for c in fake.calls if c.kind == "stream").messages
    assert len(sent) <= 6 and sent[0]["role"] == "user" and sent[-1]["content"] == "And the fees?"
    assert all(a["role"] != b["role"] for a, b in zip(sent, sent[1:], strict=False))


async def test_other_origins_and_missing_origin_are_refused(api, fake):
    assert (await api.post(URL, json=ask(), csrf=False)).status_code == 403
    other = {"Origin": "https://evil.example"}
    assert (await api.post(URL, json=ask(), headers=other, csrf=False)).status_code == 403
    assert not fake.calls


async def test_daily_limit_per_visitor(api, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_help_per_ip_daily", 2)
    for left in (1, 0):
        r = await api.post(URL, json=ask(), headers=GUIDE, csrf=False)
        assert r.status_code == 200 and r.json()["remaining"] == left
    r = await api.post(URL, json=ask(), headers=GUIDE, csrf=False)
    assert r.status_code == 429 and r.json()["detail"] == "daily_limit_reached"


async def test_daily_total_for_all_visitors(api, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_help_daily_total", 1)
    assert (await api.post(URL, json=ask(), headers=GUIDE, csrf=False)).status_code == 200
    r = await api.post(URL, json=ask(), headers=GUIDE, csrf=False)
    assert r.status_code == 429 and r.json()["detail"] == "busy"


async def test_switched_off_and_bad_requests(api, fake, monkeypatch):
    long = ask("x" * (get_settings().public_help_max_chars + 1))
    assert (await api.post(URL, json=long, headers=GUIDE, csrf=False)).status_code == 422
    last_assistant = {"lang": "en", "messages": [{"role": "assistant", "content": "Hi"}]}
    assert (await api.post(URL, json=last_assistant, headers=GUIDE, csrf=False)).status_code == 422
    monkeypatch.setattr(get_settings(), "public_help_per_ip_daily", 0)
    r = await api.post(URL, json=ask(), headers=GUIDE, csrf=False)
    assert r.status_code == 503 and r.json()["detail"] == "help_unavailable"


async def test_off_topic_gets_the_fixed_reply_in_the_page_language(api, fake):
    fake.classifications = [{"label": "off_topic", "wellbeing": "none", "coursework": False}]
    r = await api.post(URL, json=ask("Write me a poem", lang="de"), headers=GUIDE, csrf=False)
    assert r.status_code == 200
    assert r.json()["role"] == "notice"
    assert r.json()["content"].startswith("Ich kann nur beim Grundkenntnistest")
    assert not any(c.kind == "stream" for c in fake.calls)


# --- Question of the day -------------------------------------------------------------------


async def add(qid: str, *, english: str | None = "approved", **kw) -> None:
    async with SessionLocal() as db:
        db.add(make_question(qid, **kw))
        if english:
            db.add(
                QuestionTranslation(
                    question_id=qid,
                    lang="en",
                    source_version=1,
                    question=f"English {qid}",
                    options={"a": "Confederation", "b": "Canton", "c": "Commune", "d": "District"},
                    explanation="It is the Confederation.",
                    status=english,
                    content_hash="seed",
                )
            )
        await db.commit()


async def test_question_of_the_day_needs_an_approved_question_with_english(api):
    r = await api.get("/api/public/question-of-the-day")
    assert r.status_code == 404
    await add("ohne-englisch", english=None)
    await add("englisch-entwurf", english="draft")
    await add("im-review", status="in_review")
    assert (await api.get("/api/public/question-of-the-day")).status_code == 404
    await add("bereit")
    r = await api.get("/api/public/question-of-the-day")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "bereit" and body["correct"] == "a"
    assert body["de"]["options"]["a"] == "Bund" and body["en"]["question"] == "English bereit"
    assert r.headers["cache-control"] == "public, max-age=600"
    assert (await api.get("/api/public/question-of-the-day")).json()["id"] == "bereit"


async def test_canton_questions_of_another_canton_are_left_out(api):
    await add("aargau-frage", scope="ag", canton="ag", topic_code="kanton.geografie.aargau")
    assert (await api.get("/api/public/question-of-the-day?canton=zh")).status_code == 404


def test_pick_changes_from_day_to_day():
    picks = {pick_index(40, day) for day in range(739_000, 739_010)}
    assert len(picks) == 10


# --- Free practice without an account --------------------------------------------------------


async def test_sample_questions_side_by_side_with_answers_without_an_account(api):
    for i in range(35):
        await add(f"probe-{i:02d}", english="approved" if i % 2 == 0 else None)
    r = await api.get("/api/public/sample-questions?canton=zh&lang=en")
    assert r.status_code == 200
    qs = r.json()["questions"]
    assert len(qs) == 30  # the same sample set a new free account gets
    first = qs[0]
    assert first["mode"] == "side" and first["translation"]["question"].startswith("English")
    assert first["answer"] == "a" and first["explanation"]["lang"] == "en"
    no_english = next(q for q in qs if q["translation"] is None)
    assert no_english["mode"] == "de" and no_english["fallback"] is True
    german = (await api.get("/api/public/sample-questions?lang=de")).json()["questions"]
    assert german[0]["mode"] == "de" and german[0]["fallback"] is False
    assert (await api.get("/api/public/sample-questions?lang=xx")).json()["lang"] == "en"
