"""Account self-deletion. See docs/runbooks/account-deletion.md for what is kept and why.

Everything is deleted explicitly rather than through database cascades, so the result is the
same on SQLite (tests, development) and PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import email_digest
from app.db import utcnow
from app.models import (
    Attempt,
    AuditLog,
    Conversation,
    DiagnosticRun,
    Entitlement,
    GenerationBatch,
    LlmCall,
    Message,
    OneTimeToken,
    Payment,
    Question,
    QuestionReport,
    Session,
    StripeEvent,
    TopicMastery,
    User,
)


def _redacted(event: dict[str, Any], when: str) -> dict[str, Any]:
    """Keep only what identifies the event itself; Stripe holds the full record."""
    return {"id": event.get("id"), "type": event.get("type"), "redacted_at": when}


async def _redact_stripe_events(db: AsyncSession, user: User) -> int:
    """Webhook payloads carry the customer's email and billing details. Strip the payloads
    that mention this person's customer or user id (processed or not: the account they
    would apply to is gone)."""
    needles = [str(user.id)]
    if user.stripe_customer_id:
        needles.append(user.stripe_customer_id)
    text = cast(StripeEvent.payload, String)
    query = select(StripeEvent).where(or_(*[text.contains(n) for n in needles]))
    rows = (await db.execute(query)).scalars().all()
    when = utcnow().isoformat()
    for row in rows:
        row.payload = _redacted(row.payload or {}, when)
        row.processed_at = row.processed_at or utcnow()
    return len(rows)


async def delete_account(db: AsyncSession, user: User) -> None:
    """Delete the person and their learning data; keep billing records without the email
    and AI cost records without the user id. Flushes but does not commit."""
    uid = user.id
    now = utcnow()

    # Kept, de-identified.
    await db.execute(
        update(Payment)
        .where(Payment.user_id == uid)
        .values(user_id=None, email_hash=email_digest(user.email) if user.email else None)
    )
    await db.execute(update(LlmCall).where(LlmCall.user_id == uid).values(user_id=None))
    await _redact_stripe_events(db, user)
    await db.execute(
        update(AuditLog).where(AuditLog.actor_user_id == uid).values(actor_user_id=None)
    )
    await db.execute(
        update(GenerationBatch).where(GenerationBatch.requested_by == uid).values(requested_by=None)
    )
    await db.execute(update(Question).where(Question.reviewer_id == uid).values(reviewer_id=None))

    # Open reports count towards a question's report total; take this person's out.
    open_reports = (
        await db.execute(
            select(QuestionReport.question_id).where(
                QuestionReport.user_id == uid, QuestionReport.resolved_at.is_(None)
            )
        )
    ).scalars()
    for question_id in open_reports:
        question = await db.get(Question, question_id)
        if question is not None and question.report_count > 0:
            question.report_count -= 1

    # Deleted.
    for model in (Message, Attempt, TopicMastery, DiagnosticRun, QuestionReport, Entitlement):
        await db.execute(delete(model).where(model.user_id == uid))
    await db.execute(delete(Conversation).where(Conversation.user_id == uid))
    await db.execute(delete(OneTimeToken).where(OneTimeToken.user_id == uid))
    await db.execute(
        delete(Session).where((Session.user_id == uid) | (Session.impersonator_user_id == uid))
    )
    await db.flush()
    await db.execute(delete(User).where(User.id == uid))
    db.add(
        AuditLog(
            actor_user_id=None,
            action="user.self_delete",
            target_type="user",
            target_id=str(uid),
            created_at=now,
        )
    )
    await db.flush()
