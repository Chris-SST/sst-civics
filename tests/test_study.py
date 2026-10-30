"""Study modes, progress per question and mode, readiness, Learn, Practise (spaced repetition,
weak-topic weighting) and the mock test, with the free-tier limits. Time is frozen through
app.study.clock."""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Attempt,
    GlossaryTerm,
    MockRun,
    Question,
    QuestionProgress,
    QuestionTranslation,
    Topic,
    User,
)
from app.questions.mastery import TopicCounts, readiness_percent, topic_mastery_percent
from app.study import clock, mock, selection
from tests.conftest import Api, learner_logged_in, make_question, seed_topics

FED_A = "bund.demokratie.foederalismus"
FED_B = "bund.demokratie.volksrechte"
CANTON = "kanton.demokratie.kantonsrat"
COMMUNE = "gemeinde.leistungen"
TOPICS = (
    (FED_A, "federal", "Föderalismus", "Federalism"),
    (FED_B, "federal", "Volksrechte", "Popular rights"),
    (CANTON, "canton", "Kantonsrat", "Cantonal Parliament"),
    (COMMUNE, "commune", "Leistungen der Gemeinde", "Communal services"),
)
TOPIC_BY_SLUG = {code.split(".")[-1]: code for code, *_ in TOPICS}
EMAIL = "mira@example.ch"
RNG = random.Random  # noqa: S311 - seeded for repeatable tests


class FrozenClock:
    def __init__(self, start: datetime):
        self.t = start

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kw) -> None:
        self.t += timedelta(**kw)


