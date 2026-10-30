"""Question bank: answer and duplicate checks, reports, and which questions are served. Study
modes, progress, Learn, Practise and the mock test are in test_study.py; content import and
review in test_content.py."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import FakeProvider, set_provider
from app.models import Attempt, Question
from app.questions import checks
from tests.conftest import Api, learner_logged_in, make_question, seed_topics

TOPICS = (
    "bund.demokratie.foederalismus",
    "bund.demokratie.volksrechte",
    "kanton.demokratie.kantonsrat",
)


@pytest.fixture
def fake() -> FakeProvider:
    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


async def learner_in(api: Api) -> dict:
    """A learner with an active entitlement for their canton (zh), signed in on `api`."""
    return await learner_logged_in(api, "lina@example.ch", access=True)


async def seed_bank(n_per_topic: int = 2, topics=TOPICS, status: str = "approved") -> list[str]:
    """Topics for zh plus `n_per_topic` questions on each; returns the question ids."""
    await seed_topics()
    ids = []
    async with SessionLocal() as db:
        for topic in topics:
            canton = topic.startswith("kanton.")
            for i in range(n_per_topic):
                q = make_question(
                    f"{topic.split('.')[-1]}-{i}",
                    topic_code=topic,
                    scope="zh" if canton else "federal",
                    canton="zh" if canton else None,
                    difficulty=1 + (i % 3),
                    question_de=f"Frage {i} zu {topic}: welche Antwort stimmt?",
                    correct="abcd"[i % 4],
                    status=status,
                )
                db.add(q)
                ids.append(q.id)
        await db.commit()
    return ids


# --- Pure checks -------------------------------------------------------------------------------


def test_answer_checks_cover_multiple_choice():
    assert checks.check_answer("b", "b").correct
    assert checks.check_answer(" B. Option B", "b").correct
    assert not checks.check_answer("A", "b").correct
    assert not checks.check_answer("", "b").correct
    assert not checks.check_answer("999", "b").correct
    assert checks.option_key("c)") == "c" and checks.option_key("x") == ""


def test_options_valid_needs_keys_a_to_d_and_four_different_texts():
    opts = {"a": "Bund", "b": "Kanton", "c": "Gemeinde", "d": "Bezirk"}
    assert checks.options_valid(opts, "b")
    assert not checks.options_valid(opts, "e")
    assert not checks.options_valid({k: v for k, v in opts.items() if k != "d"}, "b")
    assert not checks.options_valid({**opts, "d": "bund"}, "b")  # same text, other case
    assert not checks.options_valid({**opts, "d": " "}, "b")
    assert not checks.options_valid(None, "b")


def test_duplicate_checks():
    dup, best = checks.is_near_duplicate(
        "Which body elects the Federal Council in Switzerland?",
        ["Which body elects the Federal Council in Switzerland every four years?"],
    )
    assert dup and best > 0.6
    assert not checks.is_near_duplicate(
        "How many cantons does Switzerland have?", ["Which body elects the Federal Council?"]
    )[0]
    assert checks.similarity("", "anything") == 0.0


# --- Learner side ------------------------------------------------------------------------------


async def practise(api: Api, topic: str | None = None, n: int | None = None):
    params = []
    if topic:
        params.append(f"topic_code={topic}")
    if n:
        params.append(f"n={n}")
    return await api.get("/api/study/practise" + ("?" + "&".join(params) if params else ""))


async def test_report_hides_a_question_after_two(api, api2, fake):
    await seed_bank(n_per_topic=2, topics=(TOPICS[0],))
    await learner_in(api2)
    r = await practise(api2, TOPICS[0], 1)
    assert r.status_code == 200, r.text
    q = r.json()["questions"][0]
    r = await api2.post(f"/api/questions/{q['id']}/report", json={"comment": "Tippfehler"})
    assert r.status_code == 201 and r.json()["report_count"] == 1
    r = await api2.post(f"/api/questions/{q['id']}/report", json={"lang": "fr"})
    assert r.json()["report_count"] == 2
    async with SessionLocal() as db:
        stored = await db.get(Question, q["id"])
        assert stored.status == "in_review" and stored.file_sync_pending is True
    r = await practise(api2, TOPICS[0], 5)
    assert [x["id"] for x in r.json()["questions"]] != [q["id"]]
    assert q["id"] not in [x["id"] for x in r.json()["questions"]]
    r = await practise(api2, "bund.gibt_es_nicht")
    assert r.status_code == 404 and r.json()["detail"] == "no_questions"
    r = await api2.post("/api/questions/gibt-es-nicht/report", json={})
    assert r.status_code == 404


async def test_answer_is_marked_by_option_key_without_any_ai_call(api, api2, fake):
    [qid] = await seed_bank(n_per_topic=1, topics=(TOPICS[0],))
    await learner_in(api2)
    r = await api2.post("/api/study/answer", json={"question_id": qid, "answer": "A"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True and body["score"] == 1.0
    assert body["answer"] == "a" and body["answer_text"] == "Bund"
    assert fake.calls == []
    async with SessionLocal() as db:
        [a] = (await db.execute(select(Attempt))).scalars().all()
        assert a.mode == "practice" and a.study_mode == "de"  # no translation: German


async def test_only_approved_questions_are_served_in_production(api, api2, fake, monkeypatch):
    await seed_bank(n_per_topic=1, topics=(TOPICS[0],), status="in_review")
    await learner_in(api2)
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", False)
    assert (await practise(api2, TOPICS[0])).status_code == 404
    assert (await api2.get("/api/study/overview")).json()["questions_available"] == 0
    # Staging may serve questions in review, never drafts.
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", True)
    assert (await practise(api2, TOPICS[0])).status_code == 200
    async with SessionLocal() as db:
        for q in (await db.execute(select(Question))).scalars():
            q.status = "draft"
        await db.commit()
    assert (await practise(api2, TOPICS[0])).status_code == 404


async def test_questions_of_another_canton_and_communes_are_not_served(api, api2, fake):
    await seed_topics()
    async with SessionLocal() as db:
        db.add(make_question("aargau-1", scope="ag", canton="ag", topic_code=TOPICS[2]))
        db.add(
            make_question("gemeinde-1", scope="zh-winterthur", canton="zh", topic_code=TOPICS[2])
        )
        await db.commit()
    await learner_in(api2)
    assert (await practise(api2, TOPICS[2])).status_code == 404
    r = await api2.post("/api/study/answer", json={"question_id": "aargau-1", "answer": "a"})
    assert r.status_code == 404
    assert (await api2.get("/api/study/question/gemeinde-1")).status_code == 404
