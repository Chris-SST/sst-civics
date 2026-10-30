"""Explain this (task 1.10): a chat bound to one question, answered in the learner's language,
gated to the question's topic, counted against the daily limit, and absent from mock tests."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.llm.client import FakeProvider, set_provider
from app.models import Conversation, LlmCall, MockRun, QuestionTranslation, User
from tests.conftest import Api, learner_logged_in, make_question, seed_topics
from tests.test_tutor import parse_sse

EMAIL = "mira.keller@example.ch"
QID = "erklaer-staatsebenen"


@pytest.fixture
def fake() -> FakeProvider:
    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


@pytest.fixture(autouse=True)
async def _bank():
    await seed_topics()
    async with SessionLocal() as db:
        db.add(
            make_question(
                QID,
                question_de="Auf wie vielen Ebenen ist die Schweiz organisiert?",
                options_de={"a": "Zwei", "b": "Drei", "c": "Vier", "d": "Eine"},
                correct="b",
                explanation_de="Bund, Kantone und Gemeinden: drei Ebenen.",
                sources=[
                    {"url": "https://www.ch.ch/de/staat-und-politik/", "checked": "2026-10-30"}
                ],
            )
        )
        db.add(make_question("andere-frage"))
        await db.commit()


async def add_translation(lang: str = "en", *, status: str = "approved") -> None:
    async with SessionLocal() as db:
        db.add(
            QuestionTranslation(
                question_id=QID,
                lang=lang,
                source_version=1,
                question="On how many levels is Switzerland organised?",
                options={"a": "Two", "b": "Three", "c": "Four", "d": "One"},
                explanation="Confederation, cantons and communes: three levels.",
                status=status,
                content_hash="seed",
            )
        )
        await db.commit()


async def learner(api: Api, *, access: bool = True) -> dict:
    return await learner_logged_in(api, EMAIL, access=access)


async def start(api: Api, question_id: str = QID, **body):
    return await api.post("/api/explain/start", json={"question_id": question_id, **body})


async def test_start_needs_a_pass(api, fake):
    await learner(api, access=False)
    r = await start(api)
    assert r.status_code == 403 and r.json()["detail"] == "no_access"
    async with SessionLocal() as db:
        assert (await db.execute(select(Conversation))).first() is None


async def test_one_open_conversation_per_question_and_user(api, api2, fake):
    await learner(api)
    first = await start(api, lang="en")
    assert first.status_code == 201, first.text
    again = await start(api, lang="fr")
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["language"] == "fr"  # the reply language follows the latest choice
    other = await start(api, "andere-frage")
    assert other.json()["id"] != first.json()["id"]
    body = first.json()
    assert body["question_id"] == QID and body["topic_code"] == "bund.demokratie.foederalismus"
    assert body["tutor_enabled"] is True and body["usage"]["daily_limit"] == 20
    # Another learner has their own conversation about the same question.
    await learner_logged_in(api2, "other.learner@example.ch", access=True)
    theirs = await start(api2)
    assert theirs.status_code == 201 and theirs.json()["id"] != first.json()["id"]
    # Explain conversations stay out of the general chat lists.
    assert (await api.get("/api/tutor/conversations")).json() == []
    assert (await api.get("/api/tutor/overview")).json()["recent"] == []
    assert (await start(api, "gibt-es-nicht")).status_code == 404


async def test_ended_conversation_is_replaced_by_a_new_one(api, fake):
    await learner(api)
    first = (await start(api)).json()
    assert (await api.post(f"/api/tutor/conversations/{first['id']}/end")).status_code == 200
    second = await start(api)
    assert second.status_code == 201 and second.json()["id"] != first["id"]


async def test_system_prompt_has_the_question_and_translation_and_no_personal_data(api, fake):
    await learner(api)
    await add_translation("en")
    conv = (await start(api, lang="en")).json()
    fake.replies = ["Because Switzerland has three levels: the Bund, the cantons and the communes."]
    r = await api.post(
        f"/api/tutor/conversations/{conv['id']}/messages",
        json={"content": "Why is the answer Drei?"},
    )
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    assert next(d for e, d in events if e == "message")["role"] == "assistant"
    call = next(c for c in fake.calls if c.kind == "stream")
    context = call.system[2]["text"]
    assert "Auf wie vielen Ebenen ist die Schweiz organisiert?" in context
    assert "a) Zwei" in context and "b) Drei" in context and "c) Vier" in context
    assert "Correct option: b" in context
    assert "Bund, Kantone und Gemeinden: drei Ebenen." in context
    assert "On how many levels is Switzerland organised?" in context  # approved translation
    assert "Confederation, cantons and communes" in context
    assert "https://www.ch.ch/de/staat-und-politik/" in context
    assert "Reply language: English" in context
    assert "never give legal advice" in context.lower() or "legal advice" in context.lower()
    assert "{{" not in context
    assert len(call.system) == 3  # base, civics (cached), session context
    joined = json.dumps(call.system) + json.dumps(call.messages)
    for private in (EMAIL, "mira", "keller", "example.ch"):
        assert private not in joined.lower()
    assert call.messages[-1] == {"role": "user", "content": "Why is the answer Drei?"}
    async with SessionLocal() as db:
        reply = (
            (await db.execute(select(LlmCall).where(LlmCall.purpose == "tutor_reply")))
            .scalars()
            .one()
        )
        assert reply.prompt_version == "base@v2+civics@v1+explain@v1"
        gate = (
            (await db.execute(select(LlmCall).where(LlmCall.purpose == "gatekeeper")))
            .scalars()
            .one()
        )
        assert gate.prompt_version == "gatekeeper@v2"
    gate_call = next(c for c in fake.calls if c.kind == "structured")
    assert "Auf wie vielen Ebenen" in gate_call.messages[0]["content"]
    assert "about this question or its topic" in gate_call.system


async def test_translation_not_approved_or_other_language_is_left_out(api, fake):
    await learner(api)
    await add_translation("en", status="draft")
    conv = (await start(api, lang="en")).json()
    await api.post(f"/api/tutor/conversations/{conv['id']}/messages", json={"content": "Hi"})
    context = next(c for c in fake.calls if c.kind == "stream").system[2]["text"]
    assert "On how many levels" not in context
    assert "No approved translation" in context


async def test_off_topic_gets_the_fixed_reply_without_calling_the_tutor(api, fake):
    await learner(api)
    conv = (await start(api, lang="de")).json()
    fake.classifications = [{"label": "off_topic", "wellbeing": "none", "coursework": False}]
    r = await api.post(
        f"/api/tutor/conversations/{conv['id']}/messages",
        json={"content": "Write me a poem about my cat"},
    )
    events = parse_sse(r.text)
    assert ("notice", {"kind": "off_topic"}) in events
    message = next(d for e, d in events if e == "message")
    assert message["role"] == "notice" and message["content"].startswith("Ich kann hier nur")
    assert not any(c.kind == "stream" for c in fake.calls)


async def test_daily_limit_applies_to_explain_messages(api, fake, monkeypatch):
    await learner(api)
    monkeypatch.setattr(get_settings(), "ai_daily_message_limit", 2)
    conv = (await start(api)).json()
    url = f"/api/tutor/conversations/{conv['id']}/messages"
    for _ in range(2):
        assert (await api.post(url, json={"content": "Why?"})).status_code == 200
    r = await api.post(url, json={"content": "And again?"})
    assert r.status_code == 429 and r.json()["detail"] == "daily_limit_reached"
    assert (await start(api)).json()["usage"]["daily_exhausted"] is True


async def test_access_is_checked_again_when_sending(api, fake):
    await learner(api)
    conv = (await start(api)).json()
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalars().one()
        for ent in list(user.entitlements):
            ent.expires_at = utcnow() - timedelta(days=1)
        await db.commit()
    r = await api.post(f"/api/tutor/conversations/{conv['id']}/messages", json={"content": "Hi"})
    assert r.status_code == 403 and r.json()["detail"] == "no_access"


async def test_mock_test_has_no_explain_entry_point(api, fake):
    paths = list((await api.get("/api/openapi.json")).json()["paths"])
    assert "/api/explain/start" in paths
    assert not [p for p in paths if "mock" in p and "explain" in p]
    await learner(api)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalars().one()
        db.add(
            MockRun(
                id=uuid.uuid4(),
                user_id=user.id,
                canton="zh",
                question_ids=[QID],
                minutes=45,
                pass_mark=30,
                deadline_at=utcnow() + timedelta(minutes=45),
            )
        )
        await db.commit()
    # A running mock test closes Explain this (D-051) ...
    r = await start(api)
    assert r.status_code == 409 and r.json()["detail"] == "mock_in_progress"
    # ... and the mock test's own payload carries nothing to explain with.
    run = (await api.get("/api/mock")).json()["active_run_id"]
    payload = (await api.get(f"/api/mock/{run}")).json()
    assert "explanation" not in json.dumps(payload) and "explain" not in json.dumps(payload).lower()
