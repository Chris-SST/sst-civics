"""Seed plan limits (still read by the tutor's message limits until task 0.7) and,
optionally, the first admin account. Further admins are added the same way.

Usage:
  python -m scripts.seed                       # plans only
  ADMIN_EMAIL=you@example.ch ADMIN_PASSWORD=... python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.auth.passwords import hash_password, password_is_acceptable
from app.billing.plans import PLAN_DEFAULTS
from app.db import SessionLocal, utcnow
from app.models import ROLE_ADMIN, Plan, User


async def seed_plans() -> int:
    created = 0
    async with SessionLocal() as db:
        for d in PLAN_DEFAULTS:
            if await db.get(Plan, d.key) is None:
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
                created += 1
        await db.commit()
    return created


async def seed_admin(email: str, password: str) -> bool:
    if not password_is_acceptable(password):
        raise SystemExit("ADMIN_PASSWORD must be at least 10 characters")
    async with SessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email.lower()))
        if existing.scalar_one_or_none() is not None:
            return False
        db.add(
            User(
                role=ROLE_ADMIN,
                email=email.lower(),
                email_verified_at=utcnow(),
                password_hash=hash_password(password),
                locale="en",
            )
        )
        await db.commit()
    return True


async def main() -> None:
    n = await seed_plans()
    print(f"Plans: {n} created")
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if email and password:
        created = await seed_admin(email, password)
        print("Admin: created" if created else "Admin: already exists")
        print("The admin must set up an authenticator app at first login.")


if __name__ == "__main__":
    asyncio.run(main())
