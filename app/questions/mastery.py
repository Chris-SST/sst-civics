"""Topic mastery and the readiness estimate, both computed from question progress
(app.study.progress) rather than stored.

Mastery of a topic: known questions count fully, questions understood but not yet known count
half, over the topic's approved questions (the whole bank, also for free-tier learners, so a
learner who has studied only the sample questions does not see a full bar).

Readiness for a canton: the share of known questions per topic, weighted by the topic's
`target_questions` in the canton's topic file, so topics that weigh more in the official
catalogue weigh more here. It is labelled "practice estimate, not an official result".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

READINESS_LABEL_KEY = "study.readinessLabel"


@dataclass(frozen=True)
class TopicCounts:
    topic_code: str
    target: int  # target_questions from the topic file
    total: int  # approved (servable) questions on the topic
    understood: int  # understood, known or not
    known: int


def topic_mastery_percent(known: int, understood: int, total: int) -> int:
    """0 to 100. `understood` includes the known questions."""
    if total <= 0:
        return 0
    known = min(known, total)
    understood_only = max(0, min(understood, total) - known)
    return int(round(100 * (known + 0.5 * understood_only) / total))


def readiness_percent(topics: Iterable[TopicCounts]) -> int:
    """0 to 100: known share per topic weighted by target_questions. Topics without questions
    yet count as not known, because the test may still ask about them. When no topic has a
    target, every topic weighs the same."""
    rows = list(topics)
    if not rows:
        return 0
    weights = [t.target for t in rows]
    if sum(weights) <= 0:
        weights = [1] * len(rows)
    shares = [min(t.known, t.total) / t.total if t.total else 0.0 for t in rows]
    num = sum(w * share for w, share in zip(weights, shares, strict=True))
    return int(round(100 * num / sum(weights)))
