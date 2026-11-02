"""Free practice without an account (Chris, 2 November 2026: the way from the guide to the first
question was too long). `GET /api/public/sample-questions?canton=zh&lang=en` returns the
canton's free sample set (`selection.sample_of`, the same 30 questions a new account gets) in
the side-by-side mode, German with the visitor's language, each with its correct key and
explanation, so the page `/try` in the app can check answers in the browser. Nothing is stored
and nothing is counted; signing up keeps the learner's own progress from then on."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import CANTONS, LANGUAGES, MODE_SIDE
from app.questions import bank
from app.study import modes, selection

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/sample-questions")
async def sample_questions(
    response: Response,
    canton: str = Query(default="zh", max_length=2),
    lang: str = Query(default="en", max_length=5),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    canton = canton if canton in CANTONS else "zh"
    lang = lang if lang in LANGUAGES else "en"
    sample = selection.sample_of(await selection.servable_questions(db, canton))
    translations = await modes.translations_for(db, [q.id for q in sample], lang)
    names = await bank.topic_names(db, canton, lang)
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "canton": canton,
        "lang": lang,
        "questions": [
            modes.render(
                q,
                mode=MODE_SIDE,
                study_language=lang,
                translation=translations.get(q.id),
                glossary=[],
                topic_name=names.get(q.topic_code),
                reveal=True,
            )
            for q in sample
        ],
    }
