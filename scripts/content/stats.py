"""Where the question bank stands: per canton, questions by status and translations by
language and status, and how far each topic is from its target.

Usage:
  python -m scripts.content.stats [--canton zh] [--root content]

A canton's questions are the federal ones plus its own (zh and zh-<commune>). A topic's
count is its questions that are not retired; the gap is target_questions minus that count,
which is also what scripts.content.draft drafts by default. Reads the files only; no AI."""

from __future__ import annotations

import sys

from app.content.files import ContentSet
from app.content.schema import QuestionFile, TopicEntry
from app.models import (
    Q_APPROVED,
    Q_RETIRED,
    QUESTION_STATUSES,
    TRANSLATION_LANGUAGES,
    TRANSLATION_STATUSES,
)
from scripts.content._common import base_parser, load, main_of, root_of, say


def canton_questions(cs: ContentSet, canton: str) -> list[QuestionFile]:
    return [q for q in cs.questions.values() if q.scope == "federal" or q.canton == canton]


def topic_questions(cs: ContentSet, canton: str, topic: TopicEntry) -> list[QuestionFile]:
    return [
        q
        for q in canton_questions(cs, canton)
        if q.topic == topic.code and (q.scope == "federal") == (topic.scope == "federal")
    ]


def canton_report(cs: ContentSet, canton: str) -> list[str]:
    qs = canton_questions(cs, canton)
    lines = [f"== {canton.upper()}: {len(qs)} question(s), federal and cantonal =="]
    lines.append("".join(f"{s:>11}" for s in QUESTION_STATUSES))
    lines.append("".join(f"{sum(1 for q in qs if q.status == s):>11}" for s in QUESTION_STATUSES))

    approved = [q for q in qs if q.status == Q_APPROVED]
    cols = (*TRANSLATION_STATUSES, "stale", "missing")
    lines.append("")
    lines.append(f"Translations of the {len(approved)} approved question(s)")
    lines.append(f"{'lang':<6}" + "".join(f"{c:>11}" for c in cols))
    for lang in TRANSLATION_LANGUAGES:
        row = dict.fromkeys(cols, 0)
        for q in approved:
            tr = cs.translations.get((lang, q.id))
            if tr is None:
                row["missing"] += 1
            elif tr.source_version < q.version:
                row["stale"] += 1
            else:
                row[tr.status] += 1
        lines.append(f"{lang:<6}" + "".join(f"{row[c]:>11}" for c in cols))

    lines.append("")
    lines.append(f"{'topic':<44}{'target':>7}{'have':>6}{'approved':>9}{'gap':>6}")
    total_target = total_have = 0
    for topic in cs.topic_files[canton].topics:
        tq = [q for q in topic_questions(cs, canton, topic) if q.status != Q_RETIRED]
        have = len(tq)
        ok = sum(1 for q in tq if q.status == Q_APPROVED)
        gap = max(0, topic.target_questions - have)
        total_target += topic.target_questions
        total_have += have
        lines.append(f"{topic.code:<44}{topic.target_questions:>7}{have:>6}{ok:>9}{gap:>6}")
    lines.append(
        f"{'total':<44}{total_target:>7}{total_have:>6}"
        f"{'':>9}{max(0, total_target - total_have):>6}"
    )
    return lines


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--canton", default=None)
    args = parser.parse_args(argv)
    cs = load(root_of(args))
    cantons = [args.canton] if args.canton else sorted(cs.topic_files)
    for canton in cantons:
        if canton not in cs.topic_files:
            say(f"There is no topic file topics/{canton}.yaml.")
            return 1
        for line in canton_report(cs, canton):
            say(line)
        say("")
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
