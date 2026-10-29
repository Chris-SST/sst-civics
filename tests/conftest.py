"""Test configuration. Environment is set before the app is imported so settings pick
up SQLite, in-process jobs and the in-memory email outbox."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import AsyncIterator

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

from app.auth import ratelimit  # noqa: E402
from app.auth.passwords import hash_password  # noqa: E402
from app.billing import routes as billing_routes  # noqa: E402
from app.billing.plans import PLAN_DEFAULTS  # noqa: E402
from app.db import Base, SessionLocal, engine, utcnow  # noqa: E402
from app.email.backend import memory_outbox  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ROLE_ADMIN, ROLE_TUTOR, Plan, User  # noqa: E402


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


async def signup_and_verify(
    api: Api, email: str, password: str = "Parent-pass-123", account_type: str = "parent"
) -> None:
    r = await api.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": password,
            "locale": "en",
            "account_type": account_type,
            "guardian_confirmed": account_type == "parent",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    token = token_from_link(last_email_link())
    r = await api.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text


async def login(api: Api, identifier: str, password: str):
    return await api.post("/api/auth/login", json={"identifier": identifier, "password": password})


async def parent_logged_in(api: Api, email: str = "parent@example.ch") -> dict:
    await signup_and_verify(api, email)
    r = await login(api, email, "Parent-pass-123")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    return r.json()["me"]


async def create_staff(
    email: str, role: str = ROLE_ADMIN, password: str = "Staff-pass-123", totp: bool = False
) -> User:
    async with SessionLocal() as db:
        user = User(
            role=role,
            email=email,
            email_verified_at=utcnow(),
            password_hash=hash_password(password),
            first_name="Staff",
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
    user = await create_staff(email, ROLE_ADMIN, totp=True)
    r = await login(api, email, "Staff-pass-123")
    assert r.json()["status"] == "mfa_required"
    code = pyotp.TOTP(user.totp_secret).now()
    r = await api.post("/api/auth/totp/verify", json={"code": code})
    assert r.status_code == 200, r.text
    return user


__all__ = ["ROLE_TUTOR"]
