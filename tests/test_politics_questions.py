"""Current-affairs questions (D-074): expiry, the app's endpoints, and that they never enter
the question bank, the free sample set, the mock test, attempts, progress or readiness."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.db import SessionLocal, utcnow
from app.models import (
    CA_OK,
    CA_RETIRED,
    Article,
    Attempt,
    CurrentAffairsQuestion,
    QuestionProgress,
)
from app.politics import questions
from app.study import selection
from tests.conftest import learner_logged_in, make_question, seed_topics


def ca_question(**overrides) -> CurrentAffairsQuestion:
    fields = {
        "canton": "zh",
        "page_key": "zh-week-2026-46",
        "page_kind": "roundup",
        "page_revision": 1,
        "page_paths": {
            "en": "/en/politics/zh/canton-of-zurich-week-46-2026/",
            "de": "/de/politik/zh/kanton-zuerich-woche-46-2026/",
        },
        "refers_to": date(2026, 11, 12),
        "expires_at": utcnow() + timedelta(days=100),
        "position": 1,
        "question_de": "Welche Behörde beschloss im November 2026 die Energiestrategie?",
        "options_de": {
            "a": "Der Regierungsrat",
            "b": "Der Bundesrat",
            "c": "Der Stadtrat",
            "d": "Das Obergericht",
        },  # fmt: skip
        "correct": "a",
        "explanation_de": "Der Regierungsrat hat die Energiestrategie beschlossen.",
        "translations": {
            "en": {
                "question": "Which authority adopted the energy strategy in November 2026?",
                "options": {
                    "a": "The Regierungsrat",
                    "b": "The Federal Council",
                    "c": "The Stadtrat",
                    "d": "The High Court",
                },  # fmt: skip
                "explanation": "The cantonal government adopted it.",
            }
        },
        "status": CA_OK,
        "check": {},
    }
    fields.update(overrides)
    return CurrentAffairsQuestion(**fields)


def test_expiry_dates():
    week = Article(key="k", kind="roundup", plan={"period_end": "2026-11-12"})
    vote = Article(key="v", kind="vote", plan={"vote_date": "2027-02-28"})
    assert questions.refers_to(week) == date(2026, 11, 12)
    assert questions.expires_at(week).date() in (date(2027, 5, 13), date(2027, 5, 14))
    assert questions.expires_at(vote) - questions.expires_at(week) > timedelta(days=200)
    assert questions.refers_to(vote) == date(2027, 2, 28)


async def test_only_checked_current_questions_of_the_canton_are_served(api):
    async with SessionLocal() as db:
        db.add(ca_question())
        db.add(ca_question(question_de="Abgelaufen?", expires_at=utcnow() - timedelta(minutes=1)))
        db.add(ca_question(question_de="Ersetzt?", status=CA_RETIRED))
        db.add(ca_question(question_de="Bern?", canton="be"))
        await db.commit()
    await learner_logged_in(api)  # no pass: current affairs are free
    r = await api.get("/api/study/current-affairs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    q = body["questions"][0]
    assert q["refers_to"] == "2026-11-12"
    assert q["page_url"].endswith("/en/politics/zh/canton-of-zurich-week-46-2026/")
    assert q["german"]["question"].startswith("Welche Behörde")
    assert q["translation"]["lang"] == "en"
    assert "answer" not in q and "explanation_de" not in q  # nothing given away

    r = await api.post(
        "/api/study/current-affairs/answer", json={"question_id": q["id"], "answer": "b"}
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["correct"] is False and out["answer"] == "a"
    assert out["explanation"]["text"] == "The cantonal government adopted it."
    r = await api.post(
        "/api/study/current-affairs/answer", json={"question_id": q["id"], "answer": "a"}
    )
    assert r.json()["correct"] is True
    # Nothing is recorded: no attempt, no progress.
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Attempt)) == 0
        assert await db.scalar(select(func.count()).select_from(QuestionProgress)) == 0


async def test_expired_question_cannot_be_answered(api):
    async with SessionLocal() as db:
        q = ca_question(expires_at=utcnow() - timedelta(seconds=1))
        db.add(q)
        await db.commit()
        qid = str(q.id)
    await learner_logged_in(api)
    r = await api.post(
        "/api/study/current-affairs/answer", json={"question_id": qid, "answer": "a"}
    )
    assert r.status_code == 404


async def test_hidden_when_there_are_none(api):
    await learner_logged_in(api)
    r = await api.get("/api/study/current-affairs")
    assert r.json() == {"canton": "zh", "count": 0, "questions": []}


async def test_never_part_of_the_bank_sample_mock_or_readiness(api):
    await seed_topics()
    async with SessionLocal() as db:
        for i in range(3):
            db.add(make_question(f"q-bank-{i}"))
        for i in range(5):
            db.add(ca_question(question_de=f"Aktuell {i}?", position=i))
        await db.commit()
    await learner_logged_in(api)
    overview = (await api.get("/api/study/overview")).json()
    assert overview["questions_total"] == 3
    assert all(t["topic_code"] != "current_affairs" for t in overview["topics"])
    async with SessionLocal() as db:
        servable = await selection.servable_questions(db, "zh")
        assert {q.id for q in servable} == {"q-bank-0", "q-bank-1", "q-bank-2"}
        assert len(selection.sample_of(servable)) == 3
    r = await api.get("/api/study/practise")
    ids = {q["id"] for q in r.json()["questions"]}
    assert ids <= {"q-bank-0", "q-bank-1", "q-bank-2"}
    ca_ids = {str(q.id) for q in await _all_ca()}
    r = await api.post("/api/mock/start")
    if r.status_code == 201:
        assert not (set(r.json().get("question_ids") or []) & ca_ids)
        assert all(q["id"] not in ca_ids for q in r.json().get("questions") or [])
    before = overview["readiness"]["value"]
    q = (await api.get("/api/study/current-affairs")).json()["questions"][0]
    await api.post(
        "/api/study/current-affairs/answer", json={"question_id": q["id"], "answer": "a"}
    )
    after = (await api.get("/api/study/overview")).json()["readiness"]["value"]
    assert after == before


async def _all_ca():
    async with SessionLocal() as db:
        return (await db.execute(select(CurrentAffairsQuestion))).scalars().all()


async def test_generation_keeps_only_checked_questions_and_retires_old_ones(politics):
    now = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
    a = Article(
        key="zh-week-2026-46", kind="roundup", category="politics", canton="zh",
        publish_at=now, status="published", plan={"period_end": "2026-11-12", "set_canton": "zh"},
        english={"title": "T", "summary": ["s"], "body": "b"}, translations={}, reviews=[],
        feedback=[], sources_read=[], live_urls={"en": "https://viapunt.example/en/politics/zh/x/"},
        live_files={}, review_nonce="n", revision=1, published_revision=1,
    )  # fmt: skip
    async with SessionLocal() as db:
        db.add(a)
        db.add(ca_question(question_de="Alt?"))
        await db.commit()
        n, note = await questions.generate(db, a, now)
    assert n == 2, note
    rows = await _all_ca()
    assert sorted(r.status for r in rows) == [CA_OK, CA_OK, CA_RETIRED]
    fresh = [r for r in rows if r.status == CA_OK]
    assert all(r.page_paths == {"en": "/en/politics/zh/x/"} for r in fresh)
    assert all(r.check["verdict"]["answer"] == r.correct for r in fresh)


async def test_generation_stores_nothing_when_the_check_fails(politics):
    politics["fake"].json_replies["politics/question_check"] = {"checks": []}
    now = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
    a = Article(
        key="vote-zh-2027-02-28-x", kind="vote", category="politics", canton="zh",
        publish_at=now, status="published", plan={"vote_date": "2027-02-28"},
        english={"title": "T", "summary": ["s"], "body": "b"}, translations={}, reviews=[],
        feedback=[], sources_read=[], live_urls={}, live_files={}, review_nonce="n",
    )  # fmt: skip
    async with SessionLocal() as db:
        db.add(a)
        await db.commit()
        n, note = await questions.generate(db, a, now)
    assert n == 0 and "check" in note
    assert await _all_ca() == []
