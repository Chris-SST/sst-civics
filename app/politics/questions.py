"""Current-affairs practice questions (contract "Practice questions in the app", D-074).

After a round-up or a vote explainer is published, the worker writes two or three
multiple-choice questions in German on facts stated in the page (prompt
politics/questions), has another model answer them from the page without the key and check
that each has a single correct answer and is neutral (politics/question_check), keeps only
those that pass, and translates them into the other site languages
(politics/question_translate).

They live in `current_affairs_questions`, apart from the question bank, and expire: a
round-up's six months after the end of its week, a vote's twelve months after the vote.
Nothing here touches attempts, progress, the free sample set, the mock test or readiness."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm import articles as llm
from app.llm import politics as ai
from app.models import (
    CA_OK,
    CA_RETIRED,
    OPTION_KEYS,
    Article,
    CurrentAffairsQuestion,
)
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

TTL = {"roundup": timedelta(days=183), "vote": timedelta(days=365)}
QUESTION_LANGS = ("en", "fr", "it", "pt", "es", "sq", "tr")
QUESTIONS_MIN, QUESTIONS_MAX = 2, 3


def refers_to(a: Article) -> date:
    plan = a.plan or {}
    raw = plan.get("period_end") if a.kind == "roundup" else plan.get("vote_date")
    return date.fromisoformat(raw)


def expires_at(a: Article) -> datetime:
    day = refers_to(a) + TTL[a.kind]
    return datetime.combine(day, time(0, 0), tzinfo=ZURICH).astimezone(UTC)


def page_paths(a: Article) -> dict[str, str]:
    base = get_settings().guide_base_url.rstrip("/")
    return {
        lang: url[len(base) :] if url.startswith(base) else url
        for lang, url in (a.live_urls or {}).items()
    }


def _options_ok(options: Any) -> bool:
    if not isinstance(options, dict) or set(options) != set(OPTION_KEYS):
        return False
    texts = [str(options[k]).strip() for k in OPTION_KEYS]
    return all(texts) and len(set(texts)) == 4 and all(len(t) <= 300 for t in texts)


def well_formed(q: dict[str, Any]) -> bool:
    return (
        isinstance(q.get("question_de"), str)
        and 10 <= len(q["question_de"].strip()) <= 400
        and _options_ok(q.get("options_de"))
        and q.get("correct") in OPTION_KEYS
        and isinstance(q.get("explanation_de"), str)
        and q["explanation_de"].strip() != ""
    )


def _page(a: Article) -> dict[str, Any]:
    en = a.english or {}
    de = ((a.translations or {}).get("de") or {}).get("content") or {}
    return {
        "kind": a.kind,
        "date": refers_to(a).isoformat(),
        "title": en.get("title"),
        "summary": en.get("summary"),
        "body": en.get("body"),
        "german_body": de.get("body"),
    }


async def _call(db: AsyncSession, purpose, prompt, model, payload, schema) -> dict | None:
    result = await llm.call(
        purpose=purpose,
        prompt_name=prompt,
        model=model,
        payload=payload,
        schema=schema,
        effort="medium",
        max_tokens=8000,
    )
    a_cost = await llm.record(db, result)
    await db.commit()
    log.debug("Politics questions: %s cost CHF %.3f", purpose, a_cost)
    return result.data if result.ok else None


async def generate(db: AsyncSession, a: Article, now: datetime) -> tuple[int, str]:
    """Write, check, translate and store the questions of a published page. Returns the
    number stored and a short note. Earlier questions of the same page are retired."""
    s = get_settings()
    page = _page(a)
    data = await _call(
        db,
        ai.PURPOSE_QUESTIONS,
        ai.PROMPT_QUESTIONS,
        s.politics_question_model,
        {"page": page, "count": [QUESTIONS_MIN, QUESTIONS_MAX]},
        ai.QUESTIONS_SCHEMA,
    )
    if data is None:
        return 0, "the question writer failed"
    drafts = [q for q in data.get("questions") or [] if isinstance(q, dict) and well_formed(q)]
    drafts = drafts[:QUESTIONS_MAX]
    if not drafts:
        return 0, "no well-formed question"
    check = await _call(
        db,
        ai.PURPOSE_QUESTION_CHECK,
        ai.PROMPT_QUESTION_CHECK,
        s.politics_question_check_model,
        {
            "page": page,
            "questions": [
                {"n": i, "question_de": q["question_de"], "options_de": q["options_de"]}
                for i, q in enumerate(drafts, 1)
            ],
        },
        ai.QUESTION_CHECK_SCHEMA,
    )
    if check is None:
        return 0, "the independent check failed"
    verdicts = {c.get("n"): c for c in check.get("checks") or [] if isinstance(c, dict)}
    kept: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i, q in enumerate(drafts, 1):
        v = verdicts.get(i) or {}
        if (
            v.get("answer") == q["correct"]
            and v.get("answerable_from_page") is True
            and v.get("single_correct") is True
            and v.get("neutral") is True
        ):
            kept.append((q, v))
    if not kept:
        return 0, "no question passed the independent check"
    tr = await _call(
        db,
        ai.PURPOSE_QUESTION_TRANSLATE,
        ai.PROMPT_QUESTION_TRANSLATE,
        s.articles_translate_model,
        {
            "languages": list(QUESTION_LANGS),
            "questions": [
                {
                    "n": i,
                    "question_de": q["question_de"],
                    "options_de": q["options_de"],
                    "explanation_de": q["explanation_de"],
                }
                for i, (q, _) in enumerate(kept, 1)
            ],
        },
        ai.QUESTION_TRANSLATE_SCHEMA,
    )
    by_n = {t.get("n"): t for t in (tr or {}).get("translations") or [] if isinstance(t, dict)}
    await db.execute(
        update(CurrentAffairsQuestion)
        .where(CurrentAffairsQuestion.page_key == a.key, CurrentAffairsQuestion.status == CA_OK)
        .values(status=CA_RETIRED)
    )
    canton = (a.plan or {}).get("set_canton") or a.canton
    paths = page_paths(a)
    for i, (q, v) in enumerate(kept, 1):
        translations = {}
        for lang in QUESTION_LANGS:
            t = (by_n.get(i) or {}).get(lang) or {}
            if (
                isinstance(t.get("question"), str)
                and t["question"].strip()
                and _options_ok(t.get("options"))
                and isinstance(t.get("explanation"), str)
            ):
                translations[lang] = {
                    "question": t["question"].strip(),
                    "options": {k: str(t["options"][k]).strip() for k in OPTION_KEYS},
                    "explanation": t["explanation"].strip(),
                }
        db.add(
            CurrentAffairsQuestion(
                canton=canton,
                page_key=a.key,
                page_kind=a.kind,
                page_revision=a.published_revision or a.revision,
                page_paths=paths,
                refers_to=refers_to(a),
                expires_at=expires_at(a),
                position=i,
                question_de=q["question_de"].strip(),
                options_de={k: str(q["options_de"][k]).strip() for k in OPTION_KEYS},
                correct=q["correct"],
                explanation_de=q["explanation_de"].strip(),
                translations=translations,
                status=CA_OK,
                check={"verdict": v, "page_fact": q.get("page_fact", "")},
                created_at=now,
            )
        )
    await db.commit()
    return len(kept), f"{len(kept)} question(s) stored"


# --- what the app serves ----------------------------------------------------------------------


async def servable(db: AsyncSession, canton: str, now: datetime) -> list[CurrentAffairsQuestion]:
    """The questions a learner of `canton` may see: checked and not expired."""
    rows = await db.execute(
        select(CurrentAffairsQuestion)
        .where(
            CurrentAffairsQuestion.canton == canton,
            CurrentAffairsQuestion.status == CA_OK,
            CurrentAffairsQuestion.expires_at > now,
        )
        .order_by(
            CurrentAffairsQuestion.refers_to.desc(),
            CurrentAffairsQuestion.page_key,
            CurrentAffairsQuestion.position,
        )
    )
    return list(rows.scalars().all())


def page_url(q: CurrentAffairsQuestion, lang: str) -> str | None:
    path = (q.page_paths or {}).get(lang) or (q.page_paths or {}).get("en")
    return get_settings().guide_base_url.rstrip("/") + path if path else None


def render(q: CurrentAffairsQuestion, lang: str, *, reveal: bool = False) -> dict[str, Any]:
    t = (q.translations or {}).get(lang) if lang != "de" else None
    out: dict[str, Any] = {
        "id": str(q.id),
        "refers_to": q.refers_to.isoformat(),
        "page_kind": q.page_kind,
        "page_url": page_url(q, lang),
        "german": {
            "lang": "de",
            "question": q.question_de,
            "options": [{"key": k, "text": q.options_de.get(k, "")} for k in OPTION_KEYS],
        },
        "translation": (
            {
                "lang": lang,
                "question": t["question"],
                "options": [{"key": k, "text": t["options"].get(k, "")} for k in OPTION_KEYS],
            }
            if t
            else None
        ),
    }
    if reveal:
        out["answer"] = q.correct
        out["explanation_de"] = q.explanation_de
        out["explanation"] = (
            {"lang": lang, "text": t["explanation"]}
            if t
            else {"lang": "de", "text": q.explanation_de}
        )
    return out
