"""Question bank on the canton's topics: checks, mastery, diagnostic, practice rounds,
attempts and reports. Content import and review are in test_content.py."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import FakeProvider, set_provider
from app.models import Attempt, Question, TopicMastery
from app.questions import checks, mastery
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


def test_mastery_rating_uses_difficulties_one_to_three():
    r = mastery.START_RATING
    assert mastery.mastery_percent(r) == 50
    assert [mastery.question_rating(d) for d in (1, 2, 3)] == [800, 1200, 1600]
    assert mastery.question_rating(5) == 1600  # clamped
    up = r + mastery.K_EARLY * (1 - mastery.expected_score(r, mastery.question_rating(2)))
    assert mastery.mastery_percent(up) > mastery.mastery_percent(r)
    assert mastery.target_difficulty(600) == 1 and mastery.target_difficulty(1900) == 3
    assert mastery.target_difficulty(r) == 2


# --- Learner side ------------------------------------------------------------------------------


async def test_overview_lists_the_canton_topics_in_file_order(api, api2, fake):
    await seed_bank(n_per_topic=2)
    await seed_topics("ag", (("bund.demokratie.foederalismus", "federal", "F", "F"),))
    await learner_in(api2)
    r = await api2.get("/api/practice/overview")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["canton"] == "zh" and data["overall"] is None and data["diagnostic"] is None
    assert [t["topic_code"] for t in data["topics"]] == list(TOPICS)
    assert data["topics"][0]["topic_name"] == "Federalism"  # English interface
    assert data["topics"][0]["name_de"] == "Föderalismus" and data["topics"][2]["scope"] == "canton"
    assert data["questions_available"] == 6
    assert data["diagnostic_total_estimate"] == 3  # one per topic by default


async def test_diagnostic_flow_updates_mastery_and_suggests_next(api, api2, fake, monkeypatch):
    monkeypatch.setattr(get_settings(), "diagnostic_questions_per_topic", 2)
    await seed_bank(n_per_topic=3)
    await learner_in(api2)
    r = await api2.post("/api/practice/diagnostic/start")
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "in_progress" and run["total"] == 6 and run["canton"] == "zh"
    assert "answer" not in run["question"]
    assert [o["key"] for o in run["question"]["options"]] == ["a", "b", "c", "d"]

    answers_right = [True, False, True, True, False, False]
    final = None
    for right in answers_right:
        q = run["question"]
        async with SessionLocal() as db:
            stored = await db.get(Question, q["id"])
        r = await api2.post(
            "/api/practice/attempts",
            json={
                "question_id": q["id"],
                "answer": stored.correct if right else "x",
                "mode": "diagnostic",
                "diagnostic_id": run["id"],
            },
        )
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["correct"] is right
        assert res["answer"] == stored.correct and res["explanation"].startswith("Gemeint")
        run = res["diagnostic"]
        final = res
    assert run["status"] == "done" and final["diagnostic"]["summary"]
    r = await api2.get(f"/api/practice/diagnostic/{run['id']}")
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["summary"]
    weakest = final["diagnostic"]["next"][0]
    async with SessionLocal() as db:
        rows = (await db.execute(select(TopicMastery))).scalars().all()
        assert len(rows) == 3 and all(m.attempts == 2 for m in rows)
        assert weakest["topic_code"] == min(rows, key=lambda m: m.rating).topic_code
        attempts = (await db.execute(select(Attempt))).scalars().all()
        assert len(attempts) == 6 and all(a.mode == "diagnostic" for a in attempts)

    r = await api2.get("/api/practice/overview")
    assert r.json()["overall"] is not None and r.json()["diagnostic"]["status"] == "done"
    r = await api2.post("/api/practice/diagnostic/start")
    assert r.status_code == 201 and r.json()["status"] == "in_progress"  # a fresh run later


async def test_practice_next_and_report_hides_after_two(api, api2, fake):
    await seed_bank(n_per_topic=2, topics=(TOPICS[0],))
    await learner_in(api2)
    r = await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")
    assert r.status_code == 200, r.text
    q = r.json()
    r = await api2.post(
        "/api/practice/attempts", json={"question_id": q["id"], "answer": "x", "mode": "practice"}
    )
    assert r.status_code == 200 and r.json()["correct"] is False
    assert r.json()["mastery"]["mastery"] < 50
    r = await api2.post(f"/api/practice/questions/{q['id']}/report", json={"comment": "Tippfehler"})
    assert r.status_code == 201 and r.json()["report_count"] == 1
    r = await api2.post(f"/api/questions/{q['id']}/report", json={})
    assert r.json()["report_count"] == 2
    async with SessionLocal() as db:
        stored = await db.get(Question, q["id"])
        assert stored.status == "in_review" and stored.file_sync_pending is True
    r = await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")
    assert r.json()["id"] != q["id"]
    r = await api2.get("/api/practice/next?topic_code=bund.gibt_es_nicht")
    assert r.status_code == 404 and r.json()["detail"] == "no_questions"
    r = await api2.post("/api/questions/gibt-es-nicht/report", json={})
    assert r.status_code == 404


async def test_practice_round_never_repeats_while_alternatives_exist(api, api2, fake):
    await seed_bank(n_per_topic=4, topics=(TOPICS[0],))
    await learner_in(api2)
    r = await api2.get(f"/api/practice/round?topic_code={TOPICS[0]}")
    assert r.status_code == 200, r.text
    rnd = r.json()
    assert rnd["topic_name"] == "Federalism"
    assert rnd["pool"] == 4 and rnd["unseen"] == 4 and rnd["mastery"] == 50
    ids = [q["id"] for q in rnd["questions"]]
    assert len(ids) == 4 and len(set(ids)) == 4

    for i, qid in enumerate(ids):
        async with SessionLocal() as db:
            stored = await db.get(Question, qid)
        r = await api2.post(
            "/api/practice/attempts",
            json={"question_id": qid, "answer": "x" if i < 2 else stored.correct},
        )
        assert r.status_code == 200, r.text
        m = r.json()["mastery"]
        # An easy question moves the rating by less than one percentage point at times.
        assert m["mastery"] <= m["previous"] if i < 2 else m["mastery"] >= m["previous"]

    r = await api2.get(f"/api/practice/round?topic_code={TOPICS[0]}")
    again = [q["id"] for q in r.json()["questions"]]
    assert r.json()["unseen"] == 0 and len(set(again)) == 4
    assert set(again[:2]) == set(ids[:2]) and again[-1] == ids[-1]
    r = await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")
    assert r.json()["id"] in ids[:2]
    r = await api2.get("/api/practice/round?topic_code=bund.gibt_es_nicht")
    assert r.status_code == 404 and r.json()["detail"] == "no_questions"


async def test_attempt_is_marked_by_option_key_without_any_ai_call(api, api2, fake):
    [qid] = await seed_bank(n_per_topic=1, topics=(TOPICS[0],))
    await learner_in(api2)
    r = await api2.post("/api/practice/attempts", json={"question_id": qid, "answer": "A"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True and body["score"] == 1.0
    assert body["answer"] == "a" and body["answer_text"] == "Bund"
    assert "worked_solution" not in body and fake.calls == []


async def test_only_approved_questions_are_served_in_production(api, api2, fake, monkeypatch):
    await seed_bank(n_per_topic=1, topics=(TOPICS[0],), status="in_review")
    await learner_in(api2)
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", False)
    r = await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")
    assert r.status_code == 404
    assert (await api2.get("/api/practice/overview")).json()["questions_available"] == 0
    # Staging may serve questions in review, never drafts.
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", True)
    assert (await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")).status_code == 200
    async with SessionLocal() as db:
        for q in (await db.execute(select(Question))).scalars():
            q.status = "draft"
        await db.commit()
    assert (await api2.get(f"/api/practice/next?topic_code={TOPICS[0]}")).status_code == 404


async def test_questions_of_another_canton_and_communes_are_not_served(api, api2, fake):
    await seed_topics()
    async with SessionLocal() as db:
        db.add(make_question("aargau-1", scope="ag", canton="ag", topic_code=TOPICS[2]))
        db.add(
            make_question("gemeinde-1", scope="zh-winterthur", canton="zh", topic_code=TOPICS[2])
        )
        await db.commit()
    await learner_in(api2)
    assert (await api2.get(f"/api/practice/next?topic_code={TOPICS[2]}")).status_code == 404
    r = await api2.post("/api/practice/attempts", json={"question_id": "aargau-1", "answer": "a"})
    assert r.status_code == 404


async def test_practice_needs_a_pass(api, fake):
    await seed_bank(n_per_topic=1, topics=(TOPICS[0],))
    await learner_logged_in(api, "olaf@example.ch")
    assert (await api.get("/api/practice/overview")).status_code == 200
    r = await api.get(f"/api/practice/round?topic_code={TOPICS[0]}")
    assert r.status_code == 403 and r.json()["detail"] == "no_access"
    r = await api.post("/api/practice/diagnostic/start")
    assert r.status_code == 403
