"""Question bank: checks, generation pipeline, review, diagnostic, mastery, practice."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import FakeProvider, set_provider
from app.models import (
    Q_APPROVED,
    Q_AUTO_VERIFIED,
    Q_NEEDS_REVIEW,
    Attempt,
    GenerationBatch,
    LlmCall,
    Question,
    TopicMastery,
)
from app.questions import checks, mastery, pipeline
from tests.conftest import Api, admin_logged_in, learner_logged_in

GOOD_SOLVE = {"final_answer": "", "confidence": "high", "issue": ""}


@pytest.fixture
def fake() -> FakeProvider:
    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)


@pytest.fixture(autouse=True)
def _serve_unreviewed(monkeypatch):
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", True)


OPTIONS = [{"key": k, "text": f"Option {k}"} for k in "ABCD"]


def gen_item(topic="AA-1.2", answer="B", difficulty=3, text=None, **kw):
    item = {
        "topic_code": topic,
        "difficulty": difficulty,
        "question_text": text
        or f"Which option is right about {topic} number {uuid.uuid4().hex[:6]}?",
        "options": OPTIONS,
        "answer": answer,
        "worked_solution": "Option B is right because of the rule; the others are not.",
    }
    item.update(kw)
    return item


async def learner_in(api: Api) -> dict:
    """A learner with an active entitlement for their canton, signed in on `api`."""
    return await learner_logged_in(api, "lina@example.ch", access=True)


async def seed_questions(
    n_per_topic=2, topics=("AA-1.1", "AA-1.2", "AA-2.1"), status=Q_AUTO_VERIFIED
):
    async with SessionLocal() as db:
        for topic in topics:
            for i in range(n_per_topic):
                db.add(
                    Question(
                        module_key="ib_maths_aa",
                        level="both",
                        topic_code=topic,
                        difficulty=2 + (i % 3),
                        qtype="mcq",
                        language="en",
                        question_text=f"Question {i} on {topic}: which option is right?",
                        options=OPTIONS,
                        answer="ABCD"[i % 4],
                        worked_solution="The first option states the rule.",
                        status=status,
                        prompt_version="seed",
                    )
                )
        await db.commit()


# --- Pure checks -------------------------------------------------------------------------------


def test_answer_checks_cover_multiple_choice():
    assert checks.check_answer("b", "B").correct
    assert checks.check_answer(" B. Option B", "B").correct
    assert not checks.check_answer("A", "B").correct
    assert not checks.check_answer("", "B").correct
    assert not checks.check_answer("999", "B").correct


def test_options_valid_needs_four_distinct_options_containing_the_answer():
    assert checks.options_valid(OPTIONS, "B")
    assert checks.options_valid(OPTIONS, "c")
    assert not checks.options_valid(OPTIONS, "E")
    assert not checks.options_valid(OPTIONS[:3], "B")
    assert not checks.options_valid([*OPTIONS[:3], {"key": "A", "text": "again"}], "B")
    assert not checks.options_valid(None, "B")


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


def test_mastery_rating_moves_and_maps_to_percent():
    r = mastery.START_RATING
    assert 45 <= mastery.mastery_percent(r) <= 55
    up = r + mastery.K_EARLY * (1 - mastery.expected_score(r, mastery.question_rating(3)))
    assert mastery.mastery_percent(up) > mastery.mastery_percent(r)
    assert mastery.target_difficulty(600) == 1 and mastery.target_difficulty(1900) == 5


# --- Pipeline ------------------------------------------------------------------------------------


async def test_direct_generation_runs_checks_and_sets_status(api, api2, api3, fake):
    await admin_logged_in(api3)
    good = gen_item(answer="B", text="Which body elects the Federal Council?")
    wrong_solution = gen_item(answer="C", text="Who may launch a popular initiative?")
    good2 = gen_item(answer="D", text="How many cantons does Switzerland have?")
    fake.classifications = [
        {"questions": [good, wrong_solution, good2]},  # generation
        {**GOOD_SOLVE, "final_answer": "B"},  # solve good -> matches
        {**GOOD_SOLVE, "final_answer": "A"},  # solve wrong_solution -> differs
        {**GOOD_SOLVE, "final_answer": "D"},  # solve good2 -> matches
    ]
    r = await api3.post(
        "/api/review/generate",
        json={
            "module_key": "ib_maths_aa",
            "level": "sl",
            "topic_codes": ["AA-1.2"],
            "difficulties": [3],
            "per_request": 3,
            "mode": "direct",
        },
    )
    assert r.status_code == 202, r.text
    batch_id = r.json()["id"]
    async with SessionLocal() as db:
        batch = await db.get(GenerationBatch, uuid.UUID(batch_id))
        assert batch.status == "processed" and batch.questions_created == 3
        qs = (await db.execute(select(Question).order_by(Question.created_at))).scalars().all()
        by_text = {q.question_text[:10]: q for q in qs}
        assert by_text["Which body"].status == Q_AUTO_VERIFIED
        assert by_text["Which body"].spot_check is True  # first 50 per course are spot-checked
        assert by_text["Who may la"].status == Q_NEEDS_REVIEW
        assert "answers_differ" in by_text["Who may la"].check_results["issues"]
        assert by_text["How many c"].status == Q_AUTO_VERIFIED
        calls = (await db.execute(select(LlmCall.purpose))).scalars().all()
        assert sorted(calls) == [
            "question_gen",
            "question_solve",
            "question_solve",
            "question_solve",
        ]
    # Generation prompts carry the course module and examples, nothing personal
    gen_call = next(c for c in fake.calls if c.kind == "structured")
    assert "Style examples" in gen_call.messages[0]["content"]
    assert "multiple-choice" in gen_call.messages[0]["content"]
    assert "topic code AA-1.2" in gen_call.messages[0]["content"]

    # Review queue shows the two that need a look (needs_review + spot check)
    r = await api3.get("/api/review/queue?module_key=ib_maths_aa")
    assert r.status_code == 200 and len(r.json()) == 3
    r = await api3.get("/api/review/stats")
    assert r.json()["modules"][0]["by_status"] == {"auto_verified": 2, "needs_review": 1}


async def test_pipeline_rejects_correct_option_missing_from_the_four(api3, fake):
    await admin_logged_in(api3)
    bad = gen_item(answer="E", text="Which level of government runs the army?")
    fake.classifications = [
        {"questions": [bad]},
        {**GOOD_SOLVE, "final_answer": "E"},  # even a solver that agrees cannot save it
    ]
    r = await api3.post(
        "/api/review/generate",
        json={
            "module_key": "ib_maths_aa",
            "level": "both",
            "topic_codes": ["AA-1.2"],
            "difficulties": [3],
            "per_request": 1,
            "mode": "direct",
        },
    )
    assert r.status_code == 202, r.text
    async with SessionLocal() as db:
        q = (await db.execute(select(Question))).scalars().one()
        assert q.status == Q_NEEDS_REVIEW and q.spot_check is False
        assert "mcq_options_invalid" in q.check_results["issues"]


async def test_batch_generation_is_polled_and_processed(api3, fake):
    await admin_logged_in(api3)
    r = await api3.post(
        "/api/review/generate",
        json={
            "module_key": "ib_physics",
            "level": "both",
            "topic_codes": ["PH-A.1", "PH-A.2"],
            "difficulties": [2, 4],
            "per_request": 1,
            "mode": "batch",
        },
    )
    assert r.status_code == 202, r.text
    batch = r.json()
    assert batch["status"] == "submitted" and batch["requests"] == 4
    # Provider results arrive: one per custom id; solves all agree
    for topic, d in [(t, str(d)) for t in ("PH-A.1", "PH-A.2") for d in (2, 4)]:
        cid = pipeline.custom_id(uuid.UUID(batch["id"]), topic, int(d))
        assert len(cid) <= 64 and all(c.isalnum() or c in "_-" for c in cid)
        text = {
            "2": f"A stone falls for {d} s from rest; find the distance fallen ({topic}).",
            "4": f"A car brakes from 30 m/s to rest in {d} s; find the deceleration ({topic}).",
        }[d] + (" Take g as 9.81." if topic == "PH-A.1" else " Ignore air resistance entirely.")
        fake.batch_answers[cid] = {"questions": [gen_item(topic=topic, answer="B", text=text)]}
    fake.classifications = [{**GOOD_SOLVE, "final_answer": "B"}] * 4
    r = await api3.post(f"/api/review/batches/{batch['id']}/poll")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "processed" and r.json()["questions_created"] == 4
    async with SessionLocal() as db:
        qs = (
            (await db.execute(select(Question).where(Question.status == Q_AUTO_VERIFIED)))
            .scalars()
            .all()
        )
        assert len(qs) == 4
        assert all(q.qtype == "mcq" and len(q.options) == 4 for q in qs)


async def test_admin_reviews_every_module(api, api2, fake):
    await seed_questions(status=Q_NEEDS_REVIEW, topics=("AA-1.1",))
    await admin_logged_in(api)
    modules = {m["module_key"] for m in (await api.get("/api/review/modules")).json()}
    assert {"ib_maths_aa", "ib_physics"} <= modules
    r = await api.get("/api/review/queue?module_key=ib_maths_aa")
    assert r.status_code == 200 and len(r.json()) == 2
    qid = r.json()[0]["id"]
    r = await api.patch(
        f"/api/review/questions/{qid}",
        json={
            "action": "approve",
            "edits": {"answer": "3", "difficulty": 1},
            "note": "Fixed wording",
            "minutes": 4,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == Q_APPROVED and r.json()["difficulty"] == 1
    r = await api.get("/api/review/stats")
    assert r.json()["my_review_minutes"] == 4
    # Learners have no access to the review queue
    await learner_in(api2)
    assert (await api2.get("/api/review/queue")).status_code == 403


# --- Learner side ------------------------------------------------------------------------------


async def test_diagnostic_flow_updates_mastery_and_suggests_next(api, api2, fake):
    await seed_questions(n_per_topic=3)
    await learner_in(api2)
    r = await api2.get("/api/practice/overview?course_key=ib_maths_aa_hl")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["overall"] is None and data["diagnostic"] is None
    assert data["questions_available"] == 9
    assert data["diagnostic_total_estimate"] == 6
    assert {t["topic_code"] for t in data["next"]} == {"AA-1.1", "AA-1.2", "AA-2.1"}

    r = await api2.post("/api/practice/diagnostic/start", json={"course_key": "ib_maths_aa_hl"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "in_progress" and run["total"] == 6  # two per topic with questions
    assert "answer" not in run["question"]

    answers_right = [True, False, True, True, False, False]
    final = None
    for right in answers_right:
        q = run["question"]
        async with SessionLocal() as db:
            stored = await db.get(Question, uuid.UUID(q["id"]))
        answer = stored.answer if right else "999"
        r = await api2.post(
            "/api/practice/attempts",
            json={
                "question_id": q["id"],
                "answer": answer,
                "mode": "diagnostic",
                "diagnostic_id": run["id"],
            },
        )
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["correct"] is right
        assert res["answer"] == stored.answer and res["worked_solution"]
        run = res["diagnostic"]
        final = res
    assert run["status"] == "done"
    assert final["diagnostic"]["summary"]
    r = await api2.get(f"/api/practice/diagnostic/{run['id']}")
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["summary"]
    weakest = final["diagnostic"]["next"][0]
    async with SessionLocal() as db:
        rows = (await db.execute(select(TopicMastery))).scalars().all()
        assert len(rows) == 3 and all(m.attempts == 2 for m in rows)
        lowest = min(rows, key=lambda m: m.rating)
        assert weakest["topic_code"] == lowest.topic_code
        attempts = (await db.execute(select(Attempt))).scalars().all()
        assert len(attempts) == 6 and all(a.mode == "diagnostic" for a in attempts)

    # Overview now has mastery, and a second start does not create a new run
    r = await api2.get("/api/practice/overview?course_key=ib_maths_aa_hl")
    assert r.json()["overall"] is not None and r.json()["diagnostic"]["status"] == "done"
    r = await api2.post("/api/practice/diagnostic/start", json={"course_key": "ib_maths_aa_hl"})
    assert (
        r.status_code == 201 and r.json()["status"] == "in_progress"
    )  # a fresh run is allowed later


async def test_practice_next_and_report_hides_after_two(api, api2, fake):
    await seed_questions(n_per_topic=2, topics=("AA-1.2",))
    await learner_in(api2)
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.status_code == 200, r.text
    q = r.json()
    r = await api2.post(
        "/api/practice/attempts",
        json={"question_id": q["id"], "answer": "wrong", "mode": "practice"},
    )
    assert r.status_code == 200 and r.json()["correct"] is False
    assert r.json()["mastery"]["mastery"] < 50
    r = await api2.post(
        f"/api/practice/questions/{q['id']}/report", json={"comment": "Typo in the question"}
    )
    assert r.status_code == 201 and r.json()["report_count"] == 1
    r = await api2.post(f"/api/practice/questions/{q['id']}/report", json={})
    assert r.json()["report_count"] == 2
    async with SessionLocal() as db:
        stored = await db.get(Question, uuid.UUID(q["id"]))
        assert stored.status == Q_NEEDS_REVIEW  # hidden until a tutor looks
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.json()["id"] != q["id"]
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-5.4")
    assert r.status_code == 404 and r.json()["detail"] == "no_questions"


async def test_practice_round_never_repeats_while_alternatives_exist(api, api2, fake):
    """Staging showed the same question twice in a row once a small topic was used up."""
    await seed_questions(n_per_topic=4, topics=("AA-1.2",))
    await learner_in(api2)
    r = await api2.get("/api/practice/round?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.status_code == 200, r.text
    rnd = r.json()
    assert rnd["topic_name"] == "Exponents and logarithms"
    assert rnd["pool"] == 4 and rnd["unseen"] == 4 and rnd["mastery"] == 50
    ids = [q["id"] for q in rnd["questions"]]
    assert len(ids) == 4 and len(set(ids)) == 4  # the round is as long as the pool allows

    # Answer the whole round: the first two wrong, the last two right.
    for i, qid in enumerate(ids):
        async with SessionLocal() as db:
            stored = await db.get(Question, uuid.UUID(qid))
        r = await api2.post(
            "/api/practice/attempts",
            json={
                "question_id": qid,
                "answer": "999" if i < 2 else stored.answer,
                "mode": "practice",
            },
        )
        assert r.status_code == 200, r.text
        m = r.json()["mastery"]
        assert "previous" in m and m["previous"] != m["mastery"]

    # Second round: nothing is new, the wrong ones come first, the last answered comes last.
    r = await api2.get("/api/practice/round?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    again = [q["id"] for q in r.json()["questions"]]
    assert r.json()["unseen"] == 0 and len(set(again)) == 4
    assert set(again[:2]) == set(ids[:2]) and again[-1] == ids[-1]

    # /next, used by the chat check panel, follows the same order.
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.json()["id"] in ids[:2]
    r = await api2.get("/api/practice/round?course_key=ib_maths_aa_hl&topic_code=AA-5.4")
    assert r.status_code == 404 and r.json()["detail"] == "no_questions"


async def test_attempt_is_marked_by_option_key_without_any_ai_call(api, api2, fake):
    await seed_questions(n_per_topic=1, topics=("AA-1.2",))
    await learner_in(api2)
    async with SessionLocal() as db:
        stored = (await db.execute(select(Question))).scalars().one()
    r = await api2.post(
        "/api/practice/attempts",
        json={"question_id": str(stored.id), "answer": stored.answer.lower(), "mode": "practice"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True and body["score"] == 1.0
    assert body["answer_text"] == "Option A" and "feedback" not in body and "ai_marked" not in body
    assert fake.calls == []


async def test_production_serves_only_approved(api, api2, fake, monkeypatch):
    await seed_questions(n_per_topic=1, topics=("AA-1.2",), status=Q_AUTO_VERIFIED)
    await learner_in(api2)
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", False)
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.status_code == 404
    r = await api2.get("/api/practice/overview?course_key=ib_maths_aa_hl")
    assert r.json()["questions_available"] == 0


def test_question_item_schema_is_multiple_choice_only():
    props = pipeline.QUESTION_ITEM_SCHEMA["properties"]
    for gone in ("qtype", "unit", "tolerance", "mark_scheme", "marks", "calculator_allowed"):
        assert gone not in props
    assert "options" in props and "options" in pipeline.QUESTION_ITEM_SCHEMA["required"]


def test_structured_output_schemas_avoid_unsupported_keywords():
    """The provider rejects minimum/maximum on numbers in output schemas (seen on staging)."""
    import json as _json

    for schema in (pipeline.GEN_SCHEMA, pipeline.SOLVE_SCHEMA):
        text = _json.dumps(schema)
        assert "minimum" not in text and "maximum" not in text
