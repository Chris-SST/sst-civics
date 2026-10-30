"""The refund rule (plan, "Payments and pricing"; D-015): a payment is refunded on request
within 14 days of purchase if fewer than 50 questions have been studied since. Learners ask
support; an admin issues the refund and the `charge.refunded` webhook shortens access."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.models import Attempt, Payment, User

NO_PAYMENT = "no_payment"
REFUNDED = "refunded"
TOO_LATE = "too_late"
TOO_MANY_QUESTIONS = "too_many_questions"


@dataclass
class Eligibility:
    eligible: bool
    reason: str | None  # why not, when not eligible
    payment_id: str | None = None
    product: str | None = None
    canton: str | None = None
    paid_at: datetime | None = None
    deadline: datetime | None = None
    questions_studied: int = 0
    max_questions: int = 0
    window_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("paid_at", "deadline"):
            d[k] = d[k].isoformat() if d[k] else None
        return d


async def latest_payment(db: AsyncSession, user: User) -> Payment | None:
    stmt = (
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.paid_at.desc()).limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def questions_studied_since(db: AsyncSession, user_id, since: datetime) -> int:
    """Distinct questions the learner has answered since `since`, in any mode."""
    stmt = select(func.count(func.distinct(Attempt.question_id))).where(
        Attempt.user_id == user_id, Attempt.created_at >= since
    )
    return int((await db.execute(stmt)).scalar_one())


async def eligibility(
    db: AsyncSession, payment: Payment | None, now: datetime | None = None
) -> Eligibility:
    settings = get_settings()
    window = settings.refund_window_days
    limit = settings.refund_max_questions_studied
    if payment is None:
        return Eligibility(False, NO_PAYMENT, max_questions=limit, window_days=window)
    now = now or utcnow()
    deadline = payment.paid_at + timedelta(days=window)
    studied = (
        await questions_studied_since(db, payment.user_id, payment.paid_at)
        if payment.user_id
        else 0
    )
    if payment.refunded_at is not None:
        reason: str | None = REFUNDED
    elif now > deadline:
        reason = TOO_LATE
    elif studied >= limit:
        reason = TOO_MANY_QUESTIONS
    else:
        reason = None
    return Eligibility(
        eligible=reason is None,
        reason=reason,
        payment_id=str(payment.id),
        product=payment.product,
        canton=payment.canton,
        paid_at=payment.paid_at,
        deadline=deadline,
        questions_studied=studied,
        max_questions=limit,
        window_days=window,
    )
