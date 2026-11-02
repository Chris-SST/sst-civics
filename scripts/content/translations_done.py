"""Clear `translations_missing` on approved questions that now have every translation (D-069).

Usage:
  python -m scripts.content.translations_done [--root DIR]

The AI review panel approves a question before it is translated and marks it
`translations_missing: true` so the content check passes. Once scripts.content.translate has
written a file for every language, this drops the mark. No AI calls."""

from __future__ import annotations

import sys

from app.content import store
from app.models import Q_APPROVED, TRANSLATION_LANGUAGES
from scripts.content._common import base_parser, load, main_of, root_of, say


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    args = parser.parse_args(argv)
    root = root_of(args)
    cs = load(root)
    cleared = waiting = 0
    for q in cs.questions.values():
        if q.status != Q_APPROVED or not q.translations_missing:
            continue
        if all((lang, q.id) in cs.translations for lang in TRANSLATION_LANGUAGES):
            data = store.question_data(q)
            data.pop("translations_missing", None)
            store.write_question(root, data)
            cleared += 1
        else:
            waiting += 1
    say(f"{cleared} questions complete, {waiting} still missing a language")
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
