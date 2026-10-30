"""Start the API for the end-to-end tests (web/e2e, run by Playwright's webServer option).

Everything is local and disposable: a fresh SQLite database under var/e2e/, jobs run in the
API process, emails are written to var/e2e/outbox/, the AI provider is the fake one and Stripe
has no key (only a webhook secret, so tests can post signed events). It then
  1. generates the example questions (tests/e2e/make_fixture_content.py) into var/e2e/content,
  2. migrates the database and imports that content,
  3. seeds an admin with an authenticator secret the tests also know,
  4. builds the SPA if web/dist is missing or older than web/src (E2E_BUILD=1 forces a rebuild),
  5. serves API and SPA on 127.0.0.1:8100.

It never touches content/, .env or var/dev.db."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = REPO / "var" / "e2e"
PORT = int(os.environ.get("E2E_PORT", "8100"))
BASE_URL = f"http://127.0.0.1:{PORT}"

ADMIN_EMAIL = "e2e-admin@example.ch"
ADMIN_PASSWORD = "E2e-admin-password-1"
# Base32 secret for the admin's authenticator; web/e2e/helpers.ts derives codes from it.
ADMIN_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
WEBHOOK_SECRET = "whsec_e2e_test_secret"


def environment() -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "SECRET_KEY": "e2e-secret-key-not-for-production",
        "DATABASE_URL": f"sqlite+aiosqlite:///{(WORK / 'e2e.db').as_posix()}",
        "JOBS_INLINE": "true",
        "EMAIL_BACKEND": "console",
        "EMAIL_OUTBOX_DIR": str(WORK / "outbox"),
        "LLM_FAKE": "true",
        "CONTENT_DIR": str(WORK / "content"),
        "APP_BASE_URL": BASE_URL,
        "COOKIE_SECURE": "false",
        # No Stripe key: checkout is "not connected". The webhook secret lets tests post events.
        "STRIPE_SECRET_KEY": "",
        "STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET,
        "CANTONS_FOR_SALE": "zh",
        "SENTRY_DSN": "",
        # Many tests sign in from one address.
        "LOGIN_RATE_LIMIT": "1000",
        "LINK_RATE_LIMIT_PER_EMAIL": "1000",
        "LINK_RATE_LIMIT_PER_IP": "1000",
        "LINK_CONSUME_RATE_LIMIT": "1000",
    }


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=REPO, check=True)  # noqa: S603


def build_web() -> None:
    dist = REPO / "web" / "dist" / "index.html"
    sources = [p.stat().st_mtime for p in (REPO / "web" / "src").rglob("*") if p.is_file()]
    stale = not dist.exists() or max(sources, default=0) > dist.stat().st_mtime
    if not stale and os.environ.get("E2E_BUILD") != "1":
        return
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm, "run", "build"], cwd=REPO / "web", check=True)  # noqa: S603


async def seed_admin() -> None:
    import pyotp  # noqa: F401  (fail early if the dev dependencies are missing)
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User
    from scripts.seed import seed_admin as create

    await create(ADMIN_EMAIL, ADMIN_PASSWORD)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one()
        user.totp_secret = ADMIN_TOTP_SECRET
        user.totp_enabled = True
        await db.commit()


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)  # a synced folder may hold a lock
    WORK.mkdir(parents=True, exist_ok=True)
    os.environ.update(environment())
    sys.path.insert(0, str(REPO))
    os.chdir(REPO)

    run("tests/e2e/make_fixture_content.py", "--out", str(WORK / "content"))
    run("-m", "alembic", "upgrade", "head")
    run("-m", "scripts.import_content", "--root", str(WORK / "content"))
    asyncio.run(seed_admin())
    build_web()

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
