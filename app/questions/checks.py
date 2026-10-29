"""Automatic checks: does a given answer match the stored one, and is a question a near
duplicate of an existing one. Pure functions, no database and no provider."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

from sympy import N, nsimplify, simplify
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

log = logging.getLogger(__name__)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class CheckOutcome:
    correct: bool
    method: str  # mcq | numeric | symbolic | text | none
    detail: str = ""


def _strip_math(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$|^\$+|\$+$", "", s).strip()
    s = s.replace("\\,", "").replace("\\;", "").replace("\\!", "").replace("\\ ", "")
    s = re.sub(r"\\text\{[^}]*\}", "", s)  # units written as text
    s = s.replace("×", "*").replace("·", "*").replace("−", "-").replace("÷", "/")
    s = re.sub(r"\\times", "*", s)
    return s.strip()


def parse_number(s: str) -> float | None:
    """First number in the string, accepting 1.5e3, 1,5 (Swiss decimal comma) and 2 x 10^3."""
    s = _strip_math(s)
    if re.fullmatch(r"[-+]?\d{1,3}(?:'\d{3})+(?:[.,]\d+)?", s):
        s = s.replace("'", "")
    if re.fullmatch(r"[-+]?\d+,\d+", s):
        s = s.replace(",", ".")
    m = re.search(r"([-+]?\d+\.?\d*)\s*(?:\*|x|X)?\s*10\s*\^\s*\{?([-+]?\d+)\}?", s)
    if m:
        try:
            return float(m.group(1)) * 10 ** int(m.group(2))
        except ValueError:
            return None
    m = _NUMBER_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def numbers_match(given: str, expected: str, tolerance: float | None) -> CheckOutcome:
    g = parse_number(given)
    e = parse_number(expected)
    if g is None or e is None:
        return CheckOutcome(False, "numeric", "could not read a number")
    tol = tolerance if tolerance is not None else 0.01
    if e == 0:
        ok = abs(g) <= max(tol, 1e-9)
    else:
        ok = abs(g - e) / abs(e) <= tol
    return CheckOutcome(ok, "numeric", f"given {g:g}, expected {e:g}, tolerance {tol:g}")


def _to_sympy(s: str):
    s = _strip_math(s)
    if not s:
        return None
    if "\\" in s:
        try:
            return parse_latex(s)
        except Exception:  # noqa: BLE001
            return None
    try:
        return parse_expr(s.replace("^", "**"), transformations=_TRANSFORMS, evaluate=True)
    except Exception:  # noqa: BLE001
        return None


def _normalise_text(s: str) -> str:
    s = _strip_math(s).lower()
    s = re.sub(r"\s+", "", s)
    s = s.replace("{", "").replace("}", "").replace("*", "")
    return s


def expressions_match(given: str, expected: str) -> CheckOutcome:
    """Symbolic equality when both sides parse; otherwise a normalised string compare.
    `x = 2 or x = -1` style answers are compared as sets of normalised parts."""
    g_parts = [p for p in re.split(r"\bor\b|,|;", given) if p.strip()]
    e_parts = [p for p in re.split(r"\bor\b|,|;", expected) if p.strip()]
    if len(g_parts) > 1 or len(e_parts) > 1:
        if len(g_parts) != len(e_parts):
            return CheckOutcome(False, "text", "different number of parts")
        gset = {_normalise_text(p.split("=")[-1]) for p in g_parts}
        eset = {_normalise_text(p.split("=")[-1]) for p in e_parts}
        return CheckOutcome(gset == eset, "text", "set of parts")
    g_rhs = given.split("=")[-1] if given.count("=") == 1 else given
    e_rhs = expected.split("=")[-1] if expected.count("=") == 1 else expected
    g = _to_sympy(g_rhs)
    e = _to_sympy(e_rhs)
    if g is not None and e is not None:
        try:
            diff = simplify(nsimplify(g) - nsimplify(e))
            if diff == 0:
                return CheckOutcome(True, "symbolic", "simplify(difference) == 0")
            val = N(diff)
            if val.is_number and abs(float(val)) < 1e-9:
                return CheckOutcome(True, "symbolic", "numerically equal")
            # Fall back to a numeric comparison when both are plain numbers
            if g.is_number and e.is_number:
                return CheckOutcome(False, "symbolic", f"{N(g)} vs {N(e)}")
        except Exception as exc:  # noqa: BLE001
            log.debug("symbolic compare failed: %s", exc.__class__.__name__)
    ok = _normalise_text(given) == _normalise_text(expected)
    return CheckOutcome(ok, "text", "normalised text compare")


def mcq_match(given: str, expected: str) -> CheckOutcome:
    g = re.sub(r"[^a-d]", "", given.strip().lower())[:1]
    e = expected.strip().lower()[:1]
    return CheckOutcome(bool(g) and g == e, "mcq", f"given {g or '?'}, expected {e}")


def check_answer(qtype: str, given: str, expected: str, tolerance: float | None) -> CheckOutcome:
    given = (given or "").strip()
    if not given:
        return CheckOutcome(False, "none", "empty answer")
    if qtype == "mcq":
        return mcq_match(given, expected)
    if qtype == "numeric":
        return numbers_match(given, expected, tolerance)
    if qtype == "short":
        g, e = parse_number(given), parse_number(expected)
        if (
            g is not None
            and e is not None
            and _NUMBER_RE.fullmatch(_strip_math(given))
            and _NUMBER_RE.fullmatch(_strip_math(expected))
        ):
            return numbers_match(given, expected, tolerance or 0.005)
        return expressions_match(given, expected)
    return CheckOutcome(False, "none", "structured answers are marked by the model")


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


def sig_figs_of(answer: str) -> int | None:
    """Number of significant figures in a decimal string, or None."""
    s = _strip_math(answer)
    m = _NUMBER_RE.fullmatch(s)
    if not m:
        return None
    digits = re.sub(r"[-+]|[eE].*$", "", s).replace(".", "").lstrip("0")
    return len(digits) if digits else None


def required_tolerance(expected: str) -> float | None:
    """Relative tolerance equal to half a unit in the last significant figure."""
    e = parse_number(expected)
    sf = sig_figs_of(expected)
    if e is None or sf is None or e == 0:
        return None
    half_ulp = 0.5 * 10 ** (math.floor(math.log10(abs(e))) - sf + 1)
    return half_ulp / abs(e)


def rounds_consistently(expected: str, tolerance: float | None) -> bool:
    """A numeric answer given to n significant figures needs a tolerance at least as wide
    as half a unit in the last place, or students who round correctly are marked wrong."""
    e = parse_number(expected)
    sf = sig_figs_of(expected)
    if e is None or sf is None or e == 0 or tolerance is None:
        return True
    half_ulp = 0.5 * 10 ** (math.floor(math.log10(abs(e))) - sf + 1)
    return tolerance >= half_ulp / abs(e) * 0.99
