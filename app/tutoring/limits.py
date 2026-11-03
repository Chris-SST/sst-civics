"""Message limits for the AI chats. Every learner with an active entitlement for their canton
gets one daily cap for Explain this and the help chat together (`AI_DAILY_MESSAGE_LIMIT`).
Learners without one get two separate daily allowances, so that trying one feature does not
use up the other: `AI_FREE_DAILY_MESSAGE_LIMIT` for the help chat and
`AI_FREE_EXPLAIN_DAILY_LIMIT` for Explain this on the free sample questions (which questions
may be explained is checked in app.tutoring.explain and the message endpoint). A free count
looks only at its own kind of conversation: Explain conversations are the ones bound to a
question. There is no monthly cap; months are still counted for display. Days and months are
counted in Swiss time."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.config import get_settings
from app.db import utcnow
from app.models import MESSAGE_USER, Conversation, Message, User

ZURICH = ZoneInfo("Europe/Zurich")


@dataclass
class UsageInfo:
    daily_used: int
    daily_limit: int | None
    monthly_used: int
    monthly_limit: int | None

    @property
    def daily_exhausted(self) -> bool:
        return self.daily_limit is not None and self.daily_used >= self.daily_limit

    @property
    def monthly_exhausted(self) -> bool:
        return self.monthly_limit is not None and self.monthly_used >= self.monthly_limit

    @property
    def monthly_fraction(self) -> float:
        if not self.monthly_limit:
            return 0.0
        return self.monthly_used / self.monthly_limit

    def to_dict(self) -> dict:
        d = asdict(self)
        d["daily_exhausted"] = self.daily_exhausted
        d["monthly_exhausted"] = self.monthly_exhausted
        d["near_monthly_limit"] = self.monthly_fraction >= 0.8 and not self.monthly_exhausted
        return d


def day_start(now: datetime | None = None) -> datetime:
    local = (now or utcnow()).astimezone(ZURICH)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def month_start(now: datetime | None = None) -> datetime:
    local = (now or utcnow()).astimezone(ZURICH)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def _count(db: AsyncSession, user_id, since: datetime, explain: bool | None) -> int:
    """Counted learner messages since `since`; only Explain this (True), only the other chats
    (False) or all of them (None)."""
    stmt = select(func.count(Message.id)).where(
        Message.user_id == user_id,
        Message.role == MESSAGE_USER,
        Message.counted.is_(True),
        Message.created_at >= since,
    )
    if explain is not None:
        bound = Conversation.question_id.is_not(None)
        stmt = stmt.join(Conversation, Conversation.id == Message.conversation_id).where(
            bound if explain else ~bound
        )
    return int((await db.execute(stmt)).scalar_one())


async def usage_for(db: AsyncSession, user: User, *, explain: bool = False) -> UsageInfo:
    """The learner's allowance for Explain this (`explain=True`) or the help chat. With a pass
    both share one count and cap."""
    now = utcnow()
    settings = get_settings()
    if has_access(user, user.canton):
        kind, limit = None, settings.ai_daily_message_limit
    elif explain:
        kind, limit = True, settings.ai_free_explain_daily_limit
    else:
        kind, limit = False, settings.ai_free_daily_message_limit
    return UsageInfo(
        daily_used=await _count(db, user.id, day_start(now), kind),
        daily_limit=limit,
        monthly_used=await _count(db, user.id, month_start(now), kind),
        monthly_limit=None,
    )
