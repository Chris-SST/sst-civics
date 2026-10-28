"""Access level derived from subscription status and free-access grants.

full      : the plan's features
read_only : past chats and progress only, no new messages
none      : never subscribed and no grant
"""

from __future__ import annotations

from datetime import timedelta

from app.db import utcnow
from app.models import Family

FULL = "full"
READ_ONLY = "read_only"
NONE = "none"

PAST_DUE_GRACE = timedelta(days=7)


def compute_access(family: Family | None) -> str:
    if family is None:
        return NONE
    now = utcnow()
    if family.free_access_until and family.free_access_until > now:
        return FULL
    status = family.subscription_status
    if status in ("trialing", "active"):
        return FULL
    if status == "past_due":
        since = family.past_due_since or now
        return FULL if now - since < PAST_DUE_GRACE else READ_ONLY
    if status in ("canceled", "unpaid", "incomplete_expired", "paused"):
        return READ_ONLY
    if status in ("incomplete",):
        return NONE
    return NONE