@pytest.fixture
def frozen(monkeypatch) -> FrozenClock:
    c = FrozenClock(datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
    monkeypatch.setattr(clock, "now", c)
    return c


@pytest.fixture
def mock_format(tmp_path: Path, monkeypatch) -> Path:
    """A topic file with Zurich's test block, read by the mock test."""
    root = tmp_path / "content"
    (root / "topics").mkdir(parents=True)
    data = {
        "canton": "zh",
        "test": {
            "questions": 50,
            "minutes": 60,
            "pass_mark": 30,
            "proportions": {"federal": 0.78, "canton": 0.16, "commune": 0.06},
        },
        "topics": [
            {"code": c, "scope": s, "name_de": d, "name_en": e, "target_questions": 5}
            for c, s, d, e in TOPICS
        ],
    }
    (root / "topics" / "zh.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(get_settings(), "content_dir", str(root))
    return root


async def seed(per_topic: dict[str, int], *, targets: dict[str, int] | None = None) -> list[str]:
    """The four topics and `per_topic` approved questions on each; ids are <topic>-<nn>."""
    await seed_topics(topics=TOPICS)
    ids = []
    async with SessionLocal() as db:
        if targets:
            for t in (await db.execute(select(Topic))).scalars():
                t.target_questions = targets.get(t.code, t.target_questions)
        for code, n in per_topic.items():
            federal = code.startswith("bund.")
            for i in range(n):
                q = make_question(
                    f"{code.split('.')[-1]}-{i:02d}",
                    topic_code=code,
                    scope="federal" if federal else "zh",
                    canton=None if federal else "zh",
                    difficulty=1 + (i % 3),
                    correct="abcd"[i % 4],
                    question_de=f"Frage {i} zum Bund und zu {code}?",
                )
                db.add(q)
                ids.append(q.id)
        await db.commit()
    return ids


async def translate(qid: str, lang: str = "en", **overrides) -> None:
    async with SessionLocal() as db:
        fields = {
            "question_id": qid,
            "lang": lang,
            "source_version": 1,
            "question": f"Question {qid} about the Confederation?",
            "options": {"a": "Confederation", "b": "Canton", "c": "Commune", "d": "District"},
            "explanation": "It is the Confederation, the highest level.",
            "status": "approved",
            "content_hash": "seed",
        }
        fields.update(overrides)
        db.add(QuestionTranslation(**fields))
        await db.commit()


async def correct_of(qid: str) -> str:
    async with SessionLocal() as db:
        return (await db.get(Question, qid)).correct


async def answer(api: Api, qid: str, right: bool = True, **extra):
    key = await correct_of(qid)
    wrong = "b" if key == "a" else "a"
    r = await api.post(
        "/api/study/answer", json={"question_id": qid, "answer": key if right else wrong, **extra}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def paid(api: Api) -> dict:
    return await learner_logged_in(api, EMAIL, access=True)


async def free(api: Api, email: str = EMAIL) -> dict:
    return await learner_logged_in(api, email)


# --- Pure rules ------------------------------------------------------------------------------


def test_topic_mastery_and_readiness_formulas():
    assert topic_mastery_percent(0, 0, 0) == 0
    assert topic_mastery_percent(known=2, understood=2, total=4) == 50
    assert topic_mastery_percent(known=1, understood=3, total=4) == 50  # 1 + 2 halves
    assert topic_mastery_percent(known=0, understood=4, total=4) == 50
    rows = [
        TopicCounts("a", target=30, total=10, understood=10, known=10),  # all known
        TopicCounts("b", target=10, total=10, understood=10, known=0),  # understood only
    ]
    assert readiness_percent(rows) == 75  # weighted by targets 30 and 10, known only
    assert readiness_percent([TopicCounts("x", 0, 4, 4, 2), TopicCounts("y", 0, 0, 0, 0)]) == 25
    assert readiness_percent([]) == 0


def test_mock_allocation_follows_proportions_and_caps():
    assert mock.largest_remainder(50, {"federal": 0.78, "canton": 0.16, "commune": 0.06}) == {
        "canton": 8,
        "commune": 3,
        "federal": 39,
    }
    # Too few commune questions: the shortfall goes to the other scopes.
    out = mock.allocate(
        50,
        {"federal": 0.78, "canton": 0.16, "commune": 0.06},
        {"federal": 99, "canton": 99, "commune": 1},
    )
    assert out["commune"] == 1 and sum(out.values()) == 50 and out["federal"] > 39
    # No weights at all: shared by spare room.
    assert mock.allocate(5, {"a": 0.0}, {"a": 3, "b": 9}) == {"a": 1, "b": 4}
    assert mock.allocate(5, {"a": 1.0}, {"a": 3, "b": 9}) == {"a": 3, "b": 2}


def test_plan_round_prefers_weak_topics_and_puts_recent_last():
    now = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    qs = [make_question(f"strong-{i}", topic_code="s") for i in range(6)]
    qs += [make_question(f"weak-{i}", topic_code="w") for i in range(6)]
    picked = selection.plan_round(qs, {}, {"s": 90, "w": 0}, 6, now, RNG(1))
    count = Counter(q.topic_code for q in picked)
    assert count["w"] > count["s"] >= 1
    recent = QuestionProgress(question_id="weak-0", last_answered_at=now, due_at=now)
    picked = selection.plan_round(qs, {"weak-0": recent}, {"w": 0}, 12, now, RNG(1))
    assert picked[-1].id == "weak-0" and len({q.id for q in picked}) == 12


# --- Study modes -------------------------------------------------------------------------------


async def test_modes_render_the_contract_and_fall_back_without_translation(api):
    [q1, q2] = await seed({FED_A: 2})
    await translate(q1)
    async with SessionLocal() as db:
        db.add(GlossaryTerm(term="Bund", lang="en", translation="Confederation", note="Federal."))
        db.add(GlossaryTerm(term="Ständerat", lang="en", translation="Council of States"))
        await db.commit()
    await paid(api)

    own = (await api.get(f"/api/study/question/{q1}?mode=own")).json()
    assert own["mode"] == "own" and own["fallback"] is False
    assert own["translation"]["question"].startswith("Question") and own["german"]["question"]
    assert own["terms"] == [] and "answer" not in own and "explanation" not in own
    side = (await api.get(f"/api/study/question/{q1}?mode=side")).json()
    assert side["mode"] == "side" and side["translation"] and side["german"]
    help_ = (await api.get(f"/api/study/question/{q1}?mode=help")).json()
    assert help_["mode"] == "help" and help_["translation"] is None
    assert help_["terms"] == [
        {"term": "Bund", "translation": "Confederation", "note": "Federal.", "in_text": True}
    ]
    de = (await api.get(f"/api/study/question/{q1}?mode=de")).json()
    assert de["mode"] == "de" and de["translation"] is None and de["terms"] == []

    # No approved translation: own and side fall back to German only, with the flag.
    fb = (await api.get(f"/api/study/question/{q2}?mode=side")).json()
    assert fb["requested_mode"] == "side" and fb["mode"] == "de" and fb["fallback"] is True
    # A stale translation (older German version) does not count either.
    await translate(q2, source_version=1)
    async with SessionLocal() as db:
        (await db.get(Question, q2)).version = 2
        await db.commit()
    assert (await api.get(f"/api/study/question/{q2}?mode=own")).json()["fallback"] is True

    revealed = (await api.get(f"/api/study/question/{q1}?mode=own&reveal=true")).json()
    assert revealed["answer"] == await correct_of(q1)
    assert revealed["explanation"] == {"lang": "en", "text": revealed["translation"]["explanation"]}
    assert revealed["german"]["explanation"].startswith("Gemeint")


async def test_stored_mode_per_question_and_step_back(api):
    [q1, _] = await seed({FED_A: 2})
    await translate(q1)
    await paid(api)
    assert (await api.get(f"/api/study/question/{q1}")).json()["mode"] == "own"  # default
    r = await api.post(f"/api/study/question/{q1}/mode", json={"mode": "help"})
    assert r.status_code == 200 and r.json()["mode"] == "help"
    assert (await api.get(f"/api/study/question/{q1}")).json()["mode"] == "help"
    r = await api.post(f"/api/study/question/{q1}/mode", json={"mode": "side"})  # a step back
    body = r.json()
    assert body["mode"] == "side" and body["progress"]["mode_reached"] == "help"
    r = await api.post(f"/api/study/question/{q1}/mode", json={"mode": "loud"})
    assert r.status_code == 422


async def test_german_learner_always_gets_german_only(api):
    [q1] = await seed({FED_A: 1})
    await translate(q1)
    await paid(api)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        user.study_language = "de"
        await db.commit()
    r = (await api.get(f"/api/study/question/{q1}?mode=own")).json()
    assert r["mode"] == "de" and r["fallback"] is False
    res = await answer(api, q1)
    assert res["progress"]["understood"] is True  # German is this learner's language


# --- Progress rules ----------------------------------------------------------------------------


async def test_understood_and_known_follow_the_plan(api, frozen):
    [q1] = await seed({FED_A: 1})
    await translate(q1)
    await paid(api)

    res = await answer(api, q1, right=False)  # wrong in own language: nothing moves
    assert res["mode"] == "own" and res["progress"]["mode"] == "own"
    assert res["progress"]["understood"] is False and res["progress"]["box"] == 0
    assert res["explanation"]["lang"] == "en"  # feedback in the learner's language

    res = await answer(api, q1)  # correct in own language: understood, on to side by side
    assert res["progress"]["understood"] is True and res["progress"]["newly_understood"] is True
    assert res["progress"]["mode"] == "side" and res["progress"]["moved_forward"] is True
    assert res["mastery"] == {"topic_code": FED_A, "mastery": 50, "previous": 0}
    res = await answer(api, q1)
    assert res["mode"] == "side" and res["progress"]["mode"] == "help"
    res = await answer(api, q1)
    assert res["mode"] == "help" and res["progress"]["mode"] == "de"
    assert res["progress"]["known"] is False

    res = await answer(api, q1)  # first correct in German only
    assert res["mode"] == "de" and res["progress"]["known"] is False
    frozen.advance(hours=2)
    res = await answer(api, q1)  # again on the same day: still not known
    assert res["progress"]["known"] is False
    frozen.advance(days=1)
    res = await answer(api, q1)  # a different day: known
    assert res["progress"]["known"] is True and res["progress"]["newly_known"] is True
    assert res["mastery"]["mastery"] == 100

    async with SessionLocal() as db:
        p = (await db.execute(select(QuestionProgress))).scalar_one()
        assert (p.correct_own, p.correct_side, p.correct_help, p.correct_de, p.wrong) == (
            1,
            1,
            1,
            3,
            1,
        )
        assert p.last_correct_de_date.isoformat() == "2026-11-03"
        modes = [a.study_mode for a in (await db.execute(select(Attempt))).scalars()]
        assert sorted(modes) == sorted(["own", "own", "side", "help", "de", "de", "de"])


async def test_known_needs_german_only_not_help(api, frozen):
    [q1] = await seed({FED_A: 1})
    await paid(api)  # no translation: every answer is in German only (fallback)
    await answer(api, q1, mode="help")
    frozen.advance(days=1)
    res = await answer(api, q1, mode="help")
    assert res["mode"] == "help" and res["progress"]["known"] is False
    assert res["progress"]["understood"] is False  # not in the learner's language
    frozen.advance(days=1)
    await answer(api, q1, mode="de")
    frozen.advance(days=1)
    assert (await answer(api, q1, mode="de"))["progress"]["known"] is True


async def test_readiness_on_the_overview_is_weighted_and_labelled(api, frozen):
    ids = await seed({FED_A: 2, FED_B: 2}, targets={FED_A: 30, FED_B: 10, CANTON: 0, COMMUNE: 0})
    await paid(api)
    fed_a = [i for i in ids if i.startswith("foederalismus")]
    for qid in fed_a:  # make both FED_A questions known
        await answer(api, qid, mode="de")
    frozen.advance(days=1)
    for qid in fed_a:
        await answer(api, qid, mode="de")
    data = (await api.get("/api/study/overview")).json()
    assert data["readiness"] == {"value": 75, "label_key": "study.readinessLabel"}
    topics = {t["topic_code"]: t for t in data["topics"]}
    assert [t["topic_code"] for t in data["topics"]] == [c for c, *_ in TOPICS]  # file order
    assert topics[FED_A]["known"] == 2 and topics[FED_A]["mastery"] == 100
    assert topics[FED_B]["mastery"] == 0 and data["free_tier"] is False


# --- Learn and Practise ------------------------------------------------------------------------


async def test_learn_shows_answers_in_the_chosen_mode_and_marks_seen(api):
    [q1, q2] = await seed({FED_A: 2})
    await translate(q1)
    await paid(api)
    r = await api.get(f"/api/study/learn?topic_code={FED_A}&mode=side")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["topic_name"] == "Federalism" and len(data["cards"]) == 2
    by_id = {c["id"]: c for c in data["cards"]}
    assert by_id[q1]["mode"] == "side" and by_id[q1]["translation"]["explanation"]
    assert by_id[q2]["mode"] == "de" and by_id[q2]["fallback"] is True
    assert all(c["answer"] and c["german"]["explanation"] for c in data["cards"])
    r = await api.post(f"/api/study/question/{q1}/seen")
    assert r.status_code == 200 and r.json()["progress"]["seen"] is True
    async with SessionLocal() as db:
        assert (await db.execute(select(Attempt))).first() is None  # no scoring
    topics = {t["topic_code"]: t for t in (await api.get("/api/study/overview")).json()["topics"]}
    assert topics[FED_A]["seen"] == 1 and topics[FED_A]["mastery"] == 0
    assert (await api.get("/api/study/learn?topic_code=bund.nichts")).status_code == 404


async def test_practise_prefers_weak_topics_and_never_repeats(api, frozen, monkeypatch):
    ids = await seed({FED_A: 6, FED_B: 6})
    await paid(api)
    strong = [i for i in ids if i.startswith("foederalismus")]
    # Make FED_A strong: four of its six questions known.
    for qid in strong[:4]:
        await answer(api, qid, mode="de")
    frozen.advance(days=1)
    for qid in strong[:4]:
        await answer(api, qid, mode="de")
    frozen.advance(minutes=30)  # nothing is recent any more; the known ones are not due
    r = await api.get("/api/study/practise?n=6")
    assert r.status_code == 200, r.text
    picked = [q["id"] for q in r.json()["questions"]]
    count = Counter("strong" if q in strong else "weak" for q in picked)
    assert count["weak"] > count["strong"] and len(set(picked)) == 6
    assert not set(picked) & set(strong[:4])  # not due while new ones exist

    # Answer the round; the next round brings none of them back while others are left.
    for qid in picked:
        await answer(api, qid, right=False)
    again = [q["id"] for q in (await api.get("/api/study/practise?n=4")).json()["questions"]]
    rest = set(ids) - set(picked)
    assert set(again) <= rest | set(strong[:4]) and not set(again) & set(picked)
    # One topic only, with the topic's mastery.
    r = (await api.get(f"/api/study/practise?topic_code={FED_A}&n=20")).json()
    assert {q["topic_code"] for q in r["questions"]} == {FED_A} and r["mastery"] > 0
    assert len(r["questions"]) == 6 and r["pool"] == 6


async def test_practise_round_serves_each_question_in_its_stored_mode(api, frozen):
    [q1] = await seed({FED_A: 1})
    await translate(q1)
    await paid(api)
    await answer(api, q1)  # own -> side
    frozen.advance(minutes=30)
    [q] = (await api.get("/api/study/practise")).json()["questions"]
    assert q["id"] == q1 and q["mode"] == "side" and "answer" not in q


# --- Free tier ----------------------------------------------------------------------------------


async def test_free_tier_studies_the_sample_set_only(api, api2):
    ids = await seed({FED_A: 20, FED_B: 15, CANTON: 5})
    await free(api)
    sample = sorted(ids, key=lambda i: (1 + int(i.split("-")[-1]) % 3, i))[: selection.SAMPLE_SIZE]
    data = (await api.get("/api/study/overview")).json()
    assert data["free_tier"] is True and data["questions_available"] == 30
    assert data["questions_total"] == 40
    r = (await api.get("/api/study/practise?n=20")).json()
    assert set(q["id"] for q in r["questions"]) <= set(sample) and r["pool"] == 30
    outside = next(i for i in ids if i not in sample)
    r = await api.get(f"/api/study/question/{outside}")
    assert r.status_code == 403 and r.json()["detail"] == "sample_only"
    r = await api.post("/api/study/answer", json={"question_id": outside, "answer": "a"})
    assert r.status_code == 403
    cards = (await api.get(f"/api/study/learn?topic_code={FED_A}")).json()["cards"]
    assert {c["id"] for c in cards} <= set(sample)

    await learner_logged_in(api2, "pia@example.ch", access=True)
    data = (await api2.get("/api/study/overview")).json()
    assert data["free_tier"] is False and data["questions_available"] == 40
    assert (await api2.get(f"/api/study/question/{outside}")).status_code == 200


# --- Mock test ----------------------------------------------------------------------------------


MOCK_BANK = {FED_A: 30, FED_B: 20, CANTON: 10, COMMUNE: 5}


async def test_mock_draws_counts_and_proportions_and_hides_help(api, mock_format, frozen):
    await seed(MOCK_BANK)
    await paid(api)
    info = (await api.get("/api/mock")).json()
    assert info["questions"] == 50 and info["minutes"] == 60 and info["pass_mark"] == 30
    assert info["pass_mark_confirmed"] is False and info["enough_questions"] is True
    r = await api.post("/api/mock/start")
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["total"] == 50 and len(run["questions"]) == 50 and run["seconds_left"] == 3600
    assert run["deadline_at"].startswith("2026-11-02T10:00")
    ids = [q["id"] for q in run["questions"]]
    assert len(set(ids)) == 50
    scopes = Counter(mock.scope_of(TOPIC_BY_SLUG[i.rsplit("-", 1)[0]]) for i in ids)
    assert scopes == {"federal": 39, "canton": 8, "commune": 3}
    per_topic = Counter(i.rsplit("-", 1)[0] for i in ids)
    assert set(per_topic) == {"foederalismus", "volksrechte", "kantonsrat", "leistungen"}
    assert abs(per_topic["foederalismus"] - per_topic["volksrechte"]) <= 1  # equal targets
    q = run["questions"][0]
    assert set(q) == {"id", "question", "options"}  # German only: no answer, help or translation
    # Starting again returns the running test.
    assert (await api.post("/api/mock/start")).json()["id"] == run["id"]


async def test_mock_deadline_scoring_pass_fail_and_review(api, mock_format, frozen):
    await seed(MOCK_BANK)
    await paid(api)
    run = (await api.post("/api/mock/start")).json()
    ids = [q["id"] for q in run["questions"]]
    await translate(ids[0])
    for qid in ids[:31]:  # 31 right
        r = await api.post(
            f"/api/mock/{run['id']}/answer",
            json={"question_id": qid, "answer": await correct_of(qid)},
        )
        assert r.status_code == 200, r.text
    key = await correct_of(ids[0])
    wrong = "b" if key == "a" else "a"
    r = await api.post(
        f"/api/mock/{run['id']}/answer", json={"question_id": ids[0], "answer": wrong}
    )
    assert r.json()["answered"] == 31  # changed, not added
    r = await api.post(
        f"/api/mock/{run['id']}/answer", json={"question_id": "fremd", "answer": "a"}
    )
    assert r.status_code == 404
    frozen.advance(minutes=60, seconds=1)
    r = await api.post(
        f"/api/mock/{run['id']}/answer", json={"question_id": ids[40], "answer": "a"}
    )
    assert r.status_code == 409 and r.json()["detail"] == "deadline_passed"
    res = (await api.get(f"/api/mock/{run['id']}")).json()
    assert res["status"] == "expired" and res["score"] == 30 and res["passed"] is True
    assert res["pass_mark"] == 30 and res["pass_mark_label_key"] == "mock.passMarkUnconfirmed"
    assert "questions" not in res
    review = {item["id"]: item for item in res["review"]}
    assert len(review) == 20 and ids[0] in review and ids[1] not in review
    first = review[ids[0]]
    assert first["given"] == wrong and first["answer"] == key
    assert first["mode"] == "own" and first["explanation"]["lang"] == "en"
    assert review[ids[45]]["given"] is None and review[ids[45]]["explanation"]["lang"] == "de"
    async with SessionLocal() as db:
        attempts = (await db.execute(select(Attempt))).scalars().all()
        assert len(attempts) == 31 and {a.mode for a in attempts} == {"mock"}
        assert (await db.execute(select(QuestionProgress))).first() is None  # a measurement only

    # A second run, handed in early with 29 right: a fail.
    run = (await api.post("/api/mock/start")).json()
    for q in run["questions"][:29]:
        await api.post(
            f"/api/mock/{run['id']}/answer",
            json={"question_id": q["id"], "answer": await correct_of(q["id"])},
        )
    res = (await api.post(f"/api/mock/{run['id']}/finish")).json()
    assert res["status"] == "finished" and res["score"] == 29 and res["passed"] is False
    r = await api.post(
        f"/api/mock/{run['id']}/answer",
        json={"question_id": run["questions"][40]["id"], "answer": "a"},
    )
    assert r.status_code == 409 and r.json()["detail"] == "mock_finished"
    again = (await api.post(f"/api/mock/{run['id']}/finish")).json()
    assert again["score"] == 29  # idempotent


async def test_free_tier_gets_one_mock_test_and_paid_unlimited(api, api2, mock_format, frozen):
    await seed(MOCK_BANK)
    await free(api)
    info = (await api.get("/api/mock")).json()
    assert info["can_start"] is True and info["free_mock_used"] is False and info["paid"] is False
    run = (await api.post("/api/mock/start")).json()
    assert run["free"] is True
    await api.post(f"/api/mock/{run['id']}/finish")
    r = await api.post("/api/mock/start")
    assert r.status_code == 403 and r.json()["detail"] == "free_mock_used"
    info = (await api.get("/api/mock")).json()
    assert info["can_start"] is False and info["free_mock_used"] is True
    assert info["recent"][0]["id"] == run["id"]

    await learner_logged_in(api2, "pia@example.ch", access=True)
    for _ in range(3):
        r = await api2.post("/api/mock/start")
        assert r.status_code == 201 and r.json()["free"] is False
        await api2.post(f"/api/mock/{r.json()['id']}/finish")
    async with SessionLocal() as db:
        assert len((await db.execute(select(MockRun))).scalars().all()) == 4
    # Someone else's run is not visible.
    assert (await api.get(f"/api/mock/{r.json()['id']}")).status_code == 404


async def test_mock_needs_enough_questions_and_a_format(api, mock_format, monkeypatch, tmp_path):
    await seed({FED_A: 10})
    await paid(api)
    assert (await api.get("/api/mock")).json()["enough_questions"] is False
    r = await api.post("/api/mock/start")
    assert r.status_code == 409 and r.json()["detail"] == "not_enough_questions"
    monkeypatch.setattr(get_settings(), "content_dir", str(tmp_path / "nowhere"))
    assert (await api.get("/api/mock")).json()["configured"] is False
    assert (await api.post("/api/mock/start")).status_code == 404


async def test_check_questions_after_a_chat_use_the_study_api(api):
    from app.models import Conversation

    [q1, _] = await seed({FED_A: 2})
    await paid(api)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        conv = Conversation(user_id=user.id, canton="zh", topic_code=FED_A, topic_name="F")
        db.add(conv)
        await db.commit()
        conv_id = str(conv.id)
    data = (await api.get(f"/api/study/check?conversation_id={conv_id}")).json()
    assert len(data["questions"]) == 2 and data["questions"][0]["mode"] == "de"
    res = await answer(api, q1, context="check", conversation_id=conv_id)
    assert res["correct"] is True and "mastery" in res["mastery"]
    r = await api.post(
        "/api/study/answer", json={"question_id": q1, "answer": "a", "context": "check"}
    )
    assert r.status_code == 400 and r.json()["detail"] == "conversation_required"
    async with SessionLocal() as db:
        a = (await db.execute(select(Attempt))).scalar_one()
        assert a.mode == "check" and str(a.conversation_id) == conv_id
