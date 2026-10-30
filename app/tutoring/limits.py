"""Message limits for "Explain this". Every learner with an active entitlement gets the same
daily cap (`AI_DAILY_MESSAGE_LIMIT`); learners without one cannot use the chat at all (the
routes check `has_access`). There is no monthly cap; months are still counted for display.
Days and months are counted in Swiss time."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.models import MESSAGE_USER, Message, User

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


async def _count(db: AsyncSession, user_id, since: datetime) -> int:
    stmt = select(func.count(Message.id)).where(
        Message.user_id == user_id,
        Message.role == MESSAGE_USER,
        Message.counted.is_(True),
        Message.created_at >= since,
    )
    return int((await db.execute(stmt)).scalar_one())


async def usage_for(db: AsyncSession, user: User) -> UsageInfo:
    now = utcnow()
    return UsageInfo(
        daily_used=await _count(db, user.id, day_start(now)),
        daily_limit=get_settings().ai_daily_message_limit,
        monthly_used=await _count(db, user.id, month_start(now)),
        monthly_limit=None,
    )
