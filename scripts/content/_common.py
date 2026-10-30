"""Shared helpers of the content pipeline scripts: arguments, loading the files, choosing
questions, and the AI run options. Every AI call goes through app.llm.content."""

from __future__ import annotations

import argparse
import asyncio
import re
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.content.files import ContentSet, content_root, load_content
from app.content.schema import QuestionFile, TopicEntry
from app.llm.client import LLMUnavailable
from app.llm.content import BudgetExceeded, RunOptions

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "var" / "content-batches"  # request maps of batches, for --resume


def say(message: str) -> None:
    print(message, flush=True)


# --- Arguments ----------------------------------------------------------------------------


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--root", type=Path, default=None, help="content directory")
    parser.add_argument(
        "--today", type=date.fromisoformat, default=None, help="date to record (tests)"
    )
    return parser


def add_ai_args(parser: argparse.ArgumentParser, *, max_tokens: int) -> None:
    g = parser.add_argument_group("AI calls")
    g.add_argument("--direct", action="store_true", help="send requests one by one, not as a batch")
    g.add_argument("--model", default=None, help="model (default: TUTOR_MODEL)")
    g.add_argument("--effort", default="medium", choices=("low", "medium", "high"))
    g.add_argument("--max-tokens", type=int, default=max_tokens)
    g.add_argument("--max-requests", type=int, default=500, help="refuse runs larger than this")
    g.add_argument(
        "--resume", metavar="BATCH_ID", default=None, help="collect a batch sent earlier"
    )
    g.add_argument("--poll-seconds", type=float, default=30.0)
    g.add_argument(
        "--allow-over-budget",
        action="store_true",
        help="run even if this month's AI spend has reached AI_MONTHLY_BUDGET_CHF",
    )


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ids", nargs="+", default=None, help="only these question ids")
    parser.add_argument("--canton", default=None, help="only federal and this canton's questions")
    parser.add_argument("--topic", default=None, help="only this topic code")
    parser.add_argument("--redo", action="store_true", help="also items already checked")


def run_options(args: argparse.Namespace) -> RunOptions:
    return RunOptions(
        model=args.model or get_settings().tutor_model,
        direct=args.direct,
        effort=args.effort,
        max_tokens=args.max_tokens,
        max_requests=args.max_requests,
        resume_batch=args.resume,
        poll_seconds=args.poll_seconds,
        state_dir=STATE_DIR,
        allow_over_budget=args.allow_over_budget,
    )


def root_of(args: argparse.Namespace) -> Path:
    return (args.root or content_root()).resolve()


def today_of(args: argparse.Namespace) -> date:
    return args.today or date.today()


# --- Content ------------------------------------------------------------------------------


def load(root: Path) -> ContentSet:
    """All files that parse; files with schema errors are reported and left out."""
    if not root.is_dir():
        raise SystemExit(f"Content directory {root} not found.")
    cs = load_content(root)
    for issue in cs.issues:
        say(f"WARNING {issue.path}: {issue.message} (file left out of this run)")
    return cs


def select_questions(
    cs: ContentSet,
    args: argparse.Namespace,
    statuses: Iterable[str] | None,
) -> list[QuestionFile]:
    wanted = set(statuses) if statuses is not None else None
    ids = set(args.ids) if getattr(args, "ids", None) else None
    out = []
    for qid in sorted(cs.questions):
        q = cs.questions[qid]
        if ids is not None and qid not in ids:
            continue
        if wanted is not None and q.status not in wanted:
            continue
        canton = getattr(args, "canton", None)
        if canton and q.canton not in (None, canton):
            continue
        topic = getattr(args, "topic", None)
        if topic and q.topic != topic:
            continue
        out.append(q)
    if ids:
        for missing in sorted(ids - set(cs.questions)):
            say(f"{missing}: no such question")
    return out


def find_topic(cs: ContentSet, canton: str, code: str) -> TopicEntry:
    tf = cs.topic_files.get(canton)
    if tf is None:
        raise SystemExit(f"There is no topic file topics/{canton}.yaml.")
    for t in tf.topics:
        if t.code == code:
            return t
    raise SystemExit(f"Topic {code} is not in topics/{canton}.yaml.")


def options_block(options: dict[str, str]) -> str:
    return "\n".join(f"{k}) {options[k]}" for k in sorted(options))


def swiss_german(text: str) -> str:
    """Swiss standard German writes ss, never the sharp s."""
    return text.replace("ß", "ss").replace("ẞ", "SS")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", text).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rsplit("-", 1)[0]
    return slug or "frage"


# --- Running ------------------------------------------------------------------------------


def main_of(run: Callable[[list[str] | None], Awaitable[int]]) -> Callable[..., int]:
    """`main(argv)` for a script whose `run(argv)` is a coroutine: runs it and closes the
    database engine; a missing key or a spent budget ends the run with a message."""

    def main(argv: list[str] | None = None) -> int:
        async def go() -> int:
            from app.db import engine

            try:
                return await run(argv)
            except LLMUnavailable:
                say("No AI provider configured (ANTHROPIC_API_KEY is empty); nothing sent.")
                return 1
            except BudgetExceeded as exc:
                say(f"Stopped: {exc}. Use --allow-over-budget to run anyway.")
                return 1
            finally:
                await engine.dispose()

        return asyncio.run(go())

    return main
