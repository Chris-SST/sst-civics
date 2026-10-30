"""Test configuration. Environment is set before the app is imported so settings pick
up SQLite, in-process jobs and the in-memory email outbox."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import AsyncIterator
from datetime import timedelta

_TMP = tempfile.mkdtemp(prefix="sst-tests-")
os.environ.update(
    {
        "APP_ENV": "test",
        "SECRET_KEY": "test-secret-key-not-for-production",
        "DATABASE_URL": os.environ.get("CI_DATABASE_URL") or f"sqlite+aiosqlite:///{_TMP}/test.db",
        "JOBS_INLINE": "true",
        "EMAIL_BACKEND": "memory",
        "STRIPE_SECRET_KEY": "sk_test_dummy",
        "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
        "APP_BASE_URL": "http://localhost:5173",
        "COOKIE_SECURE": "false",
    }
)

import pyotp  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth import ratelimit  # noqa: E402
from app.auth.passwords import hash_password  # noqa: E402
from app.billing import routes as billing_routes  # noqa: E402
from app.billing.plans import PLAN_DEFAULTS  # noqa: E402
from app.db import Base, SessionLocal, engine, utcnow  # noqa: E402
from app.email.backend import memory_outbox  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ENTITLEMENT_ADMIN, ROLE_ADMIN, Entitlement, Plan, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_state():
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    async with SessionLocal() as db:
        for d in PLAN_DEFAULTS:
            db.add(
                Plan(
                    key=d.key,
                    kind=d.kind,
                    monthly_message_limit=d.monthly_message_limit,
                    daily_message_limit=d.daily_message_limit,
                    sort_order=d.sort_order,
                    is_active=True,
                )
            )
        await db.commit()
    memory_outbox.clear()
    ratelimit.reset_memory()
    billing_routes.clear_price_cache()
    yield


class Api:
    """AsyncClient wrapper that adds the CSRF header on state-changing requests."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def _csrf(self) -> str:
        token = self.client.cookies.get("sst_csrf")
        if not token:
            r = await self.client.get("/api/auth/csrf")
            token = r.json()["csrf_token"]
        return token

    async def get(self, url: str, **kw):
        return await self.client.get(url, **kw)

    async def post(self, url: str, json=None, csrf: bool = True, **kw):
        headers = dict(kw.pop("headers", {}) or {})
        if csrf:
            headers["X-CSRF-Token"] = await self._csrf()
        return await self.client.post(url, json=json, headers=headers, **kw)

    async def patch(self, url: str, json=None, **kw):
        headers = {"X-CSRF-Token": await self._csrf()}
        return await self.client.patch(url, json=json, headers=headers, **kw)

    async def delete(self, url: str, **kw):
        headers = {"X-CSRF-Token": await self._csrf()}
        return await self.client.delete(url, headers=headers, **kw)


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield Api(c)


@pytest.fixture
async def api2() -> AsyncIterator[Api]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield Api(c)


@pytest.fixture
async def api3() -> AsyncIterator[Api]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield Api(c)


def last_email_link() -> str:
    assert memory_outbox.messages, "no email was sent"
    text = memory_outbox.messages[-1].text
    match = re.search(r"https?://\S+", text)
    assert match, text
    return match.group(0)


def token_from_link(link: str) -> str:
    return link.split("token=")[1]


LEARNER_PASSWORD = "Learner-pass-123"
ADMIN_PASSWORD = "Admin-pass-123"


def signup_body(email: str, password: str = LEARNER_PASSWORD, **overrides) -> dict:
    body = {
        "email": email,
        "password": password,
        "locale": "en",
        "study_language": "en",
        "canton": "zh",
        "age_confirmed": True,
        "accept_terms": True,
    }
    body.update(overrides)
    return body


async def signup_and_verify(api: Api, email: str, password: str = LEARNER_PASSWORD) -> None:
    r = await api.post("/api/auth/signup", json=signup_body(email, password))
    assert r.status_code == 201, r.text
    token = token_from_link(last_email_link())
    r = await api.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text


async def login(api: Api, email: str, password: str):
    return await api.post("/api/auth/login", json={"email": email, "password": password})


async def grant_access(email: str, canton: str = "zh", days: int = 30) -> None:
    """Give a learner an active entitlement directly in the database."""
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        db.add(
            Entitlement(
                user_id=user.id,
                canton=canton,
                starts_at=utcnow() - timedelta(minutes=1),
                expires_at=utcnow() + timedelta(days=days),
                source=ENTITLEMENT_ADMIN,
            )
        )
        await db.commit()


async def learner_logged_in(
    api: Api, email: str = "learner@example.ch", *, access: bool = False
) -> dict:
    """A verified learner (canton zh), signed in. With `access`, also an active entitlement."""
    await signup_and_verify(api, email)
    if access:
        await grant_access(email)
    r = await login(api, email, LEARNER_PASSWORD)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    return r.json()["me"]


async def create_admin(email: str, password: str = ADMIN_PASSWORD, totp: bool = False) -> User:
    async with SessionLocal() as db:
        user = User(
            role=ROLE_ADMIN,
            email=email,
            email_verified_at=utcnow(),
            password_hash=hash_password(password),
            locale="en",
        )
        if totp:
            user.totp_secret = pyotp.random_base32()
            user.totp_enabled = True
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def admin_logged_in(api: Api, email: str = "admin@sst-example.ch") -> User:
    """Admin with 2FA already enabled, fully signed in."""
    user = await create_admin(email, totp=True)
    r = await login(api, email, ADMIN_PASSWORD)
    assert r.json()["status"] == "mfa_required"
    code = pyotp.TOTP(user.totp_secret).now()
    r = await api.post("/api/auth/totp/verify", json={"code": code})
    assert r.status_code == 200, r.text
    return user
