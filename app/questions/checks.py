"""Automatic checks: does a given answer match the correct option, are four options valid,
and is a question a near duplicate of another (kept for the content pipeline, task 1.5).
Pure functions, no database and no provider."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import OPTION_KEYS


@dataclass(frozen=True)
class CheckOutcome:
    correct: bool
    method: str  # mcq | none
    detail: str = ""


def option_key(given: str) -> str:
    """The option key a learner chose: "B", "b)" and "b. text" all give "b"."""
    return re.sub(r"[^a-d]", "", (given or "").strip().lower())[:1]


def mcq_match(given: str, expected: str) -> CheckOutcome:
    g = option_key(given)
    e = expected.strip().lower()[:1]
    return CheckOutcome(bool(g) and g == e, "mcq", f"given {g or '?'}, expected {e}")


def check_answer(given: str, expected: str) -> CheckOutcome:
    """Four-option multiple choice is the only question kind: compare the option key."""
    given = (given or "").strip()
    if not given:
        return CheckOutcome(False, "none", "empty answer")
    return mcq_match(given, expected)


def options_valid(options: dict[str, str] | None, correct: str) -> bool:
    """Exactly the keys a to d, four different non-empty texts, and the correct key among
    them."""
    if not options or set(options) != set(OPTION_KEYS):
        return False
    texts = [str(options[k]).strip().casefold() for k in OPTION_KEYS]
    return all(texts) and len(set(texts)) == 4 and correct in OPTION_KEYS


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
