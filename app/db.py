"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class TZDateTime(TypeDecorator):
    """Timezone-aware datetime that stays aware on SQLite, which drops the offset."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


_settings = get_settings()
# Under test every connection is opened fresh: pooled asyncpg connections are bound to the
# event loop that created them and fail when another loop reuses them.
engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    **({"poolclass": NullPool} if _settings.app_env == "test" else {}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
