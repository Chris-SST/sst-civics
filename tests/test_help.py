"""The help chat (D-066): one open conversation per learner, open to free learners within a
small daily allowance, answered by the fast model from the reference material in content/help,
and closed while a mock test runs. Explain this also runs on the fast model."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.llm import service
from app.llm.client import FakeProvider, set_provider
from app.models import Conversation, LlmCall, MockRun, User
from tests.conftest import Api, learner_logged_in, make_question, seed_topics
from tests.test_tutor import parse_sse

EMAIL = "lea.brunner@example.ch"
ROOT = Path(__file__).resolve().parents[1]


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
        db.add(make_question("hilfe-frage"))
        await db.commit()


async def start(api: Api, **body):
    return await api.post("/api/help/start", json=body)


async def send(api: Api, conv_id: str, text: str = "Which documents do I need?"):
    return await api.post(f"/api/tutor/conversations/{conv_id}/messages", json={"content": text})


async def test_free_learner_gets_the_small_allowance(api, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_free_daily_message_limit", 2)
    await learner_logged_in(api, EMAIL, access=False)
    r = await start(api, lang="en")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["paid"] is False and body["usage"]["daily_limit"] == 2
    assert body["topic_code"] == "_help" and body["question_id"] is None
    for _ in range(2):
        assert (await send(api, body["id"])).status_code == 200
    r = await send(api, body["id"])
    assert r.status_code == 429 and r.json()["detail"] == "daily_limit_reached"
    # Explain this stays a paid feature.
    r = await api.post("/api/explain/start", json={"question_id": "hilfe-frage"})
    assert r.status_code == 403


async def test_free_help_can_be_switched_off(api, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_free_daily_message_limit", 0)
    await learner_logged_in(api, EMAIL, access=False)
    assert (await start(api)).status_code == 403


async def test_pass_holder_shares_the_daily_limit_and_gets_one_open_conversation(api, fake):
    await learner_logged_in(api, EMAIL, access=True)
    first = await start(api, lang="de")
    assert first.status_code == 201
    assert first.json()["paid"] is True and first.json()["usage"]["daily_limit"] == 20
    again = await start(api, lang="fr")
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert again.json()["language"] == "fr"
    fresh = await start(api, new=True)
    assert fresh.status_code == 201 and fresh.json()["id"] != first.json()["id"]
    async with SessionLocal() as db:
        old = await db.get(Conversation, uuid.UUID(first.json()["id"]))
        assert old.status == "ended"
    # Help conversations stay out of the topic chat lists.
    assert (await api.get("/api/tutor/conversations")).json() == []
    assert (await api.get("/api/tutor/overview")).json()["recent"] == []


async def test_reply_comes_from_the_fast_model_with_the_reference_material(api, fake):
    await learner_logged_in(api, EMAIL, access=False)
    conv = (await start(api, lang="en")).json()
    fake.replies = ["Two documents are required in Zurich. More: [Documents](https://...)"]
    r = await send(api, conv["id"])
    assert r.status_code == 200, r.text
    assert next(d for e, d in parse_sse(r.text) if e == "message")["role"] == "assistant"
    call = next(c for c in fake.calls if c.kind == "stream")
    assert call.model == get_settings().help_model == "claude-haiku-5-5"
    assert len(call.system) == 4
    reference = call.system[2]
    assert reference["cache_control"] == {"type": "ephemeral"}
    text = reference["text"]
    assert "# Help chat" in text and "# Reference material" in text
    assert "## Page: Documents for Naturalisation in Zurich" in text
    assert (
        "https://viapunt.ch/en/documents/" in text and "https://viapunt.ch/de/unterlagen/" in text
    )
    assert "Confoederatio Helvetica" in text  # a fact from the Zurich checklist
    assert "{{" not in text
    context = call.system[3]["text"]
    assert "Reply language: English" in context and EMAIL not in context
    gate = next(c for c in fake.calls if c.kind == "structured")
    assert "General help" in gate.messages[0]["content"]
    async with SessionLocal() as db:
        reply = (
            (await db.execute(select(LlmCall).where(LlmCall.purpose == "tutor_reply")))
            .scalars()
            .one()
        )
    assert reply.model == "claude-haiku-5-5"
    assert reply.prompt_version == "base@v3+civics@v2+help@v1"


async def test_guide_address_comes_from_the_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "guide_base_url", "https://staging.viapunt.ch/")
    text = service.help_reference("zh")
    assert "https://staging.viapunt.ch/en/fees/" in text and "viapunt.ch//" not in text


async def test_explain_this_runs_on_the_fast_model(api, fake):
    await learner_logged_in(api, EMAIL, access=True)
    conv = (
        await api.post("/api/explain/start", json={"question_id": "hilfe-frage", "lang": "en"})
    ).json()
    assert (await send(api, conv["id"], "Why?")).status_code == 200
    call = next(c for c in fake.calls if c.kind == "stream")
    assert call.model == get_settings().explain_model == "claude-haiku-5-5"
    model, effort = service.reply_model(
        service.TutorContext(canton="zh", language="en", topic_code="x", topic_name="x")
    )
    assert model == get_settings().tutor_model and effort == get_settings().tutor_effort


async def test_closed_while_a_mock_test_runs(api, fake):
    await learner_logged_in(api, EMAIL, access=True)
    conv = (await start(api)).json()
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalars().one()
        db.add(
            MockRun(
                id=uuid.uuid4(),
                user_id=user.id,
                canton="zh",
                question_ids=["hilfe-frage"],
                minutes=45,
                pass_mark=30,
                deadline_at=utcnow() + timedelta(minutes=45),
            )
        )
        await db.commit()
    r = await start(api)
    assert r.status_code == 409 and r.json()["detail"] == "mock_in_progress"
    r = await send(api, conv["id"])
    assert r.status_code == 409 and r.json()["detail"] == "mock_in_progress"


def test_reference_material_is_up_to_date():
    """content/help is generated from the guide pages and the scope files: run
    scripts/build_help_pack.py after changing either."""
    spec = importlib.util.spec_from_file_location(
        "build_help_pack", ROOT / "scripts" / "build_help_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for path, text in module.build().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is out of date"
