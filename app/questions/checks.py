"""Automatic checks: does a given answer match the stored one, and is a question a near
duplicate of an existing one. Pure functions, no database and no provider."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckOutcome:
    correct: bool
    method: str  # mcq | none
    detail: str = ""


def mcq_match(given: str, expected: str) -> CheckOutcome:
    g = re.sub(r"[^a-d]", "", given.strip().lower())[:1]
    e = expected.strip().lower()[:1]
    return CheckOutcome(bool(g) and g == e, "mcq", f"given {g or '?'}, expected {e}")


def check_answer(given: str, expected: str) -> CheckOutcome:
    """Multiple choice is the only question kind: compare the chosen option key."""
    given = (given or "").strip()
    if not given:
        return CheckOutcome(False, "none", "empty answer")
    return mcq_match(given, expected)


def options_valid(options: list[dict[str, str]] | None, answer: str) -> bool:
    """Exactly four options with distinct keys, and the stated answer is one of them."""
    keys = [str(o.get("key", "")).strip().upper()[:1] for o in (options or [])]
    return len(keys) == 4 and len(set(keys)) == 4 and answer.strip().upper()[:1] in keys


# --- Duplicate detection ------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zà-ÿ]+|\d+(?:\.\d+)?")


def tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2 or t.isdigit()}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_near_duplicate(text: str, others: list[str], threshold: float = 0.6) -> tuple[bool, float]:
    best = max((similarity(text, o) for o in others), default=0.0)
    return best >= threshold, best
