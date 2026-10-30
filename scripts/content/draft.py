"""Draft new questions for one topic in German (PLAN.md, Question bank, step 2).

Usage:
  python -m scripts.content.draft --canton zh --topic bund.demokratie.volksrechte [--count N]
      [--commune winterthur] [--per-request 5] [--direct] [--model ...] [--resume BATCH_ID]

The default count is the topic's target_questions minus the questions on that topic that
are not retired. Each result is written to content/questions/<scope>/<id>.yaml with
status draft and version 1; near-duplicates of existing questions are skipped and listed.
Prompt: prompts/content/draft/vN.md."""

from __future__ import annotations

import math
import random
import sys
from typing import Any

from app.content import store
from app.content.fetch import is_official_url
from app.content.schema import QuestionFile, TopicEntry
from app.db import SessionLocal
from app.llm.content import PURPOSE_DRAFT, Job, run_jobs
from app.models import OPTION_KEYS, Q_DRAFT, Q_RETIRED
from app.questions import checks
from scripts.content._common import (
    add_ai_args,
    base_parser,
    find_topic,
    load,
    main_of,
    options_block,
    root_of,
    run_options,
    say,
    slugify,
    swiss_german,
    today_of,
)

PROMPT = "content/draft"
DUPLICATE_THRESHOLD = 0.6

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "question_de": {"type": "string"},
                    "options_de": {
                        "type": "object",
                        "properties": {k: {"type": "string"} for k in OPTION_KEYS},
                        "required": list(OPTION_KEYS),
                        "additionalProperties": False,
                    },
                    "correct": {"type": "string", "enum": list(OPTION_KEYS)},
                    "explanation_de": {"type": "string"},
                    "difficulty": {"type": "integer"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "glossary": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "slug",
                    "question_de",
                    "options_de",
                    "correct",
                    "explanation_de",
                    "difficulty",
                    "sources",
                    "glossary",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

LEVEL_DE = {"federal": "Bund", "canton": "Kanton", "commune": "Gemeinde"}


def question_scope(topic: TopicEntry, canton: str, commune: str | None) -> tuple[str, str | None]:
    if topic.scope == "federal":
        return "federal", None
    if topic.scope == "commune" and commune:
        return f"{canton}-{slugify(commune)}", canton
    return canton, canton


def on_topic(q: QuestionFile, topic: TopicEntry, canton: str) -> bool:
    if q.topic != topic.code or q.status == Q_RETIRED:
        return False
    return q.scope == "federal" if topic.scope == "federal" else q.canton == canton


def request_text(
    *,
    canton: str,
    topic: TopicEntry,
    scope: str,
    count: int,
    part: int,
    parts: int,
    existing: list[QuestionFile],
) -> str:
    lines = [
        f"Kanton: {canton.upper()}",
        f"Ebene: {LEVEL_DE[topic.scope]} (Geltungsbereich der Fragen: {scope})",
        f"Thema: {topic.name_de} (Code {topic.code})",
        "Ausgangsquellen:",
        *[f"- {u}" for u in topic.sources],
        f"Anzahl Fragen: {count}",
    ]
    if parts > 1:
        lines.append(
            f"Dies ist Anfrage {part} von {parts} zum gleichen Thema. Teile das Thema gedanklich "
            f"in {parts} Teilbereiche und schreibe nur Fragen zum Teilbereich {part}."
        )
    if existing:
        lines.append("Bestehende Fragen zu diesem Thema (nicht wiederholen):")
        lines += [f"- {q.question_de}" for q in existing[:80]]
    else:
        lines.append("Zu diesem Thema gibt es noch keine Fragen.")
    return "\n".join(lines)


def shuffle_options(qid: str, options: dict[str, str], correct: str) -> tuple[dict[str, str], str]:
    """Put the correct answer at a position chosen from the id, so the bank does not lean
    towards one letter. The same id always gives the same order."""
    texts = [options[k] for k in OPTION_KEYS]
    order = list(range(4))
    random.Random(qid).shuffle(order)  # noqa: S311  not for security
    new = {OPTION_KEYS[i]: texts[j] for i, j in enumerate(order)}
    new_correct = OPTION_KEYS[order.index(OPTION_KEYS.index(correct))]
    return new, new_correct


def unique_id(base: str, taken: set[str]) -> str:
    qid, n = base, 2
    while qid in taken:
        qid = f"{base}-{n}"
        n += 1
    return qid


def clean_item(item: dict[str, Any], *, commune: bool) -> tuple[dict[str, Any] | None, str]:
    """A checked candidate, or None and the reason it was rejected."""
    try:
        options = {k: swiss_german(str(item["options_de"][k]).strip()) for k in OPTION_KEYS}
        correct = str(item["correct"]).strip().lower()
        question = swiss_german(str(item["question_de"]).strip())
        explanation = swiss_german(str(item["explanation_de"]).strip())
        difficulty = int(item["difficulty"])
    except (KeyError, TypeError, ValueError):
        return None, "incomplete reply"
    if not question or not explanation:
        return None, "empty question or explanation"
    if not checks.options_valid(options, correct):
        return None, "options are not four different answers with a correct key"
    urls = [str(u).strip() for u in item.get("sources") or []]
    good = [u for u in dict.fromkeys(urls) if is_official_url(u, commune=commune)]
    if not good:
        return None, "no official https source"
    glossary = [swiss_german(str(t).strip()) for t in item.get("glossary") or [] if str(t).strip()]
    return {
        "slug": str(item.get("slug") or ""),
        "question_de": question,
        "options_de": options,
        "correct": correct,
        "explanation_de": explanation,
        "difficulty": min(3, max(1, difficulty)),
        "sources": good[:3],
        "glossary": list(dict.fromkeys(glossary))[:8],
    }, ""


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--canton", required=True)
    parser.add_argument("--topic", required=True, help="topic code from topics/<canton>.yaml")
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--commune", default=None, help="commune slug for commune questions")
    parser.add_argument("--per-request", type=int, default=5, help="questions per request")
    add_ai_args(parser, max_tokens=8000)
    args = parser.parse_args(argv)
    root = root_of(args)
    today = today_of(args)
    cs = load(root)
    topic = find_topic(cs, args.canton, args.topic)
    scope, canton = question_scope(topic, args.canton, args.commune)
    existing = [q for q in cs.questions.values() if on_topic(q, topic, args.canton)]
    count = args.count
    if count is None:
        count = max(0, topic.target_questions - len(existing))
    if count <= 0:
        have = f"{len(existing)} of {topic.target_questions}"
        say(f"{topic.code}: {have} questions exist; none drafted.")
        return 0
    per = max(1, args.per_request)
    parts = math.ceil(count / per)
    jobs = []
    for part in range(1, parts + 1):
        n = min(per, count - (part - 1) * per)
        text = request_text(
            canton=args.canton,
            topic=topic,
            scope=scope,
            count=n,
            part=part,
            parts=parts,
            existing=existing,
        )
        jobs.append(Job(key=f"draft-{part}", text=text))
    say(f"{topic.code}: drafting {count} question(s) in {len(jobs)} request(s), scope {scope}")

    async with SessionLocal() as db:
        outcomes = await run_jobs(
            db,
            purpose=PURPOSE_DRAFT,
            prompt_name=PROMPT,
            schema=SCHEMA,
            jobs=jobs,
            options=run_options(args),
            say=say,
        )

    taken = set(cs.questions)
    known = [(q.id, q.question_de) for q in cs.questions.values() if q.status != Q_RETIRED]
    written, skipped, rejected = [], [], []
    for job in jobs:
        outcome = outcomes.get(job.key)
        items = (outcome.data or {}).get("questions") if outcome else None
        for item in items or []:
            if len(written) >= count:
                break
            cand, why = clean_item(
                item if isinstance(item, dict) else {}, commune=topic.scope == "commune"
            )
            if cand is None:
                rejected.append(why)
                say(f"rejected: {why}")
                continue
            dup, score = checks.is_near_duplicate(cand["question_de"], [t for _, t in known])
            if dup:
                twin = max(known, key=lambda k: checks.similarity(cand["question_de"], k[1]))[0]
                skipped.append(twin)
                say(f"skipped near-duplicate of {twin} ({score:.2f}): {cand['question_de']}")
                continue
            qid = unique_id(slugify(cand["slug"] or cand["question_de"]), taken)
            options, correct = shuffle_options(qid, cand["options_de"], cand["correct"])
            data = {
                "id": qid,
                "version": 1,
                "scope": scope,
                "canton": canton,
                "topic": topic.code,
                "question_de": cand["question_de"],
                "options_de": options,
                "correct": correct,
                "explanation_de": cand["explanation_de"],
                "sources": [{"url": u, "checked": today} for u in cand["sources"]],
                "glossary": cand["glossary"],
                "status": Q_DRAFT,
                "difficulty": cand["difficulty"],
            }
            try:
                store.write_question(root, data)
            except ValueError as exc:
                rejected.append("schema")
                say(f"rejected: does not fit the schema ({str(exc).splitlines()[0]})")
                continue
            taken.add(qid)
            known.append((qid, cand["question_de"]))
            written.append(qid)
            body = f"{cand['question_de']}\n{options_block(options)}"
            say(f"wrote questions/{scope}/{qid}.yaml\n{body}")
    say(
        f"{topic.code}: {len(written)} written, {len(skipped)} near-duplicate(s) skipped, "
        f"{len(rejected)} rejected"
    )
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
