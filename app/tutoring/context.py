"""What "Explain this" sends to the provider about a question: its text, the four options,
the correct key, the explanation, the approved translation in the conversation's language and
the official sources. Question content only; nothing about the learner."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.service import QuestionContext
from app.models import CONTENT_MASTER_LANGUAGE, OPTION_KEYS, Question, User
from app.study import mock, modes


async def question_context(db: AsyncSession, q: Question, lang: str) -> QuestionContext:
    translation = None
    if lang != CONTENT_MASTER_LANGUAGE:
        tr = (await modes.translations_for(db, [q.id], lang)).get(q.id)
        if tr is not None and modes.translation_usable(q, tr):
            translation = {
                "lang": lang,
                "question": tr.question,
                "options": {k: tr.options.get(k, "") for k in OPTION_KEYS},
                "explanation": tr.explanation,
            }
    return QuestionContext(
        question_de=q.question_de,
        options_de={k: q.options_de.get(k, "") for k in OPTION_KEYS},
        correct=q.correct,
        explanation_de=q.explanation_de,
        sources=[str(s["url"]) for s in q.sources or [] if s.get("url")],
        translation=translation,
    )


async def mock_running(db: AsyncSession, user: User) -> bool:
    """A mock test is open for this learner: no Explain this until it is handed in (D-051)."""
    run = await mock.active_run(db, user)
    return run is not None and mock.is_open(run)
