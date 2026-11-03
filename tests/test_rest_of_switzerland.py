"""Rest of Switzerland ("ch"): learners whose canton has no question set of its own study the
federal questions only, and can buy a pass for that (Chris, 3 November 2026)."""

from __future__ import annotations

from app.billing.products import PASS_CH, PASS_FOR_CANTON, PRODUCTS
from app.config import get_settings
from app.db import SessionLocal
from tests.conftest import (
    LEARNER_PASSWORD,
    Api,
    last_email_link,
    login,
    make_question,
    seed_topics,
    signup_body,
    token_from_link,
)

FEDERAL = (
    ("bund.demokratie.foederalismus", "federal", "Föderalismus", "Federalism"),
    ("bund.demokratie.volksrechte", "federal", "Volksrechte", "Popular rights"),
)


async def rest_of_switzerland_learner(api: Api, email: str = "noa@example.ch") -> None:
    r = await api.post("/api/auth/signup", json=signup_body(email, canton="ch"))
    assert r.status_code == 201, r.text
    r = await api.post("/api/auth/verify-email", json={"token": token_from_link(last_email_link())})
    assert r.status_code == 200, r.text
    assert (await login(api, email, LEARNER_PASSWORD)).status_code == 200


async def test_federal_questions_only(api):
    await seed_topics("zh")
    await seed_topics("ch", FEDERAL)
    async with SessionLocal() as db:
        db.add(make_question("bund-frage"))
        db.add(
            make_question(
                "zuerich-frage", scope="zh", canton="zh", topic_code="kanton.demokratie.kantonsrat"
            )
        )
        await db.commit()
    await rest_of_switzerland_learner(api)
    overview = (await api.get("/api/study/overview")).json()
    assert overview["canton"] == "ch"
    assert {t["topic_code"] for t in overview["topics"]} == {code for code, *_ in FEDERAL}
    assert overview["questions_total"] == 1
    assert (await api.get("/api/study/question/bund-frage")).status_code == 200
    assert (await api.get("/api/study/question/zuerich-frage")).status_code == 404


def test_a_pass_exists_and_ch_is_on_sale():
    assert PASS_FOR_CANTON["ch"] == PASS_CH and PRODUCTS[PASS_CH].months == 6
    assert "ch" in get_settings().cantons_on_sale and "zh" in get_settings().cantons_on_sale
