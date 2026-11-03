"""The Viapunt Pass products. Prices live in Stripe under these lookup keys and are never
held here; this module knows only what each key buys and for how long (D-015)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime

PASS_ZH = "civics_pass_zh"  # noqa: S105 (a lookup key, not a secret)
PASS_AG = "civics_pass_ag"  # noqa: S105
PASS_CH = "civics_pass_ch"  # noqa: S105 (Rest of Switzerland: federal questions only)
EXTENSION = "civics_extension"

KIND_PASS = "pass"  # noqa: S105
KIND_EXTENSION = "extension"


@dataclass(frozen=True)
class Product:
    key: str
    kind: str  # pass | extension
    canton: str | None  # the canton a pass is for; an extension applies to any pass
    months: int  # access period; the Stripe price's `access_months` metadata says the same
    name: str  # product name in Stripe


PRODUCTS: dict[str, Product] = {
    PASS_ZH: Product(PASS_ZH, KIND_PASS, "zh", 12, "Viapunt Pass: canton of Zurich"),
    PASS_AG: Product(PASS_AG, KIND_PASS, "ag", 12, "Viapunt Pass: canton of Aargau"),
    PASS_CH: Product(PASS_CH, KIND_PASS, "ch", 12, "Viapunt Pass: rest of Switzerland"),
    EXTENSION: Product(EXTENSION, KIND_EXTENSION, None, 3, "Viapunt Pass: three-month extension"),
}
ALL_KEYS = tuple(PRODUCTS)
PASS_FOR_CANTON = {p.canton: p.key for p in PRODUCTS.values() if p.kind == KIND_PASS}


def add_months(value: datetime, months: int) -> datetime:
    """The same day and time `months` calendar months later (or earlier, if negative),
    clamped to the last day of a shorter month."""
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
