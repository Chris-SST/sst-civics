"""One place for the time the study rules use, so tests can freeze it. Calendar days (for
"known: correct on two different days") are Zurich days, as the daily chat limit's are."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.db import utcnow

ZURICH = ZoneInfo("Europe/Zurich")


def now() -> datetime:
    return utcnow()


def zurich_day(moment: datetime) -> date:
    return moment.astimezone(ZURICH).date()
