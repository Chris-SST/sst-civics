"""Check the content files (questions, topics, translations) before the tests run in CI.

Usage:
  python scripts/validate_content.py [--root content] [--today 2026-10-30] [--quiet]

Exits 1 on any error and 0 otherwise; warnings (stale translations) do not fail the build.
The rules are in app/content/validate.py; tests import `run` from here."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):  # run as a file: make the repository importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.validate import Report, validate_content  # noqa: E402


def run(root: Path | None = None, today: date | None = None, *, quiet: bool = False) -> Report:
    report = validate_content(root, today=today)
    if not quiet:
        for line in report.summary_lines():
            print(line)
        for issue in report.issues:
            print(f"{issue.level.upper():<8}{issue.path}: {issue.message} [{issue.kind}]")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="content directory")
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    parser.add_argument("--quiet", action="store_true", help="print nothing, exit code only")
    args = parser.parse_args(argv)
    report = run(args.root, args.today, quiet=args.quiet)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
