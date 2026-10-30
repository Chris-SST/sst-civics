"""Seed the first admin account. Further admins are added the same way. There is nothing
else to seed: prices live in Stripe and chat limits are settings.

Usage:
  ADMIN_EMAIL=you@example.ch ADMIN_PASSWORD=... python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.auth.passwords import hash_password, password_is_acceptable
from app.db import SessionLocal, utcnow
from app.models import ROLE_ADMIN, User


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
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not (email and password):
        print("Nothing to do: set ADMIN_EMAIL and ADMIN_PASSWORD to create an admin.")
        return
    created = await seed_admin(email, password)
    print("Admin: created" if created else "Admin: already exists")
    print("The admin must set up an authenticator app at first login.")


if __name__ == "__main__":
    asyncio.run(main())
