"""Question bank: checks, generation pipeline, review, diagnostic, mastery, practice."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.llm.client import FakeProvider, set_provider
from app.models import (
    Q_APPROVED,
    Q_AUTO_VERIFIED,
    Q_NEEDS_REVIEW,
    Attempt,
    Family,
    GenerationBatch,
    LlmCall,
    Question,
    TopicMastery,
    User,
)
from app.questions import checks, mastery, pipeline
from tests.conftest import Api, admin_logged_in, create_staff, login, parent_logged_in

STUDENT = {
    "first_name": "Lina",
    "year_of_birth": 2010,
    "curriculum": "ib_dp",
    "courses": ["ib_maths_aa_hl"],
    "locale": "en",
    "username": "lina",
    "password": "Lina-secret-99",
}

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


def gen_item(topic="AA-1.2", qtype="short", answer="9", difficulty=3, text=None, **kw):
    item = {
        "topic_code": topic,
        "qtype": qtype,
        "difficulty": difficulty,
        "calculator_allowed": False,
        "question_text": text or f"Solve something about {topic} number {uuid.uuid4().hex[:6]}.",
        "options": [],
        "answer": answer,
        "unit": "",
        "tolerance": 0.01,
        "worked_solution": "Work it out step by step.",
        "mark_scheme": "",
        "marks": 1,
    }
    item.update(kw)
    return item


async def student_logged_in(api: Api, api2: Api) -> dict:
    await parent_logged_in(api)
    r = await api.post("/api/family/students", json=STUDENT)
    assert r.status_code == 201, r.text
    async with SessionLocal() as db:
        family = (await db.execute(select(Family))).scalars().one()
        family.free_access_until = utcnow() + timedelta(days=30)
        await db.commit()
    r = await login(api2, "lina", "Lina-secret-99")
    assert r.status_code == 200, r.text
    return r.json()["me"]


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
                        qtype="short",
                        language="en",
                        question_text=f"Question {i} on {topic}: what is 3 + {i}?",
                        answer=str(3 + i),
                        worked_solution="Add them.",
                        status=status,
                        prompt_version="seed",
                    )
                )
        await db.commit()


# --- Pure checks -------------------------------------------------------------------------------


def test_answer_checks_cover_numbers_expressions_and_mcq():
    assert checks.check_answer("numeric", "0.5", "0.500", 0.01).correct
    assert checks.check_answer("numeric", "0,5", "0.5", 0.01).correct  # Swiss decimal comma
    assert checks.check_answer("numeric", "5.77 x 10^3", "5771", 0.01).correct
    assert not checks.check_answer("numeric", "0.6", "0.5", 0.01).correct
    assert checks.check_answer("short", "2x+3", "3 + 2x", None).correct
    assert checks.check_answer("short", "\\frac{1}{2}", "0.5", None).correct
    assert checks.check_answer("short", "x = -1 or x = 2", "x = 2 or x = -1", None).correct
    assert not checks.check_answer("short", "2x+4", "2x+3", None).correct
    assert checks.check_answer("short", "k = 9", "9", None).correct
    assert checks.check_answer("mcq", "b", "B", None).correct
    assert not checks.check_answer("mcq", "A", "B", None).correct
    assert not checks.check_answer("short", "", "9", None).correct


def test_duplicate_and_tolerance_checks():
    dup, best = checks.is_near_duplicate(
        "Find the gradient of the line through (1, 2) and (3, 8).",
        ["Find the gradient of the line through (1, 2) and (3, 8) and its intercept."],
    )
    assert dup and best > 0.6
    assert not checks.is_near_duplicate("Integrate x e^{2x}", ["Solve 2^x = 10"])[0]
    assert checks.rounds_consistently("0.500", 0.01)
    assert not checks.rounds_consistently(
        "5771", 0.00001
    )  # tighter than half a unit in the last place


def test_mastery_rating_moves_and_maps_to_percent():
    r = mastery.START_RATING
    assert 45 <= mastery.mastery_percent(r) <= 55
    up = r + mastery.K_EARLY * (1 - mastery.expected_score(r, mastery.question_rating(3)))
    assert mastery.mastery_percent(up) > mastery.mastery_percent(r)
    assert mastery.target_difficulty(600) == 1 and mastery.target_difficulty(1900) == 5


# --- Pipeline ------------------------------------------------------------------------------------


async def test_direct_generation_runs_checks_and_sets_status(api, api2, api3, fake):
    await admin_logged_in(api3)
    good = gen_item(answer="9", text="Find k so that x^2 - 6x + k has one real root.")
    wrong_solution = gen_item(answer="7", text="Find the value of 3 + 4 squared minus something.")
    mcq = gen_item(
        qtype="mcq",
        answer="B",
        text="Which equals log_3 81 - log_3 9?",
        options=[
            {"key": "A", "text": "log_3 72"},
            {"key": "B", "text": "2"},
            {"key": "C", "text": "9"},
            {"key": "D", "text": "log_3 90"},
        ],
    )
    fake.classifications = [
        {"questions": [good, wrong_solution, mcq]},  # generation
        {**GOOD_SOLVE, "final_answer": "k = 9"},  # solve good -> matches
        {**GOOD_SOLVE, "final_answer": "49"},  # solve wrong_solution -> differs
        {**GOOD_SOLVE, "final_answer": "B"},  # solve mcq -> matches
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
        assert by_text["Find k so "].status == Q_AUTO_VERIFIED
        assert by_text["Find k so "].spot_check is True  # first 50 per course are spot-checked
        assert by_text["Find the v"].status == Q_NEEDS_REVIEW
        assert "answers_differ" in by_text["Find the v"].check_results["issues"]
        assert by_text["Which equa"].status == Q_AUTO_VERIFIED
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
    assert "topic code AA-1.2" in gen_call.messages[0]["content"]

    # Review queue shows the two that need a look (needs_review + spot check)
    r = await api3.get("/api/review/queue?module_key=ib_maths_aa")
    assert r.status_code == 200 and len(r.json()) == 3
    r = await api3.get("/api/review/stats")
    assert r.json()["modules"][0]["by_status"] == {"auto_verified": 2, "needs_review": 1}


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
        fake.batch_answers[cid] = {
            "questions": [gen_item(topic=topic, qtype="numeric", answer="24", unit="m", text=text)]
        }
    fake.classifications = [{**GOOD_SOLVE, "final_answer": "24"}] * 4
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
        assert all(q.tolerance >= 0.02 for q in qs)  # widened: "24" is given to 2 s.f.


async def test_tutor_reviews_only_tagged_courses(api, api2, fake):
    await seed_questions(status=Q_NEEDS_REVIEW, topics=("AA-1.1",))
    tutor = await create_staff("tutor@sst-example.ch", role="tutor", totp=True)
    async with SessionLocal() as db:
        t = await db.get(User, tutor.id)
        t.tagged_courses = ["ib_physics_hl"]
        await db.commit()
    import pyotp

    r = await login(api, "tutor@sst-example.ch", "Staff-pass-123")
    assert r.json()["status"] == "mfa_required"
    r = await api.post("/api/auth/totp/verify", json={"code": pyotp.TOTP(tutor.totp_secret).now()})
    assert r.status_code == 200
    r = await api.get("/api/review/queue")
    assert r.status_code == 200 and r.json() == []  # physics tutor sees no maths questions
    r = await api.get("/api/review/queue?module_key=ib_maths_aa")
    assert r.status_code == 403
    r = await api.post(
        "/api/review/generate", json={"module_key": "ib_physics", "topic_codes": ["PH-A.1"]}
    )
    assert r.status_code == 403  # admin only

    async with SessionLocal() as db:
        t = await db.get(User, tutor.id)
        t.tagged_courses = ["ib_maths_aa_hl"]
        await db.commit()
    r = await api.get("/api/review/queue")
    assert len(r.json()) == 2
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


# --- Student side ------------------------------------------------------------------------------


async def test_diagnostic_flow_updates_mastery_and_suggests_next(api, api2, fake):
    await seed_questions(n_per_topic=3)
    await student_logged_in(api, api2)
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
    await student_logged_in(api, api2)
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


async def test_structured_answers_are_ai_marked(api, api2, fake):
    async with SessionLocal() as db:
        db.add(
            Question(
                module_key="ib_maths_aa",
                level="hl",
                topic_code="AA-5.2",
                difficulty=4,
                qtype="structured",
                language="en",
                question_text="Integrate x e^{2x} and hence find an area.",
                answer="(x/2)e^{2x} - (1/4)e^{2x} + C; (e^2+1)/4",
                worked_solution="By parts.",
                mark_scheme="M1 parts; A1 v; M1 apply; A1 result; M1 limits; A1 area",
                marks=6,
                status=Q_APPROVED,
            )
        )
        await db.commit()
        qid = (await db.execute(select(Question.id))).scalar_one()
    await student_logged_in(api, api2)
    fake.classifications = [
        {"score": 0.5, "feedback": "Good method, the constant was lost.", "correct": False}
    ]
    r = await api2.post(
        "/api/practice/attempts",
        json={
            "question_id": str(qid),
            "answer": "I used parts and got x e^{2x}/2",
            "mode": "practice",
        },
    )
    assert r.status_code == 200, r.text
    assert (
        r.json()["ai_marked"] is True and r.json()["score"] == 0.5 and r.json()["correct"] is False
    )
    assert "constant" in r.json()["feedback"]
    mark_call = [c for c in fake.calls if c.kind == "structured"][-1]
    assert "<answer>" in mark_call.messages[0]["content"]
    assert "Lina" not in mark_call.messages[0]["content"]


async def test_production_serves_only_approved(api, api2, fake, monkeypatch):
    await seed_questions(n_per_topic=1, topics=("AA-1.2",), status=Q_AUTO_VERIFIED)
    await student_logged_in(api, api2)
    monkeypatch.setattr(get_settings(), "serve_unreviewed_questions", False)
    r = await api2.get("/api/practice/next?course_key=ib_maths_aa_hl&topic_code=AA-1.2")
    assert r.status_code == 404
    r = await api2.get("/api/practice/overview?course_key=ib_maths_aa_hl")
    assert r.json()["questions_available"] == 0


def test_structured_output_schemas_avoid_unsupported_keywords():
    """The provider rejects minimum/maximum on numbers in output schemas (seen on staging)."""
    import json as _json

    for schema in (pipeline.GEN_SCHEMA, pipeline.SOLVE_SCHEMA, pipeline.MARK_SCHEMA):
        text = _json.dumps(schema)
        assert "minimum" not in text and "maximum" not in text
