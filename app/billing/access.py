"""Access per canton, derived from the learner's entitlements.

An entitlement gives one canton's content from `starts_at` until `expires_at`. It comes
from a Stripe payment, an admin grant or a trial. Admins have access to every canton.

full : the learner may use the paid features for that canton
none : no active entitlement for that canton
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.db import utcnow
from app.models import Entitlement, User

FULL = "full"
NONE = "none"


@dataclass(frozen=True)
class CantonAccess:
    canton: str
    expires_at: datetime
    source: str


def is_active(entitlement: Entitlement, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return entitlement.starts_at <= now < entitlement.expires_at


def compute_access(
    user: User | None, entitlements: Iterable[Entitlement], now: datetime | None = None
) -> dict[str, CantonAccess]:
    """Active access per canton. Where several entitlements overlap, the one that runs
    longest wins."""
    if user is None:
        return {}
    now = now or utcnow()
    out: dict[str, CantonAccess] = {}
    for e in entitlements:
        if e.user_id != user.id or not is_active(e, now):
            continue
        current = out.get(e.canton)
        if current is None or e.expires_at > current.expires_at:
            out[e.canton] = CantonAccess(canton=e.canton, expires_at=e.expires_at, source=e.source)
    return out


def has_access(user: User | None, canton: str, now: datetime | None = None) -> bool:
    """True if the user may use the paid features for `canton` at `now`."""
    if user is None or not user.is_active:
        return False
    if user.is_staff:
        return True
    return canton in compute_access(user, user.entitlements, now)


def access_level(user: User | None, canton: str | None = None) -> str:
    """The old string form used by the front end: "full" or "none" for the user's canton."""
    if user is None:
        return NONE
    return FULL if has_access(user, canton or user.canton) else NONE
